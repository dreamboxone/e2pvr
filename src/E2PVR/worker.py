# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
from __future__ import print_function, unicode_literals
import base64
import os
import subprocess
import sys
import threading
import time
if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from E2PVR.core import logger, steady_time
    from E2PVR.storage import read_json, atomic_json
    from E2PVR.live import LiveSession, connection_error
else:
    from .core import logger, steady_time
    from .storage import read_json, atomic_json
    from .live import LiveSession, connection_error


def merge_text(current, update):
    if not current:
        return update
    if update.startswith(current):
        return update
    if current.endswith(update):
        return current
    return current + update


def stop_process(process):
    if process is None:
        return
    process.stdout.close()
    if process.poll() is None:
        process.kill()
    process.wait()


def run(directory):
    state_path = os.path.join(directory, "state.json")
    control_path = os.path.join(directory, "control.json")
    lock = threading.Lock()
    state = dict(ready=False, generation=None, cues=[], until_ms=0, language="", error=None)
    flow = dict(cursor=0, pending="", start=0, sequence=0, anchors=[], last_input_end=0,
                pending_since=0, pending_end=0, changed_at=0, full_text="", committed=0)
    connection, decoder, active = None, None, None
    session_handle = None
    retry_at, publish_at, eof, failures = 0, 0, False, 0

    def commit(force=False):
        remainder = flow["full_text"][flow["committed"]:]
        text = remainder.strip()
        if not text:
            return
        boundary = max([text.rfind(mark) for mark in (".", "!", "?", "؟", "؛", "\n")]) + 1
        if not boundary and len(text) >= 92:
            boundary = text.rfind(" ", 3, 93)
            if boundary <= 0:
                boundary = 92
        if not boundary and not force:
            return
        boundary = boundary or len(text)
        cue_text = text[:boundary].strip()
        if cue_text:
            duration = max(1000, min(6000, len(cue_text) * 1000 // 17))
            beginning = flow["start"]
            end = max(beginning + duration, flow["pending_end"])
            available_position = max(0, read_json(control_path).get("position_ms", 0))
            flow["sequence"] += 1
            state["cues"].append(dict(start=available_position, end=available_position + duration,
                source_start=beginning, source_end=end, text=cue_text,
                id=flow["sequence"], final=True, revision=1, available_monotonic=steady_time()))
            state["cues"] = state["cues"][-32:]
            flow["start"] = end
            logger().info("Subtitle cue committed: sequence=%d chars=%d", flow["sequence"], len(cue_text))
        flow["committed"] += len(remainder) - len(remainder.lstrip()) + boundary
        flow["pending"] = flow["full_text"][flow["committed"]:].strip()
        flow["pending_since"] = steady_time() if flow["pending"] else 0

    def receive(content):
        with lock:
            source = content.get("inputTranscription") or {}
            if source.get("languageCode"):
                state["language"] = source["languageCode"]
            source_text = source.get("text", "").strip()
            if source_text:
                estimated = max(400, min(6000, len(source_text) * 1000 // 17))
                end = flow["cursor"]
                start = max(flow["last_input_end"], end - estimated)
                flow["anchors"].append((start, max(end, start + 400)))
                flow["anchors"] = flow["anchors"][-16:]
                flow["last_input_end"] = end
            output = content.get("outputTranscription") or {}
            text = output.get("text", "")
            if text:
                if not flow["pending"]:
                    anchor = flow["anchors"].pop(0) if flow["anchors"] else (max(0, flow["cursor"] - 3000), flow["cursor"])
                    flow["start"], flow["pending_end"] = anchor
                    flow["pending_since"] = steady_time()
                flow["full_text"] = merge_text(flow["full_text"], text)
                flow["pending"] = flow["full_text"][flow["committed"]:].strip()
                flow["changed_at"] = steady_time()
                commit()
            if content.get("turnComplete") or content.get("interrupted"):
                while flow["pending"]:
                    commit(force=True)
                flow["full_text"], flow["committed"] = "", 0

    def stop_decoder():
        stop_process(decoder)

    try:
        while True:
            command = read_json(control_path)
            if not command.get("target"):
                time.sleep(0.1)
                continue
            identity = (command.get("generation"), command.get("source"), command["target"])
            if identity != active:
                reusable = active is not None and not active[1] and active[2] == identity[2]
                session_handle = None
                stop_decoder()
                decoder = None
                if connection and not reusable:
                    connection.close()
                    connection = None
                active = identity
                position = max(0, command.get("position_ms", 0))
                with lock:
                    state.update(generation=identity[0], cues=[], until_ms=position, error=None,
                                 ready=bool(connection and connection.ready.is_set()))
                    flow.update(cursor=position, pending="", start=position, sequence=0,
                        anchors=[], last_input_end=position, pending_since=0, pending_end=position,
                        full_text="", committed=0)
                    atomic_json(state_path, state)
                eof = False
                retry_at = 0
            if connection is None and steady_time() >= retry_at:
                try:
                    connection = LiveSession(command["target"], receive, session_handle)
                    if not connection.ready.wait(10):
                        raise RuntimeError(connection.error or "Live setup timed out")
                    failures = 0
                    with lock:
                        state.update(ready=True, error=None)
                except Exception as error:
                    if connection:
                        connection.close()
                    connection = None
                    session_handle = None
                    stop_decoder()
                    decoder = None
                    with lock:
                        flow["cursor"] = max(0, command.get("position_ms", 0))
                        flow["pending"] = ""
                        flow["full_text"], flow["committed"] = "", 0
                        flow["anchors"] = []
                        state.update(ready=False, error=connection_error(error))
                    failures += 1
                    retry_at = steady_time() + min(60, 2 ** min(6, failures))
            if connection and (connection.closed.is_set() or connection.rotate_at is not None):
                session_handle = connection.handle
                connection.close()
                connection = None
                with lock:
                    behind = flow["cursor"] < command.get("position_ms", 0) - 450
                    if not session_handle or behind:
                        session_handle = None
                        stop_decoder()
                        decoder = None
                        flow["cursor"] = max(0, command.get("position_ms", 0))
                        flow["pending"] = ""
                        flow["full_text"], flow["committed"] = "", 0
                        flow["anchors"] = []
                    state.update(ready=False, error="Live connection interrupted; reconnecting")
                retry_at = steady_time() + 0.25
            source = command.get("source")
            if source and connection and not eof:
                if decoder is None:
                    with open(os.devnull, "wb") as null:
                        decoder = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-ss", "%.3f" % (flow["cursor"] / 1000.0), "-i", source,
                            "-map", command.get("audio_stream", "0:a:0"), "-vn", "-sn", "-dn", "-ac", "1", "-ar", "16000",
                            "-f", "s16le", "pipe:1"], stdout=subprocess.PIPE, stderr=null, close_fds=True)
                position = max(0, command.get("position_ms", 0))
                if flow["cursor"] < position + 4000:
                    wanted = min(3200, max(0, position + 4000 - flow["cursor"]) * 32)
                    pcm = decoder.stdout.read(wanted)
                    if pcm:
                        try:
                            connection.ws.send_json({"realtimeInput": {"audio": {
                                "mimeType": "audio/pcm;rate=16000", "data": base64.b64encode(pcm).decode("ascii")}}})
                            with lock:
                                flow["cursor"] += len(pcm) // 32
                                state["until_ms"] = flow["cursor"]
                        except Exception:
                            connection.close()
                    else:
                        if decoder.wait() != 0:
                            with lock:
                                state["error"] = "Unable to decode recording audio"
                        try:
                            connection.ws.send_json({"realtimeInput": {"audioStreamEnd": True}})
                        except Exception:
                            connection.close()
                        eof = True
            with lock:
                if flow["pending"] and steady_time() - flow["changed_at"] >= 2:
                    commit(force=True)
                if steady_time() - publish_at >= 0.1:
                    atomic_json(state_path, state)
                    publish_at = steady_time()
            time.sleep(0.005)
    except Exception:
        logger().exception("Subtitle worker stopped")
        with lock:
            state.update(ready=False, error="Subtitle processing failed")
            atomic_json(state_path, state)
    finally:
        if connection:
            connection.close()
        stop_decoder()


if __name__ == "__main__":
    run(sys.argv[1])

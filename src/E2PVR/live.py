# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
from __future__ import unicode_literals
import json
import threading
import socket
import ssl
from .core import logger, steady_time
from .service import read_keys, ServiceError
from .transport import WebSocket, WebSocketUpgradeError

MODEL = "gemini-3.5-live-translate-preview"
KEY_ERRORS = ("API key rejected", "Service access denied", "Service quota exceeded")


def connection_error(error):
    if isinstance(error, ServiceError):
        return str(error)
    if isinstance(error, socket.gaierror):
        return "DNS lookup failed; check receiver network"
    if isinstance(error, (socket.timeout, ssl.SSLError)):
        return "Secure connection failed or timed out"
    if isinstance(error, WebSocketUpgradeError):
        if error.error_kind == "edge_block":
            return "Network route denied by service"
        return {400: "API key rejected", 401: "API key rejected", 403: "Service access denied",
                429: "Service quota exceeded"}.get(error.status_code, "Live connection failed; retrying")
    return "Live connection failed; retrying"


def open_live(target, on_message, preferred=None, handle=None, rejected=None):
    keys = read_keys()
    if preferred in keys:
        keys.remove(preferred)
        keys.insert(0, preferred)
    if rejected in keys:
        keys.remove(rejected)
        keys.append(rejected)
    last_error = None
    for key in keys:
        session = None
        try:
            session = LiveSession(target, on_message, key, handle if key == preferred else None)
            session.setup_finished.wait(10)
            if not session.ready.is_set() or session.closed.is_set():
                raise ServiceError(session.error or "Live setup timed out")
            return session
        except Exception as error:
            if session is not None:
                session.close()
            last_error = connection_error(error)
            if last_error not in KEY_ERRORS:
                raise ServiceError(last_error)
            logger().warning("Gemini credential attempt failed: %s", last_error)
    raise ServiceError(last_error)


def probe_live(target="fa"):
    session = open_live(target, lambda content: None)
    session.close()


def setup(target, handle=None):
    if target not in ("fa", "ar", "ru"):
        raise ServiceError("Unsupported subtitle language")
    return {"setup": {"model": "models/" + MODEL,
        "generationConfig": {"responseModalities": ["TEXT"], "translationConfig": {
            "targetLanguageCode": target, "echoTargetLanguage": True}},
        "inputAudioTranscription": {}, "outputAudioTranscription": {},
        "sessionResumption": {"handle": handle}}}


class LiveSession(object):
    def __init__(self, target, on_message, key, handle=None):
        self.key = key
        self.ws = WebSocket(key)
        self.error = None
        self.closed = threading.Event()
        self.ready = threading.Event()
        self.setup_finished = threading.Event()
        self.on_message = on_message
        self.handle = None
        self.rotate_at = None
        try:
            self.ws.connect()
            self.ws.send_json(setup(target, handle))
        except Exception:
            self.ws.close()
            raise
        self.reader = threading.Thread(target=self.receive)
        self.reader.daemon = True
        self.reader.start()

    def receive(self):
        try:
            while not self.closed.is_set():
                _, raw = self.ws.recv_message()
                value = json.loads(raw.decode("utf-8"))
                if value.get("error"):
                    # Never pass server messages containing credentials to logs.
                    code = value["error"].get("code")
                    raise ServiceError({400: "Invalid service request", 401: "API key rejected", 403: "Service access denied",
                        429: "Service quota exceeded"}.get(code, "Live service unavailable"))
                if "setupComplete" in value:
                    self.ready.set()
                    self.setup_finished.set()
                update = value.get("sessionResumptionUpdate") or {}
                if update.get("resumable"):
                    self.handle = update.get("newHandle")
                if value.get("goAway") is not None:
                    self.rotate_at = steady_time()
                content = value.get("serverContent")
                if content:
                    # Inline audio is intentionally discarded without decoding or playback.
                    self.on_message(content)
        except Exception as error:
            if not self.closed.is_set():
                self.error = "Live connection closed" if not isinstance(error, ServiceError) else str(error)
        finally:
            self.closed.set()
            self.setup_finished.set()

    def close(self):
        self.closed.set()
        self.ws.close()
        if threading.current_thread() is not self.reader:
            self.reader.join(2)

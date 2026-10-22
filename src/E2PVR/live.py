# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import threading
import socket
import ssl
from .core import steady_time
from .service import read_key, ServiceError
from .transport import WebSocket, WebSocketUpgradeError

MODEL = "gemini-3.5-live-translate-preview"


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


def probe_live(target="fa"):
    session = None
    try:
        session = LiveSession(target, lambda content: None)
        if not session.ready.wait(10):
            raise ServiceError(session.error or "Live setup timed out")
    except Exception as error:
        raise ServiceError(connection_error(error))
    finally:
        if session is not None:
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
    def __init__(self, target, on_message, handle=None):
        self.ws = WebSocket(read_key())
        self.error = None
        self.closed = threading.Event()
        self.ready = threading.Event()
        self.on_message = on_message
        self.handle = None
        self.rotate_at = None
        self.ws.connect()
        self.ws.send_json(setup(target, handle))
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

    def close(self):
        self.closed.set()
        self.ws.close()
        if threading.current_thread() is not self.reader:
            self.reader.join(2)

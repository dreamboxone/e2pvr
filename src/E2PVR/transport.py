# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Proprietary software. See LICENSE-E2Dub.txt.
from __future__ import print_function
import base64
import errno
import hashlib
import json
import os
import re
import socket
import ssl
import struct
import sys
import threading
from .core import steady_time, logger
HOST = "generativelanguage.googleapis.com"
PORT = 443
TLS_HANDSHAKE_TIMEOUT_SECONDS = 30
HTTP_UPGRADE_TIMEOUT_SECONDS = 10
WEBSOCKET_READ_TIMEOUT_SECONDS = 2
MAX_WS_MESSAGE_BYTES = 8 * 1024 * 1024
EDGE_BLOCK_MARKERS = ("does not have permission to get url", "client does not have permission")
STOP = threading.Event()
def log(message):
    logger().info(message)

def create_ipv4_connection(host, port, timeout):
    """Connect over IPv4 so full-device IPv4 TUN clients carry Gemini traffic."""
    last_error = None
    addresses = socket.getaddrinfo(
        host, port, socket.AF_INET, socket.SOCK_STREAM
    )
    for family, socktype, proto, _canonname, sockaddr in addresses:
        raw = socket.socket(family, socktype, proto)
        raw.settimeout(timeout)
        try:
            raw.connect(sockaddr)
            return raw
        except Exception as error:
            last_error = error
            try:
                raw.close()
            except Exception:
                pass
    if last_error is not None:
        raise last_error
    raise socket.error("No IPv4 address found for %s" % host)

def is_read_timeout(error):
    """Recognize socket and Python 2.7/OpenSSL read-timeout variants."""
    if isinstance(error, socket.timeout):
        return True
    error_number = getattr(error, "errno", None)
    if error_number is None:
        try:
            error_number = error.args[0]
        except Exception:
            error_number = None
    transient = (errno.EAGAIN, errno.EWOULDBLOCK)
    if error_number in transient:
        return True
    if isinstance(error, ssl.SSLError):
        message = str(error).lower()
        return (
            "timed out" in message or
            "read operation timed out" in message or
            "did not complete (read)" in message or
            "want read" in message
        )
    return False

def to_bytes(value):
    """Return exact byte content on both Python 2 and Python 3."""
    if isinstance(value, bytearray):
        if sys.version_info[0] >= 3:
            return bytes(value)
        return value.decode("latin-1").encode("latin-1")
    return value

def sanitize_detail(value):
    """Keep state/log diagnostics useful without leaking credentials or payloads."""
    try:
        value = str(value).replace("\r", " ").replace("\n", " ")
    except Exception:
        value = "unknown error"
    if "?key=" in value:
        value = value.split("?key=", 1)[0] + "?key=[redacted]"
    return value[:240]

class WebSocketClosed(IOError):
    def __init__(self, code, reason):
        self.code = code
        self.reason = sanitize_detail(reason)
        IOError.__init__(self, "WebSocket closed (code=%s, reason=%s)" %
                         (code, self.reason or "none"))

class WebSocketUpgradeError(IOError):
    def __init__(self, status_code, status_line, error_kind=""):
        self.status_code = status_code
        self.status_line = sanitize_detail(status_line)
        self.error_kind = error_kind
        IOError.__init__(
            self, "WebSocket upgrade rejected (%s)" % self.status_line
        )

def upgrade_rejection_kind(status_code, body_detail):
    """Separate a Gemini denial from a refusal somewhere on the network path.

    The Live API answers a denied request with its documented JSON error body.
    A 403 carrying an HTML page was written by something in front of the API -
    Google's own edge refusing the client IP, or a proxy or captive portal - so
    the request never reached Gemini and the API key cannot be the cause.
    """
    lowered = (body_detail or "").lower()
    if any(marker in lowered for marker in EDGE_BLOCK_MARKERS):
        return "edge_block"
    if status_code == 403 and lowered.startswith("unparsed_body="):
        return "edge_block"
    return ""

def parse_http_status(response):
    """Return a safe HTTP status without logging the credential-bearing URL."""
    try:
        first = response.split("\r\n", 1)[0].strip()
    except Exception:
        first = "unreadable HTTP response"
    first = sanitize_detail(first)
    code = None
    parts = first.split(" ", 2)
    if len(parts) >= 2:
        try:
            code = int(parts[1])
        except Exception:
            pass
    return code, first

def parse_http_error_body(body):
    """Extract only documented Google error fields; never log arbitrary HTML."""
    if not body:
        return ""
    try:
        if not isinstance(body, str):
            body = body.decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            # Chunked framing wraps the JSON in hex length lines, so fall back
            # to the outermost brace pair before giving up on the payload.
            start = body.find("{")
            end = body.rfind("}")
            if start < 0 or end <= start:
                raise
            parsed = json.loads(body[start:end + 1])
        error = parsed.get("error") if isinstance(parsed, dict) else None
        if not isinstance(error, dict):
            return ""
        parts = []
        for key in ("code", "status", "message"):
            if error.get(key) is not None:
                parts.append("%s=%s" % (key, sanitize_detail(error.get(key))))
        return ", ".join(parts)[:240]
    except Exception:
        # A proxy or Google's own edge can answer with an HTML page instead.
        # Dropping it left the status line as the only evidence, which is what
        # made a network block indistinguishable from a rejected API key.  Log
        # a short, tag-free snippet instead.
        try:
            if not isinstance(body, str):
                body = body.decode("utf-8", "replace")
            # Google's edge 403 page carries its stylesheet inline, which
            # otherwise fills the whole snippet with CSS and truncates away the
            # one sentence that says why the request was refused.
            cleaned = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
            text = re.sub(r"<[^>]*>", " ", cleaned)
            text = " ".join(text.split())
            return ("unparsed_body=%s" % sanitize_detail(text)[:180]) if text else ""
        except Exception:
            return ""

def certificate_common_name(certificate, field):
    """Return one public certificate CN without dumping the full certificate."""
    try:
        for relative_name in certificate.get(field, ()):
            for name, value in relative_name:
                if name == "commonName":
                    return sanitize_detail(value)
    except Exception:
        pass
    return "unknown"

def tls_session_summary(tls, verified):
    """Return non-secret TLS diagnostics supported by old embedded Python."""
    version = "unknown"
    cipher_name = "unknown"
    subject = "unknown"
    issuer = "unknown"
    try:
        callback = getattr(tls, "version", None)
        if callback is not None:
            version = sanitize_detail(callback())
    except Exception:
        pass
    try:
        cipher = tls.cipher()
        if cipher:
            cipher_name = sanitize_detail(cipher[0])
    except Exception:
        pass
    try:
        certificate = tls.getpeercert() or {}
        subject = certificate_common_name(certificate, "subject")
        issuer = certificate_common_name(certificate, "issuer")
    except Exception:
        pass
    return ("version=%s cipher=%s verified=%s subject_cn=%s issuer_cn=%s" %
            (version, cipher_name, "yes" if verified else "legacy",
             subject, issuer))

class WebSocket(object):
    def __init__(self, api_key):
        self.api_key = api_key
        self.sock = None
        self.write_lock = threading.Lock()
        self.fragments = bytearray()
        self.fragment_opcode = None
        self.recv_buffer = bytearray()

    def connect(self):
        # Prefer IPv4 because many receiver/router VPN policies cover IPv4 but
        # let an AAAA route bypass the tunnel. Log stage boundaries so a TCP,
        # TLS, proxy/DPI or WebSocket failure can be distinguished remotely.
        tcp_started = steady_time()
        log("Gemini connection stage=tcp_connect started host=%s port=%d family=IPv4" %
            (HOST, PORT))
        try:
            raw = create_ipv4_connection(HOST, PORT, 15)
        except Exception as error:
            log("Gemini connection stage=tcp_connect failed elapsed=%.2fs detail=%s" %
                (steady_time() - tcp_started, sanitize_detail(error)))
            raise
        try:
            peer = raw.getpeername()[0]
            log("Gemini connection stage=tcp_connect complete elapsed=%.2fs peer=%s" %
                (steady_time() - tcp_started, peer))
        except Exception:
            log("Gemini connection stage=tcp_connect complete elapsed=%.2fs peer=unknown" %
                (steady_time() - tcp_started))
        # Keep the connection timeout for the TLS handshake.  Version 0.3.0
        # shortened this to two seconds before wrap_socket(), which made
        # otherwise healthy embedded receivers fail behind a TUN/VPN.
        raw.settimeout(TLS_HANDSHAKE_TIMEOUT_SECONDS)
        context = None
        if hasattr(ssl, "create_default_context"):
            context = ssl.create_default_context()
        tls_started = steady_time()
        log("Gemini connection stage=tls_handshake started timeout=%.1fs sni=%s" %
            (TLS_HANDSHAKE_TIMEOUT_SECONDS, HOST))
        try:
            if context is not None:
                tls = context.wrap_socket(raw, server_hostname=HOST)
            else:
                tls = ssl.wrap_socket(raw, ssl_version=ssl.PROTOCOL_TLSv1_2)
        except Exception as error:
            log("Gemini connection stage=tls_handshake failed elapsed=%.2fs detail=%s" %
                (steady_time() - tls_started, sanitize_detail(error)))
            try:
                raw.close()
            except Exception:
                pass
            raise
        log("Gemini connection stage=tls_handshake complete elapsed=%.2fs %s" %
            (steady_time() - tls_started,
             tls_session_summary(tls, context is not None)))
        tls.settimeout(HTTP_UPGRADE_TIMEOUT_SECONDS)

        nonce = base64.b64encode(os.urandom(16))
        if not isinstance(nonce, str):
            nonce = nonce.decode("ascii")
        path = ("/ws/google.ai.generativelanguage.v1beta."
                "GenerativeService.BidiGenerateContent")
        request = (
            "GET %s HTTP/1.1\r\n"
            "Host: %s\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "x-goog-api-key: %s\r\nUser-Agent: e2pvr/0.2.0\r\n\r\n"
        ) % (path, HOST, nonce, self.api_key)
        upgrade_started = steady_time()
        log("Gemini connection stage=websocket_upgrade started timeout=%.1fs" %
            HTTP_UPGRADE_TIMEOUT_SECONDS)
        try:
            tls.sendall(request.encode("ascii"))
            log("Gemini connection stage=websocket_upgrade request_sent")
            response, remainder = self._read_headers(tls)
            lines = response.split("\r\n")
            status_code, status_line = parse_http_status(response)
            log("Gemini connection stage=websocket_upgrade response elapsed=%.2fs status=%s" %
                (steady_time() - upgrade_started,
                 status_code if status_code is not None else "unknown"))
            if not lines or " 101 " not in lines[0]:
                body = self._read_http_error_body(tls, lines, remainder)
                body_detail = parse_http_error_body(body)
                if body_detail:
                    body_detail = body_detail.replace(self.api_key, "[redacted]")
                    status_line = "%s: %s" % (status_line, body_detail)
                raise WebSocketUpgradeError(
                    status_code, status_line,
                    upgrade_rejection_kind(status_code, body_detail),
                )
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    name, value = line.split(":", 1)
                    headers[name.strip().lower()] = value.strip()
            expected = base64.b64encode(hashlib.sha1(
                (nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest())
            if not isinstance(expected, str):
                expected = expected.decode("ascii")
            if headers.get("sec-websocket-accept") != expected:
                raise IOError("Invalid WebSocket handshake")
        except Exception as error:
            log("Gemini connection stage=websocket_upgrade failed elapsed=%.2fs detail=%s" %
                (steady_time() - upgrade_started, sanitize_detail(error)))
            try:
                tls.close()
            except Exception:
                pass
            raise
        tls.settimeout(WEBSOCKET_READ_TIMEOUT_SECONDS)
        self.recv_buffer = bytearray(remainder)
        self.sock = tls
        log("Gemini connection stage=websocket_upgrade complete elapsed=%.2fs buffered=%d" %
            (steady_time() - upgrade_started, len(remainder)))

    def _read_headers(self, sock):
        data = bytearray()
        marker = b"\r\n\r\n"
        while data.find(marker) < 0:
            chunk = sock.recv(1024)
            if not chunk:
                raise IOError("Connection closed during handshake")
            data.extend(bytearray(chunk))
            if len(data) > 32768:
                raise IOError("Oversized handshake")
        end = data.find(marker) + len(marker)
        raw = to_bytes(data[:end])
        remainder = to_bytes(data[end:])
        text = raw.decode("iso-8859-1") if not isinstance(raw, str) else raw
        return text, remainder

    def _read_http_error_body(self, sock, header_lines, remainder):
        length = 0
        for line in header_lines[1:]:
            if line.lower().startswith("content-length:"):
                try:
                    length = min(4096, int(line.split(":", 1)[1].strip()))
                except Exception:
                    length = 0
                break
        data = bytearray(remainder[:4096])
        while length and len(data) < length:
            try:
                chunk = sock.recv(min(1024, length - len(data)))
            except Exception as error:
                if is_read_timeout(error):
                    break
                raise
            if not chunk:
                break
            data.extend(bytearray(chunk))
        return to_bytes(data[:length or len(data)])

    def send_json(self, value):
        payload = json.dumps(value, separators=(",", ":"))
        self.send_frame(0x1, payload.encode("utf-8"))

    def send_frame(self, opcode, payload):
        if self.sock is None:
            raise IOError("WebSocket is closed")
        if isinstance(payload, bytearray):
            payload = to_bytes(payload)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xffff:
            header.append(0x80 | 126)
            header.extend(bytearray(struct.pack("!H", length)))
        else:
            header.append(0x80 | 127)
            header.extend(bytearray(struct.pack("!Q", length)))
        mask = os.urandom(4)
        header.extend(bytearray(mask))
        masked = bytearray(payload)
        mask_values = bytearray(mask)
        for index in range(length):
            masked[index] ^= mask_values[index & 3]
        packet = header + masked
        packet = to_bytes(packet)
        with self.write_lock:
            self.sock.sendall(packet)

    def recv_message(self):
        while True:
            first = self._recv_exact(2)
            b1, b2 = bytearray(first)
            final = bool(b1 & 0x80)
            if b1 & 0x70:
                raise IOError("Unsupported WebSocket RSV bits")
            opcode = b1 & 0x0f
            masked = bool(b2 & 0x80)
            if masked:
                raise IOError("Protocol error: masked server frame")
            length = b2 & 0x7f
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            if length > MAX_WS_MESSAGE_BYTES:
                raise IOError("WebSocket frame is too large")
            if opcode >= 0x8 and (not final or length > 125):
                raise IOError("Invalid WebSocket control frame")
            mask = self._recv_exact(4) if masked else None
            payload = bytearray(self._recv_exact(length))
            if mask:
                mask_values = bytearray(mask)
                for index in range(length):
                    payload[index] ^= mask_values[index & 3]

            raw_payload = to_bytes(payload)
            if opcode == 0x8:
                code = 1005
                reason = ""
                if len(raw_payload) >= 2:
                    code = struct.unpack("!H", raw_payload[:2])[0]
                    try:
                        reason = raw_payload[2:].decode("utf-8", "replace")
                    except Exception:
                        reason = "unreadable"
                try:
                    self.send_frame(0x8, raw_payload or struct.pack("!H", 1000))
                except Exception:
                    pass
                raise WebSocketClosed(code, reason)
            if opcode == 0x9:
                self.send_frame(0xA, raw_payload)
                continue
            if opcode == 0xA:
                continue
            if opcode in (0x1, 0x2):
                if self.fragment_opcode is not None:
                    raise IOError("Unexpected data frame during fragmentation")
                if final:
                    return opcode, raw_payload
                self.fragment_opcode = opcode
                self.fragments = bytearray(payload)
                continue
            if opcode == 0x0 and self.fragment_opcode is not None:
                self.fragments.extend(payload)
                if len(self.fragments) > MAX_WS_MESSAGE_BYTES:
                    raise IOError("WebSocket message is too large")
                if final:
                    result = self.fragments
                    result_opcode = self.fragment_opcode
                    self.fragments = bytearray()
                    self.fragment_opcode = None
                    raw = to_bytes(result)
                    return result_opcode, raw
                continue
            raise IOError("Unsupported WebSocket opcode %s" % opcode)

    def _recv_exact(self, size):
        chunks = []
        remaining = size
        if self.recv_buffer:
            count = min(remaining, len(self.recv_buffer))
            chunks.append(to_bytes(self.recv_buffer[:count]))
            del self.recv_buffer[:count]
            remaining -= count
        sock = self.sock
        if sock is None:
            raise IOError("WebSocket is closed")
        while remaining:
            try:
                chunk = sock.recv(remaining)
            except Exception as error:
                if is_read_timeout(error):
                    if STOP.is_set():
                        raise IOError("Stopping")
                    continue
                raise
            if not chunk:
                raise IOError("WebSocket connection lost")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def close(self):
        sock = self.sock
        self.sock = None
        if sock is not None:
            # Safe even if a signal interrupts send_frame under write_lock.
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

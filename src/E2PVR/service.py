# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
from __future__ import unicode_literals
import io
import re
import socket
import ssl
from .platform_support import api_key_file
try:
    from httplib import HTTPSConnection
except ImportError:
    from http.client import HTTPSConnection

HOST = "generativelanguage.googleapis.com"
KEY_FILE = api_key_file()
DEFAULT_MODEL = "gemini-3.5-live-translate-preview"
MODELS = (DEFAULT_MODEL,)


class ServiceError(Exception):
    def __init__(self, message, retryable=False):
        Exception.__init__(self, message)
        self.retryable = retryable


def read_key(path=None):
    path = path or api_key_file()
    try:
        with io.open(path, encoding="utf-8-sig") as stream:
            key = stream.read(4097).strip()
    except IOError:
        raise ServiceError("Key file is missing: " + path)
    except UnicodeError:
        raise ServiceError("Invalid key file: " + path)
    if not key:
        raise ServiceError("Key file is empty: " + path)
    if len(key) > 4096 or not re.match(r"^[!-~]+$", key):
        raise ServiceError("Invalid key file: " + path)
    return key


class IPv4HTTPSConnection(HTTPSConnection):
    def connect(self):
        context = ssl.create_default_context()
        last_error = None
        for family, kind, protocol, _, address in socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM):
            raw = socket.socket(family, kind, protocol)
            raw.settimeout(self.timeout)
            try:
                raw.connect(address)
                self.sock = context.wrap_socket(raw, server_hostname=self.host)
                return
            except (socket.error, ssl.SSLError) as error:
                raw.close()
                last_error = error
        raise last_error or socket.error("Connection failed")


def probe(model=DEFAULT_MODEL):
    if model not in MODELS:
        raise ServiceError("Unsupported service model")
    key = read_key()
    connection = IPv4HTTPSConnection(HOST, 443, timeout=12)
    try:
        connection.request("GET", "/v1beta/models/" + model, headers={"x-goog-api-key": key})
        response = connection.getresponse()
        if response.status != 200:
            messages = {400: "API key rejected", 401: "API key rejected", 403: "Service access denied",
                        404: "Service model unavailable", 429: "Service quota exceeded"}
            raise ServiceError(messages.get(response.status, "Service HTTP %d" % response.status))
        response.read(16384)
    except (socket.error, ssl.SSLError):
        raise ServiceError("Secure connection failed or timed out", retryable=True)
    finally:
        connection.close()

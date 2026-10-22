# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE.
from __future__ import unicode_literals
import os
import shutil
import struct
import subprocess
import tempfile
import threading
from functools import partial
from xml.sax.saxutils import escape
from .process_guard import guard_parent
from .core import logger


def font_family(path):
    with open(path, "rb") as stream:
        header = stream.read(12)
        count = struct.unpack(">H", header[4:6])[0]
        for unused in range(count):
            tag, checksum, offset, length = struct.unpack(">4sIII", stream.read(16))
            if tag == b"name":
                stream.seek(offset)
                data = stream.read(length)
                records, strings = struct.unpack(">HH", data[2:6])
                candidates = []
                for index in range(records):
                    platform, encoding, language, name, size, beginning = struct.unpack(">6H", data[6 + index * 12:18 + index * 12])
                    if name == 1:
                        raw = data[strings + beginning:strings + beginning + size]
                        value = raw.decode("utf-16-be" if platform in (0, 3) else "mac_roman")
                        candidates.append((language != 1033, platform != 3, value))
                if candidates:
                    return sorted(candidates)[0][2]
                break
    return os.path.splitext(os.path.basename(path))[0]


class Rasterizer(object):
    def __init__(self, font_path, points, width, color):
        self.directory = tempfile.mkdtemp(prefix="e2pvr-raster-")
        self.family = font_family(font_path) if font_path else "sans"
        self.points, self.width, self.color = points, width, color
        self.jobs, self.sequence = [], 0
        config = os.path.join(self.directory, "fonts.conf")
        with open(config, "wb") as stream:
            stream.write(('<?xml version="1.0"?><fontconfig><dir>%s</dir>'
                '<dir>/usr/share/fonts</dir><cachedir>%s</cachedir></fontconfig>' %
                (escape(os.path.dirname(font_path)) if font_path else "/usr/share/fonts",
                 escape(self.directory))).encode("utf-8"))
        self.environment = os.environ.copy()
        self.environment["FONTCONFIG_FILE"] = config

    def request(self, text):
        self.sequence += 1
        for job in self.jobs:
            if job["process"].poll() is None:
                job["process"].kill()
        if not text:
            return
        stem = os.path.join(self.directory, str(self.sequence))
        with open(stem + ".txt", "wb") as stream:
            stream.write(text.encode("utf-8") if not isinstance(text, bytes) else text)
        arguments = ["/usr/bin/pango-view", "--no-display", "--pixels", "--dpi=72",
            "--font=%s %d" % (self.family, self.points), "--foreground=#" + self.color,
            "--background=transparent", "--margin=2", "--width=%d" % self.width,
            "--wrap=word-char", "--align=center", "--output=" + stem + ".png", stem + ".txt"]
        # Pango determines the direction from the actual text; no manual reversal.
        with open(os.devnull, "wb") as null:
            process = subprocess.Popen([value.encode("utf-8") for value in arguments],
                stdin=null, stdout=null, stderr=null, env=self.environment, close_fds=True,
                preexec_fn=partial(guard_parent, os.getpid()))
        self.jobs.append(dict(process=process, sequence=self.sequence, stem=stem))

    def discard(self, job):
        for suffix in (".txt", ".png"):
            try:
                os.unlink(job["stem"] + suffix)
            except OSError:
                pass

    def poll(self):
        for job in list(self.jobs):
            code = job["process"].poll()
            if code is None:
                continue
            self.jobs.remove(job)
            if code == 0 and job["sequence"] == self.sequence:
                return job
            if code != 0 and job["sequence"] == self.sequence:
                logger().warning("Subtitle shaping process failed: status=%d", code)
            self.discard(job)
        return None

    def close(self):
        jobs, self.jobs = self.jobs, []
        for job in jobs:
            if job["process"].poll() is None:
                job["process"].kill()
        directory = self.directory
        def cleanup():
            for job in jobs:
                job["process"].wait()
            shutil.rmtree(directory, ignore_errors=True)
        thread = threading.Thread(target=cleanup)
        thread.daemon = True
        thread.start()

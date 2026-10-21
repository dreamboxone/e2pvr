# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import bisect
import io
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import time
import textwrap


def steady_time():
    callback = getattr(time, "monotonic", None)
    return callback() if callback is not None else os.times()[4]


def logger():
    log = logging.getLogger("e2pvr")
    if not log.handlers:
        handler = RotatingFileHandler("/tmp/e2pvr.log", maxBytes=262144,
                                      backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


def storage_paths(mount_file="/proc/mounts"):
    paths = []
    try:
        with io.open(mount_file, encoding="utf-8") as stream:
            for line in stream:
                parts = line.split()
                if len(parts) < 4:
                    continue
                path = parts[1].replace("\\040", " ").replace("\\134", "\\")
                if (path.startswith("/media/") and "rw" in parts[3].split(",")
                        and os.path.isdir(path) and os.access(path, os.W_OK)):
                    paths.append(path)
    except IOError:
        pass
    return sorted(set(paths), key=lambda path: (path != "/media/hdd", path))


def default_model_path():
    paths = storage_paths()
    return os.path.join(paths[0] if paths else "/data", "e2pvr", "models")


def overlay_geometry(width, height, position, size):
    points = {"small": 32, "medium": 42, "large": 54}[size]
    font = max(16, int(points * height / 720.0))
    box_height = min(height, font * 3 + 24)
    box_width = int(width * 0.90)
    y = int(height * max(0, min(100, position)) / 100.0)
    return (int((width - box_width) / 2), min(y, height - box_height),
            box_width, box_height, font)


class SubtitleTrack(object):
    def __init__(self, cues):
        self.cues = sorted(cues)
        self.starts = [cue[0] for cue in self.cues]

    def text_at(self, milliseconds):
        index = bisect.bisect_right(self.starts, milliseconds) - 1
        if index >= 0:
            start, end, text = self.cues[index]
            if start <= milliseconds < end:
                return text
        return ""

    @classmethod
    def load(cls, path):
        with io.open(path, encoding="utf-8-sig") as stream:
            content = stream.read().replace("\r\n", "\n")
        stamp = r"(\d+):(\d{2}):(\d{2})[,.](\d{3})"
        timing = re.compile(r"^" + stamp + r"\s*-->\s*" + stamp + r"(?:\s+.*)?$")
        cues = []
        for block in re.split(r"\n\s*\n", content.strip()):
            lines = block.splitlines()
            for index, line in enumerate(lines):
                match = timing.match(line.strip())
                if match:
                    values = [int(value) for value in match.groups()]
                    start = ((values[0] * 60 + values[1]) * 60 + values[2]) * 1000 + values[3]
                    end = ((values[4] * 60 + values[5]) * 60 + values[6]) * 1000 + values[7]
                    if end > start:
                        cues.append((start, end, "\n".join(lines[index + 1:])))
                    break
        return cls(cues)


def split_cues(cues, line_chars):
    """Split complete cues without dropping words or crossing their source interval."""
    output = []
    for cue in cues:
        original = cue["text"].splitlines()
        text = " ".join(cue["text"].split())
        lines = original if len(original) <= 2 and all(len(line) <= line_chars for line in original) else textwrap.wrap(text, line_chars)
        groups = ["\n".join(lines[index:index + 2]) for index in range(0, len(lines), 2)]
        total = sum(len(value) for value in groups) or 1
        start, consumed = cue["start"], 0
        duration = cue["end"] - start
        for index, value in enumerate(groups):
            end = start + duration * (consumed + len(value)) // total
            beginning = start + duration * consumed // total
            if end > beginning:
                output.append(dict(start=beginning, end=end, text=value,
                                   id=(cue["start"], cue.get("id", 0), index)))
            consumed += len(value)
    return output


class CueScheduler(object):
    """Commit-only FIFO display with bounded backlog and protected reading time."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.pending = {}
        self.seen = []
        self.current = None
        self.shown_at = 0
        self.last_id = None

    def refresh(self, cues, position, correction=0):
        for cue in cues:
            if not cue.get("final", True):
                continue
            identity = tuple(cue.get("id", (cue["start"], 0)))
            if identity in self.seen or (self.last_id is not None and identity <= self.last_id):
                continue
            self.seen.append(identity)
            if len(self.seen) > 32:
                self.seen = self.seen[-16:]
            due = max(cue["start"] + correction, position)
            if position - (cue["start"] + correction) <= 4000:
                self.pending[identity] = dict(cue, due=due)
        while len(self.pending) > 6:
            self.pending.pop(sorted(self.pending)[0])
        ready = [(identity, cue) for identity, cue in sorted(self.pending.items())
                 if cue["due"] <= position and (self.last_id is None or identity > self.last_id)]
        reading = max(2000, min(6000, len(self.current["text"]) * 1000 // 17)) if self.current else 0
        if ready and (not self.current or position - self.shown_at >= reading):
            identity, cue = ready[0]
            consumed = [identity]
            if len(ready) > 1 and "\n" not in cue["text"] and "\n" not in ready[1][1]["text"]:
                next_id, next_cue = ready[1]
                cue = dict(cue, text=cue["text"] + "\n" + next_cue["text"])
                identity = next_id
                consumed.append(next_id)
            for key in consumed:
                self.pending.pop(key, None)
            self.current, self.last_id, self.shown_at = cue, identity, position
        if self.current:
            timeout = max(3000, max(2000, min(6000, len(self.current["text"]) * 1000 // 17)))
            if position - self.shown_at <= timeout:
                return self.current["text"]
            self.current = None
        return ""

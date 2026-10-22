# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
from __future__ import unicode_literals
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from functools import partial
from .storage import atomic_json, read_json
from . import PACKAGE_DIR
from .process_guard import guarded_session


def worker_python():
    candidates = ("/usr/bin/python3",) if sys.version_info[0] >= 3 else (
        "/usr/bin/python2.7", "/usr/bin/python2", "/usr/bin/python")
    for path in candidates:
        if os.access(path, os.X_OK):
            return path
    if os.path.basename(sys.executable).startswith("python"):
        return sys.executable
    raise RuntimeError("Python interpreter is unavailable")


class Runtime(object):
    def __init__(self, target="fa"):
        self.directory = tempfile.mkdtemp(prefix="e2pvr-")
        atomic_json(os.path.join(self.directory, "control.json"),
                    dict(source="", target=target, generation=0, position_ms=0))
        root = PACKAGE_DIR
        with open(os.path.join(self.directory, "worker.log"), "wb") as errors:
            self.process = subprocess.Popen([worker_python(), os.path.join(root, "worker_main.py"), self.directory],
                stdout=errors, stderr=errors, preexec_fn=partial(guarded_session, os.getpid()), close_fds=True)

    def state(self):
        state = read_json(os.path.join(self.directory, "state.json"))
        if self.process.poll() is not None and not state.get("error"):
            state["error"] = "Processing worker stopped"
        return state

    def command(self, source, target, model, generation, position, audio_stream="0:a:0", preview_origin=None, preview_delay_ms=0):
        if self.process.poll() is None:
            atomic_json(os.path.join(self.directory, "control.json"), dict(source=source, target=target,
                model=model, generation=generation, position_ms=position, audio_stream=audio_stream,
                preview_origin_ms=preview_origin, preview_delay_ms=preview_delay_ms))

    def stop(self):
        process, directory = self.process, self.directory
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass

        def cleanup():
            process.wait()
            shutil.rmtree(directory, ignore_errors=True)
        thread = threading.Thread(target=cleanup)
        thread.daemon = True
        thread.start()

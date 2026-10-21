# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from .state import atomic_json, read_json


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
        root = os.path.dirname(__file__)
        with open(os.path.join(self.directory, "worker.log"), "wb") as errors:
            self.process = subprocess.Popen([worker_python(), os.path.join(root, "worker.py"), self.directory],
                stdout=errors, stderr=errors, preexec_fn=os.setsid, close_fds=True)

    def state(self):
        state = read_json(os.path.join(self.directory, "state.json"))
        if self.process.poll() is not None and not state.get("error"):
            state["error"] = "Processing worker stopped"
        return state

    def command(self, source, target, model, generation, position, audio_stream="0:a:0"):
        if self.process.poll() is None:
            atomic_json(os.path.join(self.directory, "control.json"), dict(source=source, target=target,
                model=model, generation=generation, position_ms=position, audio_stream=audio_stream))

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

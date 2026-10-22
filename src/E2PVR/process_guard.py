# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE.
import ctypes
import os
import signal
import sys

_prctl = getattr(ctypes.CDLL(None), "prctl", None) if sys.platform.startswith("linux") else None


def guard_parent(expected_pid):
    if _prctl is not None:
        if _prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            os._exit(1)
        if os.getppid() != expected_pid:
            os._exit(0)


def guarded_session(expected_pid):
    os.setsid()
    guard_parent(expected_pid)

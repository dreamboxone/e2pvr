# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
from __future__ import unicode_literals
import io
import json
import os


def atomic_json(path, value):
    temporary = path + ".new"
    with io.open(temporary, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False))
        stream.flush()
    os.rename(temporary, path)


def read_json(path):
    try:
        with io.open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (IOError, ValueError):
        return {}

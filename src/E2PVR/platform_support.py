# -*- coding: utf-8 -*-
# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
from .platform_profile import PLATFORM_PROFILE


def is_oe_alliance():
    if PLATFORM_PROFILE != "auto":
        return PLATFORM_PROFILE == "oealliance-universal"
    try:
        with open("/etc/os-release", "r") as stream:
            release = stream.read().lower()
        return "opendreambox" not in release and "dreamos" not in release
    except IOError:
        return False


def api_key_file():
    return "/home/root/apikey.txt" if is_oe_alliance() else "/root/apikey.txt"

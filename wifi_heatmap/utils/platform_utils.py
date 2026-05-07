from __future__ import annotations

import sys


def get_platform() -> str:
    return sys.platform


def is_windows() -> bool:
    return sys.platform == "win32"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def get_wifi_interface() -> str:
    if is_linux():
        return "wlan0"
    if is_macos():
        return "en0"
    return ""

"""Shared utilities."""

import subprocess
import sys


def hide_window() -> dict:
    """Return kwargs for subprocess calls to hide the console window on Windows.

    Usage: subprocess.run([...], **hide_window())
    """
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        return {"startupinfo": si}
    return {}

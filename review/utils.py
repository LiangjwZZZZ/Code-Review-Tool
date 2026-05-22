"""Shared utilities."""

import subprocess
import sys


def hide_window() -> dict:
    """Return kwargs for subprocess calls to hide the console window on Windows.

    Uses CREATE_NO_WINDOW creation flag for GUI apps (PyInstaller console=False).
    Usage: subprocess.run([...], **hide_window())
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}

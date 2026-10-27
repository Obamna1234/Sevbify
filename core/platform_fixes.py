"""Small operating-system fixes applied once at start-up (no UI code)."""
import os
import subprocess

CREATE_NO_WINDOW = 0x08000000


def hide_console_windows(popen_cls=subprocess.Popen, windows=None):
    """On Windows, programs Sevbify starts in the background (ffmpeg, yt-dlp helpers) would briefly flash a
    black console window. Give every such start the "no window" flag unless the caller chose its own flags."""
    windows = (os.name == "nt") if windows is None else windows
    if not windows:
        return False
    original = popen_cls.__init__
    if getattr(original, "_sevbify_no_window", False):
        return True

    def __init__(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = CREATE_NO_WINDOW
        original(self, *args, **kwargs)

    __init__._sevbify_no_window = True
    popen_cls.__init__ = __init__
    return True


def reveal_in_file_manager(path, run=subprocess.Popen, system=None):
    """Open the folder that holds `path` with the file selected (Explorer / Finder / the Linux file manager)."""
    import sys
    system = system or sys.platform
    path = os.path.abspath(path)
    if system.startswith("win"):
        cmd = f'explorer /select,"{path}"'          # explorer wants the quotes around the path only
    elif system == "darwin":
        cmd = ["open", "-R", path]
    else:
        cmd = ["xdg-open", os.path.dirname(path)]
    try:
        run(cmd)
        return True
    except Exception:
        return False

"""Portable mode: keep everything (playlists, settings, caches) in a "Sevbify data" folder next to the app instead
of the usual per-user folder (AppData on Windows), e.g. to carry Sevbify on a USB stick.

It's on when that folder exists next to Sevbify.exe (or next to app.py when run from source). app.py checks this
before anything else loads; Settings → Your Library → "Keep my data next to the app" switches it on or off by
copying your data across (the old copy is left where it was, so nothing is lost if a copy goes wrong).
"""
import os
import shutil
import sys

FOLDER = "Sevbify data"


def app_folder():
    if getattr(sys, "frozen", False):
        exe = os.path.dirname(sys.executable)
        # macOS: next to Sevbify.app, not inside it
        if sys.platform == "darwin" and exe.endswith(os.path.join("Contents", "MacOS")):
            return os.path.dirname(os.path.dirname(os.path.dirname(exe)))
        return exe
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def portable_dir():
    return os.path.join(app_folder(), FOLDER)


def apply_at_start():
    """Called first thing by app.py: use the portable folder when it exists."""
    d = portable_dir()
    owned = not hasattr(os, "getuid") or (not os.path.islink(d) and os.path.isdir(d) and os.stat(d).st_uid == os.getuid())
    if not os.environ.get("SEVBIFY_DATA_DIR") and os.path.isdir(d) and owned:
        os.environ["SEVBIFY_DATA_DIR"] = portable_dir()
        return True
    return False


def is_portable(current_dir):
    return os.path.normcase(os.path.abspath(current_dir)) == os.path.normcase(os.path.abspath(portable_dir()))


def _copy(src, dst):
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.islink(s):
            continue                # never copy what a shortcut points at
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True, symlinks=True)
        else:
            shutil.copy2(s, d)


def enable(current_dir):
    """Copy your data next to the app. Used from the next start. Raises OSError if the folder can't be written
    (e.g. the app is in Program Files)."""
    target = portable_dir()
    probe = os.path.join(app_folder(), ".sevbify-write-test")
    with open(probe, "w") as f:
        f.write("x")
    os.remove(probe)
    _copy(current_dir, target)
    return target


def disable(current_dir, normal_dir):
    """Copy your data back to the usual folder and rename the portable one so it's no longer used."""
    _copy(current_dir, normal_dir)
    old = portable_dir() + " (not used)"
    n = 2
    while os.path.exists(old):
        old = f"{portable_dir()} (not used {n})"
        n += 1
    os.rename(portable_dir(), old)
    return normal_dir

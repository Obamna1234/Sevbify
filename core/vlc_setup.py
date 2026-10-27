"""Use the copy of VLC's playback engine (libVLC) bundled inside the packaged app.

The ready-made Windows app ships libvlc.dll, libvlccore.dll and VLC's plugins in a "vlc" folder, so
nobody has to install VLC separately. This must run before anything imports `vlc`. When running from
source (Run Sevbify.bat) there is no bundled copy, and the installed VLC is used as before.
VLC is made by VideoLAN (libVLC: LGPL 2.1+; https://www.videolan.org).
"""
import os
import sys

BUNDLED_FOLDER = "vlc"


def bundled_vlc_dir():
    """The bundled VLC folder inside the packaged app, or "" when there is none."""
    if not getattr(sys, "frozen", False):
        return ""
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    folder = os.path.join(base, BUNDLED_FOLDER)
    lib = "libvlc.dll" if os.name == "nt" else "libvlc.so"
    return folder if os.path.isfile(os.path.join(folder, lib)) else ""


def use_bundled_vlc():
    """Point python-vlc at the bundled libVLC. Returns the folder used, or "" (installed VLC is used)."""
    folder = bundled_vlc_dir()
    if not folder:
        return ""
    lib = os.path.join(folder, "libvlc.dll" if os.name == "nt" else "libvlc.so")
    plugins = os.path.join(folder, "plugins")
    os.environ["PYTHON_VLC_LIB_PATH"] = lib
    os.environ["PYTHON_VLC_MODULE_PATH"] = plugins
    os.environ["VLC_PLUGIN_PATH"] = plugins
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(folder)        # so libvlc.dll finds libvlccore.dll next to it
        except OSError:
            pass
    os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
    return folder

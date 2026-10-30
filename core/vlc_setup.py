"""Use the copy of VLC's playback engine (libVLC) bundled inside the packaged app.

The ready-made Windows and macOS apps ship libVLC (libvlc.dll / libvlc.dylib), libvlccore and VLC's
plugins in a "vlc" folder, so nobody has to install VLC separately. The Linux app uses the VLC installed
from the system's package manager (sudo apt install vlc), like most Linux programs. This must run before anything imports `vlc`. When running from
source (Run Sevbify.bat) there is no bundled copy, and the installed VLC is used as before.
VLC is made by VideoLAN (libVLC: LGPL 2.1+; https://www.videolan.org).
"""
import os
import sys

BUNDLED_FOLDER = "vlc"


def _lib_name(system=None):
    system = system or sys.platform
    if system.startswith("win"):
        return "libvlc.dll"
    if system == "darwin":
        return os.path.join("lib", "libvlc.dylib")      # VLC.app's layout: plugins find lib/ next to them
    return "libvlc.so"


def bundled_vlc_dir():
    """The bundled VLC folder inside the packaged app, or "" when there is none."""
    if not getattr(sys, "frozen", False):
        return ""
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    folder = os.path.join(base, BUNDLED_FOLDER)
    return folder if os.path.isfile(os.path.join(folder, _lib_name())) else ""


def use_bundled_vlc():
    """Point python-vlc at the bundled libVLC. Returns the folder used, or "" (installed VLC is used)."""
    folder = bundled_vlc_dir()
    if not folder:
        return ""
    lib = os.path.join(folder, _lib_name())
    plugins = os.path.join(folder, "plugins")
    if sys.platform == "darwin":
        # libvlc.dylib needs libvlccore loaded first (python-vlc does the same for an installed VLC.app).
        core = os.path.join(folder, "lib", "libvlccore.dylib")
        if os.path.isfile(core):
            try:
                import ctypes
                ctypes.CDLL(core, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass
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

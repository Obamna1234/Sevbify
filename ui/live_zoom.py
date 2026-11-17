"""Zoom that applies straight away (Ctrl + / Ctrl - / Ctrl 0), like Spotify's.

Qt normally fixes its scale (QT_SCALE_FACTOR, set from Settings → Zoom when Sevbify starts) for the whole run.
Qt has a function to change it while running, QHighDpiScaling::setGlobalFactor; it isn't part of Qt's public
API, so it's looked up by name in Qt's own library and Sevbify falls back to "applies after a restart" whenever
it isn't there (another Qt build) or anything goes wrong.

After the scale changes, each open window gets a fresh native window (hide, recreate, show), so it's drawn at
the new size; its place and size on the screen stay the same, as in Spotify, and the content gets bigger or
smaller. The taskbar buttons (Windows) are added again when Windows announces the new taskbar button.
"""
import ctypes
import os
import sys

_func = None
_looked = False
current = None        # the factor set while running (None: still the one Sevbify started with)


why = ""              # why it isn't available (shown in the tests' output)


def _qt_gui_libraries():
    """Places Qt's GUI library may be found, most likely first."""
    import glob
    import PyQt6
    base = os.path.join(os.path.dirname(PyQt6.__file__), "Qt6")
    if sys.platform == "win32":
        yield lambda: ctypes.WinDLL("Qt6Gui.dll")                     # already loaded by PyQt6
        yield lambda: ctypes.WinDLL(os.path.join(base, "bin", "Qt6Gui.dll"))
        return
    if sys.platform == "darwin":
        for path in [os.path.join(base, "lib", "QtGui.framework", "QtGui")] + sorted(
                glob.glob(os.path.join(base, "lib", "QtGui.framework", "Versions", "*", "QtGui"))):
            yield lambda path=path: ctypes.CDLL(path)
    else:
        yield lambda: ctypes.CDLL("libQt6Gui.so.6")
        yield lambda: ctypes.CDLL(os.path.join(base, "lib", "libQt6Gui.so.6"))
    yield lambda: ctypes.CDLL(None)                                  # everything already loaded


def _set_global_factor():
    global _func, _looked, why
    if _looked:
        return _func
    _looked = True
    problems = []
    for open_lib in _qt_gui_libraries():
        try:
            lib = open_lib()
        except OSError as e:
            problems.append(str(e)[:160])
            continue
        for name in ("?setGlobalFactor@QHighDpiScaling@@SAXN@Z",        # Windows (MSVC)
                     "_ZN15QHighDpiScaling15setGlobalFactorEd"):        # Linux, macOS
            try:
                f = getattr(lib, name)
            except AttributeError:
                continue
            f.argtypes = [ctypes.c_double]
            f.restype = None
            _func = f
            return _func
        problems.append(f"{getattr(lib, '_name', lib)}: no setGlobalFactor")
    why = "; ".join(problems)
    return _func


def available():
    return _set_global_factor() is not None


def apply(old_percent, new_percent, windows):
    """Rescale the running app from old_percent to new_percent. `windows`: the top-level widgets to redraw.
    Returns True when it worked (else the caller offers a restart)."""
    f = _set_global_factor()
    if f is None or old_percent == new_percent:
        return f is not None
    from PyQt6.QtCore import Qt, qInstallMessageHandler
    ratio = old_percent / new_percent
    shown = [w for w in windows if w is not None and w.isVisible() and w.windowHandle() is not None]
    states = []
    for w in shown:
        scr = w.screen()
        origin = scr.geometry().topLeft() if scr is not None else None   # a screen keeps its corner when scaled
        states.append((w, w.windowState(), w.geometry(), origin))
    # Qt warns "should only be called when no windows exist"; the windows are recreated right after, which is
    # what that warning is about, so it's kept out of the logs.
    previous = qInstallMessageHandler(lambda kind, ctx, msg: None
                                      if "setFactor" in msg else (previous(kind, ctx, msg) if previous else None))
    try:
        f(new_percent / 100.0)
        global current
        current = new_percent / 100.0
    finally:
        qInstallMessageHandler(previous)
    for w, state, geo, origin in states:
        handle = w.windowHandle()
        w.hide()
        if handle is not None:
            handle.destroy()
        special = (Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen
                   | Qt.WindowState.WindowMinimized)
        if state & special:
            w.setWindowState(state)                       # maximised / full screen / minimised stay so
            w.show()
        else:
            # Same place and size on the screen: the logical size changes by old/new.
            ox, oy = (origin.x(), origin.y()) if origin is not None else (0, 0)
            w.setGeometry(ox + round((geo.x() - ox) * ratio), oy + round((geo.y() - oy) * ratio),
                          max(1, round(geo.width() * ratio)), max(1, round(geo.height() * ratio)))
            w.show()
    return True

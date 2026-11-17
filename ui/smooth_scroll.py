"""Smooth scrolling everywhere, like Spotify's: one notch of the mouse wheel glides about 100 px over a fifth of a
second (eased), and quick notches add up so a flick keeps going smoothly. Touchpads and trackpads already send
smooth pixel steps, so those are left as they are.

Installed once (`install(app)`): every scroll area, list and table gets it. The filter sits on each scroll area's
viewport, never on the whole application: an app-wide Python event filter is also called for widgets that are
half-destroyed, and wrapping those crashed the app (closing a dialog with a rich-text label, and on exit on
Windows). New scroll areas are picked up within SCAN_MS (`hook_now()` does it at once).
"""
from PyQt6.QtCore import QObject, QEvent, QVariantAnimation, QEasingCurve, Qt
from PyQt6.QtWidgets import QAbstractScrollArea, QApplication

STEP = 100            # pixels per wheel notch
DURATION = 220        # ms


class _Smoother(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._anims = {}          # scrollbar -> (animation, target)

    def eventFilter(self, obj, e):
        if e.type() != QEvent.Type.Wheel:
            return False
        area = obj.parent() if obj is not None else None
        if not isinstance(area, QAbstractScrollArea) or obj is not area.viewport():
            return False
        if not e.pixelDelta().isNull() or e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return False                       # touchpad (already smooth) / Ctrl+wheel (zoom)
        dy, dx = e.angleDelta().y(), e.angleDelta().x()
        horizontal = (dx and not dy) or bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        bar = area.horizontalScrollBar() if horizontal else area.verticalScrollBar()
        delta = (dx or dy) if horizontal else dy
        if bar is None or bar.maximum() <= bar.minimum() or not delta:
            return False
        anim, target = self._anims.get(bar, (None, None))
        start = bar.value()
        base = target if anim is not None and anim.state() == QVariantAnimation.State.Running else start
        new_target = max(bar.minimum(), min(bar.maximum(), int(base - delta / 120 * STEP)))
        if new_target == start and anim is None:
            return True
        if anim is None:
            anim = QVariantAnimation(self)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.valueChanged.connect(lambda v, b=bar: b.setValue(int(v)))
            bar.destroyed.connect(lambda *_a, b=bar: self._anims.pop(b, None))
        anim.stop()
        anim.setDuration(DURATION)
        anim.setStartValue(start)
        anim.setEndValue(new_target)
        self._anims[bar] = (anim, new_target)
        anim.start()
        return True


_installed = None
_timer = None
SCAN_MS = 700
_HOOKED = "_sevbifySmooth"


def hook_now():
    """Put the smoother on every scroll area that doesn't have it yet."""
    if _installed is None:
        return 0
    n = 0
    for w in QApplication.allWidgets():
        if isinstance(w, QAbstractScrollArea) and not w.property(_HOOKED):
            vp = w.viewport()
            if vp is None:
                continue
            vp.installEventFilter(_installed)
            w.setProperty(_HOOKED, True)
            n += 1
    return n


def install(app=None):
    """Turn smooth wheel scrolling on for the whole app (once)."""
    global _installed, _timer
    from PyQt6.QtCore import QTimer
    app = app or QApplication.instance()
    if app is None or _installed is not None:
        return _installed
    _installed = _Smoother(app)
    _timer = QTimer(_installed)
    _timer.setInterval(SCAN_MS)
    _timer.timeout.connect(hook_now)
    _timer.start()
    hook_now()
    app.aboutToQuit.connect(uninstall)
    return _installed


def uninstall():
    global _installed, _timer
    if _timer is not None:
        try:
            _timer.stop()
        except RuntimeError:
            pass
    _timer = None
    _installed = None

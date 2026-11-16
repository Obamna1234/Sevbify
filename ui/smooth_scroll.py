"""Smooth scrolling everywhere, like Spotify's: one notch of the mouse wheel glides about 100 px over a fifth of a
second (eased), and quick notches add up so a flick keeps going smoothly. Touchpads and trackpads already send
smooth pixel steps, so those are left as they are.

Installed once on the application (`install(app)`); every scroll area, list and table gets it.
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


def install(app=None):
    """Turn smooth wheel scrolling on for the whole app (once)."""
    global _installed
    app = app or QApplication.instance()
    if app is None or _installed is not None:
        return _installed
    _installed = _Smoother(app)
    app.installEventFilter(_installed)
    # Taken off again before Python starts tearing things down: an app-wide filter still being called while the
    # interpreter exits crashed the Windows build on closing (access violation in the smoke test).
    app.aboutToQuit.connect(uninstall)
    return _installed


def uninstall():
    global _installed
    app = QApplication.instance()
    if app is not None and _installed is not None:
        try:
            app.removeEventFilter(_installed)
        except RuntimeError:
            pass
    _installed = None

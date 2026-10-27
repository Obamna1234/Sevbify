"""Small reusable widgets in Spotify's style."""
from PyQt6.QtWidgets import QAbstractButton, QSizePolicy
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt, QSize, QRectF

from . import theme


class ToggleSwitch(QAbstractButton):
    """On/off switch: green with the knob on the right when on, grey when off."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(40, 22)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        on = self.isChecked()
        track = QColor(theme.GREEN if on else "#727272")
        if not self.isEnabled():
            track = QColor("#3e3e3e")
        elif self.underMouse():
            track = track.lighter(112)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.right() - d - 3 if on else r.left() + 3
        p.setBrush(QColor("#000000" if on else "#ffffff") if self.isEnabled() else QColor("#727272"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))
        p.end()

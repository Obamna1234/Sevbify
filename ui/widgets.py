"""Small reusable widgets in Spotify's style."""
from PyQt6.QtWidgets import QAbstractButton, QSizePolicy, QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt, QSize, QRectF, QPointF, QObject, pyqtSignal

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


class EqualizerCurve(QAbstractButton):
    """Spotify's equaliser: a smooth green curve over the bands with a dot to drag on each band
    (up = louder, down = quieter, -12 to +12 dB shown)."""
    changed = pyqtSignal(list)        # every move (live)
    released = pyqtSignal(list)       # when a dot is let go (save)

    RANGE = 12.0

    def __init__(self, values, labels, parent=None):
        super().__init__(parent)
        self.values = [max(-self.RANGE, min(self.RANGE, float(v))) for v in values]
        self.labels = list(labels)
        self._drag = -1
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        return QSize(600, 220)

    def set_values(self, values):
        self.values = [max(-self.RANGE, min(self.RANGE, float(v))) for v in values]
        self.update()

    def _plot(self):
        return QRectF(40, 12, self.width() - 56, self.height() - 48)

    def _point(self, i):
        r = self._plot()
        n = max(1, len(self.values) - 1)
        x = r.left() + r.width() * i / n
        y = r.center().y() - (self.values[i] / self.RANGE) * (r.height() / 2)
        return QPointF(x, y)

    def paintEvent(self, _e):
        from PyQt6.QtGui import QPainterPath, QPen, QLinearGradient, QFont
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._plot()
        enabled = self.isEnabled()
        green = QColor(theme.GREEN if enabled else "#535353")
        f = QFont(self.font())
        f.setPixelSize(11)
        p.setFont(f)
        # grid: 0 dB line and the band lines
        p.setPen(QPen(QColor(255, 255, 255, 25), 1))
        for db in (-self.RANGE, 0, self.RANGE):
            y = r.center().y() - (db / self.RANGE) * (r.height() / 2)
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))
            p.setPen(QColor(theme.SUBDUED))
            p.drawText(QRectF(0, y - 8, 36, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{int(db):+d}dB" if db else "0dB")
            p.setPen(QPen(QColor(255, 255, 255, 25), 1))
        pts = [self._point(i) for i in range(len(self.values))]
        path = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):                       # smooth curve through the points
            mid = (b.x() - a.x()) / 2
            path.cubicTo(QPointF(a.x() + mid, a.y()), QPointF(b.x() - mid, b.y()), b)
        fill = QPainterPath(path)
        fill.lineTo(pts[-1].x(), r.bottom())
        fill.lineTo(pts[0].x(), r.bottom())
        fill.closeSubpath()
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        c1, c2 = QColor(green), QColor(green)
        c1.setAlpha(90)
        c2.setAlpha(0)
        g.setColorAt(0, c1)
        g.setColorAt(1, c2)
        p.fillPath(fill, g)
        p.setPen(QPen(green, 3))
        p.drawPath(path)
        for i, pt in enumerate(pts):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("white") if (i in (self._drag, self._hover) and enabled) else green)
            p.drawEllipse(pt, 7 if i in (self._drag, self._hover) else 6, 7 if i in (self._drag, self._hover) else 6)
            p.setPen(QColor(theme.SUBDUED))
            p.drawText(QRectF(pt.x() - 30, r.bottom() + 10, 60, 16), Qt.AlignmentFlag.AlignCenter,
                       self.labels[i] if i < len(self.labels) else "")
        if self._drag >= 0:
            pt = pts[self._drag]
            p.setPen(QColor("white"))
            p.drawText(QRectF(pt.x() - 30, pt.y() - 26, 60, 16), Qt.AlignmentFlag.AlignCenter,
                       f"{self.values[self._drag]:+.1f} dB")
        p.end()

    def _nearest(self, pos):
        best, dist = -1, 1e9
        for i in range(len(self.values)):
            d = abs(self._point(i).x() - pos.x())
            if d < dist:
                best, dist = i, d
        return best if dist < 40 else -1

    def _set_from(self, pos):
        r = self._plot()
        db = (r.center().y() - pos.y()) / (r.height() / 2) * self.RANGE
        self.values[self._drag] = round(max(-self.RANGE, min(self.RANGE, db)), 1)
        self.changed.emit(list(self.values))
        self.update()

    def mousePressEvent(self, e):
        if not self.isEnabled():
            return
        self._drag = self._nearest(e.position())
        if self._drag >= 0:
            self._set_from(e.position())

    def mouseMoveEvent(self, e):
        if self._drag >= 0:
            self._set_from(e.position())
        else:
            h = self._nearest(e.position())
            if h != self._hover:
                self._hover = h
                self.update()

    def mouseReleaseEvent(self, e):
        if self._drag >= 0:
            self._drag = -1
            self.released.emit(list(self.values))
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()


class ZoomPreview(QAbstractButton):
    """One of the three little pictures above the zoom levels (Dense / Default / Spacious), like Spotify's."""

    def __init__(self, label, scale, parent=None):
        super().__init__(parent)
        self.label, self.scale = label, scale
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(96, 96)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        r = QRectF(2, 2, self.width() - 4, self.height() - 28)
        p.setPen(QColor(theme.GREEN if on else "#535353"))
        p.setBrush(QColor("#1f1f1f"))
        p.drawRoundedRect(r, 6, 6)
        rows = max(2, int(5 / self.scale))
        h = (r.height() - 12) / rows
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(rows):
            y = r.top() + 6 + i * h
            p.setBrush(QColor(theme.GREEN if on else "#727272"))
            p.drawRoundedRect(QRectF(r.left() + 6, y + h * 0.15, h * 0.7, h * 0.7), 2, 2)
            p.setBrush(QColor("#b3b3b3" if on else "#535353"))
            p.drawRoundedRect(QRectF(r.left() + 10 + h * 0.7, y + h * 0.3, r.width() * 0.55, h * 0.35), 2, 2)
        p.setPen(QColor(theme.TEXT if on else theme.SUBDUED))
        p.drawText(QRectF(0, self.height() - 22, self.width(), 20), Qt.AlignmentFlag.AlignCenter, self.label)
        p.end()


class HoverHint(QObject):
    """Spotify-style labels for the player bar's buttons: a small dark label just above the button, shown quickly
    (a quarter of a second) instead of Qt's slower tooltip by the mouse pointer. The text is the button's tooltip,
    so it can change (Mute / Unmute) like before. Install once per button with HoverHint.attach(button)."""
    _label = None
    _instances = []

    def __init__(self, button):
        super().__init__(button)
        from PyQt6.QtCore import QTimer
        self.button = button
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._show)
        button.installEventFilter(self)

    @classmethod
    def attach(cls, button):
        cls._instances.append(cls(button))
        return button

    @classmethod
    def _bubble(cls):
        from PyQt6.QtWidgets import QLabel
        if cls._label is None:
            lab = QLabel()
            lab.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
            lab.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            lab.setStyleSheet("QLabel { background: #282828; color: white; padding: 5px 9px; border-radius: 4px;"
                              " font-size: 13px; font-weight: 600; }")
            cls._label = lab
        return cls._label

    def _show(self):
        b = self.button
        text = b.toolTip()
        if not text or not b.isVisible() or not b.underMouse():
            return
        lab = self._bubble()
        lab.setText(text)
        lab.adjustSize()
        top = b.mapToGlobal(b.rect().topLeft())
        lab.move(top.x() + (b.width() - lab.width()) // 2, top.y() - lab.height() - 6)
        lab.show()
        lab.raise_()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        t = event.type()
        if t == QEvent.Type.ToolTip:
            return True                      # our own label instead of Qt's tooltip
        if t == QEvent.Type.Enter:
            self.timer.start()
        elif t in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.Hide):
            self.timer.stop()
            if HoverHint._label is not None:
                HoverHint._label.hide()
        return False


class PanelResizeHandle(QWidget):
    """The thin strip on a side panel's inner edge: drag it to make the panel wider or narrower (Spotify's
    right-hand panel works the same way). `done(width)` is called when the drag ends."""

    def __init__(self, panel, minimum, maximum, done=None):
        super().__init__()
        self.panel, self.minimum, self.maximum, self.done = panel, minimum, maximum, done
        self.setFixedWidth(theme.GAP)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        panel.installEventFilter(self)
        self.setToolTip("Drag to resize")
        self._start = None
        self._hover = False

    def eventFilter(self, obj, e):
        from PyQt6.QtCore import QEvent
        if obj is self.panel and e.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show,
                                              QEvent.Type.Hide, QEvent.Type.ParentChange):
            self._follow()
        return False

    def _follow(self):
        parent = self.panel.parentWidget()
        if parent is None:
            return
        if self.parentWidget() is not parent:
            self.setParent(parent)
        g = self.panel.geometry()
        self.setGeometry(g.x() - self.width(), g.y(), self.width(), g.height())
        self.setVisible(self.panel.isVisible())
        self.raise_()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        if self._hover or self._start is not None:
            p = QPainter(self)
            p.fillRect(self.width() // 2 - 1, 0, 2, self.height(), QColor("#7c7c7c"))
            p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._start = (e.globalPosition().x(), self.panel.width())

    def mouseMoveEvent(self, e):
        if self._start is None:
            return
        x0, w0 = self._start
        # The panel is on the right: dragging the edge left makes it wider.
        width = int(min(self.maximum, max(self.minimum, w0 - (e.globalPosition().x() - x0))))
        self.panel.setFixedWidth(width)

    def mouseReleaseEvent(self, e):
        if self._start is not None:
            self._start = None
            self.update()
            if self.done:
                self.done(self.panel.width())

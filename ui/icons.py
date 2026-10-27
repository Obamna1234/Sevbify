"""Small vector icons drawn with QPainter.

Drawing them (instead of using emoji/font glyphs) means they look the same on
Windows, macOS and Linux and can be recoloured, e.g. green when active.
"""
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QPainterPath, QFont, QPolygonF

WHITE = "#ffffff"
GREY = "#b3b3b3"
GREEN = "#1db954"


def _canvas(size):
    pm = QPixmap(size * 2, size * 2)          # 2x for crisp high-DPI rendering
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(2.0)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pm, p


def _pen(color, width):
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _arrow_head(p, tip: QPointF, direction: str, size: float, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    if direction == "right":
        pts = [tip, QPointF(tip.x() - size, tip.y() - size * 0.8), QPointF(tip.x() - size, tip.y() + size * 0.8)]
    else:
        pts = [tip, QPointF(tip.x() + size, tip.y() - size * 0.8), QPointF(tip.x() + size, tip.y() + size * 0.8)]
    p.drawPolygon(QPolygonF(pts))


def shuffle(color=GREY, size=20, dot=False):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.09))
    path = QPainterPath()
    path.moveTo(s * 0.12, s * 0.28)
    path.cubicTo(s * 0.45, s * 0.28, s * 0.45, s * 0.68, s * 0.80, s * 0.68)
    p.drawPath(path)
    path2 = QPainterPath()
    path2.moveTo(s * 0.12, s * 0.68)
    path2.cubicTo(s * 0.45, s * 0.68, s * 0.45, s * 0.28, s * 0.80, s * 0.28)
    p.drawPath(path2)
    _arrow_head(p, QPointF(s * 0.92, s * 0.28), "right", s * 0.14, color)
    _arrow_head(p, QPointF(s * 0.92, s * 0.68), "right", s * 0.14, color)
    if dot:
        p.setBrush(QColor(color)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.95), s * 0.05, s * 0.05)
    p.end()
    return QIcon(pm)


def repeat(color=GREY, size=20, one=False, dot=False):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.09))
    p.setBrush(Qt.BrushStyle.NoBrush)
    rect = QRectF(s * 0.12, s * 0.25, s * 0.76, s * 0.46)
    path = QPainterPath()
    path.moveTo(s * 0.55, rect.top())
    path.lineTo(rect.right() - s * 0.12, rect.top())
    path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + s * 0.12)
    path.lineTo(rect.right(), rect.bottom() - s * 0.12)
    path.quadTo(rect.right(), rect.bottom(), rect.right() - s * 0.12, rect.bottom())
    path.lineTo(rect.left() + s * 0.12, rect.bottom())
    path.quadTo(rect.left(), rect.bottom(), rect.left(), rect.bottom() - s * 0.12)
    path.lineTo(rect.left(), rect.top() + s * 0.12)
    path.quadTo(rect.left(), rect.top(), rect.left() + s * 0.12, rect.top())
    path.lineTo(s * 0.33, rect.top())
    p.drawPath(path)
    _arrow_head(p, QPointF(s * 0.47, rect.top()), "right", s * 0.13, color)
    if one:
        p.setPen(QColor(color))
        f = QFont(); f.setPixelSize(int(s * 0.42)); f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(s * 0.12, s * 0.25, s * 0.76, s * 0.46), Qt.AlignmentFlag.AlignCenter, "1")
    if dot:
        p.setBrush(QColor(color)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.95), s * 0.05, s * 0.05)
    p.end()
    return QIcon(pm)


def queue(color=GREY, size=20, dot=False):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.08))
    for y in (0.25, 0.45):
        p.drawLine(QPointF(s * 0.12, s * y), QPointF(s * 0.88, s * y))
    p.drawLine(QPointF(s * 0.12, s * 0.65), QPointF(s * 0.50, s * 0.65))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([QPointF(s * 0.62, s * 0.55), QPointF(s * 0.62, s * 0.77), QPointF(s * 0.86, s * 0.66)]))
    if dot:
        p.drawEllipse(QPointF(s * 0.5, s * 0.95), s * 0.05, s * 0.05)
    p.end()
    return QIcon(pm)


def now_playing(color=GREY, size=20, dot=False):
    """A rectangle with a smaller filled rectangle inside (Spotify's 'Now playing view')."""
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.18, s * 0.76, s * 0.60), s * 0.08, s * 0.08)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(s * 0.50, s * 0.30, s * 0.26, s * 0.36), s * 0.04, s * 0.04)
    if dot:
        p.drawEllipse(QPointF(s * 0.5, s * 0.95), s * 0.05, s * 0.05)
    p.end()
    return QIcon(pm)


def radio(color=GREY, size=20):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    c = QPointF(s * 0.5, s * 0.5)
    p.setBrush(QColor(color)); p.drawEllipse(c, s * 0.07, s * 0.07); p.setBrush(Qt.BrushStyle.NoBrush)
    for r, span in ((0.22, 100), (0.38, 100)):
        rect = QRectF(c.x() - s * r, c.y() - s * r, 2 * s * r, 2 * s * r)
        p.drawArc(rect, int((180 - span / 2 + 90) * 16) - 90 * 16, int(span * 16))   # left arc
        p.drawArc(rect, int(-span / 2 * 16), int(span * 16))                          # right arc
    p.end()
    return QIcon(pm)


def download(color=GREY, size=20):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.40, s * 0.40)
    p.drawLine(QPointF(s * 0.5, s * 0.28), QPointF(s * 0.5, s * 0.66))
    p.drawLine(QPointF(s * 0.34, s * 0.52), QPointF(s * 0.5, s * 0.68))
    p.drawLine(QPointF(s * 0.66, s * 0.52), QPointF(s * 0.5, s * 0.68))
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------------------
# Navigation / player icons (Spotify-style shapes, drawn so they recolour)
# ---------------------------------------------------------------------------
def home(color=WHITE, size=24, filled=False):
    pm, p = _canvas(size)
    s = size
    path = QPainterPath()
    path.moveTo(s * 0.5, s * 0.12)
    path.lineTo(s * 0.88, s * 0.42)
    path.lineTo(s * 0.88, s * 0.88)
    path.lineTo(s * 0.60, s * 0.88)
    path.lineTo(s * 0.60, s * 0.62)
    path.lineTo(s * 0.40, s * 0.62)
    path.lineTo(s * 0.40, s * 0.88)
    path.lineTo(s * 0.12, s * 0.88)
    path.lineTo(s * 0.12, s * 0.42)
    path.closeSubpath()
    if filled:
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    else:
        p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def search(color=GREY, size=24):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.09)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(s * 0.43, s * 0.43), s * 0.27, s * 0.27)
    p.drawLine(QPointF(s * 0.63, s * 0.63), QPointF(s * 0.86, s * 0.86))
    p.end()
    return QIcon(pm)


def chevron(direction="left", color=WHITE, size=24):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.1))
    if direction == "left":
        pts = [QPointF(s * 0.6, s * 0.25), QPointF(s * 0.36, s * 0.5), QPointF(s * 0.6, s * 0.75)]
    else:
        pts = [QPointF(s * 0.4, s * 0.25), QPointF(s * 0.64, s * 0.5), QPointF(s * 0.4, s * 0.75)]
    p.drawPolyline(QPolygonF(pts))
    p.end()
    return QIcon(pm)


def play(color="#000000", size=16):
    pm, p = _canvas(size)
    s = size
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([QPointF(s * 0.22, s * 0.10), QPointF(s * 0.22, s * 0.90), QPointF(s * 0.92, s * 0.50)]))
    p.end()
    return QIcon(pm)


def pause(color="#000000", size=16):
    pm, p = _canvas(size)
    s = size
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(s * 0.18, s * 0.08, s * 0.22, s * 0.84), s * 0.04, s * 0.04)
    p.drawRoundedRect(QRectF(s * 0.60, s * 0.08, s * 0.22, s * 0.84), s * 0.04, s * 0.04)
    p.end()
    return QIcon(pm)


def skip(direction="next", color=GREY, size=18):
    pm, p = _canvas(size)
    s = size
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    if direction == "next":
        p.drawPolygon(QPolygonF([QPointF(s * 0.15, s * 0.12), QPointF(s * 0.15, s * 0.88), QPointF(s * 0.72, s * 0.5)]))
        p.drawRoundedRect(QRectF(s * 0.74, s * 0.12, s * 0.12, s * 0.76), s * 0.03, s * 0.03)
    else:
        p.drawPolygon(QPolygonF([QPointF(s * 0.85, s * 0.12), QPointF(s * 0.85, s * 0.88), QPointF(s * 0.28, s * 0.5)]))
        p.drawRoundedRect(QRectF(s * 0.14, s * 0.12, s * 0.12, s * 0.76), s * 0.03, s * 0.03)
    p.end()
    return QIcon(pm)


def volume(level=2, color=GREY, size=18):
    """level 0 = muted, 1 = low, 2 = high."""
    pm, p = _canvas(size)
    s = size
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([QPointF(s * 0.10, s * 0.38), QPointF(s * 0.28, s * 0.38), QPointF(s * 0.50, s * 0.16),
                             QPointF(s * 0.50, s * 0.84), QPointF(s * 0.28, s * 0.62), QPointF(s * 0.10, s * 0.62)]))
    p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    if level == 0:
        p.drawLine(QPointF(s * 0.64, s * 0.38), QPointF(s * 0.88, s * 0.62))
        p.drawLine(QPointF(s * 0.88, s * 0.38), QPointF(s * 0.64, s * 0.62))
    else:
        p.drawArc(QRectF(s * 0.40, s * 0.30, s * 0.30, s * 0.40), -60 * 16, 120 * 16)
        if level >= 2:
            p.drawArc(QRectF(s * 0.36, s * 0.14, s * 0.52, s * 0.72), -60 * 16, 120 * 16)
    p.end()
    return QIcon(pm)


def plus(color=GREY, size=18):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.1))
    p.drawLine(QPointF(s * 0.5, s * 0.18), QPointF(s * 0.5, s * 0.82))
    p.drawLine(QPointF(s * 0.18, s * 0.5), QPointF(s * 0.82, s * 0.5))
    p.end()
    return QIcon(pm)


def library(color=GREY, size=24):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(s * 0.18, s * 0.15), QPointF(s * 0.18, s * 0.85))
    p.drawLine(QPointF(s * 0.38, s * 0.15), QPointF(s * 0.38, s * 0.85))
    p.drawLine(QPointF(s * 0.58, s * 0.18), QPointF(s * 0.84, s * 0.84))
    p.end()
    return QIcon(pm)


def gear(color=GREY, size=20):
    import math
    pm, p = _canvas(size)
    s = size
    c = QPointF(s / 2, s / 2)
    p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, s * 0.14, s * 0.14)
    path = QPainterPath()
    teeth = 8
    for i in range(teeth * 2):
        r = s * (0.40 if i % 2 == 0 else 0.30)
        a = math.pi * i / teeth
        pt = QPointF(c.x() + r * math.cos(a), c.y() + r * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def clock(color=GREY, size=16):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(s / 2, s / 2), s * 0.38, s * 0.38)
    p.drawLine(QPointF(s / 2, s / 2), QPointF(s / 2, s * 0.28))
    p.drawLine(QPointF(s / 2, s / 2), QPointF(s * 0.66, s * 0.6))
    p.end()
    return QIcon(pm)


def expand(color=GREY, size=18, out=True):
    """Two diagonal arrows: pointing out (expand) or in (shrink back)."""
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.09))
    if out:
        p.drawLine(QPointF(s * 0.58, s * 0.42), QPointF(s * 0.84, s * 0.16))
        p.drawPolyline(QPolygonF([QPointF(s * 0.58, s * 0.16), QPointF(s * 0.84, s * 0.16), QPointF(s * 0.84, s * 0.42)]))
        p.drawLine(QPointF(s * 0.42, s * 0.58), QPointF(s * 0.16, s * 0.84))
        p.drawPolyline(QPolygonF([QPointF(s * 0.16, s * 0.58), QPointF(s * 0.16, s * 0.84), QPointF(s * 0.42, s * 0.84)]))
    else:
        p.drawLine(QPointF(s * 0.84, s * 0.16), QPointF(s * 0.58, s * 0.42))
        p.drawPolyline(QPolygonF([QPointF(s * 0.58, s * 0.18), QPointF(s * 0.58, s * 0.42), QPointF(s * 0.82, s * 0.42)]))
        p.drawLine(QPointF(s * 0.16, s * 0.84), QPointF(s * 0.42, s * 0.58))
        p.drawPolyline(QPolygonF([QPointF(s * 0.18, s * 0.58), QPointF(s * 0.42, s * 0.58), QPointF(s * 0.42, s * 0.82)]))
    p.end()
    return QIcon(pm)


def sort_lines(color=GREY, size=16):
    """Three lines getting shorter (the Recents / sort button)."""
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.1))
    for i, w in enumerate((0.8, 0.6, 0.4)):
        y = s * (0.28 + i * 0.22)
        p.drawLine(QPointF(s * 0.12, y), QPointF(s * (0.12 + w), y))
    p.end()
    return QIcon(pm)


def grid(color=GREY, size=16):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.08)); p.setBrush(Qt.BrushStyle.NoBrush)
    for x in (0.14, 0.56):
        for y in (0.14, 0.56):
            p.drawRoundedRect(QRectF(s * x, s * y, s * 0.3, s * 0.3), s * 0.04, s * 0.04)
    p.end()
    return QIcon(pm)


def folder(color=GREY, size=24):
    pm, p = _canvas(size)
    s = size
    p.setPen(_pen(color, s * 0.07)); p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(s * 0.12, s * 0.28)
    path.lineTo(s * 0.40, s * 0.28)
    path.lineTo(s * 0.48, s * 0.36)
    path.lineTo(s * 0.88, s * 0.36)
    path.lineTo(s * 0.88, s * 0.78)
    path.lineTo(s * 0.12, s * 0.78)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)

"""Playlist ••• → Sort by energy…: three big cards (Energetic → Easing down → Calm, Calm → Ramping up → Energetic,
Mixed energies throughout), each with a line showing how the energy moves from the first song to the last.
Sevbify then makes a new playlist "<name> · <order>"; the original isn't touched, and songs in the new one can be
dragged around or removed like in any playlist. The ordering itself is core/flow_order.py (the same on the phones).
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QWidget
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath

from . import theme

INTRO = ("Sorting by energy makes a copy of this playlist, with the songs arranged in the energy flow you choose. "
         "Your original playlist stays exactly as it is.")

CARDS = [
    ("wind_down", "Energetic → Easing down → Calm", "The most energetic songs first, settling down to the calmest."),
    ("build", "Calm → Ramping up → Energetic", "Starts with the calmest songs and builds up to the most energetic."),
    ("mix", "Mixed energies throughout", "Calm, in-between and energetic songs spread all the way through."),
]

# The shape of each card's line (x, y from 0 to 1, y = 0 at the top: energetic).
SHAPES = {
    "wind_down": [(0, .12), (.25, .16), (.45, .38), (.7, .62), (1, .8)],
    "build": [(0, .8), (.25, .76), (.45, .55), (.7, .3), (1, .12)],
    "mix": [(0, .5), (.09, .2), (.18, .7), (.27, .3), (.36, .82), (.45, .15), (.55, .6), (.64, .25), (.73, .78),
            (.82, .2), (.91, .66), (1, .4)],
}


class EnergyLine(QWidget):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.on = False
        self.setFixedHeight(56)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#1ed760" if self.on else "#ffffff"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        w, h = self.width() - 8, self.height() - 8
        pts = [QPointF(4 + x * w, 4 + y * h) for x, y in SHAPES[self.mode]]
        path = QPainterPath(pts[0])
        if self.mode == "mix":
            for q in pts[1:]:
                path.lineTo(q)
        else:
            for a, b in zip(pts, pts[1:]):                       # gentle curve through the points
                mid = (a.x() + b.x()) / 2
                path.cubicTo(QPointF(mid, a.y()), QPointF(mid, b.y()), b)
        p.drawPath(path)


class Card(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, mode, title, text):
        super().__init__()
        self.mode = mode
        self.setObjectName("energyCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(2)
        top = QHBoxLayout()
        self.line = EnergyLine(mode)
        top.addWidget(self.line, 1)
        self.tick = QLabel("✓")
        self.tick.setFixedSize(22, 22)
        self.tick.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tick.setStyleSheet("background: #1ed760; color: #000000; border-radius: 11px; font-weight: 900;")
        top.addWidget(self.tick, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        ends = QHBoxLayout()
        for word in ("Start", "End"):
            lbl = QLabel(word)
            lbl.setStyleSheet("color: #888888; font-size: 10px;")
            ends.addWidget(lbl)
            if word == "Start":
                ends.addStretch(1)
        lay.addLayout(ends)
        name = QLabel(title)
        name.setStyleSheet("font-size: 17px; font-weight: 800; margin-top: 6px;")
        lay.addWidget(name)
        why = QLabel(text)
        why.setWordWrap(True)
        why.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
        lay.addWidget(why)
        self.set_on(False)

    def set_on(self, on):
        self.line.on = on
        self.line.update()
        self.tick.setVisible(on)
        self.setStyleSheet("#energyCard { border-radius: 12px; border: 2px solid %s; background: %s; }"
                           " QLabel { background: transparent; color: #ffffff; }" %
                           (("#1ed760", "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1f3a29, stop:1 #232323)")
                            if on else ("transparent", "#2a2a2a")))
        self.tick.setStyleSheet("background: #1ed760; color: #000000; border-radius: 11px; font-weight: 900;")

    def mousePressEvent(self, e):
        self.clicked.emit(self.mode)


class FlowDialog(QDialog):
    """Sort by energy. choice() → (mode, artists_apart, start) when accepted."""

    def __init__(self, parent, playlist_name, count):
        super().__init__(parent)
        self.setWindowTitle("Sort by energy")
        self.setStyleSheet("QDialog { background: #212121; } QLabel { color: #ffffff; background: transparent; }")
        self.setFixedWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        title = QLabel("Sort by energy")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        lay.addWidget(title)
        sub = QLabel(f"{playlist_name} · {count} songs")
        sub.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
        lay.addWidget(sub)
        intro = QLabel(INTRO)
        intro.setWordWrap(True)
        intro.setFixedWidth(416)
        intro.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
        intro.ensurePolished()
        intro.setMinimumHeight(intro.heightForWidth(416))
        lay.addWidget(intro)
        self.cards = []
        for mode, name, text in CARDS:
            c = Card(mode, name, text)
            c.clicked.connect(self.pick)
            self.cards.append(c)
            lay.addWidget(c)
        self.mode = "wind_down"
        self.pick(self.mode)

        self.go = QPushButton("Create sorted playlist")
        self.go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go.setFixedHeight(48)
        self.go.setStyleSheet("QPushButton { background: #1ed760; color: #000000; font-weight: 800; font-size: 15px;"
                              " border: none; border-radius: 24px; } QPushButton:hover { background: #3be477; }")
        self.go.clicked.connect(self.accept)
        lay.addSpacing(4)
        lay.addWidget(self.go)
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet("QPushButton { color: #ffffff; background: transparent; border: none; font-weight: 700;"
                             " font-size: 14px; padding: 6px; } QPushButton:hover { color: #1ed760; }")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel, 0, Qt.AlignmentFlag.AlignHCenter)

    def pick(self, mode):
        self.mode = mode
        for c in self.cards:
            c.set_on(c.mode == mode)

    def choice(self):
        return self.mode, True, "calm"

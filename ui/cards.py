"""Home page building blocks (Spotify style): cards and quick-play tiles."""
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from . import icons, theme
from .library_panel import rounded


def green_play_button(size=48):
    b = QPushButton()
    b.setIcon(icons.play("#000000", int(size * 0.4)))
    b.setIconSize(QSize(int(size * 0.4), int(size * 0.4)))
    b.setFixedSize(size, size)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setToolTip("Play")
    b.setStyleSheet(f"QPushButton {{ background: {theme.GREEN}; border: none; border-radius: {size // 2}px; }}"
                    f" QPushButton:hover {{ background: #3be477; }}")
    return b


class Card(QFrame):
    """Square artwork with title and subtitle; green play button on hover."""
    clicked = pyqtSignal()
    play_clicked = pyqtSignal()
    context_requested = pyqtSignal(object)

    def __init__(self, pixmap, title, subtitle, art=160, round_art=False):
        super().__init__()
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(art + 24)
        self._style(False)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 16)
        v.setSpacing(4)
        self.art_holder = QWidget()
        self.art_holder.setFixedSize(art, art)
        self.art = QLabel(self.art_holder)
        self.art.setGeometry(0, 0, art, art)
        self.art.setPixmap(rounded(pixmap, art, art // 2 if round_art else 6))
        self.play = green_play_button(48)
        self.play.setParent(self.art_holder)
        self.play.move(art - 56, art - 56)
        self.play.hide()
        self.play.clicked.connect(self.play_clicked.emit)
        v.addWidget(self.art_holder)
        v.addSpacing(6)
        t = QLabel()
        t.setStyleSheet(f"color: {theme.TEXT}; font-size: 15px; font-weight: 600; background: transparent;")
        s = QLabel()
        s.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px; background: transparent;")
        for lbl, text in ((t, title), (s, subtitle)):
            lbl.setText(lbl.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, art))
            lbl.setToolTip(text)
        v.addWidget(t)
        v.addWidget(s)
        self.title_label = t

    def _style(self, hover):
        self.setStyleSheet(f"#card {{ background: {theme.ELEVATED if hover else 'transparent'}; border-radius: 8px; }}")

    def enterEvent(self, e):
        self._style(True); self.play.show(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._style(False); self.play.hide(); super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self.play.underMouse():
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def contextMenuEvent(self, e):
        self.context_requested.emit(e.globalPos())


class QuickTile(QFrame):
    """Wide tile at the top of Home: artwork on the left, name, play on hover."""
    clicked = pyqtSignal()
    play_clicked = pyqtSignal()

    def __init__(self, pixmap, title, playing=False):
        super().__init__()
        self.setObjectName("quick")
        self.setFixedHeight(64)
        self.setMinimumWidth(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style(False)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 8, 0)
        h.setSpacing(12)
        art = QLabel()
        art.setFixedSize(64, 64)
        art.setPixmap(rounded(pixmap, 64, 4))
        h.addWidget(art)
        t = QLabel(title)
        t.setStyleSheet(f"color: {theme.GREEN if playing else theme.TEXT}; font-size: 15px; font-weight: 700; background: transparent;")
        t.setMinimumWidth(0)
        t.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        t.setToolTip(title)
        h.addWidget(t, 1)
        self.play = green_play_button(40)
        self.play.clicked.connect(self.play_clicked.emit)
        sp = self.play.sizePolicy(); sp.setRetainSizeWhenHidden(True); self.play.setSizePolicy(sp)
        self.play.hide()
        h.addWidget(self.play)

    def _style(self, hover):
        bg = "rgba(255,255,255,0.18)" if hover else "rgba(255,255,255,0.08)"
        self.setStyleSheet(f"#quick {{ background: {bg}; border-radius: 4px; }}")

    def enterEvent(self, e):
        self._style(True); self.play.show(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._style(False); self.play.hide(); super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self.play.underMouse():
            self.clicked.emit()
        super().mouseReleaseEvent(e)

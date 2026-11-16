"""The small "Preview" card: a song's 30-second clip, only when you pick Preview from its menu.

Looks like Spotify's own cards: dark rounded card, the cover, title and artist, a round white play button and
the thin progress bar of Spotify's player (white, green while you hover or drag it).

Everything else (playlists, imports, search results, radio) plays the full song; a clip is never used in their place.
The clip plays on its own VLC player, so the main player is only paused, never replaced.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, QTimer, QSize

from . import icons, theme
from .click_slider import ClickSlider


def _clock(ms):
    s = max(0, int(ms or 0)) // 1000
    return f"{s // 60}:{s % 60:02d}"


SLIDER = ("QSlider::groove:horizontal { background: #4d4d4d; height: 4px; border-radius: 2px; }"
          "QSlider::sub-page:horizontal { background: #ffffff; border-radius: 2px; }"
          "QSlider::sub-page:horizontal:hover { background: #1ed760; }"
          "QSlider::handle:horizontal { background: transparent; width: 12px; height: 12px; margin: -4px 0;"
          " border-radius: 6px; }"
          "QSlider::handle:horizontal:hover { background: #ffffff; }")


class PreviewDialog(QDialog):
    def __init__(self, parent, vlc_instance, url, title, artist, cover=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Preview")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(400)
        self.player = vlc_instance.media_player_new()
        self.player.set_media(vlc_instance.media_new(url))
        self._dragging = False
        self._drag_from = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("previewCard")
        card.setStyleSheet("#previewCard { background: #282828; border-radius: 8px; }"
                           " QLabel { color: #ffffff; background: transparent; }")
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 12, 16)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(12)
        art = QLabel()
        art.setFixedSize(56, 56)
        if cover is not None and not cover.isNull():
            from .library_panel import rounded
            art.setPixmap(rounded(cover, 56, 4))
        else:
            art.setStyleSheet("background: #3e3e3e; border-radius: 4px;")
        top.addWidget(art)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        name = QLabel(title or "Unknown song")
        name.setStyleSheet("font-size: 16px; font-weight: 700;")
        name.setWordWrap(True)
        who = QLabel((f"{artist}  ·  " if artist else "") + "Preview")
        who.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
        texts.addWidget(name)
        texts.addWidget(who)
        top.addLayout(texts, 1)
        close = QPushButton()
        close.setIcon(icons.close(theme.SUBDUED, 16))
        close.setFixedSize(32, 32)
        close.setToolTip("Close")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet("QPushButton { border: none; background: transparent; border-radius: 16px; }"
                            " QPushButton:hover { background: #3e3e3e; }")
        close.clicked.connect(self.close)
        top.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.button = QPushButton()
        self.button.setFixedSize(40, 40)
        self.button.setIconSize(QSize(16, 16))
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setStyleSheet("QPushButton { background: #ffffff; border: none; border-radius: 20px; }"
                                  " QPushButton:hover { background: #f0f0f0; }")
        self.button.clicked.connect(self.toggle)
        self.slider = ClickSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 30000)
        self.slider.setStyleSheet(SLIDER)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.slider.sliderReleased.connect(self._seek)
        self.time = QLabel("0:00 / 0:30")
        self.time.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px;")
        row.addWidget(self.button)
        row.addWidget(self.slider, 1)
        row.addWidget(self.time)
        lay.addLayout(row)

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.player.play()
        self._tick()
        if parent is not None:                    # centred over Sevbify, like Spotify's cards
            g = parent.geometry()
            self.adjustSize()
            self.move(g.center().x() - self.width() // 2, g.center().y() - self.height() // 2)

    # The card has no title bar: drag it by its background.
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_from = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_from is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, e):
        self._drag_from = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        elif e.key() == Qt.Key.Key_Space:
            self.toggle()
        else:
            super().keyPressEvent(e)

    def toggle(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            if self.player.get_state() is not None and str(self.player.get_state()).endswith("Ended"):
                self.player.stop()
            self.player.play()

    def _seek(self):
        self._dragging = False
        if not self.player.is_playing():
            self.player.play()
        self.player.set_time(int(self.slider.value()))

    def _tick(self):
        length = self.player.get_length()
        if length and length > 0 and self.slider.maximum() != length:
            self.slider.setRange(0, int(length))
        pos = max(0, self.player.get_time())
        if not self._dragging:
            self.slider.setValue(int(pos))
        self.time.setText(f"{_clock(pos)} / {_clock(self.slider.maximum())}")
        playing = self.player.is_playing()
        self.button.setIcon(icons.pause("#000000", 16) if playing else icons.play("#000000", 16))
        self.button.setToolTip("Pause" if playing else "Play")

    def closeEvent(self, e):
        self.timer.stop()
        try:
            self.player.stop()
            self.player.release()
        except Exception:
            pass
        super().closeEvent(e)

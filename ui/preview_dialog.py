"""The small "Preview" window: a song's 30-second clip with a seek bar, only when you pick Preview from its menu.

Everything else (playlists, imports, search results, radio) plays the full song; a clip is never used in their place.
The clip plays on its own VLC player, so the main player is only paused, never replaced.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider
from PyQt6.QtCore import Qt, QTimer

from . import theme


def _clock(ms):
    s = max(0, int(ms or 0)) // 1000
    return f"{s // 60}:{s % 60:02d}"


class PreviewDialog(QDialog):
    def __init__(self, parent, vlc_instance, url, title, artist):
        super().__init__(parent)
        self.setWindowTitle("Preview")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedWidth(360)
        self.setStyleSheet(f"QDialog {{ background: #282828; }} QLabel {{ color: #ffffff; background: transparent; }}"
                           f" QPushButton {{ background: {theme.GREEN}; color: #000; border: none; border-radius: 18px;"
                           f" font-weight: bold; min-width: 36px; min-height: 36px; }}")
        self.player = vlc_instance.media_player_new()
        self.player.set_media(vlc_instance.media_new(url))
        self._dragging = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        name = QLabel(title or "Unknown song")
        name.setStyleSheet("font-size: 15px; font-weight: bold;")
        name.setWordWrap(True)
        who = QLabel(f"{artist} · 30-second preview" if artist else "30-second preview")
        who.setStyleSheet("color: #b3b3b3;")
        lay.addWidget(name)
        lay.addWidget(who)

        row = QHBoxLayout()
        self.button = QPushButton("❚❚")
        self.button.clicked.connect(self.toggle)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 30000)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.slider.sliderReleased.connect(self._seek)
        self.time = QLabel("0:00 / 0:30")
        self.time.setStyleSheet("color: #b3b3b3;")
        row.addWidget(self.button)
        row.addWidget(self.slider, 1)
        row.addWidget(self.time)
        lay.addLayout(row)

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.player.play()

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
        self.button.setText("❚❚" if self.player.is_playing() else "▶")

    def closeEvent(self, e):
        self.timer.stop()
        try:
            self.player.stop()
            self.player.release()
        except Exception:
            pass
        super().closeEvent(e)

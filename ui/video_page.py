"""Watching a video podcast episode (YouTube) inside Sevbify, with sound, using Qt's video player.
Music playback (VLC) is paused while a video plays; "Listen as audio only" hands the episode back to the normal
player at the same point."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QSize, QUrl, pyqtSignal

from . import icons, theme
from .click_slider import ClickSlider

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAVE_VIDEO = True
except Exception:  # pragma: no cover - multimedia missing on some Linux installs
    HAVE_VIDEO = False


def _fmt(ms):
    s = max(0, int(ms)) // 1000
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class VideoPage(QWidget):
    audio_only_requested = pyqtSignal(int)        # position in ms
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)
        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setStyleSheet(f"color: {theme.TEXT}; font-size: 22px; font-weight: 800; background: transparent;")
        v.addWidget(self.title)
        self.player = self.audio = None
        if HAVE_VIDEO:
            self.video = QVideoWidget()
            self.video.setStyleSheet("background: black;")
            v.addWidget(self.video, 1)
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            self.player.positionChanged.connect(self._position)
            self.player.durationChanged.connect(lambda d: self.seek.setRange(0, max(0, d)))
            self.player.playbackStateChanged.connect(lambda _s: self._update_play_icon())
            self.player.errorOccurred.connect(lambda *_: self.error.emit(self.player.errorString()))
        else:
            v.addWidget(QLabel("Video playback isn't available on this computer."), 1)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setIconSize(QSize(16, 16))
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("QPushButton { background: white; border: none; border-radius: 20px; }")
        self.play_btn.clicked.connect(self.toggle)
        row.addWidget(self.play_btn)
        self.time = QLabel("0:00")
        self.time.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px;")
        row.addWidget(self.time)
        self.seek = ClickSlider(Qt.Orientation.Horizontal)
        self.seek.sliderReleased.connect(lambda: self.player and self.player.setPosition(self.seek.value()))
        row.addWidget(self.seek, 1)
        self.length = QLabel("0:00")
        self.length.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px;")
        row.addWidget(self.length)
        audio_only = QPushButton("Listen as audio only")
        audio_only.setStyleSheet(theme.PILL)
        audio_only.setFixedHeight(32)
        audio_only.setCursor(Qt.CursorShape.PointingHandCursor)
        audio_only.clicked.connect(self._audio_only)
        row.addWidget(audio_only)
        v.addLayout(row)
        self._update_play_icon()

    def play(self, url, title, start_ms=0, volume=80):
        self.title.setText(title)
        if self.player is None:
            return False
        self.audio.setVolume(max(0.0, min(1.0, volume / 100)))
        self.player.setSource(QUrl(url))
        if start_ms:
            self.player.setPosition(int(start_ms))
        self.player.play()
        return True

    def stop(self):
        if self.player is not None:
            self.player.stop()
            self.player.setSource(QUrl())

    def toggle(self):
        if self.player is None:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def position(self):
        return self.player.position() if self.player is not None else 0

    def _position(self, ms):
        if not self.seek.isSliderDown():
            self.seek.setValue(ms)
        self.time.setText(_fmt(ms))
        self.length.setText(_fmt(self.player.duration()))

    def _update_play_icon(self):
        playing = self.player is not None and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setIcon(icons.pause("#000000", 16) if playing else icons.play("#000000", 16))

    def _audio_only(self):
        pos = self.position()
        self.stop()
        self.audio_only_requested.emit(pos)

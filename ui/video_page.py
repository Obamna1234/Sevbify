"""Watching a video podcast episode (YouTube) inside Sevbify, with sound, using Qt's video player.
Music playback (VLC) is paused while a video plays; "Listen as audio only" hands the episode back to the normal
player at the same point."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
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


class VideoMiniPlayer(QWidget):
    """The video in a small window that stays on top of other windows (like YouTube's mini player), so you can
    keep watching while using Sevbify or other programs."""
    expand_requested = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, page):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.page = page
        self.setWindowTitle("Sevbify")
        self.setStyleSheet(f"background: {theme.BLACK}; color: {theme.TEXT};")
        self.resize(480, 310)
        self.setMinimumSize(280, 190)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 6)
        v.setSpacing(6)
        self.video = QVideoWidget()
        self.video.setStyleSheet("background: black;")
        v.addWidget(self.video, 1)
        row = QHBoxLayout()
        row.setContentsMargins(8, 0, 8, 0)
        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setIconSize(QSize(14, 14))
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("QPushButton { background: white; border: none; border-radius: 16px; }")
        self.play_btn.clicked.connect(page.toggle)
        row.addWidget(self.play_btn)
        self.title = QLabel("")
        self.title.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px;")
        row.addWidget(self.title, 1)
        back = QPushButton("Back to Sevbify")
        back.setStyleSheet(theme.PILL)
        back.setFixedHeight(28)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self.expand_requested.emit)
        row.addWidget(back)
        v.addLayout(row)

    def update_play_icon(self, playing):
        self.play_btn.setIcon(icons.pause("#000000", 14) if playing else icons.play("#000000", 14))

    def closeEvent(self, e):
        super().closeEvent(e)
        self.closed.emit()


class VideoOverlay(QFrame):
    """The video floating inside Sevbify while you browse (like the phone app and YouTube): bottom-right of the
    page area, drag it anywhere, drag its corner to resize. Hovering shows play/pause, expand (back to the full
    video) and close (keep listening as audio); a thin line along the bottom shows how far you are."""
    expand_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, page, host):
        super().__init__(host)
        self.page, self.host = page, host
        self.setObjectName("videoOverlay")
        self.setStyleSheet("#videoOverlay { background: black; border-radius: 8px; border: 1px solid #2a2a2a; }")
        self.setMouseTracking(True)
        self.resize(400, 225)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.video = QVideoWidget(self)
        self.video.setStyleSheet("background: black;")
        self.video.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        v.addWidget(self.video)
        self.controls = QWidget(self)
        cl = QHBoxLayout(self.controls)
        cl.setContentsMargins(8, 8, 8, 8)
        btn_style = ("QPushButton { background: rgba(0,0,0,0.6); border: none; border-radius: 16px; }"
                     " QPushButton:hover { background: rgba(40,40,40,0.9); }")

        def button(icon, tip, slot):
            b = QPushButton(self.controls)
            b.setIcon(icon)
            b.setIconSize(QSize(14, 14))
            b.setFixedSize(32, 32)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(btn_style)
            b.clicked.connect(slot)
            return b
        self.play_btn = button(icons.pause("#ffffff", 14), "Pause", page.toggle)
        cl.addWidget(self.play_btn)
        cl.addStretch()
        cl.addWidget(button(icons.expand("#ffffff", 14), "Back to the video", self.expand_requested.emit))
        cl.addWidget(button(icons.close("#ffffff", 14), "Close video (keep listening)", self.close_requested.emit))
        self.controls.hide()
        self.progress = QFrame(self)
        self.progress.setStyleSheet("background: #ffffff;")
        self.grip = QFrame(self)
        self.grip.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.grip.setStyleSheet("background: transparent;")
        self._drag = None
        self._resize_from = None

    def place(self):
        """Bottom-right of the page area (unless it was moved)."""
        if getattr(self, "_moved", False):
            return
        h = self.host
        self.move(max(0, h.width() - self.width() - 16), max(0, h.height() - self.height() - 16))

    def resizeEvent(self, e):
        self.controls.setGeometry(0, 0, self.width(), 48)
        self.grip.setGeometry(self.width() - 16, self.height() - 16, 16, 16)
        self.set_progress(getattr(self, "_fraction", 0.0))
        super().resizeEvent(e)

    def set_progress(self, fraction):
        self._fraction = max(0.0, min(1.0, fraction))
        self.progress.setGeometry(0, self.height() - 3, int(self.width() * self._fraction), 3)

    def update_play_icon(self, playing):
        self.play_btn.setIcon(icons.pause("#ffffff", 14) if playing else icons.play("#ffffff", 14))
        self.play_btn.setToolTip("Pause" if playing else "Play")

    def enterEvent(self, e):
        self.controls.show()
        self.controls.raise_()

    def leaveEvent(self, e):
        self.controls.hide()

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self.grip.geometry().contains(e.position().toPoint()):
            self._resize_from = (e.globalPosition().toPoint(), self.size())
        else:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._resize_from is not None:
            start, size = self._resize_from
            d = e.globalPosition().toPoint() - start
            w = max(240, min(self.host.width() - 16, size.width() + d.x()))
            self.resize(w, int(w * 9 / 16))
            self._moved = True
        elif self._drag is not None:
            p = e.globalPosition().toPoint() - self._drag
            p.setX(max(0, min(self.host.width() - self.width(), p.x())))
            p.setY(max(0, min(self.host.height() - self.height(), p.y())))
            self.move(p)
            self._moved = True

    def mouseReleaseEvent(self, e):
        self._drag = self._resize_from = None

    def mouseDoubleClickEvent(self, e):
        self.expand_requested.emit()


class VideoPage(QWidget):
    audio_only_requested = pyqtSignal(int)        # position in ms
    error = pyqtSignal(str)
    show_requested = pyqtSignal()                 # the mini player's "Back to Sevbify"

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
        self.mini = None
        self.overlay = None
        mini_btn = QPushButton("Mini player")
        mini_btn.setToolTip("Keep watching in a small window that stays on top")
        mini_btn.setStyleSheet(theme.PILL)
        mini_btn.setFixedHeight(32)
        mini_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mini_btn.setEnabled(HAVE_VIDEO)
        mini_btn.clicked.connect(self.pop_out)
        row.addWidget(mini_btn)
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
        self._close_mini()
        self.float_in(None)

    @property
    def floating(self):
        return self.overlay is not None and not self.overlay.isHidden()

    def float_out(self, host):
        """Leaving the video page while it plays: the video floats in a small window inside Sevbify."""
        if self.player is None or self.popped_out:
            return False
        if self.overlay is None or self.overlay.host is not host:
            self.overlay = VideoOverlay(self, host)
            self.overlay.expand_requested.connect(self._overlay_expand)
            self.overlay.close_requested.connect(self._audio_only)
        self.player.setVideoOutput(self.overlay.video)
        self.overlay.update_play_icon(self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        self.overlay.place()
        self.overlay.show()
        self.overlay.raise_()
        return True

    def float_in(self, _host=None):
        """Back on the video page (or stopped): the floating video goes away."""
        if self.overlay is not None and not self.overlay.isHidden():
            self.overlay.hide()
            if self.player is not None:
                self.player.setVideoOutput(self.video)

    def _overlay_expand(self):
        self.float_in()
        self.show_requested.emit()

    @property
    def popped_out(self):
        return self.mini is not None and self.mini.isVisible()

    def pop_out(self):
        """Move the video into the always-on-top mini player (it keeps playing while you go elsewhere)."""
        if self.player is None:
            return
        if self.mini is None:
            self.mini = VideoMiniPlayer(self)
            self.mini.expand_requested.connect(self.pop_in)
            self.mini.closed.connect(self._mini_closed)
        self.mini.title.setText(self.title.text())
        self.player.setVideoOutput(self.mini.video)
        self.mini.update_play_icon(self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        self.mini.show()
        self.mini.raise_()

    def pop_in(self):
        """Back from the mini player to the video page."""
        if self.player is not None:
            self.player.setVideoOutput(self.video)
        if self.mini is not None:
            self.mini.blockSignals(True)
            self.mini.hide()
            self.mini.blockSignals(False)
        self.show_requested.emit()

    def _mini_closed(self):
        # Closing the mini player's window stops the video (like closing YouTube's mini player).
        if self.player is not None:
            self.player.pause()
            self.player.setVideoOutput(self.video)

    def _close_mini(self):
        if self.mini is not None:
            self.mini.blockSignals(True)
            self.mini.close()
            self.mini.blockSignals(False)
            if self.player is not None:
                self.player.setVideoOutput(self.video)

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
        if self.overlay is not None and not self.overlay.isHidden():
            d = self.player.duration()
            self.overlay.set_progress(ms / d if d else 0)

    def _update_play_icon(self):
        playing = self.player is not None and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setIcon(icons.pause("#000000", 16) if playing else icons.play("#000000", 16))
        if self.mini is not None:
            self.mini.update_play_icon(playing)
        if self.overlay is not None:
            self.overlay.update_play_icon(playing)

    def _audio_only(self):
        pos = self.position()
        self.stop()
        self.audio_only_requested.emit(pos)

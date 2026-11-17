"""Spotify's expanded "Now playing view": the Now playing panel opened up to fill the window (the player bar stays).

Top right, like Spotify: Show album art (the cover tilts in 3D as the mouse moves over it), Show Canvas (the loop
video, shown wide, uncropped), Show artist image (the artist's picture fills the background), Lyrics (dimmed when
the song has none), then ••• (the song's menu), Full screen and Collapse. Below: About the artist, Credits and
Next in queue. The view only shows and steers the one player in the main window.
"""
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap, QTransform
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
                             QVBoxLayout, QWidget)

from . import icons, theme

try:
    from PyQt6.QtMultimedia import QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAVE_VIDEO = True
except Exception:                       # Qt Multimedia missing: no Canvas mode
    HAVE_VIDEO = False

MAX_TILT = 9.0           # degrees


def dominant_colour(pm, fallback="#2d4a5a"):
    """The cover's average colour, darkened a little (the view's background, like Spotify's)."""
    if pm is None or pm.isNull():
        return QColor(fallback)
    c = QColor(pm.toImage().scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation).pixel(0, 0))
    h, s, v, _a = c.getHsv()
    return QColor.fromHsv(max(h, 0), min(255, int(s * 0.9)), max(40, min(150, int(v * 0.6))))


class TiltCover(QWidget):
    """The album art, tilting towards the mouse in 3D (Spotify's expanded view)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._pm = None
        self._rx = self._ry = 0.0
        self._target = (0.0, 0.0)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._step)
        self.setMinimumSize(240, 240)

    def set_pixmap(self, pm):
        self._pm = pm if pm is not None and not pm.isNull() else None
        self.update()

    def tilt(self):
        return self._rx, self._ry

    def _side(self):
        return int(min(self.width(), self.height()) * 0.82)

    def mouseMoveEvent(self, e):
        side = max(1, self._side())
        dx = (e.position().x() - self.width() / 2) / (side / 2)
        dy = (e.position().y() - self.height() / 2) / (side / 2)
        dx, dy = max(-1.0, min(1.0, dx)), max(-1.0, min(1.0, dy))
        self._target = (-dy * MAX_TILT, dx * MAX_TILT)
        self._timer.start()

    def leaveEvent(self, _e):
        self._target = (0.0, 0.0)
        self._timer.start()

    def _step(self):
        tx, ty = self._target
        self._rx += (tx - self._rx) * 0.2
        self._ry += (ty - self._ry) * 0.2
        if abs(tx - self._rx) < 0.05 and abs(ty - self._ry) < 0.05:
            self._rx, self._ry = tx, ty
            self._timer.stop()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        side = self._side()
        cx, cy = self.width() / 2, self.height() / 2
        t = QTransform()
        t.translate(cx, cy)
        t.rotate(self._ry, Qt.Axis.YAxis, 1024)
        t.rotate(self._rx, Qt.Axis.XAxis, 1024)
        t.translate(-cx, -cy)
        p.setTransform(t)
        rect = QRectF(cx - side / 2, cy - side / 2, side, side)
        for i in range(10, 0, -2):                       # soft shadow
            p.fillRect(rect.translated(0, 8).adjusted(-i, -i, i, i), QColor(0, 0, 0, 10))
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        p.setClipPath(path)
        if self._pm is not None:
            p.drawPixmap(rect.toRect(), self._pm.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                        Qt.TransformationMode.SmoothTransformation))
        else:
            p.fillRect(rect, QColor("#333333"))
        p.end()


class _Backdrop(QWidget):
    """The background: the cover's colour fading to dark, or the artist's picture (Show artist image)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colour = QColor("#2d4a5a")
        self.picture = None

    def paintEvent(self, _e):
        p = QPainter(self)
        if self.picture is not None and not self.picture.isNull():
            pm = self.picture.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((self.width() - pm.width()) // 2, (self.height() - pm.height()) // 3, pm)
            g = QLinearGradient(0, 0, 0, self.height())
            g.setColorAt(0, QColor(0, 0, 0, 60))
            g.setColorAt(1, QColor(0, 0, 0, 220))
            p.fillRect(self.rect(), g)
        else:
            g = QLinearGradient(0, 0, 0, self.height())
            g.setColorAt(0, self.colour)
            g.setColorAt(1, QColor("#121212"))
            p.fillRect(self.rect(), g)
        p.end()


def _tool(icon, tip, slot, checkable=False):
    b = QPushButton()
    b.setIcon(icon)
    b.setToolTip(tip)
    b.setFixedSize(34, 34)
    b.setCheckable(checkable)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 17px; }"
                    " QPushButton:hover { background: rgba(255,255,255,0.12); }"
                    " QPushButton:checked { background: rgba(255,255,255,0.18); }"
                    " QPushButton:disabled { opacity: 0.4; }")
    b.clicked.connect(slot)
    return b


def _card(title):
    f = QFrame()
    f.setObjectName("evCard")
    f.setStyleSheet("#evCard { background: rgba(0,0,0,0.35); border-radius: 10px; } QLabel { background: transparent; }")
    v = QVBoxLayout(f)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(6)
    h = QLabel(title)
    h.setStyleSheet("color: white; font-size: 16px; font-weight: 800;")
    v.addWidget(h)
    return f, v


class ExpandedView(QWidget):
    collapse_requested = pyqtSignal()
    full_screen_requested = pyqtSignal()
    menu_requested = pyqtSignal(object)            # the ••• button (main window builds the song's menu)
    lyrics_requested = pyqtSignal()
    mode_changed = pyqtSignal(str)                 # "art" | "canvas" | "artist" (remembered)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "art"
        self.song = None
        self.canvas_path = None
        self.backdrop = _Backdrop(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(24, 14, 24, 24)
        v.setSpacing(16)

        bar = QHBoxLayout()
        self.title = QLabel("")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setStyleSheet("color: white; font-size: 15px; font-weight: 700;")
        bar.addWidget(self.title, 1)
        self.b_art = _tool(icons.disc(), "Show album art", lambda: self.set_mode("art"), True)
        self.b_canvas = _tool(icons.video(), "Show Canvas", lambda: self.set_mode("canvas"), True)
        self.b_artist = _tool(icons.person(), "Show artist image", lambda: self.set_mode("artist"), True)
        self.b_lyrics = _tool(icons.lyrics(), "Lyrics", self.lyrics_requested.emit)
        self.b_more = _tool(icons.more(), "More options", lambda: self.menu_requested.emit(self.b_more))
        self.b_full = _tool(icons.fullscreen(), "Full screen", self.full_screen_requested.emit)
        self.b_collapse = _tool(icons.expand(out=False), "Collapse", self.collapse_requested.emit)
        for b in (self.b_art, self.b_canvas, self.b_artist, self.b_lyrics):
            bar.addWidget(b)
        sep = QFrame()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet("background: rgba(255,255,255,0.25);")
        bar.addWidget(sep)
        for b in (self.b_more, self.b_full, self.b_collapse):
            bar.addWidget(b)
        v.addLayout(bar)

        self.visual = QStackedWidget()
        self.visual.setMinimumHeight(420)
        self.visual.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.cover = TiltCover()
        self.visual.addWidget(self.cover)
        self.video = self.video_player = None
        if HAVE_VIDEO:
            self.video = QVideoWidget()
            self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)    # whole picture, wide
            self.video.setStyleSheet("background: transparent;")
            self.video_player = QMediaPlayer(self)
            self.video_player.setVideoOutput(self.video)                      # no audio output: silent
            self.video_player.setLoops(QMediaPlayer.Loops.Infinite)
            self.visual.addWidget(self.video)
        self.artist_space = QWidget()                                        # the backdrop shows the picture
        self.visual.addWidget(self.artist_space)
        v.addWidget(self.visual, 1)

        self.song_title = QLabel("")
        self.song_title.setTextFormat(Qt.TextFormat.PlainText)
        self.song_title.setStyleSheet("color: white; font-size: 28px; font-weight: 800;")
        self.song_artist = QLabel("")
        self.song_artist.setTextFormat(Qt.TextFormat.PlainText)
        self.song_artist.setStyleSheet("color: #d0d0d0; font-size: 16px;")
        v.addWidget(self.song_title)
        v.addWidget(self.song_artist)

        cards = QHBoxLayout()
        cards.setSpacing(16)
        about, av = _card("About the artist")
        self.about_text = QLabel("")
        self.about_text.setWordWrap(True)
        self.about_text.setStyleSheet("color: #d0d0d0; font-size: 13px;")
        av.addWidget(self.about_text)
        av.addStretch()
        credits, cv = _card("Credits")
        self.credits_text = QLabel("")
        self.credits_text.setWordWrap(True)
        self.credits_text.setTextFormat(Qt.TextFormat.PlainText)
        self.credits_text.setStyleSheet("color: #d0d0d0; font-size: 13px;")
        cv.addWidget(self.credits_text)
        cv.addStretch()
        nxt, nv = _card("Next in queue")
        self.next_text = QLabel("")
        self.next_text.setWordWrap(True)
        self.next_text.setTextFormat(Qt.TextFormat.PlainText)
        self.next_text.setStyleSheet("color: #d0d0d0; font-size: 13px;")
        nv.addWidget(self.next_text)
        nv.addStretch()
        for c in (about, credits, nxt):
            c.setMinimumHeight(140)
            cards.addWidget(c, 1)
        v.addLayout(cards)
        self.set_mode("art")

    def resizeEvent(self, e):
        self.backdrop.setGeometry(self.rect())
        self.backdrop.lower()
        super().resizeEvent(e)

    # --- what's shown ---------------------------------------------------------------------------------------
    def set_mode(self, mode):
        if mode == "canvas" and not (self.canvas_path and self.video_player is not None):
            mode = "art"
        if mode == "artist" and (self.backdrop.picture is None or self.backdrop.picture.isNull()) \
                and getattr(self, "_artist_pm", None) is None:
            mode = "art"
        self.mode = mode
        for b, m in ((self.b_art, "art"), (self.b_canvas, "canvas"), (self.b_artist, "artist")):
            b.setChecked(m == mode)
        self.b_canvas.setEnabled(bool(self.canvas_path) and self.video_player is not None)
        self.b_artist.setEnabled(getattr(self, "_artist_pm", None) is not None)
        if mode == "canvas":
            self.visual.setCurrentWidget(self.video)
            self.video_player.setSource(QUrl.fromLocalFile(self.canvas_path))
            self.video_player.play()
        else:
            if self.video_player is not None:
                self.video_player.stop()
            self.visual.setCurrentWidget(self.artist_space if mode == "artist" else self.cover)
        self.backdrop.picture = getattr(self, "_artist_pm", None) if mode == "artist" else None
        self.backdrop.update()
        self.mode_changed.emit(mode)

    def set_song(self, song, cover_pm=None, canvas_path=None, has_lyrics=False):
        self.song = song
        self.canvas_path = canvas_path
        self._artist_pm = None
        self.title.setText(getattr(song, "title", "") or "Now playing")
        self.song_title.setText(getattr(song, "title", "") or "Nothing playing")
        self.song_artist.setText(getattr(song, "artist", "") or "")
        self.cover.set_pixmap(cover_pm)
        self.backdrop.colour = dominant_colour(cover_pm)
        self.b_lyrics.setEnabled(bool(has_lyrics))
        self.b_lyrics.setToolTip("Lyrics" if has_lyrics else "Lyrics aren't available for this song")
        self.about_text.setText("")
        self.credits_text.setText("Looking up credits…" if song is not None else "")
        self.set_mode(self.mode if self.mode != "artist" else "art")

    def set_artist(self, picture_pm=None, about=""):
        self._artist_pm = picture_pm if picture_pm is not None and not picture_pm.isNull() else None
        self.about_text.setText(about or "")
        self.b_artist.setEnabled(self._artist_pm is not None)

    def set_credits(self, people):
        if not people:
            self.credits_text.setText("No credits found for this song.")
            return
        self.credits_text.setText("\n".join(f"{p['name']} · {', '.join(p['roles'])}" for p in people[:8]))

    def set_next(self, song):
        self.next_text.setText(f"{song.title}\n{song.artist}" if song is not None else "Nothing queued")

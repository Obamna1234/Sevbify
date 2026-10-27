"""Right-side 'Now playing' panel: big artwork (or a looping canvas video),
song title/artist, and an 'About the artist' card filled in when online."""
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QStackedWidget, QSizePolicy
)
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPixmap, QLinearGradient, QBrush, QImage
from PyQt6.QtCore import Qt, QRectF, QVariantAnimation, QEasingCurve, QUrl, pyqtSignal

try:
    from PyQt6.QtMultimedia import QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAVE_VIDEO = True
except Exception:  # pragma: no cover - multimedia missing on some Linux installs
    HAVE_VIDEO = False


def dominant_colour(pixmap: QPixmap) -> QColor:
    """Average colour of a small version of the image, darkened for backgrounds."""
    if pixmap.isNull():
        return QColor("#2a2a2a")
    img = pixmap.toImage().scaled(8, 8, Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGB32)
    r = g = b = 0
    for x in range(8):
        for y in range(8):
            c = QColor(img.pixel(x, y))
            r += c.red(); g += c.green(); b += c.blue()
    c = QColor(r // 64, g // 64, b // 64)
    h, s, v, _ = c.getHsv()
    return QColor.fromHsv(max(h, 0), min(255, int(s * 1.2)), min(v, 140))


class AnimatedArtwork(QWidget):
    """Cover art that slowly zooms in and out with a soft colour glow
    (used when the song has no canvas video)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._zoom = 1.0
        self._glow = QColor("#2a2a2a")
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(18000)
        self.anim.setStartValue(1.0)
        self.anim.setKeyValueAt(0.5, 1.09)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.anim.setLoopCount(-1)
        self.anim.valueChanged.connect(self._set_zoom)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _set_zoom(self, z):
        self._zoom = float(z)
        self.update()

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._glow = dominant_colour(pixmap)
        self.update()

    def set_animating(self, on: bool):
        if on and self.anim.state() != QVariantAnimation.State.Running:
            self.anim.start()
        elif not on:
            self.anim.pause() if self.anim.state() == QVariantAnimation.State.Running else None

    def heightForWidth(self, w):
        return w

    def resizeEvent(self, e):
        self.setFixedHeight(self.width())
        super().resizeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        p.setClipPath(path)
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0, self._glow.lighter(130))
        grad.setColorAt(1, QColor("#121212"))
        p.fillRect(rect, QBrush(grad))
        if not self._pixmap.isNull():
            side = rect.width() * self._zoom
            target = QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side)
            p.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        p.end()


class NowPlayingPanel(QWidget):
    close_requested = pyqtSignal()
    go_to_artist_radio = pyqtSignal()

    def __init__(self, pixmap_loader, parent=None):
        super().__init__(parent)
        self._loader = pixmap_loader
        self.song = None
        self.setMinimumWidth(300)
        self.setMaximumWidth(380)
        self.setObjectName("nowPlaying")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Selector by name so the background doesn't leak into child widgets.
        self.setStyleSheet("#nowPlaying { background-color: #121212; } QLabel { background: transparent; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 16, 8, 8)
        head = QHBoxLayout()
        self.source_label = QLabel("")
        self.source_label.setMinimumWidth(0)
        self.source_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.source_label.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        head.addWidget(self.source_label, 1)
        close = QPushButton("✕")
        close.setFixedSize(28, 28)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet("QPushButton { color: #b3b3b3; border: none; font-size: 16px; background: transparent; }"
                            "QPushButton:hover { color: white; }")
        close.clicked.connect(self.close_requested.emit)
        head.addWidget(close)
        outer.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: #121212; }")
        outer.addWidget(scroll, 1)
        body = QWidget()
        body.setObjectName("npBody")
        body.setStyleSheet("#npBody { background: #121212; }")
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 8, 6, 8)
        v.setSpacing(10)

        # Artwork or canvas video
        self.visual = QStackedWidget()
        self.artwork = AnimatedArtwork()
        self.visual.addWidget(self.artwork)
        self.video = None
        self.video_player = None
        if HAVE_VIDEO:
            self.video = QVideoWidget()
            self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            self.video.setStyleSheet("background: black; border-radius: 10px;")
            self.video_player = QMediaPlayer(self)
            self.video_player.setVideoOutput(self.video)       # no audio output: always silent
            self.video_player.setLoops(QMediaPlayer.Loops.Infinite)
            self.video_player.errorOccurred.connect(lambda *_: self._show_artwork())
            self.visual.addWidget(self.video)
        v.addWidget(self.visual)

        # Title / artist
        self.title = QLabel("Nothing playing")
        self.title.setStyleSheet("color: white; font-size: 22px; font-weight: 800;")
        self.title.setWordWrap(True)
        self.artist = QLabel("")
        self.artist.setWordWrap(True)
        self.artist.setStyleSheet("color: #b3b3b3; font-size: 14px;")
        v.addWidget(self.title)
        v.addWidget(self.artist)

        # About the artist
        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setStyleSheet("#card { background: #242424; border-radius: 10px; }")
        cv = QVBoxLayout(self.card)
        cv.setContentsMargins(0, 0, 0, 14)
        cv.setSpacing(8)
        self.card_heading = QLabel("About the artist")
        self.card_heading.setStyleSheet("color: white; font-size: 15px; font-weight: bold; padding: 14px 16px 2px 16px;")
        cv.addWidget(self.card_heading)
        self.card_image = QLabel()
        self.card_image.setFixedHeight(170)
        self.card_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_image.hide()
        cv.addWidget(self.card_image)
        self.card_name = QLabel("")
        self.card_name.setWordWrap(True)
        self.card_name.setStyleSheet("color: white; font-size: 16px; font-weight: bold; padding: 0 16px;")
        cv.addWidget(self.card_name)
        self.card_stats = QLabel("")
        self.card_stats.setWordWrap(True)
        self.card_stats.setStyleSheet("color: #b3b3b3; font-size: 13px; padding: 0 16px;")
        cv.addWidget(self.card_stats)
        self.card_bio = QLabel("")
        self.card_bio.setWordWrap(True)
        self.card_bio.setStyleSheet("color: #b3b3b3; font-size: 13px; padding: 0 16px;")
        cv.addWidget(self.card_bio)
        self.card_links = QLabel("")
        self.card_links.setTextFormat(Qt.TextFormat.RichText)
        self.card_links.setOpenExternalLinks(True)
        self.card_links.setWordWrap(True)
        self.card_links.setStyleSheet("color: #b3b3b3; font-size: 12px; padding: 0 16px;")
        cv.addWidget(self.card_links)
        v.addWidget(self.card)
        v.addStretch()
        self.set_card_message("")

    # ------------------------------------------------------------------
    def set_song(self, song, source_name="", canvas_path=None, playing=True):
        self.song = song
        self.source_label.setText(source_name or "Now playing")
        if song is None:
            self.title.setText("Nothing playing")
            self.artist.setText("")
            self.artwork.set_pixmap(QPixmap())
            self._show_artwork()
            return
        self.title.setText(song.title)
        self.artist.setText(song.artist)
        self.artwork.set_pixmap(self._loader(song.album_cover_path))
        if canvas_path and self.video_player is not None:
            self.video_player.setSource(QUrl.fromLocalFile(os.path.abspath(canvas_path)))
            self.visual.setCurrentWidget(self.video)
            self.video.setFixedHeight(int(max(self.width() - 20, 280) * 1.25))
            if playing:
                self.video_player.play()
        else:
            self._show_artwork()
        self.set_playing(playing)

    def _show_artwork(self):
        if self.video_player is not None:
            self.video_player.stop()
        self.visual.setCurrentWidget(self.artwork)

    @property
    def showing_video(self):
        return self.video is not None and self.visual.currentWidget() is self.video

    def set_playing(self, playing: bool):
        visible = not self.isHidden()
        if self.showing_video:
            (self.video_player.play if playing and visible else self.video_player.pause)()
        self.artwork.set_animating(playing and visible)

    def hideEvent(self, e):
        self.artwork.set_animating(False)
        if self.video_player is not None:
            self.video_player.pause()
        super().hideEvent(e)

    # ------------------------------------------------------------------
    def set_card_message(self, message):
        """Show a single line in the artist card (loading / offline / switched off)."""
        self.card_image.hide()
        self.card_name.setText("")
        self.card_stats.setText(message)
        self.card_bio.setText("")
        self.card_links.setText("")
        for lbl in (self.card_name, self.card_bio, self.card_links):
            lbl.setVisible(False)
        self.card.setVisible(bool(message))

    def set_artist_card(self, card: dict):
        self.card.show()
        for lbl in (self.card_name, self.card_bio, self.card_links):
            lbl.setVisible(True)
        self.card_name.setText(card.get("name", ""))
        parts = []
        if card.get("listeners"):
            parts.append(f"{card['listeners']:,} listeners on Last.fm")
        if card.get("fans"):
            parts.append(f"{card['fans']:,} fans on Deezer")
        self.card_stats.setText("  ·  ".join(parts))
        bio = card.get("bio", "")
        if len(bio) > 420:
            bio = bio[:420].rsplit(" ", 1)[0] + "…"
        if card.get("tags"):
            bio = (bio + "\n\n" if bio else "") + "  ·  ".join(card["tags"])
        self.card_bio.setText(bio)
        links = []
        for label, key in (("Last.fm", "url"), ("Wikipedia", "wiki_url"), ("Deezer", "deezer_url")):
            if card.get(key):
                links.append(f'<a style="color:#ffffff; text-decoration:none" href="{card[key]}">{label} ↗</a>')
        self.card_links.setText("   ".join(links))
        self.card_image.hide()

    def set_artist_image(self, path):
        pm = QPixmap(path) if path else QPixmap()
        if pm.isNull():
            self.card_image.hide()
            return
        w = max(self.card.width(), 280)
        h = self.card_image.height()
        scaled = pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - w) // 2)
        y = max(0, (scaled.height() - h) // 3)
        self.card_image.setPixmap(scaled.copy(x, y, w, h))
        self.card_image.show()

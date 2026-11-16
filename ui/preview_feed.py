"""Spotify's "Scroll through previews of tracks from this playlist": a feed over the app, one song at a time —
its big cover (or its Canvas video when you've added one), the title and artist, a short preview playing, and
buttons to like it, add it to a playlist, play the full song, or go to the next one. Scroll, ↑/↓ or Next to
move, Esc or ✕ to leave. The main player is paused while it's open and nothing replaces what you were playing.

Previews: songs on this computer play 30 seconds from a third of the way in; others use the song's 30-second
preview (asked for fresh each time; songs without one are skipped).
"""
from PyQt6.QtCore import Qt, QTimer, QSize, QRectF
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPainterPath, QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from . import icons, theme
from .click_slider import ClickSlider

PREVIEW_MS = 30_000


class _Cover(QWidget):
    """The tall card in the middle: the cover, filling a 9:16 frame, rounded."""

    def __init__(self):
        super().__init__()
        self.pm = QPixmap()
        self.setMinimumSize(270, 480)

    def set_pixmap(self, pm):
        self.pm = pm if pm is not None else QPixmap()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        w = min(self.width(), int(h * 9 / 16))
        x = (self.width() - w) // 2
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, 0, w, h), 8, 8)
        p.setClipPath(path)
        p.fillRect(x, 0, w, h, QColor("#282828"))
        if not self.pm.isNull():
            # The square cover sits in the middle of the tall card, over a blurred-looking fill of itself.
            back = self.pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.FastTransformation)
            p.setOpacity(0.35)
            p.drawPixmap(x - (back.width() - w) // 2, -(back.height() - h) // 2, back)
            p.setOpacity(1.0)
            side = int(w * 0.86)
            front = self.pm.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                   Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(x + (w - side) // 2, (h - side) // 2, front)
        p.end()


class PreviewFeed(QFrame):
    def __init__(self, win, songs, source_name):
        super().__init__(win)
        self.win, self.songs, self.source_name = win, [s for s in songs if s is not None], source_name
        self.index = 0
        self.colour = QColor("#333333")
        self.player = win.vlc_instance.media_player_new()
        self._token = 0
        self._started = 0
        self._closed = False
        self.setObjectName("previewFeed")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("QLabel { background: transparent; color: white; }")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(40, 28, 28, 28)
        outer.setSpacing(24)

        left = QVBoxLayout()
        self.context = QLabel(source_name)
        self.context.setStyleSheet("font-size: 14px; font-weight: 700;")
        left.addWidget(self.context)
        left.addStretch()
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 32px; font-weight: 800;")
        self.artist = QLabel()
        self.artist.setStyleSheet(f"font-size: 15px; color: {theme.SUBDUED};")
        left.addWidget(self.title)
        left.addWidget(self.artist)
        self.bar = ClickSlider(Qt.Orientation.Horizontal)
        self.bar.setRange(0, PREVIEW_MS)
        self.bar.setFixedWidth(240)
        self.bar.setStyleSheet("QSlider::groove:horizontal { background: rgba(255,255,255,0.3); height: 4px;"
                               " border-radius: 2px; } QSlider::sub-page:horizontal { background: white;"
                               " border-radius: 2px; } QSlider::handle:horizontal { width: 0; }")
        self.bar.sliderReleased.connect(self._seek)
        left.addWidget(self.bar)
        play_full = QPushButton("Play song")
        play_full.setCursor(Qt.CursorShape.PointingHandCursor)
        play_full.setFixedHeight(32)
        play_full.setStyleSheet("QPushButton { color: white; background: transparent; border: 1px solid #7c7c7c;"
                                " border-radius: 16px; padding: 0 16px; font-weight: 700; font-size: 14px; }"
                                " QPushButton:hover { border-color: white; }")
        play_full.clicked.connect(self.play_full_song)
        left.addSpacing(8)
        left.addWidget(play_full, 0, Qt.AlignmentFlag.AlignLeft)
        left.addStretch()
        outer.addLayout(left, 2)

        self.cover = _Cover()
        outer.addWidget(self.cover, 3)

        right = QVBoxLayout()
        top = QHBoxLayout()
        top.addStretch()
        close = self._round(icons.close("#ffffff", 16), "Close (Esc)", self.close_feed)
        top.addWidget(close)
        right.addLayout(top)
        right.addStretch()

        def side(icon, tip, slot):
            b = self._round(icon, tip, slot, 40)
            right.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
            return b
        self.like_btn = side(icons.heart("#ffffff", 20), "Add to Liked Songs", self.toggle_like)
        self.add_btn = side(icons.plus("#ffffff", 20), "Add to playlist", self.add_to_playlist)
        self.more_btn = side(icons.more("#ffffff", 20), "More options", self.more)
        right.addStretch()
        nxt = QPushButton("  Next")
        nxt.setIcon(icons.chevron("down", "#000000", 14) if hasattr(icons, "chevron") else icons.play("#000000", 12))
        nxt.setCursor(Qt.CursorShape.PointingHandCursor)
        nxt.setFixedHeight(36)
        nxt.setStyleSheet("QPushButton { color: black; background: white; border: none; border-radius: 18px;"
                          " padding: 0 18px; font-weight: 700; font-size: 14px; } QPushButton:hover { background: #f0f0f0; }")
        nxt.clicked.connect(lambda: self.go(1))
        right.addWidget(nxt, 0, Qt.AlignmentFlag.AlignRight)
        outer.addLayout(right, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    @staticmethod
    def _round(icon, tip, slot, size=36):
        b = QPushButton()
        b.setIcon(icon)
        b.setIconSize(QSize(size // 2, size // 2))
        b.setFixedSize(size, size)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background: rgba(0,0,0,0.35); border: none; border-radius: {size // 2}px; }}"
                        " QPushButton:hover { background: rgba(255,255,255,0.15); }")
        b.clicked.connect(slot)
        return b

    # --- showing --------------------------------------------------------------------------------------------
    def open(self, start=0):
        self.setGeometry(self.win.rect())
        self.show()
        self.raise_()
        self.setFocus()
        self.show_song(start)

    def resizeEvent(self, e):
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, self.colour.darker(140))
        g.setColorAt(1.0, QColor("#121212"))
        p.fillRect(self.rect(), g)
        p.end()

    @property
    def song(self):
        return self.songs[self.index] if 0 <= self.index < len(self.songs) else None

    def show_song(self, i):
        if not self.songs:
            return
        self.index = max(0, min(len(self.songs) - 1, i))
        s = self.song
        from .main_window import load_pixmap
        from .now_playing_panel import dominant_colour
        pm = load_pixmap(s.album_cover_path)
        self.cover.set_pixmap(pm)
        self.colour = dominant_colour(pm) if not pm.isNull() else QColor("#333333")
        self.title.setText(s.title)
        self.artist.setText(s.artist)
        self._update_like()
        self.update()
        self._play_preview()

    def _update_like(self):
        liked = self.win.is_liked(self.song)
        self.like_btn.setIcon(icons.heart("#1ed760" if liked else "#ffffff", 20, filled=liked))
        self.like_btn.setToolTip("Remove from Liked Songs" if liked else "Add to Liked Songs")

    def _play_preview(self):
        self._token += 1
        token, s = self._token, self.song
        self.player.stop()
        self.bar.setValue(0)
        if not getattr(s, "is_remote", False) and s.exists:
            self._start(s.file_path, max(0, (s.duration or 0) // 3))
            return
        if not self.win.online_enabled:
            return
        track = getattr(s, "track", None)
        did = track.source_id if track is not None and track.source == "deezer" else ""
        saved = track.preview_url if track is not None else ""

        def got(url):
            if token != self._token or self._closed:
                return
            if url:
                self._start(url, 0)
            else:
                self.go(1)                                   # no preview for this one
        self.win.online_call(self.win.online.deezer.fresh_preview, s.artist, s.title, did,
                             on_done=lambda u: got(u or saved), on_error=lambda _e: got(saved))

    def _start(self, location, start_ms):
        if self._closed:
            return
        self.player.set_media(self.win.vlc_instance.media_new(location))
        self.player.play()
        self._started = start_ms
        token = self._token
        if start_ms:      # (never on a player that was released meanwhile: the feed may close within 150 ms)
            QTimer.singleShot(150, lambda: not self._closed and token == self._token
                              and self.player.set_time(int(start_ms)))

    def _tick(self):
        if self._closed:
            return
        t = max(0, self.player.get_time() - self._started)
        if not self.bar.isSliderDown():
            self.bar.setValue(int(min(PREVIEW_MS, t)))
        if t >= PREVIEW_MS or str(self.player.get_state()).endswith("Ended"):
            self.go(1)

    def _seek(self):
        self.player.set_time(int(self._started + self.bar.value()))

    def go(self, step):
        if self._closed:
            return
        if self.index + step < len(self.songs) and self.index + step >= 0:
            self.show_song(self.index + step)
        elif step > 0:
            self.player.stop()

    # --- actions ---------------------------------------------------------------------------------------------
    def toggle_like(self):
        if self.song is not None:
            self.win.toggle_like(self.song)
            self._update_like()

    def add_to_playlist(self):
        if self.song is not None:
            self.win.open_save_picker(self.song, self.add_btn.mapToGlobal(self.add_btn.rect().bottomLeft()))

    def more(self):
        if self.song is not None:
            self.win.build_song_menu(self.song, self.songs, source=self.source_name).exec(
                self.more_btn.mapToGlobal(self.more_btn.rect().bottomLeft()))

    def play_full_song(self):
        s = self.song
        self.close_feed()
        if s is not None:
            self.win.play_song(s, queue=self.songs, source=self.source_name)

    def close_feed(self):
        if self._closed:
            return
        self._closed = True
        self.timer.stop()
        self._token += 1
        try:
            self.player.stop()
            self.player.release()
        except Exception:
            pass
        self.hide()
        self.deleteLater()
        if getattr(self.win, "_preview_feed", None) is self:
            self.win._preview_feed = None

    # --- keys and wheel ---------------------------------------------------------------------------------------
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close_feed()
        elif e.key() in (Qt.Key.Key_Down, Qt.Key.Key_PageDown):
            self.go(1)
        elif e.key() in (Qt.Key.Key_Up, Qt.Key.Key_PageUp):
            self.go(-1)
        elif e.key() == Qt.Key.Key_Space:
            self.player.pause() if self.player.is_playing() else self.player.play()
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        now = getattr(self, "_last_wheel", 0)
        import time
        if time.monotonic() - now < 0.5:                 # one song per flick
            return
        self._last_wheel = time.monotonic()
        self.go(1 if e.angleDelta().y() < 0 else -1)

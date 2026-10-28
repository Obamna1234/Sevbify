"""Spotify's Miniplayer and Full screen views. Both only show and steer the one player in the main window
(nothing plays twice, and switching views never stops or resets the music or the queue)."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QSize, QTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPixmap

from . import icons, theme
from .click_slider import ClickSlider
from core.models import format_time


def _round(icon, tip, slot, size=40, bg="transparent", icon_size=None):
    b = QPushButton()
    b.setIcon(icon)
    b.setIconSize(QSize(icon_size or int(size * 0.5), icon_size or int(size * 0.5)))
    b.setFixedSize(size, size)
    b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(f"QPushButton {{ background: {bg}; border: none; border-radius: {size // 2}px; }}"
                    f" QPushButton:hover {{ background: {'#f0f0f0' if bg == 'white' else 'rgba(255,255,255,0.12)'}; }}")
    b.clicked.connect(slot)
    return b


class _Controls(QWidget):
    """Shuffle / previous / play / next / repeat and the progress bar, wired to the main window."""

    def __init__(self, win, big=False, parent=None):
        super().__init__(parent)
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(18 if big else 10)
        row.addStretch()
        size = 56 if big else 36
        self.shuffle = _round(icons.shuffle(theme.SUBDUED, 24), "Shuffle", win.toggle_shuffle, 40)
        self.prev = _round(icons.skip("prev", theme.TEXT, 22), "Previous", win.prev_song, 40)
        self.play = _round(icons.play("#000000", 20), "Play", win.play_pause_song, size, "white")
        self.next = _round(icons.skip("next", theme.TEXT, 22), "Next", win.next_song, 40)
        self.repeat = _round(icons.repeat(theme.SUBDUED, 24), "Repeat", win.cycle_repeat, 40)
        for b in ((self.shuffle, self.prev, self.play, self.next, self.repeat) if big else
                  (self.prev, self.play, self.next)):
            row.addWidget(b)
        row.addStretch()
        v.addLayout(row)
        prog = QHBoxLayout()
        self.time = QLabel("0:00")
        self.length = QLabel("0:00")
        for lbl in (self.time, self.length):
            lbl.setStyleSheet(f"color: {theme.TEXT if big else theme.SUBDUED}; font-size: {13 if big else 11}px;"
                              " background: transparent;")
        self.seek = ClickSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 1000)
        from .main_window import SLIDER_STYLE
        self.seek.setStyleSheet(SLIDER_STYLE)
        self.seek.sliderReleased.connect(self._seek)
        prog.addWidget(self.time)
        prog.addWidget(self.seek, 1)
        prog.addWidget(self.length)
        v.addLayout(prog)

    def _seek(self):
        p = self.win.player
        length = p.get_length()
        if length > 0:
            p.set_time(int(self.seek.value() / 1000 * length))

    def refresh(self):
        w = self.win
        playing = bool(getattr(w, "is_playing", False))
        self.play.setIcon(icons.pause("#000000", 20) if playing else icons.play("#000000", 20))
        self.play.setToolTip("Pause" if playing else "Play")
        on = w.pq.shuffle
        self.shuffle.setIcon(icons.shuffle(theme.GREEN if on else theme.SUBDUED, 24, dot=on))
        mode = w.pq.repeat
        self.repeat.setIcon(icons.repeat(theme.SUBDUED if mode == "off" else theme.GREEN, 24, one=mode == "one",
                                         dot=mode != "off"))
        try:
            now, length = w.player.get_time(), w.player.get_length()
        except Exception:
            now, length = 0, 0
        if length > 0 and now >= 0 and not self.seek.isSliderDown():
            self.seek.setValue(int(now / length * 1000))
            self.time.setText(format_time(now))
            self.length.setText(format_time(length))


class MiniPlayer(QWidget):
    """Always-on-top small window: the cover, and the song + controls when the mouse is over it."""

    def __init__(self, win):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.win = win
        self.setWindowTitle("Sevbify Miniplayer")
        self.resize(320, 320)
        self.setMinimumSize(220, 220)
        self.setStyleSheet(f"background: {theme.PANEL};")
        self.art = QPixmap()
        self._drag = None
        self.overlay = QWidget(self)
        self.overlay.setStyleSheet("background: rgba(0,0,0,0.55);")
        ov = QVBoxLayout(self.overlay)
        ov.setContentsMargins(14, 10, 14, 12)
        top = QHBoxLayout()
        top.addStretch()
        back = _round(icons.expand(theme.TEXT, 18), "Back to Sevbify", self.back, 32)
        close = QPushButton("✕")
        close.setFixedSize(32, 32)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setToolTip("Close the Miniplayer (the music keeps playing)")
        close.setStyleSheet("QPushButton { color: white; background: transparent; border: none; font-size: 15px;"
                            " border-radius: 16px; } QPushButton:hover { background: rgba(255,255,255,0.15); }")
        close.clicked.connect(self.close)
        top.addWidget(back)
        top.addWidget(close)
        ov.addLayout(top)
        ov.addStretch()
        self.title = QLabel("")
        self.title.setStyleSheet("color: white; font-size: 15px; font-weight: 700; background: transparent;")
        self.artist = QLabel("")
        self.artist.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px; background: transparent;")
        for lbl in (self.title, self.artist):
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            ov.addWidget(lbl)
        self.controls = _Controls(win, big=False)
        self.controls.setStyleSheet("background: transparent;")
        ov.addWidget(self.controls)
        self.overlay.hide()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(300)
        self.refresh()

    def back(self):
        self.close()
        self.win.showNormal()
        self.win.raise_()
        self.win.activateWindow()

    def refresh(self):
        from .main_window import load_pixmap
        song = self.win.current_song
        self.title.setText(song.title if song else "Nothing playing")
        self.artist.setText(song.artist if song else "")
        path = song.album_cover_path if song else ""
        if path != getattr(self, "_art_path", None):
            self._art_path = path
            self.art = load_pixmap(path)
            self.update()
        self.controls.refresh()

    def paintEvent(self, e):
        p = QPainter(self)
        if not self.art.isNull():
            scaled = self.art.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled)
        else:
            p.fillRect(self.rect(), QColor(theme.ELEVATED))
        p.end()

    def resizeEvent(self, e):
        self.overlay.setGeometry(self.rect())
        super().resizeEvent(e)

    def enterEvent(self, e):
        self.overlay.show()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.overlay.hide()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.back()

    def closeEvent(self, e):
        self.timer.stop()
        if getattr(self.win, "mini_player", None) is self:
            self.win.mini_player = None
        super().closeEvent(e)


class FullScreenView(QWidget):
    """Spotify's Full screen: the big cover (or the Canvas loop), the song and the controls. Esc to leave."""

    def __init__(self, win):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.win = win
        self.setWindowTitle("Sevbify")
        self.colour = QColor("#333333")
        self.art = QPixmap()
        v = QVBoxLayout(self)
        v.setContentsMargins(48, 32, 48, 32)
        top = QHBoxLayout()
        self.context = QLabel("")
        self.context.setStyleSheet("color: white; font-size: 14px; font-weight: 700; background: transparent;")
        top.addWidget(self.context)
        top.addStretch()
        exit_btn = _round(icons.fullscreen(theme.TEXT, 22, exit_=True), "Exit full screen (Esc)", self.close, 44)
        top.addWidget(exit_btn)
        v.addLayout(top)
        v.addStretch()
        bottom = QHBoxLayout()
        bottom.setSpacing(28)
        self.cover = QLabel()
        self.cover.setFixedSize(280, 280)
        bottom.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignBottom)
        text = QVBoxLayout()
        text.addStretch()
        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("color: white; font-size: 56px; font-weight: 800; background: transparent;")
        self.artist = QLabel("")
        self.artist.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 22px; font-weight: 600;"
                                  " background: transparent;")
        text.addWidget(self.title)
        text.addWidget(self.artist)
        bottom.addLayout(text, 1)
        v.addLayout(bottom)
        v.addSpacing(24)
        self.controls = _Controls(win, big=True)
        self.controls.setStyleSheet("background: transparent;")
        v.addWidget(self.controls)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(250)
        self.refresh()

    def refresh(self):
        from .main_window import load_pixmap
        from .now_playing_panel import dominant_colour
        from .library_panel import rounded
        w = self.win
        song = w.current_song
        self.title.setText(song.title if song else "Nothing playing")
        self.artist.setText(song.artist if song else "")
        self.context.setText(f"Playing from {w.pq.source_name}" if song and w.pq.source_name else "")
        path = song.album_cover_path if song else ""
        if path != getattr(self, "_art_path", None):
            self._art_path = path
            self.art = load_pixmap(path)
            self.cover.setPixmap(rounded(self.art, 280, 6))
            self.colour = dominant_colour(self.art)
            self.update()
        self.controls.refresh()

    def paintEvent(self, e):
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, self.colour.lighter(120))
        g.setColorAt(1, QColor("#000000"))
        p.fillRect(self.rect(), g)
        p.end()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            return
        if e.key() == Qt.Key.Key_Space:
            self.win.play_pause_song()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        self.timer.stop()
        if getattr(self.win, "full_screen_view", None) is self:
            self.win.full_screen_view = None
        super().closeEvent(e)

"""Right-side Queue / Recently played panel (Spotify layout)."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QMenu, QSizePolicy
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, pyqtSignal

PANEL_STYLE = "#queuePanel { background-color: #121212; } QLabel { background: transparent; }"
MENU_STYLE = """
QMenu { background: #282828; color: white; border: 1px solid #3e3e3e; padding: 4px; font-size: 13px; }
QMenu::item { padding: 8px 24px 8px 12px; border-radius: 3px; }
QMenu::item:selected { background: #3e3e3e; }
"""
_pixmap_cache = {}


def _thumb(path, size, loader):
    key = (path, size)
    pm = _pixmap_cache.get(key)
    if pm is None:
        pm = loader(path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
        if len(_pixmap_cache) > 500:
            _pixmap_cache.clear()
        _pixmap_cache[key] = pm
    return pm


class TrackRow(QFrame):
    """Artwork + title + artist. Click to play, right-click for a menu."""
    clicked = pyqtSignal()
    context_requested = pyqtSignal(object)  # global pos

    def __init__(self, song, pixmap_loader, current=False, subtitle=None):
        super().__init__()
        self.song = song
        self.setObjectName("row")
        self.setStyleSheet("#row { border-radius: 6px; } #row:hover { background: #2a2a2a; }")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(12)
        art = QLabel()
        art.setFixedSize(48, 48)
        art.setPixmap(_thumb(song.album_cover_path, 48, pixmap_loader))
        h.addWidget(art)
        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel()
        title.setStyleSheet(f"color: {'#1db954' if current else 'white'}; font-size: 14px; font-weight: 600;")
        title.setToolTip(song.title)
        artist = QLabel()
        artist.setStyleSheet("color: #b3b3b3; font-size: 12px;")
        # Shorten long names with "…" so the panel never grows sideways.
        for lbl, full in ((title, song.title), (artist, subtitle or song.artist)):
            lbl.setText(lbl.fontMetrics().elidedText(full, Qt.TextElideMode.ElideRight, 200))
            lbl.setMinimumWidth(0)
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addWidget(title)
        text.addWidget(artist)
        h.addLayout(text, 1)
        if getattr(song, "is_remote", False):
            kind = "preview" if song.is_preview else "online"
            artist.setText(artist.fontMetrics().elidedText(f"{song.artist}  ·  {kind}", Qt.TextElideMode.ElideRight, 200))
            self.setToolTip("Not in your library: plays as a 30-second preview" if song.is_preview
                            else "Not in your library: plays online")
        elif not song.exists:
            title.setStyleSheet("color: #6a6a6a; font-size: 14px; font-weight: 600;")
            self.setToolTip("Not on this computer")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self.context_requested.emit(event.globalPos())


class QueuePanel(QWidget):
    close_requested = pyqtSignal()
    play_upcoming = pyqtSignal(int)          # position in (user queue + context upcoming)
    play_recent = pyqtSignal(object)         # Song
    remove_from_queue = pyqtSignal(int)      # position in user queue
    clear_user_queue = pyqtSignal()

    MAX_ROWS = 60

    def __init__(self, pixmap_loader, parent=None):
        super().__init__(parent)
        self._loader = pixmap_loader
        self.setObjectName("queuePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(PANEL_STYLE)
        self.setMinimumWidth(300)
        self.setMaximumWidth(380)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 16, 8, 8)
        outer.setSpacing(8)

        head = QHBoxLayout()
        self.tab_queue = self._tab_button("Queue")
        self.tab_recent = self._tab_button("Recently played")
        self.tab_queue.clicked.connect(lambda: self.set_tab("queue"))
        self.tab_recent.clicked.connect(lambda: self.set_tab("recent"))
        head.addWidget(self.tab_queue)
        head.addWidget(self.tab_recent)
        head.addStretch()
        close = QPushButton("✕")
        close.setFixedSize(28, 28)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setToolTip("Close")
        close.setStyleSheet("QPushButton { color: #b3b3b3; border: none; font-size: 16px; background: transparent; }"
                            "QPushButton:hover { color: white; }")
        close.clicked.connect(self.close_requested.emit)
        head.addWidget(close)
        outer.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: #121212; }"
            "QScrollBar:vertical { background: #121212; width: 8px; }"
            "QScrollBar::handle:vertical { background: #4d4d4d; border-radius: 4px; min-height: 30px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }")
        outer.addWidget(self.scroll, 1)
        self.tab = "queue"
        self._state = None
        self._style_tabs()

    def _tab_button(self, text):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFlat(True)
        return b

    def _style_tabs(self):
        for b, name in ((self.tab_queue, "queue"), (self.tab_recent, "recent")):
            active = self.tab == name
            b.setStyleSheet(
                "QPushButton { background: transparent; border: none; padding: 4px 2px 6px 2px; margin-right: 14px;"
                f" font-size: 15px; font-weight: bold; color: {'white' if active else '#b3b3b3'};"
                f" border-bottom: 2px solid {'#1db954' if active else 'transparent'}; }}"
                "QPushButton:hover { color: white; }")

    def set_tab(self, name):
        self.tab = name
        self._style_tabs()
        if self._state is not None:
            self.refresh(*self._state)

    # ------------------------------------------------------------------
    @staticmethod
    def _section(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: white; font-size: 16px; font-weight: bold; padding: 14px 0 4px 8px;")
        lbl.setWordWrap(True)
        return lbl

    def refresh(self, current_song, user_queue, upcoming, source_name, recent):
        """Rebuild the visible list. Cheap enough for ~60 rows."""
        self._state = (current_song, user_queue, upcoming, source_name, recent)
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 4, 0)
        v.setSpacing(0)

        if self.tab == "queue":
            v.addWidget(self._section("Now playing"))
            if current_song is not None:
                v.addWidget(TrackRow(current_song, self._loader, current=True))
            else:
                v.addWidget(self._muted("Nothing playing yet."))
            pos = 0
            if user_queue:
                head = QHBoxLayout()
                head.addWidget(self._section("Next in queue"), 1)
                clear = QPushButton("Clear")
                clear.setCursor(Qt.CursorShape.PointingHandCursor)
                clear.setToolTip("Remove all songs you added to the queue")
                clear.setStyleSheet("QPushButton { color: #b3b3b3; border: none; background: transparent; font-weight: bold; padding: 14px 8px 0 0; }"
                                    "QPushButton:hover { color: white; }")
                clear.clicked.connect(self.clear_user_queue.emit)
                head.addWidget(clear)
                v.addLayout(head)
                for i, song in enumerate(user_queue[: self.MAX_ROWS]):
                    row = TrackRow(song, self._loader)
                    row.clicked.connect(lambda p=pos + i: self.play_upcoming.emit(p))
                    row.context_requested.connect(lambda gp, i=i: self._user_queue_menu(i, gp))
                    v.addWidget(row)
                pos = len(user_queue)
            if upcoming:
                v.addWidget(self._section(f"Next from: {source_name}" if source_name else "Next up"))
                for i, song in enumerate(upcoming[: max(0, self.MAX_ROWS - len(user_queue))]):
                    row = TrackRow(song, self._loader)
                    row.clicked.connect(lambda p=pos + i: self.play_upcoming.emit(p))
                    v.addWidget(row)
            elif current_song is not None and not user_queue:
                v.addWidget(self._muted("That's the end of the queue. Turn on repeat to keep going."))
        else:
            if not recent:
                v.addWidget(self._muted("Songs you play will show up here."))
            for song in list(recent)[: self.MAX_ROWS]:
                row = TrackRow(song, self._loader, current=(song == current_song))
                row.clicked.connect(lambda s=song: self.play_recent.emit(s))
                v.addWidget(row)
        v.addStretch()
        self.scroll.setWidget(content)

    @staticmethod
    def _muted(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #b3b3b3; font-size: 13px; padding: 4px 8px;")
        lbl.setWordWrap(True)
        return lbl

    def _user_queue_menu(self, index, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction("✕  Remove from queue").triggered.connect(lambda: self.remove_from_queue.emit(index))
        menu.exec(global_pos)

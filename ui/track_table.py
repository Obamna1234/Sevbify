"""Spotify-style track list (# / Title / Artist / Album / Duration).

Used by the Your Library, Search and playlist pages.
"""
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt6.QtGui import QColor, QBrush, QIcon, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from core.models import format_time

SONG_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1

GREEN = QColor("#1db954")
WHITE = QColor("#ffffff")
GREY = QColor("#b3b3b3")
DIM = QColor("#6a6a6a")

TABLE_STYLE = """
QTableWidget { background: #121212; color: white; border: none; font-size: 13px; outline: 0; }
QTableWidget::item { padding: 6px 8px; border: none; }
QTableWidget::item:hover { background: #2a2a2a; }
QTableWidget::item:selected { background: #3e3e3e; color: white; }
QHeaderView::section { background: #121212; color: #b3b3b3; border: none;
    border-bottom: 1px solid #2a2a2a; padding: 6px 8px; font-size: 12px; text-align: left; }
QScrollBar:vertical { background: #121212; width: 10px; }
QScrollBar::handle:vertical { background: #4d4d4d; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


_thumbs = {}


def _thumb(path, size=36):
    """Small square cover icon, cached (tables can have thousands of rows)."""
    key = (path, size)
    icon = _thumbs.get(key)
    if icon is None:
        pm = QPixmap(path) if path else QPixmap()
        if pm.isNull():
            from core.paths import PLACEHOLDER_IMAGE
            pm = QPixmap(PLACEHOLDER_IMAGE)
        if not pm.isNull():
            pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation).copy(0, 0, size, size)
        icon = QIcon(pm)
        if len(_thumbs) > 3000:
            _thumbs.clear()
        _thumbs[key] = icon
    return icon


class _SortableItem(QTableWidgetItem):
    """Item that sorts by SORT_ROLE when present (numbers sort numerically)."""

    def __lt__(self, other):
        a, b = self.data(SORT_ROLE), other.data(SORT_ROLE)
        if a is not None and b is not None:
            return a < b
        return super().__lt__(other)


class TrackTable(QTableWidget):
    play_requested = pyqtSignal(object, list)          # song, songs in current view order
    context_requested = pyqtSignal(object, int, object)  # song, row, global QPoint

    COLUMNS = ["#", "Title", "Artist", "Album", "🕒"]

    def __init__(self, sortable: bool = False, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setStyleSheet(TABLE_STYLE)
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(48)
        self.setIconSize(QSize(36, 36))
        self.setWordWrap(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        header = self.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setHighlightSections(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 48)
        self.setColumnWidth(2, 200)
        self.setColumnWidth(3, 220)
        self.setColumnWidth(4, 96)

        self._sortable = sortable
        self.setSortingEnabled(False)
        if sortable:
            header.setSortIndicatorShown(True)
            header.setSectionsClickable(True)
            header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)  # start in file order

        self._current_key = None
        self.mark_pending = False      # playlists: show "⬇" on songs not downloaded yet
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context)
        self.cellDoubleClicked.connect(self._on_double_click)

    # ------------------------------------------------------------------
    def set_songs(self, songs):
        self.setSortingEnabled(False)
        self.setRowCount(len(songs))
        for row, song in enumerate(songs):
            num = _SortableItem(str(row + 1))
            num.setData(SORT_ROLE, row)
            num.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            title = _SortableItem(song.title)
            title.setIcon(_thumb(song.album_cover_path))
            title.setData(SONG_ROLE, song)
            title.setData(SORT_ROLE, song.title.casefold())
            artist = _SortableItem(song.artist)
            artist.setData(SORT_ROLE, song.artist.casefold())
            album = _SortableItem(song.album)
            album.setData(SORT_ROLE, song.album.casefold())
            dur = _SortableItem(format_time(song.duration) if song.duration else "--:--")
            dur.setData(SORT_ROLE, song.duration)
            for col, item in enumerate((num, title, artist, album, dur)):
                self.setItem(row, col, item)
            if getattr(song, "is_remote", False):
                tip = "Not in your library: plays as a 30-second preview" if song.is_preview else "Not in your library: plays online"
                if self.mark_pending:
                    title.setText(f"{song.title}   ⬇")
                    tip = ("Not downloaded yet (needed for offline listening). It fills in here automatically "
                           "when the song appears in your music folders.\n" + tip)
                for item in (num, title, artist, album, dur):
                    item.setToolTip(tip)
                dur.setText((format_time(song.duration) if song.duration else "--:--") + ("  · 30s" if song.is_preview else ""))
            elif not song.exists:
                title.setText(f"{song.title}  (file missing)")
                for item in (num, title, artist, album, dur):
                    item.setForeground(QBrush(DIM))
                    item.setToolTip(f"File not found:\n{song.file_path}")
        if self._sortable:
            self.setSortingEnabled(True)
        self._apply_highlight()

    def refresh_artwork(self):
        """Re-apply cover icons (e.g. after online covers finished downloading)."""
        for row in range(self.rowCount()):
            song = self.song_at(row)
            if song is not None:
                self.item(row, 1).setIcon(_thumb(song.album_cover_path))

    def song_at(self, row):
        item = self.item(row, 1)
        return item.data(SONG_ROLE) if item else None

    def songs_in_view(self):
        return [self.song_at(r) for r in range(self.rowCount())]

    def set_current(self, song):
        self._current_key = song.key if song else None
        self._apply_highlight()

    def _apply_highlight(self):
        for row in range(self.rowCount()):
            song = self.song_at(row)
            if song is None or (not song.exists and not getattr(song, "is_remote", False)):
                continue
            current = song.key == self._current_key
            self.item(row, 1).setForeground(QBrush(GREEN if current else WHITE))
            self.item(row, 0).setForeground(QBrush(GREEN if current else GREY))
            for col in (2, 3, 4):
                self.item(row, col).setForeground(QBrush(GREY))

    # ------------------------------------------------------------------
    def _on_double_click(self, row, _col):
        song = self.song_at(row)
        if song is not None:
            self.play_requested.emit(song, self.songs_in_view())

    def _on_context(self, pos):
        row = self.rowAt(pos.y())
        song = self.song_at(row) if row >= 0 else None
        if song is not None:
            self.selectRow(row)
            self.context_requested.emit(song, row, self.viewport().mapToGlobal(pos))

"""Spotify-style track list (# / Title / Artist / Album / Duration).

Used by the Your Library, Search and playlist pages.
"""
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QApplication
from PyQt6.QtGui import QColor, QBrush, QIcon, QPixmap, QDrag
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QMimeData, QPoint

from core.models import format_time

SONG_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1
NUMBER_ROLE = Qt.ItemDataRole.UserRole + 2

# Songs being dragged out of a song list (read by whatever they are dropped on, e.g. a playlist on the left).
SONGS_MIME = "application/x-sevbify-songs"
dragged_songs = []

GREEN = QColor("#1db954")
WHITE = QColor("#ffffff")
GREY = QColor("#b3b3b3")
DIM = QColor("#6a6a6a")

TABLE_STYLE = """
QTableWidget { background: transparent; color: white; border: none; font-size: 14px; outline: 0;
    selection-background-color: #3e3e3e; selection-color: white; }
QTableWidget::item { padding: 6px 8px; border: none; }
QTableWidget::item:hover { background: #2a2a2a; }
QTableWidget::item:selected, QTableWidget::item:selected:active, QTableWidget::item:selected:!active {
    background: #3e3e3e; color: white; }
QHeaderView { background: transparent; }
QHeaderView::section { background: transparent; color: #b3b3b3; border: none;
    border-bottom: 1px solid rgba(255,255,255,0.1); padding: 6px 8px; font-size: 13px; text-align: left; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #4d4d4d; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTableCornerButton::section { background: transparent; border: none; }
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
    rows_moved = pyqtSignal(int, int)                  # drag to reorder (playlists): from row, to row
    files_dropped = pyqtSignal(list, int)              # files/folders dropped from Explorer: paths, at row

    COLUMNS = ["#", "Title", "Artist", "Album", ""]

    def __init__(self, sortable: bool = False, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)
        from . import icons
        clock = QTableWidgetItem(icons.clock("#b3b3b3", 16), "")
        clock.setToolTip("Duration")
        self.setHorizontalHeaderItem(4, clock)
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
        # Set by the main window: key -> (state, note) from the download manager, so rows can show
        # "Queued", "Downloading…" or "Download failed".
        self.download_state = None
        self.reorder_enabled = False   # playlists: drag rows to change the order
        self.accept_files = False      # playlists: drop audio files / folders from Explorer
        self._hover_row = -1
        self._press_pos = None
        self._press_row = -1
        self._drop_row = -1
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)   # we handle dragging ourselves
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
            num.setData(NUMBER_ROLE, str(row + 1))
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
                state, note = self.download_state(song.track.key) if self.download_state else (None, "")
                label = {"queued": "   · Queued to download", "downloading": "   · Downloading…",
                         "failed": "   · Download failed"}.get(state)
                if label:
                    title.setText(song.title + label)
                    if state == "failed":
                        tip = f"Download failed: {note}. Right-click → Retry download.\n" + tip
                elif self.mark_pending:
                    title.setText(f"{song.title}   ⬇")
                if self.mark_pending:
                    tip = ("Not downloaded yet (needed for offline listening). Right-click → Download, or it "
                           "fills in here by itself when the song appears in your music folders.\n" + tip)
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
        self._hover_row = -1
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
            if getattr(song, "is_remote", False) and self.mark_pending and not current:
                # Not downloaded yet: greyed out so it's obvious, online or offline.
                for col in range(5):
                    self.item(row, col).setForeground(QBrush(DIM))
                continue
            self.item(row, 1).setForeground(QBrush(GREEN if current else WHITE))
            self.item(row, 0).setForeground(QBrush(GREEN if current else GREY))
            for col in (2, 3, 4):
                self.item(row, col).setForeground(QBrush(GREY))

    # --- hover ▶, click to play, click empty space to deselect -----------------------------------------------
    PLAY_GLYPH = "▶"

    def _set_hover(self, row):
        if row == self._hover_row:
            return
        old = self.item(self._hover_row, 0) if self._hover_row >= 0 else None
        if old is not None:
            old.setText(old.data(NUMBER_ROLE) or old.text())
        self._hover_row = row
        new = self.item(row, 0) if row >= 0 else None
        if new is not None and self.song_at(row) is not None:
            new.setText(self.PLAY_GLYPH)
            new.setToolTip(f"Play {self.song_at(row).title}")

    def mouseMoveEvent(self, e):
        self._set_hover(self.rowAt(e.position().toPoint().y()))
        if (self._press_pos is not None and e.buttons() & Qt.MouseButton.LeftButton and self._press_row >= 0
                and (e.position().toPoint() - self._press_pos).manhattanLength() >= QApplication.startDragDistance()):
            self._start_drag(self._press_row)
            self._press_pos = None
            return
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._set_hover(-1)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        row = self.rowAt(pos.y())
        if row < 0:
            self.clearSelection()                    # clicking empty space un-selects, like Spotify
            self._press_pos = None
            return
        self._press_pos, self._press_row = pos, row
        if e.button() == Qt.MouseButton.LeftButton and self.columnAt(pos.x()) == 0:
            song = self.song_at(row)
            if song is not None:                     # the ▶ next to the number plays straight away
                self.selectRow(row)
                self.play_requested.emit(song, self.songs_in_view())
                return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._press_pos = None
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.clearSelection()
            return
        super().keyPressEvent(e)

    # --- drag and drop ------------------------------------------------------------------------------
    def _start_drag(self, row):
        global dragged_songs
        song = self.song_at(row)
        if song is None:
            return
        dragged_songs = [song]
        mime = QMimeData()
        mime.setData(SONGS_MIME, str(row).encode())
        mime.setText(f"{song.artist} - {song.title}")
        drag = QDrag(self)
        drag.setMimeData(mime)
        icon = self.item(row, 1).icon()
        if not icon.isNull():
            drag.setPixmap(icon.pixmap(36, 36))
        self._drag_source_row = row
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
        self._drag_source_row = -1

    def _drop_allowed(self, mime, from_self):
        if mime.hasFormat(SONGS_MIME) and from_self:
            return self.reorder_enabled
        return self.accept_files and mime.hasUrls()

    def dragEnterEvent(self, e):
        if self._drop_allowed(e.mimeData(), e.source() is self):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._drop_allowed(e.mimeData(), e.source() is self):
            row = self.rowAt(e.position().toPoint().y())
            self._drop_row = self.rowCount() if row < 0 else row
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        mime = e.mimeData()
        row = self.rowAt(e.position().toPoint().y())
        target = self.rowCount() if row < 0 else row
        if mime.hasFormat(SONGS_MIME) and e.source() is self and self.reorder_enabled:
            src = int(bytes(mime.data(SONGS_MIME)).decode() or -1)
            if src >= 0 and target != src:
                self.rows_moved.emit(src, min(target, self.rowCount() - 1))
            e.acceptProposedAction()
        elif self.accept_files and mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths, target)
            e.acceptProposedAction()
        else:
            e.ignore()

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

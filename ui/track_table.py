"""Spotify-style track list (# / Title / Artist / Album / Duration).

Used by the Your Library, Search and playlist pages.
"""
from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QApplication,
                             QStyledItemDelegate, QStyle)
from PyQt6.QtGui import QColor, QBrush, QIcon, QPixmap, QDrag, QPainter, QPainterPath, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QMimeData, QPoint, QRectF

from core.models import format_time

SONG_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1
NUMBER_ROLE = Qt.ItemDataRole.UserRole + 2

# Songs being dragged out of a song list (read by whatever they are dropped on, e.g. a playlist on the left).
SONGS_MIME = "application/x-sevbify-songs"
dragged_songs = []
# The songs a right-click menu is for when several rows are selected (Shift / Ctrl + click), else [].
menu_selection = []
menu_selection_rows = []

GREEN = QColor("#1db954")
WHITE = QColor("#ffffff")
GREY = QColor("#b3b3b3")
DIM = QColor("#6a6a6a")

ROW_HOVER = QColor("#2a2a2a")
ROW_SELECTED = QColor("#5a5a5a")

# Row backgrounds are painted by RowDelegate (the whole row at once, rounded ends like Spotify); the stylesheet
# only sets text and spacing. beta.6 used ::item:hover, which lit up one cell at a time.
TABLE_STYLE = """
QTableWidget { background: transparent; color: white; border: none; font-size: 14px; outline: 0;
    selection-background-color: transparent; selection-color: white; }
QTableWidget::item { padding: 6px 8px; border: none; background: transparent; }
QTableWidget::item:selected, QTableWidget::item:selected:active, QTableWidget::item:selected:!active {
    background: transparent; color: white; }
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


class RowDelegate(QStyledItemDelegate):
    """Paints the hover / selected background for the whole row (rounded at both ends), the ▶ / number
    column, and the Title column as Spotify does: cover, title, and the artist on a second line."""

    def __init__(self, table):
        super().__init__(table)
        self.table = table

    def paint(self, painter, option, index):
        t = self.table
        row, col = index.row(), index.column()
        selected = t.selectionModel().isRowSelected(row, index.parent())
        hovered = row == t._hover_row
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected or hovered:
            r = QRectF(option.rect)
            first, last = col == 0, col == t.columnCount() - 1 or t.isColumnHidden(col + 1) and all(
                t.isColumnHidden(c) for c in range(col + 1, t.columnCount()))
            path = QPainterPath()
            radius = 4.0
            path.addRoundedRect(r.adjusted(0 if first else -radius * 2, 0, 0 if last else radius * 2, 0), radius, radius)
            painter.setClipRect(r)
            painter.fillPath(path, ROW_SELECTED if selected else ROW_HOVER)
            painter.setClipping(False)
        painter.restore()
        if col == 1 and t.two_line_titles:
            self._paint_title(painter, option, index)
            return
        opt = option.__class__(option)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_MouseOver
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, opt, index)

    def _paint_title(self, painter, option, index):
        t = self.table
        song = index.data(SONG_ROLE)
        rect = option.rect.adjusted(8, 0, -8, 0)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        size = 40
        if isinstance(icon, QIcon) and not icon.isNull():
            icon.paint(painter, rect.x(), rect.y() + (rect.height() - size) // 2, size, size)
        text_x = rect.x() + size + 12
        width = rect.right() - text_x
        title_colour = index.data(Qt.ItemDataRole.ForegroundRole)
        title_colour = title_colour.color() if isinstance(title_colour, QBrush) else WHITE
        painter.save()
        f = QFont(option.font)
        f.setPixelSize(15)
        painter.setFont(f)
        painter.setPen(title_colour)
        fm = painter.fontMetrics()
        title = fm.elidedText(index.data(Qt.ItemDataRole.DisplayRole) or "", Qt.TextElideMode.ElideRight, width)
        mid = rect.y() + rect.height() // 2
        painter.drawText(text_x, mid - 4, title)
        f2 = QFont(option.font)
        f2.setPixelSize(13)
        painter.setFont(f2)
        dim = title_colour == DIM
        painter.setPen(DIM if dim else GREY)
        artist = getattr(song, "artist", "") if song is not None else ""
        painter.drawText(text_x, mid + 15, painter.fontMetrics().elidedText(artist, Qt.TextElideMode.ElideRight, width))
        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), 56 if self.table.two_line_titles else 48))


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
    delete_requested = pyqtSignal(list)                # Delete key on selected rows (playlists remove them)

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
        # Click selects a song, Shift+click selects everything between, Ctrl+click adds or removes one.
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)   # Ctrl+A / Delete / Esc work after clicking a song
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(48)
        self.setIconSize(QSize(36, 36))
        self.setWordWrap(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.two_line_titles = False      # Spotify's Title column: artist under the title (Artist column hidden)
        self.setItemDelegate(RowDelegate(self))

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
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)   # we handle dragging ourselves
        # After setDragDropMode: it switches drops off again, which made every drop from File Explorer show
        # the "not allowed" cursor in beta.6.
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context)
        self.cellDoubleClicked.connect(self._on_double_click)

    # ------------------------------------------------------------------
    def set_two_line_titles(self, on=True):
        """Spotify's playlist look: # | Title (with the artist underneath) | Album | time."""
        self.two_line_titles = bool(on)
        self.setColumnHidden(2, self.two_line_titles)
        self.verticalHeader().setDefaultSectionSize(56 if on else 48)
        self.setIconSize(QSize(40, 40) if on else QSize(36, 36))
        if on:
            self.setColumnWidth(3, 280)
        self.viewport().update()

    def selected_songs(self):
        rows = sorted({i.row() for i in self.selectionModel().selectedRows()})
        return [s for s in (self.song_at(r) for r in rows) if s is not None]

    def selected_rows(self):
        return sorted({i.row() for i in self.selectionModel().selectedRows()})

    def set_songs(self, songs):
        self.setSortingEnabled(False)
        keep = {getattr(s, "key", None) for s in self.selected_songs()} if self.rowCount() else set()
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
                         "failed": "   · Download failed", "stopped": "   · Download stopped"}.get(state)
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
        if keep:                                       # a refresh (e.g. a download finished) keeps the selection
            self.clearSelection()
            for row in range(self.rowCount()):
                song = self.song_at(row)
                if song is not None and song.key in keep:
                    self.selectionModel().select(self.model().index(row, 0),
                                                 self.selectionModel().SelectionFlag.Select |
                                                 self.selectionModel().SelectionFlag.Rows)

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
        old_row, self._hover_row = self._hover_row, row
        for r in (old_row, row):                       # repaint both whole rows (not one cell)
            if r >= 0:
                top = self.visualRect(self.model().index(r, 0)).top()
                self.viewport().update(0, top, self.viewport().width(), self.rowHeight(r))
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
        mods = e.modifiers()
        if e.button() == Qt.MouseButton.RightButton and self.selectionModel().isRowSelected(row, self.rootIndex()):
            return                                     # right-click inside a selection keeps the selection
        if e.button() == Qt.MouseButton.LeftButton and self.columnAt(pos.x()) == 0 and not (
                mods & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier)):
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
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selected_rows():
            self.delete_requested.emit(self.selected_rows())
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.selected_songs():
            self.play_requested.emit(self.selected_songs()[0], self.songs_in_view())
            return
        if e.key() == Qt.Key.Key_Space:
            e.ignore()                                 # Space = play / pause (the window's shortcut)
            return
        super().keyPressEvent(e)

    # --- drag and drop ------------------------------------------------------------------------------
    def _start_drag(self, row):
        global dragged_songs
        song = self.song_at(row)
        if song is None:
            return
        chosen = self.selected_songs()
        dragged_songs = chosen if (song in chosen and len(chosen) > 1) else [song]
        mime = QMimeData()
        mime.setData(SONGS_MIME, str(row).encode())
        mime.setText("\n".join(f"{s.artist} - {s.title}" for s in dragged_songs))
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
        global menu_selection, menu_selection_rows
        row = self.rowAt(pos.y())
        song = self.song_at(row) if row >= 0 else None
        if song is not None:
            if not self.selectionModel().isRowSelected(row, self.rootIndex()):
                self.selectRow(row)
            chosen = self.selected_songs()
            menu_selection = chosen if len(chosen) > 1 else []
            menu_selection_rows = self.selected_rows() if len(chosen) > 1 else []
            try:
                self.context_requested.emit(song, row, self.viewport().mapToGlobal(pos))
            finally:
                menu_selection, menu_selection_rows = [], []

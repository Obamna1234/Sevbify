"""Left 'Your Library' panel, laid out like Spotify's.

Header: collapse button + "Your Library", + Create (Playlist / Folder), expand button.
Chips: Playlists, Albums, Artists, Downloaded, To download. A search button that opens a filter box, and a
sort/view button (Recents / Recently added / Alphabetical; Compact / List / Grid).
Rows: Your Songs and To download (pinned), folders (open/close) with their playlists, playlists; albums and
artists under their chips. Collapsed, the panel is a thin strip of covers; expanded, it fills the window as a grid.
"""
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QScrollArea, QLineEdit,
    QSizePolicy, QMenu
)
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QFont, QPainterPath, QActionGroup
from PyQt6.QtCore import Qt, QSize, QRectF, pyqtSignal, QTimer

from . import icons, theme

MENU_STYLE = (f"QMenu {{ background: #282828; color: white; border: 1px solid #3e3e3e; padding: 4px; font-size: 13px; }}"
              f" QMenu::item {{ padding: 8px 24px 8px 12px; border-radius: 3px; }}"
              f" QMenu::item:selected {{ background: #3e3e3e; }} QMenu::item:checked {{ color: {theme.GREEN}; }}"
              f" QMenu::section {{ color: #b3b3b3; padding: 8px 12px 4px 12px; font-size: 11px; }}"
              f" QMenu::separator {{ height: 1px; background: #3e3e3e; margin: 4px 0; }}")

SORTS = (("recents", "Recents"), ("added", "Recently added"), ("alpha", "Alphabetical"))
VIEWS = (("compact", "Compact"), ("list", "List"), ("grid", "Grid"))
CHIPS = (("playlists", "Playlists"), ("podcasts", "Podcasts"), ("audiobooks", "Audiobooks"), ("albums", "Albums"), ("artists", "Artists"), ("downloaded", "Downloaded"),
         ("todownload", "To download"))
COLLAPSED_WIDTH = 72


def gradient_cover(size, top, bottom, glyph):
    """Square cover with a colour gradient and a symbol (for built-in lists)."""
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), 4, 4)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor(top)); g.setColorAt(1, QColor(bottom))
    p.fillPath(path, g)
    p.setPen(QColor("white"))
    f = QFont(theme.FONT_FAMILY); f.setPixelSize(int(size * 0.42)); f.setWeight(QFont.Weight.Bold)
    p.setFont(f)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, glyph)
    p.end()
    return pm


def folder_cover(size):
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), 4, 4)
    p.fillPath(path, QColor(theme.HOVER))
    icon = icons.folder(theme.SUBDUED, int(size * 0.5)).pixmap(int(size * 0.5), int(size * 0.5))
    p.drawPixmap(int(size * 0.25), int(size * 0.25), icon)
    p.end()
    return pm


def rounded(pm: QPixmap, size, radius=4):
    out = QPixmap(size * 2, size * 2)
    out.setDevicePixelRatio(2.0)
    out.fill(Qt.GlobalColor.transparent)
    if pm.isNull():
        return out
    scaled = pm.scaled(size * 2, size * 2, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                       Qt.TransformationMode.SmoothTransformation)
    scaled.setDevicePixelRatio(2.0)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, scaled)
    p.end()
    return out


ORIGIN_COLOURS = {"": "#509bf5", "file": "#af7bff"}      # made in Sevbify: blue; from a file: purple
LINK_COLOUR = "#ffa42b"                                   # imported from a link (Spotify / Apple Music): orange


def origin_colour(origin):
    return ORIGIN_COLOURS.get(origin or "", LINK_COLOUR)


def with_ring(pm: QPixmap, size, colour, radius=4, width=None):
    """The picture with a coloured border (Settings ▸ "Show where playlists came from")."""
    width = width or (2 if size < 100 else 4)
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = p.pen()
    pen.setColor(QColor(colour))
    pen.setWidthF(width)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    half = width / 2
    p.drawRoundedRect(QRectF(half, half, size - width, size - width), radius, radius)
    p.end()
    return out


def circle(pm: QPixmap, size):
    """Round picture, used for artists (like Spotify)."""
    return rounded(pm, size, size / 2)


class LibraryRow(QFrame):
    """One item in Your Library: a row (list / compact), a tile (grid) or just a cover (collapsed)."""
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    context_requested = pyqtSignal(object)
    songs_dropped = pyqtSignal(list)          # songs dragged from a song list onto this playlist
    files_dropped = pyqtSignal(list)          # files / folders dragged from Explorer onto this playlist
    accepts_drops = False

    def __init__(self, pixmap, title, subtitle, active=False, playing=False, mode="list", indent=0, tile=160,
                 trailing=""):
        super().__init__()
        self.setObjectName("libRow")
        self.mode = mode
        self.title_text = title
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{title}\n{subtitle}" if mode == "collapsed" else "")
        self._base = (f"#libRow {{ background: {theme.HOVER if active else 'transparent'}; border-radius: 6px; }}"
                      f" #libRow:hover {{ background: {theme.SELECTED if active else theme.ELEVATED}; }}")
        self.setStyleSheet(self._base)
        title_style = (f"color: {theme.GREEN if playing else theme.TEXT}; font-size: {14 if mode == 'compact' else 15}px;"
                       f" font-weight: 500; background: transparent;")
        sub_style = f"color: {theme.SUBDUED}; font-size: 13px; background: transparent;"

        if mode == "collapsed":
            h = QHBoxLayout(self)
            h.setContentsMargins(4, 4, 4, 4)
            art = QLabel()
            art.setFixedSize(48, 48)
            art.setPixmap(pixmap)
            h.addWidget(art, 0, Qt.AlignmentFlag.AlignCenter)
            return

        if mode == "grid":
            self.setFixedWidth(tile)
            v = QVBoxLayout(self)
            v.setContentsMargins(8, 8, 8, 8)
            v.setSpacing(4)
            art = QLabel()
            art.setFixedSize(tile - 16, tile - 16)
            art.setPixmap(pixmap)
            v.addWidget(art)
            for text, style in ((title, title_style), (subtitle, sub_style)):
                lbl = QLabel(text)
                lbl.setStyleSheet(style)
                lbl.setText(lbl.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, tile - 16))
                lbl.setToolTip(text)
                v.addWidget(lbl)
            return

        h = QHBoxLayout(self)
        compact = mode == "compact"
        h.setContentsMargins(8 + indent, 4 if compact else 8, 8, 4 if compact else 8)
        h.setSpacing(12)
        if not compact:
            art = QLabel()
            art.setFixedSize(48, 48)
            art.setPixmap(pixmap)
            h.addWidget(art)
        v = QVBoxLayout()
        v.setSpacing(2)
        t = QLabel()
        t.setStyleSheet(title_style)
        sub = QLabel()
        sub.setStyleSheet(sub_style)
        width = 150 if compact else 200
        if compact:
            # Compact: "Title • Playlist" on one line, no cover, like Spotify.
            t.setText(t.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, width))
            sub.setText(sub.fontMetrics().elidedText("• " + subtitle.split(" • ")[0], Qt.TextElideMode.ElideRight, 90))
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(t)
            row.addWidget(sub)
            row.addStretch()
            v.addLayout(row)
        else:
            for lbl, text in ((t, title), (sub, subtitle)):
                lbl.setText(lbl.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width))
                lbl.setToolTip(text)
                lbl.setMinimumWidth(0)
                lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            v.addWidget(t)
            v.addWidget(sub)
        h.addLayout(v, 1)
        if playing:
            note = QLabel("♪")
            note.setStyleSheet(f"color: {theme.GREEN}; font-size: 16px; background: transparent;")
            h.addWidget(note)
        if trailing:
            arrow = QLabel(trailing)
            arrow.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px; background: transparent;")
            h.addWidget(arrow)

    # Qt finishes its own handling first, then we tell the app: the app may rebuild the list and delete this
    # row, and touching a deleted row would raise "wrapped C/C++ object ... has been deleted".
    def mouseReleaseEvent(self, e):
        left = e.button() == Qt.MouseButton.LeftButton
        super().mouseReleaseEvent(e)
        if left:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, e):
        super().mouseDoubleClickEvent(e)
        self.double_clicked.emit()

    def contextMenuEvent(self, e):
        self.context_requested.emit(e.globalPos())

    # Drop songs or files on a playlist in the list, like Spotify.
    def enable_drops(self):
        self.accepts_drops = True
        self.setAcceptDrops(True)

    def _wanted(self, mime):
        from .track_table import SONGS_MIME
        return self.accepts_drops and (mime.hasFormat(SONGS_MIME) or mime.hasUrls())

    def dragEnterEvent(self, e):
        if self._wanted(e.mimeData()):
            e.acceptProposedAction()
            self.setStyleSheet(self._base + f" #libRow {{ border: 1px solid {theme.GREEN}; }}")
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.setStyleSheet(self._base)

    def dropEvent(self, e):
        from . import track_table
        self.dragLeaveEvent(e)
        mime = e.mimeData()
        if not self._wanted(mime):
            e.ignore()
            return
        e.acceptProposedAction()
        if mime.hasFormat(track_table.SONGS_MIME):
            self.songs_dropped.emit(list(track_table.dragged_songs))
        else:
            self.files_dropped.emit([u.toLocalFile() for u in mime.urls() if u.isLocalFile()])


class LibraryPanel(QFrame):
    create_clicked = pyqtSignal()                    # Create → Playlist
    create_folder_clicked = pyqtSignal()             # Create → Folder
    import_clicked = pyqtSignal()                    # Create → Import a playlist
    open_all_songs = pyqtSignal()
    open_saved = pyqtSignal()
    open_playlist = pyqtSignal(object)
    play_playlist = pyqtSignal(object)
    playlist_menu = pyqtSignal(object, object)       # playlist, global pos
    folder_menu = pyqtSignal(str, object)            # folder name, global pos
    songs_dropped = pyqtSignal(object, list)         # playlist, songs
    files_dropped = pyqtSignal(object, list)         # playlist, file paths
    open_album = pyqtSignal(object)                  # album dict
    play_album = pyqtSignal(object)
    open_artist = pyqtSignal(object)                 # artist dict
    open_show = pyqtSignal(object)                   # followed podcast / saved audiobook (entry dict)
    play_artist = pyqtSignal(object)
    view_changed = pyqtSignal()                      # sort / view / collapsed changed (save it)
    expand_changed = pyqtSignal(bool)                # Your Library filling the window, or back
    settings_clicked = pyqtSignal()

    def __init__(self, cover_loader, parent=None):
        super().__init__(parent)
        self._cover = cover_loader
        self.setObjectName("libraryPanel")
        self.setStyleSheet(theme.panel_style("libraryPanel"))
        self.sort, self.view, self.collapsed, self.expanded = "recents", "list", False, False
        self.chip = None
        self.show_origin = False          # Settings: coloured border = where each playlist came from
        self._open_folders = set()
        self._grid_columns = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 12, 8, 8)
        v.setSpacing(8)

        # --- header -----------------------------------------------------------------------------------
        self.head = QWidget()
        head = QHBoxLayout(self.head)
        head.setContentsMargins(4, 0, 0, 0)
        head.setSpacing(4)
        self.collapse_btn = self._icon_btn(icons.library(theme.SUBDUED, 24), "Collapse Your Library", 32)
        self.collapse_btn.clicked.connect(lambda: self.set_collapsed(not self.collapsed))
        head.addWidget(self.collapse_btn)
        self.title_btn = QPushButton("Your Library")
        self.title_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title_btn.setToolTip("Collapse Your Library")
        self.title_btn.setStyleSheet(f"QPushButton {{ color: {theme.TEXT}; background: transparent; border: none;"
                                     f" font-size: 16px; font-weight: 700; text-align: left; }}"
                                     f" QPushButton:hover {{ color: {theme.TEXT}; }}")
        self.title_btn.clicked.connect(lambda: self.set_collapsed(True))
        head.addWidget(self.title_btn)
        head.addStretch()
        self.create_btn = QPushButton(" Create")
        self.create_btn.setIcon(icons.plus(theme.TEXT, 16))
        self.create_btn.setToolTip("Create a playlist or folder")
        self.create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_btn.setFixedHeight(32)
        self.create_btn.setStyleSheet(f"QPushButton {{ background: {theme.ELEVATED}; color: {theme.TEXT}; border: none;"
                                      f" border-radius: 16px; padding: 0 14px; font-weight: 700; font-size: 14px; }}"
                                      f" QPushButton:hover {{ background: {theme.HOVER}; }}")
        self.create_btn.clicked.connect(self._show_create_menu)
        head.addWidget(self.create_btn)
        self.expand_btn = self._icon_btn(icons.expand(theme.SUBDUED, 18, out=True), "Expand Your Library", 32)
        self.expand_btn.clicked.connect(lambda: self.set_expanded(not self.expanded))
        head.addWidget(self.expand_btn)
        v.addWidget(self.head)

        # collapsed header: library icon + "+" stacked
        self.mini_head = QWidget()
        mh = QVBoxLayout(self.mini_head)
        mh.setContentsMargins(0, 0, 0, 0)
        mh.setSpacing(8)
        self.open_btn = self._icon_btn(icons.library(theme.SUBDUED, 24), "Open Your Library", 40)
        self.open_btn.clicked.connect(lambda: self.set_collapsed(False))
        mini_create = self._icon_btn(icons.plus(theme.SUBDUED, 18), "Create a playlist or folder", 40)
        mini_create.clicked.connect(self._show_create_menu)
        self._mini_create = mini_create
        mh.addWidget(self.open_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        mh.addWidget(mini_create, 0, Qt.AlignmentFlag.AlignHCenter)
        self.mini_head.hide()
        v.addWidget(self.mini_head)

        # --- chips --------------------------------------------------------------------------------------
        self.chips_box = QWidget()
        chips = QHBoxLayout(self.chips_box)
        chips.setContentsMargins(0, 4, 0, 0)
        chips.setSpacing(4)
        self.clear_chip_btn = self._icon_btn(icons.chevron("left", theme.TEXT, 16), "Show everything", 28)
        self.clear_chip_btn.setStyleSheet(self.clear_chip_btn.styleSheet().replace("transparent", theme.HOVER, 1))
        self.clear_chip_btn.clicked.connect(lambda: self.set_chip(None))
        self.clear_chip_btn.hide()
        chips.addWidget(self.clear_chip_btn)
        self.chip_buttons = {}
        for key, text in CHIPS:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(30)
            # Rounded pill (a radius bigger than half the height made Qt draw square corners in beta.6)
            b.setStyleSheet(theme.CHIP.replace("padding: 6px 12px", "padding: 4px 12px")
                            .replace("border-radius: 16px", "border-radius: 15px").replace("font-size: 13px", "font-size: 13px"))
            b.clicked.connect(lambda checked, k=key: self.set_chip(k if checked else None))
            chips.addWidget(b)
            self.chip_buttons[key] = b
        chips.addStretch()
        self.chips_scroll = QScrollArea()
        self.chips_scroll.setWidget(self.chips_box)
        self.chips_scroll.setWidgetResizable(True)
        self.chips_scroll.setFixedHeight(40)
        self.chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chips_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        v.addWidget(self.chips_scroll)
        # Spotify's ‹ › buttons at the ends of the chip row when not every chip fits.
        self.chips_next = self._icon_btn(icons.chevron("right", theme.TEXT, 16), "More filters", 30)
        self.chips_prev = self._icon_btn(icons.chevron("left", theme.TEXT, 16), "Back", 30)
        for btn, step in ((self.chips_next, 1), (self.chips_prev, -1)):
            btn.setParent(self.chips_scroll)
            btn.setStyleSheet(f"QPushButton {{ background: {theme.HOVER}; border: none; border-radius: 15px; }}"
                              f" QPushButton:hover {{ background: {theme.SELECTED}; }}")
            btn.clicked.connect(lambda _=False, st=step: self._scroll_chips(st))
            btn.hide()
        self.chips_scroll.horizontalScrollBar().valueChanged.connect(lambda _v: self._place_chip_arrows())
        self.chips_scroll.horizontalScrollBar().rangeChanged.connect(lambda *_: self._place_chip_arrows())
        # older code: .chip_playlists / .chip_saved
        self.chip_playlists = self.chip_buttons["playlists"]
        self.chip_saved = self.chip_buttons["todownload"]

        # --- search + sort/view row ---------------------------------------------------------------------
        self.tools = QWidget()
        tools = QHBoxLayout(self.tools)
        tools.setContentsMargins(4, 0, 0, 0)
        tools.setSpacing(4)
        self.search_btn = self._icon_btn(icons.search(theme.SUBDUED, 18), "Search in Your Library", 32)
        self.search_btn.clicked.connect(self.show_filter)
        tools.addWidget(self.search_btn)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search in Your Library")
        self.filter_edit.addAction(icons.search(theme.SUBDUED, 18), QLineEdit.ActionPosition.LeadingPosition)
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setFixedHeight(32)
        self.filter_edit.setStyleSheet(f"QLineEdit {{ background: {theme.HOVER}; color: {theme.TEXT}; border: none;"
                                       f" border-radius: 4px; padding: 0 6px; font-size: 13px; }}")
        self.filter_edit.textChanged.connect(lambda _t: self._rebuild())
        self.filter_edit.editingFinished.connect(self._maybe_hide_filter)
        self.filter_edit.hide()
        tools.addWidget(self.filter_edit, 1)
        tools.addStretch()
        self.sort_btn = QPushButton()
        self.sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.sort_btn.setIconSize(QSize(16, 16))
        self.sort_btn.setStyleSheet(f"QPushButton {{ color: {theme.SUBDUED}; background: transparent; border: none;"
                                    f" font-size: 13px; padding: 4px 6px; }} QPushButton:hover {{ color: {theme.TEXT}; }}")
        self.sort_btn.clicked.connect(self._show_sort_menu)
        tools.addWidget(self.sort_btn)
        v.addWidget(self.tools)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {theme.PANEL}; }}")
        v.addWidget(self.scroll, 1)

        self._state = dict(playlists=[], n_songs=0, n_saved=0, active=None, playing_source="", albums=[],
                           artists=[], folders=[])
        self._special_songs = gradient_cover(48, "#450af5", "#c4efd9", "♪")
        self._special_saved = gradient_cover(48, "#1ed760", "#0b5c33", "⬇")
        self._apply_width()
        self._update_sort_button()
        self._rebuild()

    # ------------------------------------------------------------------
    @staticmethod
    def _icon_btn(icon, tip, size):
        b = QPushButton()
        b.setIcon(icon)
        b.setIconSize(QSize(int(size * 0.6), int(size * 0.6)))
        b.setFixedSize(size, size)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-radius: {size // 2}px; }}"
                        f" QPushButton:hover {{ background: {theme.HOVER}; }}")
        return b

    def _menu(self):
        m = QMenu(self)
        m.setStyleSheet(MENU_STYLE)
        return m

    def _show_create_menu(self):
        m = self._menu()
        m.addAction(icons.plus(theme.TEXT, 18), "Playlist\nCreate a playlist with songs").triggered.connect(
            self.create_clicked.emit)
        m.addAction(icons.folder(theme.TEXT, 18), "Folder\nOrganise your playlists").triggered.connect(
            self.create_folder_clicked.emit)
        m.addSeparator()
        m.addAction(icons.download(theme.TEXT, 18), "Import a playlist\nFrom Spotify, Apple Music or a file").triggered.connect(
            self.import_clicked.emit)
        btn = self._mini_create if self.collapsed else self.create_btn
        m.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def build_sort_menu(self):
        m = self._menu()
        m.addSection("Sort by")
        group = QActionGroup(m)
        for key, label in SORTS:
            a = m.addAction(label)
            a.setCheckable(True)
            a.setChecked(key == self.sort)
            a.setActionGroup(group)
            a.triggered.connect(lambda _=False, k=key: self.set_view_options(sort=k))
        m.addSection("View as")
        group2 = QActionGroup(m)
        for key, label in VIEWS:
            a = m.addAction(label)
            a.setCheckable(True)
            a.setChecked(key == self.view)
            a.setActionGroup(group2)
            a.triggered.connect(lambda _=False, k=key: self.set_view_options(view=k))
        return m

    def _show_sort_menu(self):
        self.build_sort_menu().exec(self.sort_btn.mapToGlobal(self.sort_btn.rect().bottomLeft()))

    def _update_sort_button(self):
        self.sort_btn.setText(dict(SORTS)[self.sort])
        self.sort_btn.setIcon(icons.grid(theme.SUBDUED, 16) if self.view == "grid" else icons.sort_lines(theme.SUBDUED, 16))

    def show_filter(self):
        self.search_btn.hide()
        self.filter_edit.show()
        self.filter_edit.setFocus()
        self.filter_edit.selectAll()

    def _maybe_hide_filter(self):
        if not self.filter_edit.text():
            self.filter_edit.hide()
            self.search_btn.show()

    # --- options ------------------------------------------------------------------------------------
    def set_view_options(self, sort=None, view=None, collapsed=None, emit=True):
        if sort in dict(SORTS):
            self.sort = sort
        if view in dict(VIEWS):
            self.view = view
        if collapsed is not None:
            self.collapsed = bool(collapsed)
            self._apply_width()
        self._update_sort_button()
        self._rebuild()
        if emit:
            self.view_changed.emit()

    def set_collapsed(self, on):
        if on and self.expanded:
            self.set_expanded(False)
        self.set_view_options(collapsed=on)

    def set_expanded(self, on):
        self.expanded = bool(on)
        if on and self.collapsed:
            self.collapsed = False
        self.expand_btn.setIcon(icons.expand(theme.SUBDUED, 18, out=not self.expanded))
        self.expand_btn.setToolTip("Go back" if self.expanded else "Expand Your Library")
        self._apply_width()
        self._rebuild()
        self.expand_changed.emit(self.expanded)
        QTimer.singleShot(0, self._rebuild)          # again once the panel has its new width (grid columns)

    def _apply_width(self):
        full = not self.collapsed
        for w in (self.head, self.chips_scroll, self.tools):
            w.setVisible(full)
        self.mini_head.setVisible(self.collapsed)
        if self.collapsed:
            self.setMinimumWidth(COLLAPSED_WIDTH)
            self.setMaximumWidth(COLLAPSED_WIDTH)
        elif self.expanded:
            self.setMinimumWidth(260)
            self.setMaximumWidth(16777215)
        else:
            self.setMinimumWidth(290)
            self.setMaximumWidth(400)

    def set_chip(self, key):
        self.chip = key if key in self.chip_buttons else None
        for k, b in self.chip_buttons.items():
            b.setChecked(k == self.chip)
            b.setVisible(self.chip is None or k == self.chip)
        self.clear_chip_btn.setVisible(self.chip is not None)
        self._rebuild()

    # --- data ---------------------------------------------------------------------------------------
    def _scroll_chips(self, step):
        bar = self.chips_scroll.horizontalScrollBar()
        bar.setValue(bar.value() + step * max(80, self.chips_scroll.viewport().width() * 2 // 3))

    def _place_chip_arrows(self):
        bar = self.chips_scroll.horizontalScrollBar()
        h = self.chips_scroll.height()
        self.chips_next.move(self.chips_scroll.width() - 30, (h - 30) // 2 + 2)
        self.chips_prev.move(0, (h - 30) // 2 + 2)
        self.chips_next.setVisible(bar.maximum() > 0 and bar.value() < bar.maximum())
        self.chips_prev.setVisible(bar.maximum() > 0 and bar.value() > 0)
        self.chips_next.raise_()
        self.chips_prev.raise_()

    def set_items(self, playlists, n_songs, n_saved, playing_source="", albums=None, artists=None, folders=None,
                  shows=None):
        self._state.update(playlists=list(playlists), n_songs=n_songs, n_saved=n_saved,
                           playing_source=playing_source, albums=list(albums or []), artists=list(artists or []),
                           folders=list(folders or []), shows=list(shows or []))
        self._rebuild(background=True)

    def set_show_origin(self, on):
        if bool(on) != self.show_origin:
            self.show_origin = bool(on)
            self._rebuild()

    def set_active(self, key):
        """key: "library", "saved", a Playlist, ("album", key), ("artist", name), or None."""
        self._state["active"] = key
        self._rebuild()

    @staticmethod
    def is_downloaded(pl):
        return bool(pl.songs) and all(not getattr(s, "is_remote", False) and s.exists for s in pl.songs)

    def _sorted(self, items, name, recent, added):
        if self.sort == "alpha":
            return sorted(items, key=lambda x: name(x).casefold())
        if self.sort == "added":
            return sorted(items, key=added, reverse=True)
        return sorted(items, key=lambda x: (recent(x), added(x)), reverse=True)

    def entries(self):
        """What to show, in order, as dicts: kind, title, subtitle, obj, indent. (Used by the view and tests.)"""
        st = self._state
        query = self.filter_edit.text().strip().casefold()
        chip = self.chip

        def match(*texts):
            return not query or any(query in (t or "").casefold() for t in texts)

        out = []
        n = lambda count, word: f"{count} {word}{'s' if count != 1 else ''}"
        if chip in (None, "playlists", "downloaded") and match("Your Songs"):
            out.append(dict(kind="songs", title="Your Songs", subtitle=f"Library • {n(st['n_songs'], 'song')}",
                            obj=None, indent=0))
        if chip in (None, "todownload") and match("To download"):
            out.append(dict(kind="saved", title="To download",
                            subtitle=f"Not downloaded yet • {n(st['n_saved'], 'song')}", obj=None, indent=0))

        playlists = st["playlists"]
        if chip == "downloaded":
            playlists = [p for p in playlists if self.is_downloaded(p)]
        pl_recent = lambda p: p.last_played
        pl_added = lambda p: p.created

        if chip in (None, "playlists", "downloaded"):
            if query or chip == "downloaded":
                for pl in self._sorted([p for p in playlists if match(p.name)], lambda p: p.name, pl_recent, pl_added):
                    out.append(self._pl_entry(pl, 0))
            else:
                folder_names = [f for f in st["folders"]]
                loose = [p for p in playlists if not p.folder or p.folder not in folder_names]
                children = {f: [p for p in playlists if p.folder == f] for f in folder_names}
                tops = [("folder", f) for f in folder_names] + [("playlist", p) for p in loose]

                def name(t):
                    return t[1] if t[0] == "folder" else t[1].name

                def recent(t):
                    if t[0] == "folder":
                        return max([p.last_played for p in children[t[1]]] or [0])
                    return t[1].last_played

                def added(t):
                    if t[0] == "folder":
                        return max([p.created for p in children[t[1]]] or [0])
                    return t[1].created

                for kind, obj in self._sorted(tops, name, recent, added):
                    if kind == "playlist":
                        out.append(self._pl_entry(obj, 0))
                        continue
                    kids = children[obj]
                    is_open = obj in self._open_folders
                    out.append(dict(kind="folder", title=obj, subtitle=n(len(kids), "playlist"), obj=obj, indent=0,
                                    open=is_open))
                    if is_open:
                        for pl in self._sorted(kids, lambda p: p.name, pl_recent, pl_added):
                            out.append(self._pl_entry(pl, 16))

        for show_kind in ("podcast", "audiobook"):
            if chip in (None, show_kind + "s", "downloaded"):
                shows = [e for e in self._state.get("shows", []) if e["kind"] == show_kind and match(e["title"], e["subtitle"])]
                if chip == "downloaded":           # podcasts / audiobooks with downloaded episodes
                    shows = [e for e in shows if e.get("downloaded")]
                elif chip is None or chip == show_kind + "s":
                    shows = [e for e in shows if e.get("followed", True) or e.get("downloaded")]
                for e in self._sorted(shows, lambda e: e["title"], lambda e: 0, lambda e: 0):
                    out.append(dict(kind=show_kind, title=e["title"], subtitle=e["subtitle"], obj=e, indent=0))
        if chip == "albums" or (query and chip is None):
            albums = [a for a in st["albums"] if match(a["title"], a["artist"])]
            for a in self._sorted(albums, lambda a: a["title"], lambda a: a.get("recent", 0), lambda a: a.get("added", 0)):
                out.append(dict(kind="album", title=a["title"], subtitle=f"Album • {a['artist']}", obj=a, indent=0))
        if chip == "artists" or (query and chip is None):
            artists = [a for a in st["artists"] if match(a["name"])]
            for a in self._sorted(artists, lambda a: a["name"], lambda a: a.get("recent", 0), lambda a: a.get("added", 0)):
                out.append(dict(kind="artist", title=a["name"], subtitle="Artist", obj=a, indent=0))
        return out

    @staticmethod
    def _pl_entry(pl, indent):
        n = len(pl.songs)
        return dict(kind="playlist", title=pl.name, subtitle=f"Playlist • {n} song{'s' if n != 1 else ''}",
                    obj=pl, indent=indent)

    # --- view ---------------------------------------------------------------------------------------
    def _pixmap(self, e, size):
        if e["kind"] == "songs":
            return gradient_cover(size, "#450af5", "#c4efd9", "♪")
        if e["kind"] == "saved":
            return gradient_cover(size, "#1ed760", "#0b5c33", "⬇")
        if e["kind"] == "folder":
            return folder_cover(size)
        if e["kind"] == "playlist":
            pm = rounded(self._cover(e["obj"].cover_path, size), size)
            if self.show_origin:
                pm = with_ring(pm, size, origin_colour(getattr(e["obj"], "origin", "")))
            return pm
        if e["kind"] in ("album", "podcast", "audiobook"):
            return rounded(self._cover(e["obj"]["cover_path"], size), size)
        return circle(self._cover(e["obj"]["cover_path"], size), size)

    def _is_active(self, e):
        a = self._state["active"]
        if e["kind"] == "songs":
            return a == "library"
        if e["kind"] == "saved":
            return a == "saved"
        if e["kind"] == "playlist":
            return a is e["obj"]
        if e["kind"] == "album":
            return a == ("album", e["obj"]["key"])
        if e["kind"] == "artist":
            return a in (("artist", e["obj"].get("key")), ("artist", e["obj"]["name"]))
        if e["kind"] in ("podcast", "audiobook"):
            return a == ("show", e["obj"]["key"])
        return False

    def _is_playing(self, e):
        src = self._state["playing_source"]
        if e["kind"] == "songs":
            return src in ("Your Songs", "Your Library")
        if e["kind"] == "saved":
            return src.startswith("Saved:") or src == "To download"
        if e["kind"] == "playlist":
            return src == e["obj"].name
        if e["kind"] == "album":
            return src == e["obj"]["title"]
        if e["kind"] in ("artist",):
            return src == e["obj"]["name"]
        if e["kind"] in ("podcast", "audiobook"):
            return src == e["obj"]["title"]
        return False

    def _make_row(self, e, mode, tile=160):
        size = 48 if mode != "grid" else tile - 16
        trailing = ("▾" if e.get("open") else "▸") if e["kind"] == "folder" else ""
        row = LibraryRow(self._pixmap(e, size), e["title"], e["subtitle"], active=self._is_active(e),
                         playing=self._is_playing(e), mode=mode, indent=e.get("indent", 0), tile=tile,
                         trailing=trailing)
        kind, obj = e["kind"], e["obj"]
        if kind == "songs":
            row.clicked.connect(self.open_all_songs.emit)
        elif kind == "saved":
            row.clicked.connect(self.open_saved.emit)
        elif kind == "folder":
            row.clicked.connect(lambda f=obj: self.toggle_folder(f))
            row.context_requested.connect(lambda pos, f=obj: self.folder_menu.emit(f, pos))
        elif kind == "playlist":
            row.clicked.connect(lambda p=obj: self.open_playlist.emit(p))
            row.double_clicked.connect(lambda p=obj: self.play_playlist.emit(p))
            row.context_requested.connect(lambda pos, p=obj: self.playlist_menu.emit(p, pos))
            row.enable_drops()
            row.songs_dropped.connect(lambda songs, p=obj: self.songs_dropped.emit(p, songs))
            row.files_dropped.connect(lambda paths, p=obj: self.files_dropped.emit(p, paths))
        elif kind == "album":
            row.clicked.connect(lambda a=obj: self.open_album.emit(a))
            row.double_clicked.connect(lambda a=obj: self.play_album.emit(a))
        elif kind == "artist":
            row.clicked.connect(lambda a=obj: self.open_artist.emit(a))
            row.double_clicked.connect(lambda a=obj: self.play_artist.emit(a))
        elif kind in ("podcast", "audiobook"):
            row.clicked.connect(lambda e=obj: self.open_show.emit(e))
        return row

    def toggle_folder(self, name):
        if name in self._open_folders:
            self._open_folders.discard(name)
        else:
            self._open_folders.add(name)
        self._rebuild()

    def _tile_layout(self):
        """(columns, tile width) for the grid view, from the space available."""
        width = max(self.scroll.viewport().width(), self.width() - 24, 160)
        cols = max(2, width // 180) if self.expanded else 2
        return cols, max(120, min(220, (width - 8) // cols))

    def _signature(self, items, mode):
        """What the list looks like; refreshing with the same signature changes nothing on screen."""
        out = [mode, self.chip, self.sort, repr(self._state.get("active")), self._state.get("playing_source"),
               self.show_origin]
        for e in items:
            obj = e.get("obj")
            extra = ""
            if e["kind"] == "playlist":
                extra = (getattr(obj, "cover_path", "") or "", getattr(obj, "origin", ""), tuple(getattr(s, "album_cover_path", "") or ""
                                                               for s in obj.songs[:8]), self.is_downloaded(obj))
            elif isinstance(obj, dict):
                extra = (obj.get("cover_path") or obj.get("cover") or "", len(obj.get("songs") or []))
            ident = (obj.get("key") or e["title"]) if isinstance(obj, dict) else (obj if isinstance(obj, str) else id(obj))
            out.append((e["kind"], e["title"], e["subtitle"], e.get("indent"), ident, repr(extra)))
        return tuple(out)

    def _rebuild(self, background=False):
        if background and theme.user_is_busy():
            # A download finished while a button is held or a menu is open: wait, don't pull the list away.
            if not hasattr(self, "_later"):
                self._later = QTimer(self)
                self._later.setSingleShot(True)
                self._later.timeout.connect(lambda: self._rebuild(background=True))
            self._later.start(300)
            return
        items = self.entries()
        mode = "collapsed" if self.collapsed else ("grid" if (self.view == "grid" or self.expanded) else self.view)
        sig = self._signature(items, mode)
        if background and sig == getattr(self, "_shown_sig", None):
            return
        self._shown_sig = sig
        content = QWidget()
        content.setObjectName("libContent")
        content.setStyleSheet(f"#libContent {{ background: {theme.PANEL}; }}")
        if mode == "grid":
            grid = QGridLayout(content)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(4)
            cols, tile = self._tile_layout()
            self._grid_columns = cols
            for i, e in enumerate(items):
                grid.addWidget(self._make_row(e, "grid", tile), i // cols, i % cols,
                               Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            grid.setRowStretch(len(items) // cols + 1, 1)
            grid.setColumnStretch(cols, 1)
        else:
            v = QVBoxLayout(content)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            for e in items:
                v.addWidget(self._make_row(e, mode))
            if not items and mode != "collapsed":
                query = self.filter_edit.text().strip()
                text = ("Nothing matches." if query else
                        {"albums": "Albums from your music folders show up here.",
                         "artists": "Artists from your music folders show up here.",
                         "downloaded": "Playlists where every song is on your computer show up here."
                         }.get(self.chip, "Create your first playlist with + Create."))
                empty = QLabel(text)
                empty.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px; padding: 12px; background: transparent;")
                empty.setWordWrap(True)
                v.addWidget(empty)
            v.addStretch()
        theme.replace_scroll_widget(self.scroll, content)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._place_chip_arrows)
        if not self.collapsed and (self.view == "grid" or self.expanded) and self._tile_layout()[0] != self._grid_columns:
            QTimer.singleShot(0, self._rebuild)

"""Left 'Your Library' panel (Spotify layout): Your Songs, Saved for later and
every playlist as a list with artwork, filter chips, a filter box and + Create."""
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QLineEdit, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QFont, QPainterPath
from PyQt6.QtCore import Qt, QSize, QRectF, pyqtSignal

from . import icons, theme


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


class LibraryRow(QFrame):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    context_requested = pyqtSignal(object)

    def __init__(self, pixmap, title, subtitle, active=False, playing=False):
        super().__init__()
        self.setObjectName("libRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        bg = theme.HOVER if active else "transparent"
        self.setStyleSheet(f"#libRow {{ background: {bg}; border-radius: 6px; }} #libRow:hover {{ background: {theme.ELEVATED if not active else theme.SELECTED}; }}")
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(12)
        art = QLabel()
        art.setFixedSize(48, 48)
        art.setPixmap(pixmap)
        h.addWidget(art)
        v = QVBoxLayout()
        v.setSpacing(2)
        t = QLabel()
        t.setStyleSheet(f"color: {theme.GREEN if playing else theme.TEXT}; font-size: 15px; font-weight: 500; background: transparent;")
        sub = QLabel()
        sub.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px; background: transparent;")
        for lbl, text in ((t, title), (sub, subtitle)):
            lbl.setText(lbl.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, 200))
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

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e):
        self.context_requested.emit(e.globalPos())


class LibraryPanel(QFrame):
    create_clicked = pyqtSignal()
    open_all_songs = pyqtSignal()
    open_saved = pyqtSignal()
    open_playlist = pyqtSignal(object)
    play_playlist = pyqtSignal(object)
    playlist_menu = pyqtSignal(object, object)       # playlist, global pos
    settings_clicked = pyqtSignal()

    def __init__(self, cover_loader, parent=None):
        super().__init__(parent)
        self._cover = cover_loader
        self.setObjectName("libraryPanel")
        self.setStyleSheet(theme.panel_style("libraryPanel"))
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 12, 8, 8)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.setContentsMargins(8, 0, 0, 0)
        title_icon = QLabel()
        title_icon.setPixmap(icons.library(theme.SUBDUED, 24).pixmap(24, 24))
        head.addWidget(title_icon)
        title = QLabel("Your Library")
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 16px; font-weight: 700; background: transparent;")
        head.addWidget(title)
        head.addStretch()
        create = QPushButton(" Create")
        create.setIcon(icons.plus(theme.TEXT, 16))
        create.setToolTip("Create a playlist")
        create.setCursor(Qt.CursorShape.PointingHandCursor)
        create.setFixedHeight(32)
        create.setStyleSheet(f"QPushButton {{ background: {theme.ELEVATED}; color: {theme.TEXT}; border: none;"
                             f" border-radius: 16px; padding: 0 14px; font-weight: 700; font-size: 14px; }}"
                             f" QPushButton:hover {{ background: {theme.HOVER}; }}")
        create.clicked.connect(self.create_clicked.emit)
        head.addWidget(create)
        v.addLayout(head)

        chips = QHBoxLayout()
        chips.setContentsMargins(8, 4, 0, 0)
        self.chip_playlists = self._chip("Playlists")
        self.chip_saved = self._chip("Saved for later")
        for c in (self.chip_playlists, self.chip_saved):
            c.toggled.connect(self._chip_toggled)
            chips.addWidget(c)
        chips.addStretch()
        v.addLayout(chips)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search in Your Library")
        self.filter_edit.addAction(icons.search(theme.SUBDUED, 18), QLineEdit.ActionPosition.LeadingPosition)
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setFixedHeight(34)
        self.filter_edit.setStyleSheet(f"QLineEdit {{ background: transparent; color: {theme.TEXT}; border: none;"
                                       f" border-radius: 4px; padding: 0 6px; font-size: 13px; }}"
                                       f" QLineEdit:focus {{ background: {theme.HOVER}; }}")
        self.filter_edit.textChanged.connect(lambda _t: self._rebuild())
        v.addWidget(self.filter_edit)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {theme.PANEL}; }}")
        v.addWidget(self.scroll, 1)

        self._state = dict(playlists=[], n_songs=0, n_saved=0, active=None, playing_source="")
        self._special_songs = gradient_cover(48, "#450af5", "#c4efd9", "♪")
        self._special_saved = gradient_cover(48, "#1ed760", "#0b5c33", "⬇")

    def _chip(self, text):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(theme.CHIP)
        return b

    def _chip_toggled(self, on):
        sender = self.sender()
        if on:
            for c in (self.chip_playlists, self.chip_saved):
                if c is not sender:
                    c.blockSignals(True); c.setChecked(False); c.blockSignals(False)
        self._rebuild()

    # ------------------------------------------------------------------
    def set_items(self, playlists, n_songs, n_saved, playing_source=""):
        self._state.update(playlists=list(playlists), n_songs=n_songs, n_saved=n_saved,
                           playing_source=playing_source)
        self._rebuild()

    def set_active(self, key):
        """key: "library", "saved", a Playlist object, or None."""
        self._state["active"] = key
        self._rebuild()

    def _rebuild(self):
        st = self._state
        query = self.filter_edit.text().strip().casefold()
        only_playlists = self.chip_playlists.isChecked()
        only_saved = self.chip_saved.isChecked()
        content = QWidget()
        content.setObjectName("libContent")
        content.setStyleSheet(f"#libContent {{ background: {theme.PANEL}; }}")
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        def visible(name):
            return not query or query in name.casefold()

        if not only_playlists and not only_saved and visible("Your Songs"):
            row = LibraryRow(self._special_songs, "Your Songs", f"Library • {st['n_songs']} songs",
                             active=st["active"] == "library", playing=st["playing_source"] in ("Your Songs", "Your Library"))
            row.clicked.connect(self.open_all_songs.emit)
            v.addWidget(row)
        if not only_playlists and visible("Saved for later"):
            row = LibraryRow(self._special_saved, "Saved for later", f"To download • {st['n_saved']} songs",
                             active=st["active"] == "saved", playing=st["playing_source"].startswith("Saved:"))
            row.clicked.connect(self.open_saved.emit)
            v.addWidget(row)
        if not only_saved:
            for pl in st["playlists"]:
                if not visible(pl.name):
                    continue
                n = len(pl.songs)
                row = LibraryRow(rounded(self._cover(pl.cover_path, 48), 48), pl.name,
                                 f"Playlist • {n} song{'s' if n != 1 else ''}",
                                 active=st["active"] is pl, playing=st["playing_source"] == pl.name)
                row.clicked.connect(lambda p=pl: self.open_playlist.emit(p))
                row.double_clicked.connect(lambda p=pl: self.play_playlist.emit(p))
                row.context_requested.connect(lambda pos, p=pl: self.playlist_menu.emit(p, pos))
                v.addWidget(row)
        if v.count() == 0:
            empty = QLabel("Nothing matches." if query else "Create your first playlist with + Create.")
            empty.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px; padding: 12px; background: transparent;")
            empty.setWordWrap(True)
            v.addWidget(empty)
        v.addStretch()
        self.scroll.setWidget(content)

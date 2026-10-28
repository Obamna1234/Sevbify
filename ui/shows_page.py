"""Pages for podcasts, audiobooks and Browse (Spotify layout): card grids, a show / book page with its episode or
chapter list, and coloured Browse tiles. The main window fills them with data and reacts to their signals."""
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QLineEdit, QScrollArea,
    QSizePolicy
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QTransform, QFont
from PyQt6.QtCore import Qt, QSize, QRectF, pyqtSignal, QTimer

from . import icons, theme
from .library_panel import rounded

TILE_COLOURS = ["#e8115b", "#006450", "#1e3264", "#8400e7", "#477d95", "#e13300", "#ba5d07", "#148a08", "#503750",
                "#dc148c", "#0d73ec", "#af2896", "#509bf5", "#7d4b32", "#e91429", "#8d67ab", "#27856a", "#1e3264"]


def section_title(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {theme.TEXT}; font-size: 22px; font-weight: 700; background: transparent;")
    return lbl


def muted(text):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px; background: transparent;")
    return lbl


class CardGrid(QWidget):
    """Cards in as many columns as fit; re-flows when resized. rows=1 shows a single row (a shelf)."""

    def __init__(self, cards, card_width=184, rows=0, parent=None):
        super().__init__(parent)
        self.cards, self.card_width, self.rows = list(cards), card_width, rows
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._cols = 0
        for c in self.cards:
            c.hide()
            c.setParent(self)          # inside the window from the start, never a little window of its own
        self._place(4)

    def _place(self, cols):
        self._cols = cols
        for c in self.cards:
            self.grid.removeWidget(c)
            c.hide()
        shown = self.cards if not self.rows else self.cards[:cols * self.rows]
        for i, c in enumerate(shown):
            self.grid.addWidget(c, i // cols, i % cols)
            c.show()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = max(1, (self.width() + 4) // (self.card_width + 4))
        if cols != self._cols:
            self._place(cols)


class BrowseTile(QFrame):
    """Spotify's Browse tile: coloured box, name top-left, picture tilted in the bottom-right corner."""
    clicked = pyqtSignal()

    def __init__(self, title, colour, pixmap=None, parent=None):
        super().__init__(parent)
        self.title, self.colour, self.pixmap = title, QColor(colour), pixmap
        self.setMinimumSize(200, 110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(130)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(title)

    def set_pixmap(self, pm):
        self.pixmap = pm
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        p.setClipPath(path)
        p.fillPath(path, self.colour.lighter(115) if self.underMouse() else self.colour)
        if self.pixmap is not None and not self.pixmap.isNull():
            side = int(r.height() * 0.68)
            p.save()
            p.translate(r.width() - side * 0.55, r.height() - side * 0.48)
            p.rotate(25)
            p.drawPixmap(-side // 2, -side // 2, rounded(self.pixmap, side, 4))
            p.restore()
        f = QFont(theme.FONT_FAMILY)
        f.setPixelSize(22)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRectF(16, 14, r.width() * 0.62, r.height() - 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self.title)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        left = e.button() == Qt.MouseButton.LeftButton
        super().mouseReleaseEvent(e)
        if left:
            self.clicked.emit()


class TileGrid(QWidget):
    """Browse tiles, 2–5 per row depending on the width."""

    def __init__(self, tiles, parent=None):
        super().__init__(parent)
        self.tiles = list(tiles)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)
        self._cols = 0
        for t in self.tiles:
            t.setParent(self)
        self._place(4)

    def _place(self, cols):
        self._cols = cols
        for t in self.tiles:
            self.grid.removeWidget(t)
        for i, t in enumerate(self.tiles):
            self.grid.addWidget(t, i // cols, i % cols)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = max(2, min(5, self.width() // 230))
        if cols != self._cols:
            self._place(cols)


class ElidedLabel(QLabel):
    """Text cut to whole lines with "…" (a plain word-wrapped label with a height limit cut a line in half)."""

    def __init__(self, text, lines=2, parent=None):
        super().__init__(parent)
        self.full_text, self.lines = " ".join((text or "").split()), lines
        self.setWordWrap(True)
        self.setToolTip(self.full_text if len(self.full_text) > 80 else "")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._width = 0

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.width() != self._width:
            self._width = self.width()
            self._relayout()

    def showEvent(self, e):
        super().showEvent(e)
        self._relayout()

    def _relayout(self):
        fm = self.fontMetrics()
        width = max(50, self.width())
        words, out, line = self.full_text.split(" "), [], ""
        for i, w in enumerate(words):
            trial = (line + " " + w).strip()
            if fm.horizontalAdvance(trial) <= width or not line:
                line = trial
                continue
            out.append(line)
            line = w
            if len(out) == self.lines - 1:
                line = " ".join([line] + words[i + 1:])
                break
        if line:
            out.append(fm.elidedText(line, Qt.TextElideMode.ElideRight, width) if len(out) == self.lines - 1
                       else line)
        self.setText("\n".join(out[:self.lines]))
        self.setFixedHeight(fm.lineSpacing() * max(1, min(self.lines, len(out))) + 2)


class EpisodeRow(QFrame):
    """One podcast episode or audiobook chapter: cover, title, date • length • progress, description, buttons."""
    play_clicked = pyqtSignal()
    download_clicked = pyqtSignal()
    watch_clicked = pyqtSignal()
    context_requested = pyqtSignal(object)

    def __init__(self, title, meta, description="", playing=False, downloaded=False, downloading=False,
                 can_watch=False, finished=False, show_cover=True, parent=None):
        super().__init__(parent)
        self.setObjectName("epRow")
        self.setStyleSheet(f"#epRow {{ background: transparent; border-radius: 6px; }}"
                           f" #epRow:hover {{ background: {theme.ROW_HOVER}; }}")
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 16, 16, 16)
        h.setSpacing(20)
        self.cover = QLabel()
        self.cover.setFixedSize(96, 96)
        self.cover.setStyleSheet(f"background: {theme.ELEVATED}; border-radius: 6px;")
        self.cover.setVisible(show_cover)
        h.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(4)
        t = ElidedLabel(title, 2)
        t.setStyleSheet(f"color: {theme.GREEN if playing else theme.TEXT}; font-size: 15px; font-weight: 700;"
                        f" background: transparent;")
        t.setToolTip(title)
        v.addWidget(t)
        if description:
            d = ElidedLabel(description, 2)
            d.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px; background: transparent;")
            v.addWidget(d)
        v.addSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.play_btn = QPushButton()
        self.play_btn.setIcon(icons.play("#000000", 14))
        self.play_btn.setIconSize(QSize(14, 14))
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setToolTip("Play")
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("QPushButton { background: white; border: none; border-radius: 16px; }"
                                    " QPushButton:hover { background: #f0f0f0; }")
        self.play_btn.clicked.connect(self.play_clicked.emit)
        row.addWidget(self.play_btn)
        m = QLabel(("✓ Played  •  " if finished else "") + meta)
        m.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px; background: transparent;")
        row.addWidget(m)
        row.addStretch()
        if can_watch:
            self.watch_btn = QPushButton("Watch")
            self.watch_btn.setStyleSheet(theme.PILL)
            self.watch_btn.setFixedHeight(30)
            self.watch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.watch_btn.setToolTip("Watch the video (audio-only is the play button)")
            self.watch_btn.clicked.connect(self.watch_clicked.emit)
            row.addWidget(self.watch_btn)
        self.dl_btn = QPushButton()
        self.dl_btn.setFixedSize(32, 32)
        self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if downloaded:
            self.dl_btn.setIcon(icons.download(theme.GREEN, 22))
            self.dl_btn.setToolTip("Downloaded: plays without internet")
        elif downloading:
            self.dl_btn.setText("…")
            self.dl_btn.setToolTip("Downloading…")
        else:
            self.dl_btn.setIcon(icons.download(theme.SUBDUED, 22))
            self.dl_btn.setToolTip("Download")
        self.dl_btn.setIconSize(QSize(22, 22))
        self.dl_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: {theme.SUBDUED};"
                                  f" font-size: 16px; }} QPushButton:hover {{ background: {theme.HOVER}; border-radius: 16px; }}")
        self.dl_btn.clicked.connect(self.download_clicked.emit)
        row.addWidget(self.dl_btn)
        v.addLayout(row)
        h.addLayout(v, 1)

    def set_cover(self, pixmap):
        self.cover.setPixmap(rounded(pixmap, 96, 6))

    def contextMenuEvent(self, e):
        self.context_requested.emit(e.globalPos())


class ShowsHome(QWidget):
    """The Podcasts or Audiobooks page: a search box, (for podcasts) a box for a feed / YouTube link, and
    sections of cards filled in by the main window."""
    search_requested = pyqtSignal(str)
    link_added = pyqtSignal(str)

    def __init__(self, title, intro, search_hint, link_hint="", parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(self.scroll)
        self.title, self.intro, self.search_hint, self.link_hint = title, intro, search_hint, link_hint
        self.search_edit = None
        self.set_sections([])

    def set_sections(self, sections, message=""):
        """sections: [(title, [cards] or widget, rows)] — rows 0 = all, 1 = one shelf row."""
        content = QWidget()
        content.setObjectName("showsHome")
        content.setStyleSheet("#showsHome { background: transparent; }")
        v = QVBoxLayout(content)
        v.setContentsMargins(24, 20, 24, 24)
        v.setSpacing(10)
        head = QLabel(self.title)
        head.setStyleSheet(f"color: {theme.TEXT}; font-size: 32px; font-weight: 800; background: transparent;")
        v.addWidget(head)
        v.addWidget(muted(self.intro))
        text = self.search_edit.text() if self.search_edit is not None else ""
        self.search_edit = QLineEdit(text)
        self.search_edit.setPlaceholderText(self.search_hint)
        self.search_edit.addAction(icons.search(theme.SUBDUED, 20), QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedHeight(44)
        self.search_edit.setMaximumWidth(520)
        self.search_edit.setStyleSheet(f"QLineEdit {{ background: {theme.ELEVATED}; color: {theme.TEXT}; border: 1px solid"
                                       f" {theme.ELEVATED}; border-radius: 22px; padding: 0 14px 0 6px; font-size: 14px; }}"
                                       f" QLineEdit:focus {{ border: 2px solid {theme.TEXT}; }}")
        self.search_edit.returnPressed.connect(lambda: self.search_requested.emit(self.search_edit.text().strip()))
        v.addWidget(self.search_edit)
        if self.link_hint:
            row = QHBoxLayout()
            self.link_edit = QLineEdit()
            self.link_edit.setPlaceholderText(self.link_hint)
            self.link_edit.setMaximumWidth(420)
            self.link_edit.setFixedHeight(34)
            self.link_edit.setStyleSheet(f"QLineEdit {{ background: {theme.HOVER}; color: {theme.TEXT}; border: none;"
                                         f" border-radius: 4px; padding: 0 8px; font-size: 13px; }}")
            add = QPushButton("Follow")
            add.setStyleSheet(theme.PILL)
            add.setFixedHeight(32)
            add.setCursor(Qt.CursorShape.PointingHandCursor)
            go = lambda: self.link_added.emit(self.link_edit.text().strip())
            add.clicked.connect(go)
            self.link_edit.returnPressed.connect(go)
            row.addWidget(self.link_edit)
            row.addWidget(add)
            row.addStretch()
            v.addLayout(row)
        if message:
            v.addWidget(muted(message))
        for title, cards, rows in sections:
            if not cards:
                continue
            v.addSpacing(14)
            v.addWidget(section_title(title))
            v.addWidget(cards if isinstance(cards, QWidget) else CardGrid(cards, rows=rows))
        v.addStretch()
        theme.replace_scroll_widget(self.scroll, content)


class ShowPage(QWidget):
    """A podcast, YouTube channel or audiobook: big header and its episodes / chapters."""
    play_clicked = pyqtSignal()
    follow_clicked = pyqtSignal()
    download_all_clicked = pyqtSignal()
    sort_changed = pyqtSignal(str)          # "newest" / "oldest"

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(self.scroll)
        self.cover_label = None
        self.rows = []

    def build(self, kind, title, author, description, followed, rows, top_colour="#3a3a3a", can_download_all=False,
              follow_text=("Follow", "Following"), message="", sort=None, count_text=""):
        content = QWidget()
        content.setObjectName("showPage")
        content.setStyleSheet("#showPage { background: transparent; }")
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 16)
        v.setSpacing(0)
        header = QFrame()
        header.setObjectName("showHeader")
        header.setStyleSheet(f"#showHeader {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {top_colour},"
                             f" stop:1 {theme.PANEL}); border-top-left-radius: {theme.RADIUS}px;"
                             f" border-top-right-radius: {theme.RADIUS}px; }}")
        hv = QVBoxLayout(header)
        hv.setContentsMargins(24, 24, 24, 16)
        hv.setSpacing(16)
        top = QHBoxLayout()
        top.setSpacing(24)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(200, 200)
        self.cover_label.setStyleSheet(f"background: {theme.ELEVATED}; border-radius: 8px;")
        top.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignBottom)
        info = QVBoxLayout()
        info.addStretch()
        k = QLabel(kind)
        k.setStyleSheet("color: white; font-size: 14px; font-weight: 600; background: transparent;")
        t = QLabel(title)
        t.setWordWrap(True)
        t.setMinimumWidth(10)
        t.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        t.setStyleSheet(f"color: white; font-size: {48 if len(title) < 24 else (36 if len(title) < 48 else 26)}px;"
                        f" font-weight: 800; background: transparent;")
        a = QLabel(author)
        a.setStyleSheet("color: white; font-size: 16px; font-weight: 700; background: transparent;")
        for w in (k, t, a):
            info.addWidget(w)
        top.addLayout(info, 1)
        hv.addLayout(top)
        hv.addSpacing(8)                    # clear gap between the picture and the green play button
        actions = QHBoxLayout()
        actions.setSpacing(16)
        play = QPushButton()
        play.setIcon(icons.play("#000000", 22))
        play.setIconSize(QSize(22, 22))
        play.setFixedSize(56, 56)
        play.setToolTip("Play")
        play.setCursor(Qt.CursorShape.PointingHandCursor)
        play.setStyleSheet(f"QPushButton {{ border: none; background: {theme.GREEN}; border-radius: 28px; }}"
                           "QPushButton:hover { background: #3be477; }")
        play.clicked.connect(self.play_clicked.emit)
        actions.addWidget(play)
        self.follow_btn = QPushButton(follow_text[1] if followed else follow_text[0])
        self.follow_btn.setStyleSheet(theme.PILL)
        self.follow_btn.setFixedHeight(32)
        self.follow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.follow_btn.clicked.connect(self.follow_clicked.emit)
        actions.addWidget(self.follow_btn)
        if can_download_all:
            dl = QPushButton("Download")
            dl.setIcon(icons.download(theme.TEXT, 18))
            dl.setIconSize(QSize(18, 18))
            dl.setStyleSheet(theme.PILL)
            dl.setFixedHeight(32)
            dl.setCursor(Qt.CursorShape.PointingHandCursor)
            dl.clicked.connect(self.download_all_clicked.emit)
            actions.addWidget(dl)
        actions.addStretch()
        if sort is not None:
            from PyQt6.QtWidgets import QComboBox
            box = QComboBox()
            box.addItems(["Newest first", "Oldest first"])
            box.setCurrentIndex(0 if sort == "newest" else 1)
            box.setToolTip("Sort episodes by release date")
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.setStyleSheet(f"QComboBox {{ background: transparent; color: {theme.SUBDUED}; border: none;"
                              f" font-size: 14px; padding: 4px 8px; }} QComboBox:hover {{ color: {theme.TEXT}; }}"
                              f" QComboBox QAbstractItemView {{ background: #282828; color: white;"
                              f" selection-background-color: #3e3e3e; }}")
            box.currentIndexChanged.connect(lambda i: self.sort_changed.emit("newest" if i == 0 else "oldest"))
            self.sort_box = box
            actions.addWidget(box)
        hv.addLayout(actions)
        if count_text:
            hv.addWidget(muted(count_text))
        if description:
            d = muted(description)
            d.setMaximumWidth(900)
            hv.addWidget(d)
        v.addWidget(header)
        body = QVBoxLayout()
        body.setContentsMargins(12, 8, 12, 0)
        body.setSpacing(0)
        if message:
            m = muted(message)
            m.setContentsMargins(12, 8, 12, 8)
            body.addWidget(m)
        self.rows = list(rows)
        for r in self.rows:
            body.addWidget(r)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet("background: rgba(255,255,255,0.08);")
            body.addWidget(line)
        v.addLayout(body)
        v.addStretch()
        theme.replace_scroll_widget(self.scroll, content)

    def set_cover(self, pixmap):
        if self.cover_label is not None:
            self.cover_label.setPixmap(rounded(pixmap, 200, 8))

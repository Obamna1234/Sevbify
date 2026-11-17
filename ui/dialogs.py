"""Small Spotify-style dialogs: the white "Delete from Your Library?" card, and the dark "Edit details" box.

They replace the plain Windows message boxes, which looked out of place (beta.6 test). Nothing here touches
music files: deleting a playlist or folder only changes Sevbify's own list.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFrame,
                             QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor

from . import theme


class _Card(QDialog):
    def __init__(self, parent, light):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        self.card = QFrame()
        self.card.setObjectName("card")
        bg, fg = ("#ffffff", "#000000") if light else ("#282828", "#ffffff")
        self.card.setStyleSheet(f"#card {{ background: {bg}; border-radius: 10px; }}"
                                f" QLabel {{ color: {fg}; background: transparent; }}")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(28, 24, 28, 22)
        self.body.setSpacing(10)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(e)


def confirm(parent, title, text, ok_text="Delete", cancel_text="Cancel", safe_default=False):
    """Spotify's white confirmation card. text may use <b>…</b>. Returns True for OK.
    safe_default: Enter means Cancel and OK only works after a second (for questions another device asks)."""
    d = _Card(parent, light=True)
    d.setMinimumWidth(460)
    h = QLabel(title)
    h.setStyleSheet("font-size: 22px; font-weight: 800;")
    d.body.addWidget(h)
    t = QLabel(text)
    t.setWordWrap(True)
    t.setTextFormat(Qt.TextFormat.RichText)
    t.setStyleSheet("font-size: 14px; color: #000000;")
    d.body.addWidget(t)
    d.body.addSpacing(10)
    row = QHBoxLayout()
    row.addStretch()
    cancel = QPushButton(cancel_text)
    cancel.setCursor(Qt.CursorShape.PointingHandCursor)
    cancel.setStyleSheet("QPushButton { color: #000000; background: transparent; border: none; font-size: 15px;"
                         " font-weight: 700; padding: 10px 18px; } QPushButton:hover { font-size: 15px;"
                         " color: #000000; }")
    ok = QPushButton(ok_text)
    ok.setCursor(Qt.CursorShape.PointingHandCursor)
    ok.setDefault(not safe_default)
    ok.setFixedHeight(48)                       # a full pill, like Spotify's (Qt drops a radius over half the height)
    ok.setStyleSheet(f"QPushButton {{ color: #000000; background: #1ed760; border: none; border-radius: 24px;"
                     f" font-size: 15px; font-weight: 700; padding: 0 32px; }}"
                     f" QPushButton:hover {{ background: #3be477; }}")
    cancel.clicked.connect(d.reject)
    ok.clicked.connect(d.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    d.body.addLayout(row)
    d.confirm_button, d.cancel_button = ok, cancel
    if safe_default:
        from PyQt6.QtCore import QTimer
        cancel.setDefault(True)
        cancel.setFocus()
        ok.setEnabled(False)
        QTimer.singleShot(1000, lambda: ok.setEnabled(True))
    if getattr(parent, "_auto_answer_dialogs", None) is not None:      # tests
        return bool(parent._auto_answer_dialogs)
    return d.exec() == QDialog.DialogCode.Accepted


class _CoverButton(QPushButton):
    """The cover in Edit details. On hover, like Spotify: the picture darkens and shows a pencil and
    "Choose photo"."""

    def __init__(self, pixmap):
        super().__init__()
        self.setFixedSize(180, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Choose photo")
        self._pm = pixmap if pixmap is not None and not pixmap.isNull() else None
        self._hover = False
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        from PyQt6.QtGui import QPainter, QPainterPath, QFont
        from PyQt6.QtCore import QRectF
        from . import icons
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 4, 4)
        p.setClipPath(path)
        if self._pm is not None:
            p.drawPixmap(self.rect(), self._pm.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                      Qt.TransformationMode.SmoothTransformation))
        else:
            p.fillRect(self.rect(), QColor("#282828"))
        if self._hover or self._pm is None:
            if self._pm is not None:
                p.fillRect(self.rect(), QColor(0, 0, 0, 150))
            icons.pencil("#ffffff", 44).paint(p, 68, 50, 44, 44)
            f = QFont(self.font())
            f.setPixelSize(15)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(0, 104, 180, 24), Qt.AlignmentFlag.AlignCenter, "Choose photo")
        p.end()


FIELD_STYLE = ("QLineEdit, QPlainTextEdit { background: #3e3e3e; color: white; border: 1px solid transparent;"
               " border-radius: 4px; padding: 8px 10px; font-size: 14px;"
               " selection-background-color: #2e77d0; selection-color: white; }"
               " QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #535353; background: #333333; }")
DESCRIPTION_MAX = 300


def edit_details(parent, title, name, pixmap=None, can_change_cover=True, name_label="Name", description=None):
    """Spotify's "Edit details": a cover you can click to change ("Choose photo"), the name, and (for playlists)
    an optional description of up to 300 characters. Returns (name, "choose-cover" | None, description) or None
    when cancelled. `description` None = no description box (folders)."""
    from PyQt6.QtWidgets import QPlainTextEdit
    d = _Card(parent, light=False)
    d.setMinimumWidth(560)
    head = QHBoxLayout()
    h = QLabel(title)
    h.setStyleSheet("font-size: 24px; font-weight: 800;")
    head.addWidget(h)
    head.addStretch()
    x = QPushButton("✕")
    x.setFixedSize(32, 32)
    x.setCursor(Qt.CursorShape.PointingHandCursor)
    x.setStyleSheet(f"QPushButton {{ color: {theme.SUBDUED}; background: transparent; border: none; font-size: 16px;"
                    f" border-radius: 16px; }} QPushButton:hover {{ background: #3e3e3e; color: white; }}")
    x.clicked.connect(d.reject)
    head.addWidget(x)
    d.body.addLayout(head)
    row = QHBoxLayout()
    row.setSpacing(16)
    choice = {"cover": None}
    if can_change_cover:
        cover = _CoverButton(pixmap)

        def pick():
            choice["cover"] = "choose-cover"
            d.accept()
        cover.clicked.connect(pick)
        row.addWidget(cover, 0, Qt.AlignmentFlag.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(6)
    lbl = QLabel(name_label)
    lbl.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700;")
    edit = QLineEdit(name)
    edit.setStyleSheet(FIELD_STYLE)
    edit.setMaxLength(100)
    edit.selectAll()
    col.addWidget(lbl)
    col.addWidget(edit)
    desc_box = None
    if description is not None:
        dl = QLabel("Description")
        dl.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700;")
        desc_box = QPlainTextEdit(description)
        desc_box.setPlaceholderText("Add an optional description")
        desc_box.setStyleSheet(FIELD_STYLE)
        desc_box.setFixedHeight(110 if can_change_cover else 90)
        count = QLabel()
        count.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 11px;")
        count.setAlignment(Qt.AlignmentFlag.AlignRight)

        def limit():
            text = desc_box.toPlainText()
            if len(text) > DESCRIPTION_MAX:
                cur = desc_box.textCursor()
                desc_box.setPlainText(text[:DESCRIPTION_MAX])
                cur.setPosition(DESCRIPTION_MAX)
                desc_box.setTextCursor(cur)
            count.setText(f"{len(desc_box.toPlainText())}/{DESCRIPTION_MAX}")
        desc_box.textChanged.connect(limit)
        limit()
        col.addWidget(dl)
        col.addWidget(desc_box)
        col.addWidget(count)
    col.addStretch()
    row.addLayout(col, 1)
    d.body.addLayout(row)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    save = QPushButton("Save")
    save.setDefault(True)
    save.setCursor(Qt.CursorShape.PointingHandCursor)
    save.setFixedHeight(48)
    save.setStyleSheet("QPushButton { color: black; background: white; border: none; border-radius: 24px;"
                       " font-size: 15px; font-weight: 700; padding: 0 32px; }"
                       " QPushButton:hover { background: #f0f0f0; }")
    save.clicked.connect(d.accept)
    edit.returnPressed.connect(d.accept)
    btn_row.addWidget(save)
    d.body.addLayout(btn_row)
    note = QLabel("By choosing a photo you confirm you're allowed to use it. Your music files are never renamed or "
                  "changed.")
    note.setWordWrap(True)
    note.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 600;")
    d.body.addWidget(note)
    edit.setFocus()
    d.name_edit, d.description_edit = edit, desc_box
    auto = getattr(parent, "_auto_answer_dialogs", None)
    if auto is not None and isinstance(auto, dict):                      # tests: {"name": ..., "description": ...}
        return auto.get("name", name), auto.get("cover"), auto.get("description", description)
    if d.exec() != QDialog.DialogCode.Accepted:
        return None
    return edit.text().strip(), choice["cover"], (desc_box.toPlainText().strip() if desc_box is not None else None)


def choose_downloads(parent, title, songs):
    """Spotify-like "Download …?" card without the Premium part: Download all, or tick the songs you want.
    `songs`: the songs not downloaded yet. Returns the chosen songs ([] = cancelled)."""
    if getattr(parent, "_auto_answer_dialogs", None) is not None:          # tests
        answer = parent._auto_answer_dialogs
        return list(songs) if answer is True else (list(answer) if isinstance(answer, (list, tuple)) else [])
    d = _Card(parent, light=False)
    d.setMinimumWidth(520)
    h = QLabel(f"Download {title}?")
    h.setWordWrap(True)
    h.setStyleSheet("font-size: 22px; font-weight: 800; color: white;")
    d.body.addWidget(h)
    t = QLabel(f"{len(songs)} song{'s' if len(songs) != 1 else ''} {'aren' if len(songs) != 1 else 'isn'}'t on your "
               "computer yet. Untick any you don't want.")
    t.setWordWrap(True)
    t.setStyleSheet(f"font-size: 14px; color: {theme.SUBDUED};")
    d.body.addWidget(t)
    # The songs, like Spotify's lists: cover, title with the artist underneath, and a round green tick.
    from PyQt6.QtWidgets import QScrollArea, QWidget
    from PyQt6.QtGui import QPixmap
    from .save_picker import RoundTick
    from .library_panel import rounded
    rows_box = QWidget()
    rows_box.setStyleSheet("background: transparent;")
    rv = QVBoxLayout(rows_box)
    rv.setContentsMargins(0, 0, 0, 0)
    rv.setSpacing(2)
    ticks = []

    class _SongRow(QFrame):
        def __init__(self, song):
            super().__init__()
            self.setObjectName("dlRow")
            self.setStyleSheet("#dlRow { background: transparent; border-radius: 4px; }"
                               f" #dlRow:hover {{ background: {theme.HOVER}; }}")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            h = QHBoxLayout(self)
            h.setContentsMargins(8, 4, 8, 4)
            h.setSpacing(12)
            art = QLabel()
            art.setFixedSize(40, 40)
            art.setPixmap(rounded(QPixmap(song.album_cover_path), 40, 4))
            h.addWidget(art)
            texts = QVBoxLayout()
            texts.setSpacing(0)
            name = QLabel(song.title)
            name.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
            who = QLabel(song.artist)
            who.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px;")
            texts.addWidget(name)
            texts.addWidget(who)
            h.addLayout(texts, 1)
            self.tick = RoundTick(True)
            h.addWidget(self.tick)

        def mousePressEvent(self, e):
            if e.button() == Qt.MouseButton.LeftButton:
                self.tick.toggle()

    for s in songs:
        row_w = _SongRow(s)
        rv.addWidget(row_w)
        ticks.append(row_w.tick)
    rv.addStretch()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    scroll.setWidget(rows_box)
    scroll.setMinimumHeight(min(320, 50 * len(songs) + 8))
    d.body.addWidget(scroll)
    row = QHBoxLayout()
    toggle_all = QPushButton()
    toggle_all.setCursor(Qt.CursorShape.PointingHandCursor)
    toggle_all.setStyleSheet(f"QPushButton {{ color: {theme.SUBDUED}; background: transparent; border: none;"
                             " font-weight: 700; font-size: 14px; padding: 8px 4px; } QPushButton:hover { color: white; }")
    row.addWidget(toggle_all)
    row.addStretch()
    cancel = QPushButton("Cancel")
    cancel.setCursor(Qt.CursorShape.PointingHandCursor)
    cancel.setStyleSheet(f"QPushButton {{ color: {theme.SUBDUED}; background: transparent; border: none;"
                         " font-weight: 700; font-size: 14px; padding: 10px 14px; } QPushButton:hover { color: white; }")
    ok = QPushButton()
    ok.setDefault(True)
    ok.setCursor(Qt.CursorShape.PointingHandCursor)
    ok.setStyleSheet(f"QPushButton {{ color: #000000; background: {theme.GREEN}; border: none; border-radius: 20px;"
                     f" font-size: 15px; font-weight: 700; padding: 10px 26px; }} QPushButton:hover {{ background: #3be477; }}"
                     f" QPushButton:disabled {{ background: #535353; }}")

    def count():
        n = sum(1 for t in ticks if t.isChecked())
        ok.setText("Download all" if n == len(ticks) else f"Download {n}")
        ok.setEnabled(n > 0)
        toggle_all.setText("Clear all" if n == len(ticks) else "Select all")

    def flip_all():
        on = not all(t.isChecked() for t in ticks)
        for t in ticks:
            t.setChecked(on)
        count()
    for t in ticks:
        t.toggled.connect(lambda _on: count())
    toggle_all.clicked.connect(flip_all)
    count()
    cancel.clicked.connect(d.reject)
    ok.clicked.connect(d.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    d.body.addLayout(row)
    if d.exec() != QDialog.DialogCode.Accepted:
        return []
    return [s for s, t in zip(songs, ticks) if t.isChecked()]

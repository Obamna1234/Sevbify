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


def confirm(parent, title, text, ok_text="Delete"):
    """Spotify's white confirmation card. text may use <b>…</b>. Returns True for OK."""
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
    cancel = QPushButton("Cancel")
    cancel.setCursor(Qt.CursorShape.PointingHandCursor)
    cancel.setStyleSheet("QPushButton { color: #000000; background: transparent; border: none; font-size: 15px;"
                         " font-weight: 700; padding: 10px 18px; } QPushButton:hover { font-size: 15px;"
                         " color: #000000; }")
    ok = QPushButton(ok_text)
    ok.setCursor(Qt.CursorShape.PointingHandCursor)
    ok.setDefault(True)
    ok.setStyleSheet(f"QPushButton {{ color: #000000; background: {theme.GREEN}; border: none; border-radius: 22px;"
                     f" font-size: 15px; font-weight: 700; padding: 11px 30px; }}"
                     f" QPushButton:hover {{ background: #3be477; }}")
    cancel.clicked.connect(d.reject)
    ok.clicked.connect(d.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    d.body.addLayout(row)
    d.confirm_button, d.cancel_button = ok, cancel
    if getattr(parent, "_auto_answer_dialogs", None) is not None:      # tests
        return bool(parent._auto_answer_dialogs)
    return d.exec() == QDialog.DialogCode.Accepted


class _CoverButton(QPushButton):
    def __init__(self, pixmap):
        super().__init__()
        self.setFixedSize(180, 180)
        self.setIconSize(QSize(180, 180))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Choose photo")
        self.setStyleSheet("QPushButton { background: #3e3e3e; border: none; border-radius: 4px; }"
                           " QPushButton:hover { background: #4a4a4a; }")
        if pixmap is not None and not pixmap.isNull():
            from PyQt6.QtGui import QIcon
            self.setIcon(QIcon(pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation)))


def edit_details(parent, title, name, pixmap=None, can_change_cover=True, name_label="Name"):
    """Spotify's "Edit details": a cover you can click to change, and the name. Returns
    (name, "choose-cover" | None) or None when cancelled."""
    d = _Card(parent, light=False)
    d.setMinimumWidth(560)
    head = QHBoxLayout()
    h = QLabel(title)
    h.setStyleSheet("font-size: 22px; font-weight: 800;")
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
    lbl = QLabel(name_label)
    lbl.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px; font-weight: 700;")
    edit = QLineEdit(name)
    edit.setStyleSheet("QLineEdit { background: #3e3e3e; color: white; border: 1px solid transparent;"
                       " border-radius: 4px; padding: 10px; font-size: 14px; }"
                       " QLineEdit:focus { border: 1px solid #535353; background: #333333; }")
    edit.selectAll()
    col.addWidget(lbl)
    col.addWidget(edit)
    col.addStretch()
    row.addLayout(col, 1)
    d.body.addLayout(row)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    save = QPushButton("Save")
    save.setDefault(True)
    save.setCursor(Qt.CursorShape.PointingHandCursor)
    save.setStyleSheet("QPushButton { color: black; background: white; border: none; border-radius: 22px;"
                       " font-size: 15px; font-weight: 700; padding: 11px 32px; }"
                       " QPushButton:hover { background: #f0f0f0; }")
    save.clicked.connect(d.accept)
    edit.returnPressed.connect(d.accept)
    btn_row.addWidget(save)
    d.body.addLayout(btn_row)
    note = QLabel("Your music files are never renamed or changed.")
    note.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 11px;")
    d.body.addWidget(note)
    edit.setFocus()
    if d.exec() != QDialog.DialogCode.Accepted:
        return None
    return edit.text().strip(), choice["cover"]


def choose_downloads(parent, title, songs):
    """Spotify-like "Download …?" card without the Premium part: Download all, or tick the songs you want.
    `songs`: the songs not downloaded yet. Returns the chosen songs ([] = cancelled)."""
    from PyQt6.QtWidgets import QListWidget, QListWidgetItem
    if getattr(parent, "_auto_answer_dialogs", None) is not None:          # tests
        answer = parent._auto_answer_dialogs
        return list(songs) if answer is True else (list(answer) if isinstance(answer, (list, tuple)) else [])
    d = _Card(parent, light=False)
    d.setMinimumWidth(520)
    h = QLabel(f"Download {title}?")
    h.setWordWrap(True)
    h.setStyleSheet("font-size: 22px; font-weight: 800; color: white;")
    d.body.addWidget(h)
    t = QLabel(f"{len(songs)} song{'s' if len(songs) != 1 else ''} aren't on your computer yet. Download them all, "
               "or untick the ones you don't want.")
    t.setWordWrap(True)
    t.setStyleSheet(f"font-size: 14px; color: {theme.SUBDUED};")
    d.body.addWidget(t)
    lst = QListWidget()
    lst.setMinimumHeight(260)
    lst.setStyleSheet(f"QListWidget {{ background: #1f1f1f; color: white; border: none; border-radius: 6px; font-size: 14px; }}"
                      f" QListWidget::item {{ padding: 6px; }} QListWidget::item:hover {{ background: {theme.HOVER}; }}")
    for s in songs:
        it = QListWidgetItem(f"{s.title}  —  {s.artist}")
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked)
        lst.addItem(it)
    d.body.addWidget(lst)
    row = QHBoxLayout()
    pill = (f"QPushButton {{ color: white; background: transparent; border: 1px solid {theme.DIM}; border-radius: 16px;"
            f" font-weight: 700; padding: 7px 16px; }} QPushButton:hover {{ border-color: white; }}")
    all_btn, none_btn = QPushButton("Select all"), QPushButton("Select none")
    for b, state in ((all_btn, Qt.CheckState.Checked), (none_btn, Qt.CheckState.Unchecked)):
        b.setStyleSheet(pill)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda _=False, st=state: [lst.item(i).setCheckState(st) for i in range(lst.count())])
        row.addWidget(b)
    row.addStretch()
    cancel = QPushButton("Cancel")
    cancel.setStyleSheet("QPushButton { color: white; background: transparent; border: none; font-weight: 700;"
                         " padding: 10px 14px; }")
    ok = QPushButton()
    ok.setDefault(True)
    ok.setCursor(Qt.CursorShape.PointingHandCursor)
    ok.setStyleSheet(f"QPushButton {{ color: #000000; background: {theme.GREEN}; border: none; border-radius: 20px;"
                     f" font-size: 15px; font-weight: 700; padding: 10px 26px; }} QPushButton:hover {{ background: #3be477; }}"
                     f" QPushButton:disabled {{ background: #535353; }}")

    def count():
        n = sum(1 for i in range(lst.count()) if lst.item(i).checkState() == Qt.CheckState.Checked)
        ok.setText("Download all" if n == lst.count() else f"Download {n}")
        ok.setEnabled(n > 0)
    lst.itemChanged.connect(lambda _it: count())
    count()
    cancel.clicked.connect(d.reject)
    ok.clicked.connect(d.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    d.body.addLayout(row)
    if d.exec() != QDialog.DialogCode.Accepted:
        return []
    return [s for i, s in enumerate(songs) if lst.item(i).checkState() == Qt.CheckState.Checked]

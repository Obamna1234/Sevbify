"""'Support the artist': a small card listing where to buy the music straight from the artist (core/support.py).
Each link shows its website's name; nothing opens until you click it."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import theme
from .dialogs import _Card

NOTE = "Enjoying this? Support the artists and podcasters you love: buy their music, go to their shows, or back their show directly."


def _link_row(link, on_open):
    row = QPushButton()
    row.setCursor(Qt.CursorShape.PointingHandCursor)
    row.setStyleSheet("QPushButton { background: #2a2a2a; border: none; border-radius: 8px; text-align: left;"
                      " padding: 10px 14px; } QPushButton:hover { background: #333333; }")
    lay = QVBoxLayout(row)
    lay.setContentsMargins(14, 8, 14, 8)
    lay.setSpacing(2)
    a = QLabel(link["label"])
    a.setTextFormat(Qt.TextFormat.PlainText)
    a.setStyleSheet("font-size: 15px; font-weight: 700; color: white; background: transparent;")
    b = QLabel("Opens " + link["site"])
    b.setTextFormat(Qt.TextFormat.PlainText)
    b.setStyleSheet(f"font-size: 12px; color: {theme.SUBDUED}; background: transparent;")
    for w in (a, b):
        w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(w)
    row.setMinimumHeight(58)
    row.setToolTip(link["url"])
    row.clicked.connect(lambda: on_open(link["url"]))
    return row


class SupportDialog(_Card):
    def __init__(self, win, title, subtitle=""):
        super().__init__(win, light=False)
        self.setMinimumWidth(440)
        h = QLabel(title)
        h.setTextFormat(Qt.TextFormat.PlainText)
        h.setStyleSheet("font-size: 22px; font-weight: 800;")
        self.body.addWidget(h)
        if subtitle:
            s = QLabel(subtitle)
            s.setTextFormat(Qt.TextFormat.PlainText)
            s.setWordWrap(True)
            s.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
            self.body.addWidget(s)
        self.list = QVBoxLayout()
        self.list.setSpacing(8)
        holder = QWidget()
        holder.setLayout(self.list)
        self.body.addWidget(holder)
        self.status = QLabel("Looking for the artist's own links…")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
        self.list.addWidget(self.status)
        note = QLabel(NOTE)
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px; padding-top: 6px;")
        self.body.addWidget(note)
        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton("Close")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet("QPushButton { color: white; background: transparent; border: 1px solid #7c7c7c;"
                            " border-radius: 16px; padding: 6px 16px; font-weight: 700; }"
                            " QPushButton:hover { border-color: white; }")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        self.body.addLayout(row)
        self.links = []

    def show_links(self, links, empty_text):
        self.links = list(links or [])
        if not self.links:
            self.status.setText(empty_text)
            return
        self.status.hide()
        from . import open_web
        for link in self.links:
            self.list.addWidget(_link_row(link, open_web))

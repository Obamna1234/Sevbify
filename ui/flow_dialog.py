"""Playlist ••• → Flow this playlist…: choose how the songs should flow, then Sevbify makes a new playlist
("<name> · Flow") in that order. The original playlist isn't touched; songs in the Flow copy can be dragged
around or removed like in any playlist. The ordering itself is core/flow_order.py (the same on the phones).
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton, QCheckBox,
                             QButtonGroup, QFrame, QProgressBar)
from PyQt6.QtCore import Qt

from . import theme

MODES = [
    ("wind_down", "Energy to calm", "Big, exciting songs first, then the middle ones, ending calm. (Default)"),
    ("build", "Calm to energy", "Starts calm and builds up to the big, exciting songs: good for workouts or getting ready."),
    ("waves", "Waves", "Builds up, eases off, builds up again: hot, cold, hot, cold."),
    ("smooth", "Smooth", "Every song leads gently into the next; genres blend instead of jumping."),
    ("mix", "Mix it up", "A bit of everything: calm, energetic and in-between songs spread through, shuffled."),
    ("genre", "Grouped by genre", "All the synthwave together, then the rock and so on, each smooth inside."),
]

STYLE = (f"QDialog {{ background: #121212; }} QLabel {{ color: #ffffff; background: transparent; }}"
         f" QRadioButton, QCheckBox {{ color: #ffffff; font-size: 14px; font-weight: 600; spacing: 10px; }}"
         " QRadioButton::indicator { width: 14px; height: 14px; border-radius: 9px; border: 2px solid #b3b3b3;"
         " background: transparent; }"
         " QRadioButton::indicator:checked { border: 2px solid #1ed760; background: qradialgradient(cx:0.5, cy:0.5,"
         " radius:0.5, fx:0.5, fy:0.5, stop:0 #1ed760, stop:0.55 #1ed760, stop:0.6 transparent); }"
         " QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 2px solid #b3b3b3; }"
         " QCheckBox::indicator:checked { background: #1ed760; border-color: #1ed760; }"
         " QProgressBar { background: #3e3e3e; border: none; border-radius: 2px; height: 4px; }"
         " QProgressBar::chunk { background: #1ed760; border-radius: 2px; }")


class FlowDialog(QDialog):
    """Returns (mode, artists_apart, start) when accepted."""

    def __init__(self, parent, playlist_name, count):
        super().__init__(parent)
        self.setWindowTitle("Flow")
        self.setStyleSheet(STYLE)
        self.setFixedWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        title = QLabel("Flow this playlist")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        lay.addWidget(title)
        intro = QLabel(f"Puts the {count} songs of “{playlist_name}” in an order that's nice to listen to, using each "
                       "song's tempo, loudness and style (synthwave, chillwave, soft rock, metal…). It makes a new "
                       f"playlist, “{playlist_name} · Flow”: your playlist stays exactly as it is, and you can drag "
                       "songs around in the new one.")
        intro.setWordWrap(True)
        intro.setFixedWidth(472)                     # a fixed width lets word-wrapped text take its full height
        intro.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
        intro.ensurePolished()
        intro.setMinimumHeight(intro.heightForWidth(472))
        lay.addWidget(intro)

        self.group = QButtonGroup(self)
        for k, (key, name, text) in enumerate(MODES):
            box = QFrame()
            box.setObjectName("modeBox")
            box.setStyleSheet("#modeBox { background: #1f1f1f; border-radius: 8px; }")
            b = QVBoxLayout(box)
            b.setContentsMargins(12, 8, 12, 8)
            b.setSpacing(2)
            r = QRadioButton(name)
            r.setProperty("mode", key)
            r.setChecked(k == 0)
            self.group.addButton(r)
            b.addWidget(r)
            why = QLabel(text)
            why.setWordWrap(True)
            why.setFixedWidth(420)
            why.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px; padding-left: 26px;")
            why.ensurePolished()
            why.setMinimumHeight(why.heightForWidth(420))
            b.addWidget(why)
            lay.addWidget(box)

        self.apart = QCheckBox("Don't play the same artist twice in a row")
        self.apart.setChecked(True)
        lay.addWidget(self.apart)
        start_row = QHBoxLayout()
        start_row.addWidget(QLabel("Start with"))
        self.start_group = QButtonGroup(self)
        for k, (key, name) in enumerate((("calm", "a calm song"), ("energetic", "an energetic song"))):
            r = QRadioButton(name)
            r.setProperty("start", key)
            r.setChecked(k == 0)
            self.start_group.addButton(r)
            start_row.addWidget(r)
        start_row.addStretch(1)
        lay.addLayout(start_row)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        lay.addWidget(self.progress)
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px;")
        self.status.hide()
        lay.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet("QPushButton { color: #ffffff; background: transparent; border: none; font-weight: 700;"
                             " padding: 10px 16px; } QPushButton:hover { color: #1ed760; }")
        cancel.clicked.connect(self.reject)
        self.go = QPushButton("Make Flow playlist")
        self.go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go.setFixedHeight(44)
        self.go.setStyleSheet("QPushButton { background: #1ed760; color: #000000; font-weight: 700; font-size: 14px;"
                              " border: none; border-radius: 22px; padding: 0 22px; } QPushButton:hover"
                              " { background: #3be477; } QPushButton:disabled { background: #2a6b40; }")
        self.go.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.go)
        lay.addLayout(buttons)

    def choice(self):
        mode = self.group.checkedButton().property("mode")
        start = self.start_group.checkedButton().property("start")
        return mode, self.apart.isChecked(), start

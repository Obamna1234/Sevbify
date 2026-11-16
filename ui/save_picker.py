"""Spotify's "Add to playlist" pop-up, opened from the green tick next to a song's length.

    Add to playlist
    [Find a playlist      ]
    +  New playlist
    Saved in
      [cover] Locked in 2.0        253 songs   (green tick)
    Recently updated
      [cover] Liked Songs          180 songs   ( )
      ...
                              Cancel   Done

Ticking or unticking only changes what's shown; Done saves it (Cancel or clicking away changes nothing).
"""
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                             QWidget, QAbstractButton)

from . import theme
from .library_panel import rounded

STYLE = """
#savePicker { background: #282828; border-radius: 8px; }
QLabel { background: transparent; color: #ffffff; }
QLabel#pickerTitle { color: #b3b3b3; font-size: 12px; font-weight: 700; }
QLabel#section { color: #b3b3b3; font-size: 12px; font-weight: 700; padding-top: 6px; }
QLineEdit { background: #3e3e3e; color: #ffffff; border: none; border-radius: 4px; padding: 6px 8px;
            font-size: 13px; }
QPushButton#newPl { color: #ffffff; background: transparent; border: none; text-align: left; font-size: 14px;
                    font-weight: 600; padding: 8px 4px; }
QPushButton#newPl:hover { background: #3e3e3e; border-radius: 4px; }
QPushButton#cancel { color: #b3b3b3; background: transparent; border: none; font-weight: 700; font-size: 14px;
                     padding: 6px 12px; }
QPushButton#cancel:hover { color: #ffffff; }
QPushButton#done { color: #000000; background: #ffffff; border: none; border-radius: 15px; font-weight: 700;
                   font-size: 14px; padding: 0 18px; min-height: 32px; max-height: 32px; }
QPushButton#done:hover { background: #f0f0f0; }
QScrollArea { background: transparent; border: none; }
#pickerRow { background: transparent; border-radius: 4px; }
#pickerRow:hover { background: #3e3e3e; }
"""


class RoundTick(QAbstractButton):
    """Spotify's round checkbox: an empty grey circle, or a green circle with a black tick."""

    def __init__(self, checked=False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(3, 3, 16, 16)
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#1ed760"))
            p.drawEllipse(r)
            pen = QPen(QColor("#000000"), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawPolyline(QPolygonF([QPointF(7.5, 11.3), QPointF(10, 13.8), QPointF(14.6, 8.6)]))
        else:
            p.setPen(QPen(QColor("#b3b3b3"), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(r.adjusted(0.7, 0.7, -0.7, -0.7))
        p.end()


class _Row(QFrame):
    def __init__(self, playlist, checked, cover):
        super().__init__()
        self.setObjectName("pickerRow")
        self.playlist = playlist
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 4, 6, 4)
        h.setSpacing(10)
        art = QLabel()
        art.setFixedSize(36, 36)
        art.setPixmap(rounded(cover, 36, 4))
        h.addWidget(art)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(playlist.name)
        name.setStyleSheet("font-size: 14px; font-weight: 600;")
        n = len(playlist.songs)
        count = QLabel(f"{n} song{'s' if n != 1 else ''}")
        count.setStyleSheet("color: #b3b3b3; font-size: 12px;")
        texts.addWidget(name)
        texts.addWidget(count)
        h.addLayout(texts, 1)
        self.tick = RoundTick(checked)
        h.addWidget(self.tick)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.tick.toggle()


class SavePicker(QFrame):
    """The pop-up. `apply(add, remove)` is called with lists of playlists when Done is pressed;
    `new_playlist()` when "New playlist" is pressed."""

    def __init__(self, parent, song, playlists, cover_loader, apply, new_playlist):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.song, self._apply, self._new = song, apply, new_playlist
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QFrame()
        box.setObjectName("savePicker")
        box.setStyleSheet(STYLE)
        outer.addWidget(box)
        v = QVBoxLayout(box)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(6)
        title = QLabel("Add to playlist")
        title.setObjectName("pickerTitle")
        v.addWidget(title)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Find a playlist")
        self.find.setClearButtonEnabled(True)
        self.find.textChanged.connect(self._filter)
        v.addWidget(self.find)
        new = QPushButton("＋   New playlist")
        new.setObjectName("newPl")
        new.setCursor(Qt.CursorShape.PointingHandCursor)
        new.clicked.connect(self._new_clicked)
        v.addWidget(new)

        inside = [p for p in playlists if any(s.key == song.key for s in p.songs)]
        others = sorted([p for p in playlists if p not in inside],
                        key=lambda p: max(getattr(p, "last_played", 0) or 0, getattr(p, "created", 0) or 0),
                        reverse=True)
        self._was = {id(p) for p in inside}
        self.rows = []
        lst = QWidget()
        lv = QVBoxLayout(lst)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(2)
        self._sections = []
        for heading, group in (("Saved in", inside), ("Recently updated", others)):
            if not group:
                continue
            lab = QLabel(heading)
            lab.setObjectName("section")
            lv.addWidget(lab)
            self._sections.append((lab, []))
            for pl in group:
                row = _Row(pl, pl in inside, cover_loader(pl.cover_path))
                lv.addWidget(row)
                self.rows.append(row)
                self._sections[-1][1].append(row)
        lv.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(lst)
        scroll.setMinimumHeight(min(360, 48 * max(1, len(self.rows)) + 40))
        scroll.setMaximumHeight(360)
        lst.setStyleSheet("background: transparent;")
        v.addWidget(scroll)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.close)
        done = QPushButton("Done")
        done.setObjectName("done")
        done.setCursor(Qt.CursorShape.PointingHandCursor)
        done.clicked.connect(self._done)
        buttons.addWidget(cancel)
        buttons.addWidget(done)
        v.addLayout(buttons)
        self.setFixedWidth(300)

    def _filter(self, text):
        q = text.strip().casefold()
        for lab, rows in self._sections:
            shown = 0
            for row in rows:
                ok = not q or q in row.playlist.name.casefold()
                row.setVisible(ok)
                shown += ok
            lab.setVisible(shown > 0)

    def _new_clicked(self):
        self.close()
        self._new()

    def _done(self):
        add = [r.playlist for r in self.rows if r.tick.isChecked() and id(r.playlist) not in self._was]
        remove = [r.playlist for r in self.rows if not r.tick.isChecked() and id(r.playlist) in self._was]
        self.close()
        self._apply(add, remove)

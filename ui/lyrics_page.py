"""Lyrics for the song playing, like Spotify's lyrics view: big lines, the one being sung highlighted and kept in
view; click a line to jump there (when the lyrics are time-synced). No network code here (see core/lyrics.py)."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt6.QtCore import Qt, pyqtSignal

from . import theme


class _Line(QLabel):
    clicked = pyqtSignal(int)

    def __init__(self, text, index, parent=None):
        super().__init__(text or "♪", parent)
        self.index = index
        self.setWordWrap(True)

    def mousePressEvent(self, e):
        self.clicked.emit(self.index)
        super().mousePressEvent(e)


class LyricsPage(QWidget):
    seek_requested = pyqtSignal(int)          # ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lyricsPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"#lyricsPage {{ background: #4a4a4a; border-radius: {theme.RADIUS}px; }}")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(self.scroll)
        self.labels = []
        self.lines_ms = []
        self.current = -2
        self.show_message("Play a song to see its lyrics.")

    def _content(self):
        w = QWidget()
        w.setObjectName("lyricsContent")
        w.setStyleSheet("#lyricsContent { background: transparent; }")
        v = QVBoxLayout(w)
        v.setContentsMargins(48, 40, 48, 60)
        v.setSpacing(14)
        return w, v

    def show_message(self, text, title=""):
        w, v = self._content()
        if title:
            t = QLabel(title)
            t.setStyleSheet("color: white; font-size: 18px; font-weight: 700; background: transparent;")
            v.addWidget(t)
        m = QLabel(text)
        m.setWordWrap(True)
        m.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 22px; font-weight: 700; background: transparent;")
        v.addWidget(m)
        v.addStretch()
        theme.replace_scroll_widget(self.scroll, w)
        self.labels, self.lines_ms, self.current = [], [], -2

    def show_lyrics(self, lyr, title=""):
        """lyr: core.lyrics.Lyrics."""
        w, v = self._content()
        if title:
            t = QLabel(title)
            t.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 14px; font-weight: 600; background: transparent;")
            v.addWidget(t)
        self.labels = []
        self.lines_ms = [ms for ms, _t in lyr.lines]
        texts = [t for _ms, t in lyr.lines] if lyr.synced else lyr.plain.splitlines()
        for i, text in enumerate(texts):
            lab = _Line(text, i)
            if lyr.synced:
                lab.setCursor(Qt.CursorShape.PointingHandCursor)
                lab.clicked.connect(lambda idx: self.seek_requested.emit(self.lines_ms[idx]))
            v.addWidget(lab)
            self.labels.append(lab)
        src = QLabel(f"Lyrics from {lyr.source}" if lyr.source else "")
        src.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px; background: transparent;")
        v.addSpacing(20)
        v.addWidget(src)
        v.addStretch()
        theme.replace_scroll_widget(self.scroll, w)
        self.current = -2
        self.set_position(0 if lyr.synced else None)

    def _style(self, lab, state):
        colour = {"now": "white", "past": "rgba(255,255,255,0.6)", "next": "rgba(0,0,0,0.6)", "plain": "white"}[state]
        lab.setStyleSheet(f"color: {colour}; font-size: 28px; font-weight: 800; background: transparent;")

    def set_position(self, ms):
        """Highlight the line being sung at `ms` (None: plain lyrics, all white)."""
        if not self.labels:
            return
        if ms is None or not self.lines_ms:
            for lab in self.labels:
                self._style(lab, "plain")
            return
        idx = -1
        for i, start in enumerate(self.lines_ms):
            if start <= ms:
                idx = i
            else:
                break
        if idx == self.current:
            return
        self.current = idx
        for i, lab in enumerate(self.labels):
            self._style(lab, "now" if i == idx else ("past" if i < idx else "next"))
        if idx >= 0:
            lab = self.labels[idx]
            bar = self.scroll.verticalScrollBar()
            bar.setValue(max(0, lab.y() - self.scroll.viewport().height() // 3))

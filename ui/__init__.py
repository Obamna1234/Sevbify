"""Sevbify's windows and pages (PyQt6).

Safety: text from the internet (song and episode titles, lyrics, descriptions, artist bios) is shown in labels.
Qt guesses whether a label's text is HTML, so every label made here shows plain text unless it says otherwise
(setTextFormat(RichText) for the few with our own formatting).
"""
from PyQt6.QtCore import Qt as _Qt
from PyQt6.QtWidgets import QLabel as _QLabel

if not getattr(_QLabel, "_sevbify_plain", False):
    _original_init = _QLabel.__init__

    def _plain_init(self, *args, **kwargs):
        _original_init(self, *args, **kwargs)
        self.setTextFormat(_Qt.TextFormat.PlainText)

    _QLabel.__init__ = _plain_init
    _QLabel._sevbify_plain = True

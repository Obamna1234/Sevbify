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

# Message boxes too: their text often holds a playlist, song or file name, which must never be read as HTML.
from PyQt6.QtWidgets import QMessageBox as _QMessageBox

if not getattr(_QMessageBox, "_sevbify_plain", False):
    _box_init = _QMessageBox.__init__

    def _plain_box_init(self, *args, **kwargs):
        _box_init(self, *args, **kwargs)
        self.setTextFormat(_Qt.TextFormat.PlainText)

    _QMessageBox.__init__ = _plain_box_init

    def _plain_static(icon, default_buttons):
        def show(parent, title, text, buttons=default_buttons,
                 defaultButton=_QMessageBox.StandardButton.NoButton):
            box = _QMessageBox(icon, title, text, buttons, parent)
            if defaultButton != _QMessageBox.StandardButton.NoButton:
                box.setDefaultButton(defaultButton)
            return _QMessageBox.StandardButton(box.exec())
        return staticmethod(show)

    _SB = _QMessageBox.StandardButton
    _QMessageBox.question = _plain_static(_QMessageBox.Icon.Question, _SB.Yes | _SB.No)
    _QMessageBox.warning = _plain_static(_QMessageBox.Icon.Warning, _SB.Ok)
    _QMessageBox.information = _plain_static(_QMessageBox.Icon.Information, _SB.Ok)
    _QMessageBox.critical = _plain_static(_QMessageBox.Icon.Critical, _SB.Ok)
    _QMessageBox._sevbify_plain = True


# Language: menu items Sevbify makes look like "≡  Add to queue" (a symbol, two spaces, the words). Only those are
# translated (core/i18n), so a playlist or song that happens to be called "Lyrics" is never changed.
from PyQt6.QtWidgets import QMenu as _QMenu  # noqa: E402

if not getattr(_QMenu, "_sevbify_tr", False):
    import re as _re
    _ITEM = _re.compile(r"^(\W{1,3}\s{2})(.+)$")

    def _tr_item(text):
        from core.i18n import tr
        m = _ITEM.match(text) if isinstance(text, str) else None
        return m.group(1) + tr(m.group(2)) if m else text

    _orig_add_action, _orig_add_menu = _QMenu.addAction, _QMenu.addMenu

    def _add_action(self, *args, **kwargs):
        args = tuple(_tr_item(a) if isinstance(a, str) else a for a in args)
        return _orig_add_action(self, *args, **kwargs)

    def _add_menu(self, *args, **kwargs):
        args = tuple(_tr_item(a) if isinstance(a, str) else a for a in args)
        return _orig_add_menu(self, *args, **kwargs)

    _QMenu.addAction, _QMenu.addMenu = _add_action, _add_menu
    _QMenu._sevbify_tr = True


def open_web(url):
    """Open a web page in the browser: only http(s) addresses, never file:, smb:, ms-… or other kinds of links,
    because links can come from the internet."""
    from core.online.net import is_web_url
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices
    if is_web_url(url):
        QDesktopServices.openUrl(QUrl(url))
        return True
    return False

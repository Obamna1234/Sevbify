"""Sevbify's look: colours, fonts and the base stylesheet (Spotify-inspired).

Every screen uses these values so the app looks consistent. The font is
Figtree (SIL Open Font License, bundled in assets/fonts), the closest free
match to Spotify's own typeface.
"""
import glob
import os

from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtCore import Qt

from core.paths import RESOURCE_ROOT

# --- Colours ---------------------------------------------------------------
BLACK = "#000000"          # window background, gaps between panels
PANEL = "#121212"          # the three rounded panels
ELEVATED = "#1f1f1f"       # cards / hover on panels
HOVER = "#2a2a2a"
SELECTED = "#333333"
ROW_HOVER = "#2a2a2a"       # song list row under the mouse (Spotify grey)
ROW_SELECTED = "#3e3e3e"    # selected song row
TEXT = "#ffffff"
SUBDUED = "#b3b3b3"
DIM = "#727272"
GREEN = "#1ed760"
GREEN_DARK = "#1db954"
RED = "#f15e6c"
RADIUS = 8
GAP = 8

FONT_FAMILY = "Figtree"
_fonts_loaded = False


def load_fonts():
    """Register the bundled fonts once (safe to call many times)."""
    global _fonts_loaded, FONT_FAMILY
    if _fonts_loaded:
        return FONT_FAMILY
    found = False
    for path in sorted(glob.glob(os.path.join(str(RESOURCE_ROOT), "assets", "fonts", "*.ttf"))):
        if QFontDatabase.addApplicationFont(path) >= 0:
            found = True
    if not found:
        FONT_FAMILY = "Segoe UI"
    _fonts_loaded = True
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        f = app.font()
        # Figtree covers Latin; these fill in Cyrillic, Greek, Japanese, etc. per system.
        f.setFamilies([FONT_FAMILY, "Segoe UI", "Yu Gothic UI", "Helvetica Neue", "Hiragino Sans",
                       "Noto Sans", "Noto Sans CJK JP", "DejaVu Sans"])
        app.setFont(f)
    return FONT_FAMILY


def font(px=14, weight=400):
    f = QFont(FONT_FAMILY)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(weight))
    return f


def base_stylesheet():
    return f"""
    QMainWindow, QDialog {{ background: {BLACK}; }}
    QWidget {{ color: {TEXT}; }}
    QAbstractScrollArea, QWidget#qt_scrollarea_viewport {{ background: transparent; }}
    QToolTip {{ background: #282828; color: {TEXT}; border: none; padding: 6px 8px; border-radius: 4px; }}
    QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.28); border-radius: 0; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.45); }}
    QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: rgba(255,255,255,0.28); min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
    QMenu {{ background: #282828; color: {TEXT}; border: none; padding: 4px; font-size: 14px; border-radius: 4px; }}
    QMenu::item {{ padding: 10px 28px 10px 12px; border-radius: 2px; }}
    QMenu::item:selected {{ background: #3e3e3e; }}
    QMenu::item:disabled {{ color: {DIM}; }}
    QMenu::separator {{ height: 1px; background: #3e3e3e; margin: 4px 0; }}
    QInputDialog QLineEdit, QDialog QLineEdit {{ background: #2a2a2a; color: {TEXT}; border: 1px solid #3e3e3e;
        border-radius: 4px; padding: 8px; }}
    QDialog QPushButton {{ color: {TEXT}; background: transparent; border: 1px solid {DIM}; border-radius: 16px;
        padding: 6px 18px; font-weight: 700; min-height: 20px; }}
    QDialog QPushButton:hover {{ border-color: {TEXT}; }}
    QMessageBox QLabel, QInputDialog QLabel {{ color: {TEXT}; }}
    """


def apply_dark_palette(app):
    """Dark colours for every widget, including the parts Windows would otherwise draw in its light system
    colours (scroll-area backgrounds, selected rows, menus)."""
    from PyQt6.QtGui import QPalette, QColor
    pal = app.palette()
    roles = {
        QPalette.ColorRole.Window: PANEL, QPalette.ColorRole.Base: PANEL, QPalette.ColorRole.AlternateBase: ELEVATED,
        QPalette.ColorRole.WindowText: TEXT, QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Button: ELEVATED, QPalette.ColorRole.ToolTipBase: "#282828",
        QPalette.ColorRole.ToolTipText: TEXT, QPalette.ColorRole.PlaceholderText: DIM,
        QPalette.ColorRole.Highlight: ROW_SELECTED, QPalette.ColorRole.HighlightedText: TEXT,
        QPalette.ColorRole.Link: GREEN,
    }
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for role, colour in roles.items():
            pal.setColor(group, role, QColor(colour))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(DIM))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(DIM))
    app.setPalette(pal)


def panel_style(object_name):
    """Rounded #121212 panel; use with setObjectName(object_name)."""
    return f"#{object_name} {{ background: {PANEL}; border-radius: {RADIUS}px; }}"


PILL = (f"QPushButton {{ color: {TEXT}; background: transparent; border: 1px solid {DIM}; padding: 6px 16px;"
        f" border-radius: 16px; font-weight: 700; font-size: 13px; }} QPushButton:hover {{ border-color: {TEXT}; }}")
GREEN_PILL = (f"QPushButton {{ color: black; background: {GREEN}; padding: 8px 18px; border: none; border-radius: 18px;"
              f" font-weight: 700; font-size: 14px; }} QPushButton:hover {{ background: #3be477; }}")
CHIP = (f"QPushButton {{ color: {TEXT}; background: {HOVER}; border: none; border-radius: 16px; padding: 6px 12px;"
        f" font-size: 13px; }} QPushButton:hover {{ background: {SELECTED}; }}"
        f" QPushButton:checked {{ background: {TEXT}; color: black; }}")


def replace_scroll_widget(scroll, widget):
    """Put new content in a scroll area. The old content is deleted later, after the current click or key
    press has finished: deleting it straight away crashes when the click came from a widget inside it."""
    old = scroll.widget()
    if old is not None:
        release_mouse_inside(old)
        # Hide it BEFORE taking it out. takeWidget() makes it a window of its own for a moment; on Windows a
        # still-visible one flashed up as a small "Sevbify" window that kept the mouse (beta.6 test).
        old.hide()
    old = scroll.takeWidget()
    scroll.setWidget(widget)
    if old is not None:
        old.setParent(_graveyard(scroll))   # parked under a never-shown holder, never a window of its own
        old.hide()
        old.deleteLater()


def _graveyard(near=None):
    """A hidden widget that holds pages waiting to be deleted (never shown, so nothing in it can appear).
    It lives inside the same window, so it is cleaned up with it (a free-floating one crashed Python at exit)."""
    from PyQt6.QtWidgets import QWidget
    top = near.window() if near is not None else None
    holder = getattr(top, "_sevbify_graveyard", None) if top is not None else None
    if holder is None:
        holder = QWidget(top)
        holder.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        holder.hide()
        if top is not None:
            top._sevbify_graveyard = holder
    return holder


def release_mouse_inside(widget):
    """If the mouse button is held on something inside `widget`, let go of it first."""
    from PyQt6.QtWidgets import QWidget
    grabber = QWidget.mouseGrabber()
    if grabber is not None and (grabber is widget or widget.isAncestorOf(grabber)):
        grabber.releaseMouse()


def user_is_busy():
    """True while a mouse button is held down or a menu is open: rebuilding a page then (e.g. because a download
    finished) pulls widgets out from under the click or the menu."""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    return QApplication.mouseButtons() != Qt.MouseButton.NoButton or QApplication.activePopupWidget() is not None


def apply_app_behaviour(app):
    """Menus that switch instantly like Spotify's: no fade/slide animation and no delay before a submenu
    (File → Edit → View) opens. With Windows' defaults the old submenu faded out and the new one appeared
    a quarter of a second later, which looked like blinking."""
    from PyQt6.QtWidgets import QProxyStyle, QStyle
    from PyQt6.QtCore import Qt

    class _Style(QProxyStyle):
        def styleHint(self, hint, option=None, widget=None, returnData=None):
            if hint == QStyle.StyleHint.SH_Menu_SubMenuPopupDelay:
                return 0
            if hint == QStyle.StyleHint.SH_Menu_SubMenuSloppyCloseTimeout:
                return 150
            if hint == QStyle.StyleHint.SH_Menu_FadeOutOnHide:
                return 0
            return super().styleHint(hint, option, widget, returnData)

    for effect in (Qt.UIEffect.UI_AnimateMenu, Qt.UIEffect.UI_FadeMenu, Qt.UIEffect.UI_AnimateCombo,
                   Qt.UIEffect.UI_AnimateTooltip, Qt.UIEffect.UI_FadeTooltip):
        app.setEffectEnabled(effect, False)
    style = _Style()                      # wraps the platform's default style
    app.setStyle(style)
    app._sevbify_style = style            # keep a reference
    return style

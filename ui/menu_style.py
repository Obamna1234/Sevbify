"""Right-click menus that look like Spotify's: dark grey (#282828) with rounded corners, 14 px white text, roomy
rows, a light hover, and thin outline icons drawn by ui/icons.py instead of the text symbols the menu entries are
written with ("≡  Add to queue" shows as [queue icon] Add to queue).

Menus are still built with plain addAction("<symbol>  <text>") everywhere; spotify_menu() turns the symbol into
an icon just before the menu shows, for the menu and its sub-menus.
"""
import re

from PyQt6.QtCore import Qt

from . import icons

STYLE = """
QMenu { background: #282828; color: rgba(255,255,255,0.9); border: none; border-radius: 4px; padding: 4px;
        font-size: 14px; }
QMenu::item { padding: 10px 40px 10px 40px; border-radius: 2px; background: transparent; }
QMenu::item:selected { background: #3e3e3e; color: #ffffff; }
QMenu::item:disabled { color: #6a6a6a; }
QMenu::icon { padding-left: 14px; }
QMenu::separator { height: 1px; background: #3e3e3e; margin: 4px 8px; }
QMenu::right-arrow { width: 10px; height: 10px; padding-right: 12px; }
"""

ICON = "#b3b3b3"
_PREFIX = re.compile(r"^(\S{1,3})\s{2,}(\S.*)$")


def _icon_for(symbol, text):
    t = text.casefold()
    if symbol in ("♥",):
        return icons.heart("#1ed760", 16, filled=True)
    if symbol in ("♡",):
        return icons.heart(ICON, 16)
    if symbol in ("＋", "+"):
        return icons.plus(ICON, 16)
    if symbol == "≡":
        return icons.queue(ICON, 16)
    if symbol == "⬇":
        return icons.download(ICON, 16)
    if symbol in ("✕", "⊖"):
        return icons.minus_circle(ICON, 16) if "remove" in t or "delete" in t else icons.close(ICON, 16)
    if symbol == "📂":
        return icons.folder(ICON, 16)
    if symbol in ("☾", "🌙"):
        return icons.moon(ICON, 16)
    if symbol == "▶":
        return icons.filled_play(ICON, 16)
    if symbol == "▷":
        return icons.outline_play(ICON, 16)
    if symbol == "◉":
        return icons.radio(ICON, 16)
    if symbol == "👤":
        return icons.person(ICON, 16)
    if symbol == "💿":
        return icons.disc(ICON, 16)
    if symbol == "↗":
        return icons.external(ICON, 16)
    if symbol == "▣":
        return icons.video(ICON, 16)
    if symbol == "↑":
        return icons.arrow("up", ICON, 16)
    if symbol == "↓":
        return icons.arrow("down", ICON, 16)
    if symbol == "■":
        return icons.stop_square(ICON, 16)
    if symbol in ("⤴", "⇪", "📤"):
        return icons.share(ICON, 16)
    if symbol == "📁":
        return icons.folder(ICON, 16)
    if symbol == "✎":
        return icons.pencil(ICON, 16)
    if symbol == "✓":
        return icons.check("#1ed760", 16)
    if symbol == "♫":
        return icons.note(ICON, 16)
    if symbol == "🖼":
        return icons.image(ICON, 16)
    if symbol == "↻":
        return icons.repeat(ICON, 16)
    if symbol == "❚❚":
        return icons.pause(ICON, 16)
    return None


def polish(menu):
    """Swap the leading symbols for icons (once), for this menu and every sub-menu."""
    menu.setStyleSheet(STYLE)
    for action in menu.actions():
        sub = action.menu()
        if sub is not None:
            if not sub.property("sevbify_rounded"):
                sub.setProperty("sevbify_rounded", True)
                sub.setWindowFlags(sub.windowFlags() | Qt.WindowType.FramelessWindowHint
                                   | Qt.WindowType.NoDropShadowWindowHint)
                sub.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            polish(sub)
        if action.isSeparator() or action.property("sevbify_polished"):
            continue
        action.setProperty("sevbify_polished", True)
        m = _PREFIX.match(action.text())
        if not m:
            continue
        icon = _icon_for(m.group(1), m.group(2))
        if icon is not None:
            action.setIcon(icon)
            action.setText(m.group(2))
            action.setIconVisibleInMenu(True)


def spotify_menu(menu):
    """Call once on a new QMenu: rounded corners and the icons, applied each time it's about to show."""
    menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                        | Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    menu.setStyleSheet(STYLE)
    menu.aboutToShow.connect(lambda: polish(menu))
    return menu

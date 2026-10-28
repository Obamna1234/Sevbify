"""Top bar: back/forward, Home, the "What do you want to play?" search pill,
download progress, online status and Settings (Spotify layout)."""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from . import icons, theme


class TopBar(QWidget):
    back_clicked = pyqtSignal()
    forward_clicked = pyqtSignal()
    home_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    search_activated = pyqtSignal()           # search box clicked / typed into
    browse_clicked = pyqtSignal()             # the Browse button in the search pill
    downloads_clicked = pyqtSignal()          # the download progress pill was clicked
    menu_clicked = pyqtSignal()               # the ⋯ button (File / Edit / View / Playback / Help)
    online_toggled = pyqtSignal()             # the Online / Offline button was clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(8)

        self.menu_btn = QPushButton("•••")
        self.menu_btn.setToolTip("Menu")
        self.menu_btn.setFixedSize(40, 32)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setStyleSheet(f"QPushButton {{ color: {theme.SUBDUED}; background: transparent; border: none;"
                                    f" font-size: 14px; font-weight: 800; letter-spacing: 1px; }}"
                                    f" QPushButton:hover {{ color: {theme.TEXT}; }}")
        self.menu_btn.clicked.connect(self.menu_clicked.emit)
        h.addWidget(self.menu_btn)
        self.back_btn = self._round(icons.chevron("left", theme.TEXT), "Go back", 32, "transparent")
        self.forward_btn = self._round(icons.chevron("right", theme.TEXT), "Go forward", 32, "transparent")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        self.forward_btn.clicked.connect(self.forward_clicked.emit)
        h.addWidget(self.back_btn)
        h.addWidget(self.forward_btn)
        h.addStretch(1)

        # Home + search sit in the exact middle of the window whatever is on the left or right (the online
        # state text or the download pill used to push them sideways). They're placed by _place_center().
        self.center = QWidget(self)
        c = QHBoxLayout(self.center)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(8)
        self._left_group = [self.menu_btn, self.back_btn, self.forward_btn]

        self.home_btn = self._round(icons.home(theme.TEXT, filled=True), "Home", 48, theme.ELEVATED)
        self.home_btn.clicked.connect(self.home_clicked.emit)
        c.addWidget(self.home_btn)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("What do you want to play?")
        self.search_edit.addAction(icons.search(theme.SUBDUED, 24), QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.setFixedHeight(48)
        self.search_edit.setMinimumWidth(260)
        self.search_edit.setMaximumWidth(9999)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setStyleSheet(
            f"QLineEdit {{ background: {theme.ELEVATED}; color: {theme.TEXT}; border: 1px solid {theme.ELEVATED};"
            f" border-radius: 24px; padding: 0 16px 0 8px; font-size: 15px; }}"
            f" QLineEdit:hover {{ background: {theme.HOVER}; border-color: {theme.HOVER}; }}"
            f" QLineEdit:focus {{ border: 2px solid {theme.TEXT}; }}")
        self.search_edit.textEdited.connect(lambda _t: self.search_activated.emit())
        self.search_edit.mousePressEvent = self._search_pressed
        # Browse button inside the search pill (right end), like Spotify's.
        self.browse_btn = QPushButton(self.search_edit)
        self.browse_btn.setIcon(icons.browse(theme.SUBDUED, 26))
        self.browse_btn.setIconSize(QSize(26, 26))
        self.browse_btn.setFixedSize(36, 36)
        self.browse_btn.setToolTip("Browse")
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-left: 1px solid"
                                      f" {theme.DIM}; border-radius: 0; }} QPushButton:hover {{ background: transparent; }}")
        self.browse_btn.clicked.connect(self.browse_clicked.emit)
        # Clear (✕) sits left of the divider, like Spotify's, and only while there's text.
        self.clear_btn = QPushButton(self.search_edit)
        self.clear_btn.setIcon(icons.close(theme.SUBDUED, 18))
        self.clear_btn.setIconSize(QSize(18, 18))
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.setToolTip("Clear search field")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 16px; }"
                                     " QPushButton:hover { background: rgba(255,255,255,0.08); }")
        self.clear_btn.clicked.connect(lambda: (self.search_edit.clear(), self.search_edit.setFocus()))
        self.clear_btn.hide()
        self.search_edit.textChanged.connect(lambda t: self.clear_btn.setVisible(bool(t)))
        self.search_edit.setTextMargins(0, 0, 76, 0)
        self.search_edit.resizeEvent = self._place_browse_button
        c.addWidget(self.search_edit, 1)

        # Download progress ("⬇ 2 of 5 · Song"); hidden when nothing is downloading.
        self.downloads_btn = QPushButton()
        self.downloads_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.downloads_btn.setMaximumWidth(280)
        self.downloads_btn.setStyleSheet(self._pill_style(theme.TEXT))
        self.downloads_btn.setFixedHeight(28)
        self.downloads_btn.clicked.connect(self.downloads_clicked.emit)
        self.downloads_btn.hide()
        h.addWidget(self.downloads_btn)

        # Click to go offline / online (Sevbify contacts nothing at all while offline).
        self.online_label = QPushButton()
        self.online_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.online_label.clicked.connect(self.online_toggled.emit)
        h.addWidget(self.online_label)
        self.settings_btn = self._round(icons.gear(theme.SUBDUED, 20), "Settings", 36, "transparent")
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        h.addWidget(self.settings_btn)
        self.set_online_state("unknown")
        self.set_history(False, False)

    CENTER_MAX = 48 + 8 + 480                 # Home button + gap + Spotify-width search pill

    def _place_center(self):
        w = self.width()
        left = max(b.geometry().right() for b in self._left_group) + 12
        right_items = [x for x in (self.downloads_btn, self.online_label, self.settings_btn) if not x.isHidden()]
        right = min((x.geometry().left() for x in right_items), default=w) - 12
        cw = min(self.CENTER_MAX, w - 2 * max(left, w - right))
        cw = max(cw, min(self.CENTER_MAX, right - left), 260)
        x = (w - cw) // 2
        if x < left:                       # narrow window: keep clear of the buttons on the left
            x = left
        cw = max(200, min(cw, right - x))
        self.center.setGeometry(x, (self.height() - 48) // 2, cw, 48)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._place_center)     # after the layout has placed the side buttons

    def showEvent(self, e):
        super().showEvent(e)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._place_center)

    def _place_browse_button(self, event):
        QLineEdit.resizeEvent(self.search_edit, event)
        self.browse_btn.move(self.search_edit.width() - 44, (self.search_edit.height() - 36) // 2)
        self.clear_btn.move(self.search_edit.width() - 82, (self.search_edit.height() - 32) // 2)

    def _search_pressed(self, event):
        QLineEdit.mousePressEvent(self.search_edit, event)
        self.search_activated.emit()

    @staticmethod
    def _round(icon, tip, size, bg):
        b = QPushButton()
        b.setIcon(icon)
        b.setIconSize(QSize(int(size * 0.55), int(size * 0.55)))
        b.setFixedSize(size, size)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background: {bg}; border: none; border-radius: {size // 2}px; }}"
                        f" QPushButton:hover {{ background: {theme.HOVER}; }}"
                        f" QPushButton:disabled {{ background: transparent; }}")
        return b

    def set_history(self, can_back, can_forward):
        self.back_btn.setEnabled(can_back)
        self.forward_btn.setEnabled(can_forward)
        self.back_btn.setIcon(icons.chevron("left", theme.TEXT if can_back else theme.DIM))
        self.forward_btn.setIcon(icons.chevron("right", theme.TEXT if can_forward else theme.DIM))

    def set_home_active(self, active):
        self.home_btn.setIcon(icons.home(theme.TEXT, filled=active))

    def set_downloads(self, text: str, tip: str = "", failed: bool = False):
        """Show download progress, or hide the pill when text is empty."""
        if not text:
            self.downloads_btn.hide()
            self._relayout()
            return
        text = text[2:] if text.startswith("⬇ ") else text     # the drawn icon replaces the emoji arrow
        self.downloads_btn.setIcon(icons.download(theme.RED if failed else theme.TEXT, 16))
        metrics = self.downloads_btn.fontMetrics()
        self.downloads_btn.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, 230))
        self.downloads_btn.setToolTip(tip or text)
        self.downloads_btn.setStyleSheet(self._pill_style(theme.RED if failed else theme.TEXT))
        self.downloads_btn.show()
        self._relayout()

    def _relayout(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._place_center)

    @staticmethod
    def _pill_style(colour):
        return (f"QPushButton {{ color: {colour}; background: {theme.ELEVATED}; border: none; border-radius: 14px;"
                f" padding: 5px 12px; font-size: 12px; font-weight: 600; text-align: left; }}"
                f" QPushButton:hover {{ background: {theme.HOVER}; }}")

    def set_online_state(self, state: str):
        """state: "online", "offline", "disabled" or "unknown"."""
        text, color, tip = {
            "online": ("● Online", theme.GREEN, "Online and working. Click to go offline: Sevbify then contacts "
                                                "nothing at all (your own music and downloads still play)."),
            "offline": ("● No internet", theme.RED, "Online, but the internet can't be reached. Your own music "
                                                    "still works. Click to go offline on purpose."),
            "disabled": ("● Offline", theme.SUBDUED, "Offline: Sevbify contacts nothing (no search, streaming, "
                                                     "radio, podcasts or downloads). Click to go online."),
        }.get(state, ("● Online", theme.DIM, "Online. Click to go offline."))
        self.online_state = state
        self.online_label.setText(text)
        self.online_label.setStyleSheet(
            f"QPushButton {{ color: {color}; background: transparent; border: none; border-radius: 14px;"
            f" font-size: 12px; font-weight: 600; padding: 4px 10px; }}"
            f" QPushButton:hover {{ background: {theme.HOVER}; }}")
        self.online_label.setToolTip(tip)
        # Same width whatever it says, so nothing next to it moves.
        self.online_label.setFixedWidth(self.online_label.fontMetrics().horizontalAdvance("● No internet") + 28)

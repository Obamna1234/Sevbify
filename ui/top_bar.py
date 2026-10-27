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
    downloads_clicked = pyqtSignal()          # the download progress pill was clicked
    menu_clicked = pyqtSignal()               # the ⋯ button (File / Edit / View / Playback / Help)

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

        self.home_btn = self._round(icons.home(theme.TEXT, filled=True), "Home", 48, theme.ELEVATED)
        self.home_btn.clicked.connect(self.home_clicked.emit)
        h.addWidget(self.home_btn)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("What do you want to play?")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(icons.search(theme.SUBDUED, 24), QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.setFixedHeight(48)
        self.search_edit.setMinimumWidth(260)
        self.search_edit.setMaximumWidth(480)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setStyleSheet(
            f"QLineEdit {{ background: {theme.ELEVATED}; color: {theme.TEXT}; border: 1px solid {theme.ELEVATED};"
            f" border-radius: 24px; padding: 0 16px 0 8px; font-size: 15px; }}"
            f" QLineEdit:hover {{ background: {theme.HOVER}; border-color: {theme.HOVER}; }}"
            f" QLineEdit:focus {{ border: 2px solid {theme.TEXT}; }}")
        self.search_edit.textEdited.connect(lambda _t: self.search_activated.emit())
        self.search_edit.mousePressEvent = self._search_pressed
        h.addWidget(self.search_edit, 2)
        h.addStretch(1)

        # Download progress ("⬇ 2 of 5 · Song"); hidden when nothing is downloading.
        self.downloads_btn = QPushButton()
        self.downloads_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.downloads_btn.setMaximumWidth(280)
        self.downloads_btn.setStyleSheet(self._pill_style(theme.TEXT))
        self.downloads_btn.setFixedHeight(28)
        self.downloads_btn.clicked.connect(self.downloads_clicked.emit)
        self.downloads_btn.hide()
        h.addWidget(self.downloads_btn)

        self.online_label = QLabel()
        self.online_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.online_label.mousePressEvent = lambda e: self.settings_clicked.emit()
        h.addWidget(self.online_label)
        self.settings_btn = self._round(icons.gear(theme.SUBDUED, 20), "Settings", 36, "transparent")
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        h.addWidget(self.settings_btn)
        self.set_online_state("unknown")
        self.set_history(False, False)

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
            return
        text = text[2:] if text.startswith("⬇ ") else text     # the drawn icon replaces the emoji arrow
        self.downloads_btn.setIcon(icons.download(theme.RED if failed else theme.TEXT, 16))
        metrics = self.downloads_btn.fontMetrics()
        self.downloads_btn.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, 230))
        self.downloads_btn.setToolTip(tip or text)
        self.downloads_btn.setStyleSheet(self._pill_style(theme.RED if failed else theme.TEXT))
        self.downloads_btn.show()

    @staticmethod
    def _pill_style(colour):
        return (f"QPushButton {{ color: {colour}; background: {theme.ELEVATED}; border: none; border-radius: 14px;"
                f" padding: 5px 12px; font-size: 12px; font-weight: 600; text-align: left; }}"
                f" QPushButton:hover {{ background: {theme.HOVER}; }}")

    def set_online_state(self, state: str):
        """state: "online", "offline", "disabled" or "unknown"."""
        text, color, tip = {
            "online": ("● Online", theme.GREEN, "Online features are on and working."),
            "offline": ("● Offline", theme.RED, "Can't reach the internet. Your own music still works."),
            "disabled": ("● Online features off", theme.DIM, "Switched off in Settings. Click to change."),
        }.get(state, ("● Online", theme.DIM, "Online features are on."))
        self.online_label.setText(text)
        self.online_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600; padding: 0 6px;")
        self.online_label.setToolTip(tip)

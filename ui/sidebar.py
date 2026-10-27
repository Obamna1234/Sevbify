# sidebar.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy, QLabel
from PyQt6.QtCore import pyqtSignal, Qt

class Sidebar(QWidget):
    # Signals for main window
    home_clicked = pyqtSignal()
    search_clicked = pyqtSignal()
    library_clicked = pyqtSignal()
    playlists_clicked = pyqtSignal()  # NEW signal for playlists
    settings_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #121212;")
        self.setFixedWidth(200)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 20, 10, 20)
        self.layout.setSpacing(15)
        self.setLayout(self.layout)

        # Home Button
        self.home_btn = QPushButton("🏠 Home")
        self._style_button(self.home_btn)
        self.home_btn.clicked.connect(self.home_clicked.emit)
        self.layout.addWidget(self.home_btn)

        # Search Button
        self.search_btn = QPushButton("🔍 Search")
        self._style_button(self.search_btn)
        self.search_btn.clicked.connect(self.search_clicked.emit)
        self.layout.addWidget(self.search_btn)

        # Library Button
        self.library_btn = QPushButton("📚 Your Library")
        self._style_button(self.library_btn)
        self.library_btn.clicked.connect(self.library_clicked.emit)
        self.layout.addWidget(self.library_btn)

        # Playlists Button (new)
        self.playlists_btn = QPushButton("🎵 Playlists")
        self._style_button(self.playlists_btn)
        self.playlists_btn.clicked.connect(self.playlists_clicked.emit)
        self.layout.addWidget(self.playlists_btn)

        self.layout.addStretch()

        # Online status + Settings, pinned to the bottom.
        self.online_label = QLabel()
        self.online_label.setStyleSheet("color: #b3b3b3; font-size: 12px; padding-left: 10px;")
        self.online_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.online_label.mousePressEvent = lambda e: self.settings_clicked.emit()
        self.layout.addWidget(self.online_label)
        self.set_online_state("unknown")

        self.settings_btn = QPushButton("⚙ Settings")
        self._style_button(self.settings_btn)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        self.layout.addWidget(self.settings_btn)

        self._buttons = {
            "home": self.home_btn,
            "search": self.search_btn,
            "library": self.library_btn,
            "playlists": self.playlists_btn,
        }
        for btn in self._buttons.values():
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
        self.set_active("home")

    def set_online_state(self, state: str):
        """state: "online", "offline", "disabled" or "unknown"."""
        text, color, tip = {
            "online": ("● Online", "#1db954", "Online features are on and working."),
            "offline": ("● Offline", "#f15e6c", "Can't reach the internet. Your own music still works."),
            "disabled": ("● Online features off", "#727272", "Switched off in Settings. Click to change."),
        }.get(state, ("● Online", "#727272", "Online features are on."))
        self.online_label.setText(text)
        self.online_label.setStyleSheet(f"color: {color}; font-size: 12px; padding-left: 10px;")
        self.online_label.setToolTip(tip)

    def set_active(self, name: str):
        """Highlight the button for the page currently shown."""
        btn = self._buttons.get(name)
        if btn is not None:
            btn.setChecked(True)

    def _style_button(self, btn: QPushButton):
        """Apply consistent style to sidebar buttons."""
        btn.setStyleSheet("""
            QPushButton {
                color: white;
                font-size: 14px;
                border: none;
                text-align: left;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:checked {
                background-color: #282828;
                font-weight: bold;
            }
        """)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

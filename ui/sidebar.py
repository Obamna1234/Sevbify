# sidebar.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt6.QtCore import pyqtSignal, Qt

class Sidebar(QWidget):
    # Signals for main window
    home_clicked = pyqtSignal()
    search_clicked = pyqtSignal()
    library_clicked = pyqtSignal()
    playlists_clicked = pyqtSignal()  # NEW signal for playlists

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
        """)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

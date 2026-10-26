# Home_View.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt

class HomeView(QWidget):
    def __init__(self, parent=None):  # <- allow parent
        super().__init__(parent)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        title = QLabel("Welcome to Spotify Replica")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        self.layout.addWidget(title)

        # Example placeholder playlists
        playlists = ["Top Hits", "Chill Vibes", "Relaxing Music", "Focus Playlist", "Party Hits"]
        for name in playlists:
            label = QLabel(name)
            label.setAlignment(Qt.AlignLeft)
            label.setStyleSheet("font-size: 18px; margin: 5px;")
            self.layout.addWidget(label)

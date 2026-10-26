# player_bar.py
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt
import pygame
import os

class PlayerBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize Pygame mixer
        pygame.mixer.init()

        self.current_track = None
        self.is_paused = False

        # Layout
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        # Track label
        self.track_label = QLabel("No track playing")
        self.track_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.track_label)

        # Play button
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        self.layout.addWidget(self.play_button)

        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_track)
        self.layout.addWidget(self.stop_button)

    def play_track(self, track_path):
        """Play a track given a file path."""
        if not os.path.isfile(track_path):
            print(f"File not found: {track_path}")
            return

        # Stop current track if any
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        pygame.mixer.music.load(track_path)
        pygame.mixer.music.play()
        self.current_track = track_path
        self.is_paused = False
        self.track_label.setText(os.path.basename(track_path))
        self.play_button.setText("Pause")

    def toggle_play(self):
        """Pause/resume current track."""
        if self.current_track is None:
            return

        if self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.play_button.setText("Pause")
        else:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.play_button.setText("Resume")

    def stop_track(self):
        """Stop the current track."""
        pygame.mixer.music.stop()
        self.current_track = None
        self.is_paused = False
        self.track_label.setText("No track playing")
        self.play_button.setText("Play")

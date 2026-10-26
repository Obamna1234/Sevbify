# Playlist_View.py
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QLabel, QFileDialog, QGridLayout, QMessageBox
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize
from PIL import Image

AUDIO_FOLDER = "audio"
ALBUM_CACHE = "album_covers"
PLACEHOLDER_IMAGE = "assets/placeholder.png"

# Ensure album cache exists
if not os.path.exists(ALBUM_CACHE):
    os.makedirs(ALBUM_CACHE)

class Playlist:
    """Simple playlist object."""
    def __init__(self, name):
        self.name = name
        self.songs = []
        self.custom_cover = None  # Optional user-uploaded cover
        self.cover_path = PLACEHOLDER_IMAGE

class PlaylistView(QWidget):
    def __init__(self):
        super().__init__()
        self.playlists = []
        self.current_playlist = None

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        # Left: playlist list + buttons
        self.left_layout = QVBoxLayout()
        self.playlist_list = QListWidget()
        self.playlist_list.itemClicked.connect(self.select_playlist)
        self.left_layout.addWidget(self.playlist_list)

        self.new_playlist_btn = QPushButton("New Playlist")
        self.new_playlist_btn.clicked.connect(self.create_playlist)
        self.left_layout.addWidget(self.new_playlist_btn)

        self.upload_cover_btn = QPushButton("Upload Custom Cover")
        self.upload_cover_btn.clicked.connect(self.upload_cover)
        self.left_layout.addWidget(self.upload_cover_btn)

        self.layout.addLayout(self.left_layout, 1)

        # Right: playlist details
        self.right_layout = QVBoxLayout()

        # Cover display
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(240, 240)
        self.cover_label.setPixmap(QPixmap(PLACEHOLDER_IMAGE).scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatio))
        self.right_layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Songs list
        self.songs_layout = QVBoxLayout()
        self.right_layout.addLayout(self.songs_layout)

        self.layout.addLayout(self.right_layout, 3)

    # ----------------------------
    # Playlist management
    # ----------------------------
    def create_playlist(self):
        name, ok = QFileDialog.getSaveFileName(self, "Create Playlist", "", "Playlist Files (*.txt)")
        if not name:
            return
        playlist_name = os.path.splitext(os.path.basename(name))[0]
        playlist = Playlist(playlist_name)
        self.playlists.append(playlist)
        self.playlist_list.addItem(playlist.name)

    def select_playlist(self, item):
        playlist_name = item.text()
        for pl in self.playlists:
            if pl.name == playlist_name:
                self.current_playlist = pl
                break
        self.update_playlist_view()

    def update_playlist_view(self):
        if not self.current_playlist:
            return

        # Update cover
        if self.current_playlist.custom_cover:
            cover_path = self.current_playlist.custom_cover
        else:
            cover_path = self.generate_playlist_cover(self.current_playlist)
        pixmap = QPixmap(cover_path).scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        self.cover_label.setPixmap(pixmap)

        # Update songs
        # Clear previous
        for i in reversed(range(self.songs_layout.count())):
            widget = self.songs_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        for song in self.current_playlist.songs:
            song_label = QLabel(f"{song.title} - {song.artist}")
            song_label.setStyleSheet("color: white;")
            self.songs_layout.addWidget(song_label)

    # ----------------------------
    # Cover generation
    # ----------------------------
    def generate_playlist_cover(self, playlist):
        """Create a 2x2 album cover grid from first 4 songs."""
        if not playlist.songs:
            return PLACEHOLDER_IMAGE

        # Collect up to 4 covers
        covers = []
        for song in playlist.songs[:4]:
            path = song.album_cover_path if os.path.exists(song.album_cover_path) else PLACEHOLDER_IMAGE
            covers.append(path)

        # Fill remaining slots with placeholder
        while len(covers) < 4:
            covers.append(PLACEHOLDER_IMAGE)

        # Create new 2x2 image
        size = 240
        tile_size = size // 2
        new_img = Image.new("RGB", (size, size), (24, 24, 24))

        positions = [(0,0),(tile_size,0),(0,tile_size),(tile_size,tile_size)]
        for pos, cover_path in zip(positions, covers):
            try:
                img = Image.open(cover_path).convert("RGB")
                img = img.resize((tile_size, tile_size))
                new_img.paste(img, pos)
            except Exception as e:
                print(f"Failed to add cover {cover_path}: {e}")

        # Save generated cover
        safe_name = "".join(c for c in playlist.name if c.isalnum() or c in " _-")
        cover_file = os.path.join(ALBUM_CACHE, f"{safe_name}.png")
        new_img.save(cover_file)
        playlist.cover_path = cover_file
        return cover_file

    # ----------------------------
    # Upload custom cover
    # ----------------------------
    def upload_cover(self):
        if not self.current_playlist:
            QMessageBox.warning(self, "No Playlist Selected", "Please select a playlist first.")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg)")
        if file_path:
            self.current_playlist.custom_cover = file_path
            self.update_playlist_view()

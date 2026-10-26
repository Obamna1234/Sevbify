import os
import re
import vlc
import time
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.wave import WAVE
from mutagen.oggvorbis import OggVorbis
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QScrollArea, QPushButton, QFrame, QGridLayout,
    QDialog, QLineEdit, QListWidget, QAbstractItemView,
    QDialogButtonBox, QMessageBox, QSlider
)
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QBrush, QPolygon, QColor
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QPoint
from .sidebar import Sidebar
from PIL import Image

PLACEHOLDER_IMAGE = "assets/album_covers/placeholder.png"
AUDIO_FOLDER = "audio"
ALBUM_CACHE = "album_covers"
ASSETS_FOLDER = "assets"

if not os.path.exists(ALBUM_CACHE):
    os.makedirs(ALBUM_CACHE)

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:"*?<>|]', "_", name)[:200]

def format_time(ms: int) -> str:
    """Convert milliseconds to MM:SS format"""
    seconds = ms // 1000
    mins, secs = seconds // 60, seconds % 60
    return f"{mins:02d}:{secs:02d}"

class Song:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.title = os.path.splitext(os.path.basename(file_path))[0]
        self.artist = "Unknown Artist"
        self.album = "Unknown Album"
        self.duration = 0
        self.album_cover_path = PLACEHOLDER_IMAGE
        
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = os.path.join(ASSETS_FOLDER, f"{base_name}{ext}")
            if os.path.exists(candidate):
                self.album_cover_path = candidate
                break
        
        self._extract_metadata()

    def _extract_metadata(self):
        try:
            audio = MutagenFile(self.file_path)
            if audio and hasattr(audio.info, 'length'):
                self.duration = int(audio.info.length * 1000)
            
            if isinstance(audio, MP3) and audio.tags:
                self.title = str(audio.tags.get('TIT2', [self.title])[0])
                self.artist = str(audio.tags.get('TPE1', [self.artist])[0])
                self.album = str(audio.tags.get('TALB', [self.album])[0])
            elif isinstance(audio, (FLAC, OggVorbis)) and audio.tags:
                self.title = audio.tags.get('title', [self.title])[0]
                self.artist = audio.tags.get('artist', [self.artist])[0]
                self.album = audio.tags.get('album', [self.album])[0]
            elif isinstance(audio, MP4) and audio.tags:
                self.title = audio.tags.get('\xa9nam', [self.title])[0]
                self.artist = audio.tags.get('\xa9ART', [self.artist])[0]
                self.album = audio.tags.get('\xa9alb', [self.album])[0]
            
            if self.album_cover_path == PLACEHOLDER_IMAGE:
                self._extract_album_art(audio)
        except Exception as e:
            print(f"Metadata error for {self.file_path}: {e}")

    def _extract_album_art(self, audio):
        try:
            image_data = None
            if isinstance(audio, MP3) and audio.tags:
                for tag in audio.tags.values():
                    if hasattr(tag, 'FrameID') and tag.FrameID == 'APIC':
                        image_data = tag.data
                        break
            elif isinstance(audio, (FLAC, OggVorbis)) and hasattr(audio, 'pictures') and audio.pictures:
                image_data = audio.pictures[0].data
            elif isinstance(audio, MP4) and audio.tags and 'covr' in audio.tags:
                image_data = audio.tags['covr'][0]
            
            if image_data:
                filename = sanitize_filename(f"{self.title}_{self.artist}.png")
                path = os.path.join(ALBUM_CACHE, filename)
                if not os.path.exists(path):
                    with open(path, "wb") as f:
                        f.write(image_data)
                self.album_cover_path = path
        except Exception as e:
            print(f"Album art error: {e}")

class HoverableSongTile(QWidget):
    play_clicked = pyqtSignal(object)
    
    def __init__(self, song: Song, size: int):
        super().__init__()
        self.song = song
        self.size = size
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        self.container = QFrame()
        self.container.setFixedSize(size, size)
        self.container.setStyleSheet("QFrame { border-radius: 8px; background: #181818; }")
        
        self.image_label = QLabel(self.container)
        self.image_label.setGeometry(0, 0, size, size)
        path = song.album_cover_path if os.path.exists(song.album_cover_path) else PLACEHOLDER_IMAGE
        pixmap = QPixmap(path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
        self.image_label.setStyleSheet("border-radius: 8px;")
        
        self.overlay = QLabel(self.container)
        self.overlay.setGeometry(0, 0, size, size)
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100); border-radius: 8px;")
        self.overlay.hide()
        
        self.play_button = QLabel(self.container)
        button_size = 48
        self.play_button.setGeometry(size - button_size - 8, size - button_size - 8, button_size, button_size)
        self.play_button.hide()
        self.update_play_button()
        
        layout.addWidget(self.container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel(song.title[:30] + "..." if len(song.title) > 30 else song.title)
        title.setStyleSheet("color: white; font-weight: 600; font-size: 12pt;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)
        
        artist = QLabel(song.artist)
        artist.setStyleSheet("color: #b3b3b3; font-size: 10pt;")
        artist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(artist)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_play_button(self):
        button_size = 48
        pixmap = QPixmap(button_size, button_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        color = QColor(30, 215, 96)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, button_size, button_size)
        
        painter.setBrush(QBrush(Qt.GlobalColor.black))
        cx, cy = button_size // 2, button_size // 2
        points = QPolygon([QPoint(cx - 6, cy - 10), QPoint(cx - 6, cy + 10), QPoint(cx + 10, cy)])
        painter.drawPolygon(points)
        painter.end()
        
        self.play_button.setPixmap(pixmap)

    def enterEvent(self, event):
        self.container.setStyleSheet("QFrame { border-radius: 8px; background: #282828; }")
        self.overlay.show()
        self.play_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.container.setStyleSheet("QFrame { border-radius: 8px; background: #181818; }")
        self.overlay.hide()
        self.play_button.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self.song)
        super().mousePressEvent(event)

class HoverablePlaylistTile(QWidget):
    play_clicked = pyqtSignal(object)
    
    def __init__(self, playlist, size: int):
        super().__init__()
        self.playlist = playlist
        self.size = size
        
        layout = QVBoxLayout()
        layout.setSpacing(6)
        self.setLayout(layout)
        
        self.container = QFrame()
        self.container.setFixedSize(size, size)
        self.container.setStyleSheet("QFrame { border-radius: 8px; background: #181818; }")
        
        self.image_label = QLabel(self.container)
        self.image_label.setGeometry(0, 0, size, size)
        pixmap = QPixmap(playlist.cover_path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
        self.image_label.setStyleSheet("border-radius: 8px;")
        
        self.overlay = QLabel(self.container)
        self.overlay.setGeometry(0, 0, size, size)
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100); border-radius: 8px;")
        self.overlay.hide()
        
        self.play_button = QLabel(self.container)
        button_size = 48
        self.play_button.setGeometry(size - button_size - 8, size - button_size - 8, button_size, button_size)
        self.play_button.hide()
        self.update_play_button()
        
        layout.addWidget(self.container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel(playlist.name)
        title.setStyleSheet("color: white; font-weight: 600; font-size: 11pt;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        count = QLabel(f"{len(playlist.songs)} songs")
        count.setStyleSheet("color: #b3b3b3; font-size: 9pt;")
        count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(count)

    def update_play_button(self):
        button_size = 48
        pixmap = QPixmap(button_size, button_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        color = QColor(30, 215, 96)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, button_size, button_size)
        
        painter.setBrush(QBrush(Qt.GlobalColor.black))
        cx, cy = button_size // 2, button_size // 2
        points = QPolygon([QPoint(cx - 6, cy - 10), QPoint(cx - 6, cy + 10), QPoint(cx + 10, cy)])
        painter.drawPolygon(points)
        painter.end()
        
        self.play_button.setPixmap(pixmap)

    def enterEvent(self, event):
        self.container.setStyleSheet("QFrame { border-radius: 8px; background: #282828; }")
        self.overlay.show()
        self.play_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.container.setStyleSheet("QFrame { border-radius: 8px; background: #181818; }")
        self.overlay.hide()
        self.play_button.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self.playlist)
        super().mousePressEvent(event)

class Playlist:
    def __init__(self, name: str):
        self.name = name
        self.songs = []
        self.cover_path = PLACEHOLDER_IMAGE

    def add_song(self, song: Song):
        self.songs.append(song)

    def generate_cover(self):
        covers = [s.album_cover_path for s in self.songs[:4]]
        if not covers:
            return PLACEHOLDER_IMAGE
        self.cover_path = self.create_album_collage(covers)
        return self.cover_path

    def create_album_collage(self, paths):
        tile = 150
        collage = Image.new('RGB', (tile * 2, tile * 2), '#181818')
        pos = [(0, 0), (tile, 0), (0, tile), (tile, tile)]
        
        for i, p in enumerate(paths[:4]):
            try:
                img = Image.open(p).resize((tile, tile), Image.Resampling.LANCZOS)
                collage.paste(img, pos[i])
            except:
                pass
        
        fname = os.path.join(ALBUM_CACHE, sanitize_filename(f"{self.name}_cover.png"))
        collage.save(fname)
        return fname

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Custom Spotify Replica")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #121212;")
        
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        
        self.songs = self.scan_audio_folder(AUDIO_FOLDER)
        self.current_index = 0
        self.is_playing = False
        self.slider_being_moved = False
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(100)
        
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        central.setLayout(self.main_layout)
        
        self.top_layout = QHBoxLayout()
        self.top_layout.setSpacing(0)
        self.main_layout.addLayout(self.top_layout)
        
        self.sidebar = Sidebar()
        self.top_layout.addWidget(self.sidebar)
        self.sidebar.home_clicked.connect(self.show_home)
        self.sidebar.search_clicked.connect(self.show_search)
        self.sidebar.library_clicked.connect(self.show_library)
        self.sidebar.playlists_clicked.connect(self.show_playlists)
        
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #121212;")
        self.top_layout.addWidget(self.stack)
        
        self.home_page = QWidget()
        self.search_page = QWidget()
        self.library_page = QWidget()
        self.playlists_page = QWidget()
        
        for page in [self.home_page, self.search_page, self.library_page, self.playlists_page]:
            self.stack.addWidget(page)
        
        self.setup_player_bar()
        self.setup_home_page()
        self.setup_search_page()
        self.setup_library_page()
        self.setup_playlists_page()
        
        self.stack.setCurrentWidget(self.home_page)

    def scan_audio_folder(self, folder):
        songs = []
        if os.path.exists(folder):
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
                    songs.append(Song(os.path.join(folder, f)))
        return songs

    def create_playlists(self):
        playlists = []
        for name in ["Favorites", "Chill Hits", "Workout Mix"]:
            p = Playlist(name)
            for s in self.songs[:4]:
                p.add_song(s)
            p.generate_cover()
            playlists.append(p)
        return playlists

    def display_playlists(self):
        for i in reversed(range(self.playlist_scroll_layout.count())):
            w = self.playlist_scroll_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        
        for idx, pl in enumerate(self.playlists):
            tile = HoverablePlaylistTile(pl, 150)
            tile.play_clicked.connect(self.play_playlist)
            self.playlist_scroll_layout.addWidget(tile, idx // 4, idx % 4)

    def play_playlist(self, playlist):
        if playlist.songs:
            self.play_song(playlist.songs[0])

    def create_playlist_dialog(self):
        d = QDialog(self)
        d.setWindowTitle("Create Playlist")
        d.setFixedSize(400, 500)
        d.setStyleSheet("background-color: #282828; color: white;")
        layout = QVBoxLayout()
        d.setLayout(layout)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter playlist name")
        name_input.setStyleSheet("QLineEdit { background: #3e3e3e; color: white; border: none; padding: 10px; border-radius: 5px; }")
        layout.addWidget(name_input)
        
        song_list = QListWidget()
        song_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        song_list.setStyleSheet("QListWidget { background: #3e3e3e; color: white; border: none; border-radius: 5px; } QListWidget::item { padding: 8px; } QListWidget::item:selected { background: #1db954; }")
        for s in self.songs:
            song_list.addItem(f"{s.title} - {s.artist}")
        layout.addWidget(song_list)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.setStyleSheet("QPushButton { background: #1db954; color: white; border: none; padding: 8px 16px; border-radius: 20px; font-weight: bold; } QPushButton:hover { background: #1ed760; }")
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        layout.addWidget(btns)
        
        if d.exec():
            name = name_input.text().strip()
            sel = song_list.selectedIndexes()
            if not name or not sel:
                QMessageBox.warning(self, "Error", "Invalid input")
                return
            
            pl = Playlist(name)
            for idx in sel:
                pl.add_song(self.songs[idx.row()])
            pl.generate_cover()
            self.playlists.append(pl)
            self.display_playlists()

    def setup_player_bar(self):
        self.player_bar = QFrame()
        self.player_bar.setFixedHeight(100)
        self.player_bar.setStyleSheet("background-color: #181818;")
        
        main = QVBoxLayout()
        main.setContentsMargins(10, 5, 10, 5)
        main.setSpacing(5)
        self.player_bar.setLayout(main)
        
        top = QHBoxLayout()
        main.addLayout(top)
        
        self.album_cover = QLabel()
        self.album_cover.setFixedSize(70, 70)
        self.set_album_cover(PLACEHOLDER_IMAGE)
        top.addWidget(self.album_cover)
        
        self.song_info = QLabel("No song playing")
        self.song_info.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
        top.addWidget(self.song_info)
        top.addStretch()
        
        btn_style = "QPushButton { border: none; color: white; font-size: 18px; padding: 5px 10px; background: transparent; } QPushButton:hover { color: #1db954; }"
        
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.clicked.connect(self.prev_song)
        self.prev_btn.setStyleSheet(btn_style)
        top.addWidget(self.prev_btn)
        
        self.play_btn = QPushButton("▶️")
        self.play_btn.clicked.connect(self.play_pause_song)
        self.play_btn.setStyleSheet(btn_style)
        top.addWidget(self.play_btn)
        
        self.next_btn = QPushButton("⏭")
        self.next_btn.clicked.connect(self.next_song)
        self.next_btn.setStyleSheet(btn_style)
        top.addWidget(self.next_btn)
        
        prog = QHBoxLayout()
        prog.setSpacing(10)
        main.addLayout(prog)
        
        self.time_label = QLabel("0:00")
        self.time_label.setStyleSheet("color: #b3b3b3; font-size: 11px;")
        self.time_label.setFixedWidth(40)
        prog.addWidget(self.time_label)
        
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderPressed.connect(self.slider_pressed)
        self.progress_slider.sliderReleased.connect(self.slider_released)
        self.progress_slider.setStyleSheet("QSlider::groove:horizontal { border: none; height: 4px; background: #4d4d4d; border-radius: 2px; } QSlider::handle:horizontal { background: white; border: none; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; } QSlider::sub-page:horizontal { background: #1db954; border-radius: 2px; }")
        prog.addWidget(self.progress_slider)
        
        self.duration_label = QLabel("0:00")
        self.duration_label.setStyleSheet("color: #b3b3b3; font-size: 11px;")
        self.duration_label.setFixedWidth(40)
        prog.addWidget(self.duration_label)
        
        self.main_layout.addWidget(self.player_bar)

    def slider_pressed(self):
        self.slider_being_moved = True

    def slider_released(self):
        self.slider_being_moved = False
        if self.player.is_playing() or self.player.get_state() == vlc.State.Paused:
            duration = self.player.get_length()
            if duration > 0:
                new_pos = (self.progress_slider.value() / 1000) * duration
                self.player.set_time(int(new_pos))

    def update_progress(self):
        if not self.slider_being_moved and (self.player.is_playing() or self.player.get_state() == vlc.State.Paused):
            current_time = self.player.get_time()
            duration = self.player.get_length()
            
            if duration > 0 and current_time >= 0:
                self.time_label.setText(format_time(current_time))
                self.duration_label.setText(format_time(duration))
                progress = (current_time / duration) * 1000
                self.progress_slider.setValue(int(progress))
            
            if self.player.get_state() == vlc.State.Ended:
                self.next_song()

    def set_album_cover(self, path):
        pixmap = QPixmap(path).scaled(70, 70, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        mask = QPixmap(70, 70)
        mask.fill(Qt.GlobalColor.transparent)
        p = QPainter(mask)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(pixmap))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 70, 70)
        p.end()
        self.album_cover.setPixmap(mask)

    def setup_home_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.home_page.setLayout(layout)
        
        title = QLabel("🎧 Your Songs")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #121212; }")
        content = QWidget()
        scroll_layout = QVBoxLayout()
        content.setLayout(scroll_layout)
        
        grid_widget = QWidget()
        grid = QGridLayout()
        grid.setSpacing(25)
        grid.setContentsMargins(0, 15, 0, 15)
        grid_widget.setLayout(grid)
        
        for idx, song in enumerate(self.songs):
            tile = HoverableSongTile(song, 140)
            tile.play_clicked.connect(self.play_song)
            grid.addWidget(tile, idx // 5, idx % 5)
        
        scroll_layout.addWidget(grid_widget)
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def setup_search_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.search_page.setLayout(layout)
        lbl = QLabel("🔍 Search (Coming Soon)")
        lbl.setStyleSheet("font-size: 24px; color: white;")
        layout.addWidget(lbl)
        layout.addStretch()

    def setup_library_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.library_page.setLayout(layout)
        lbl = QLabel("📚 Your Library (Coming Soon)")
        lbl.setStyleSheet("font-size: 24px; color: white;")
        layout.addWidget(lbl)
        layout.addStretch()

    def setup_playlists_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.playlists_page.setLayout(layout)
        
        top = QHBoxLayout()
        title = QLabel("🎶 Playlists")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        top.addWidget(title)
        
        btn = QPushButton("➕ Create Playlist")
        btn.setStyleSheet("color: white; background: #1db954; padding: 8px 16px; border-radius: 20px; font-weight: bold;")
        btn.clicked.connect(self.create_playlist_dialog)
        top.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(top)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #121212; }")
        content = QWidget()
        self.playlist_scroll_layout = QGridLayout()
        self.playlist_scroll_layout.setSpacing(25)
        self.playlist_scroll_layout.setContentsMargins(0, 15, 0, 15)
        content.setLayout(self.playlist_scroll_layout)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        self.playlists = self.create_playlists()
        self.display_playlists()

    def play_song(self, song: Song):
        try:
            self.player.stop()
            media = self.vlc_instance.media_new(song.file_path)
            self.player.set_media(media)
            self.player.play()
            
            self.song_info.setText(f"{song.title} - {song.artist}")
            self.set_album_cover(song.album_cover_path)
            self.play_btn.setText("⏸")
            self.current_index = self.songs.index(song)
            self.is_playing = True
            
            time.sleep(0.1)
            while self.player.get_length() == -1:
                time.sleep(0.05)
            
            self.duration_label.setText(format_time(self.player.get_length()))
        except Exception as e:
            print(f"Playback error: {e}")

    def play_pause_song(self):
        try:
            if not self.songs:
                return
            
            state = self.player.get_state()
            
            if state == vlc.State.Playing:
                self.player.pause()
                self.play_btn.setText("▶️")
                self.is_playing = False
            elif state == vlc.State.Paused:
                self.player.play()
                self.play_btn.setText("⏸")
                self.is_playing = True
            else:
                if self.current_index < len(self.songs):
                    self.play_song(self.songs[self.current_index])
        except Exception as e:
            print(f"Play/Pause error: {e}")

    def next_song(self):
        if self.songs:
            self.current_index = (self.current_index + 1) % len(self.songs)
            self.play_song(self.songs[self.current_index])

    def prev_song(self):
        if self.songs:
            self.current_index = (self.current_index - 1) % len(self.songs)
            self.play_song(self.songs[self.current_index])

    def show_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def show_search(self):
        self.stack.setCurrentWidget(self.search_page)

    def show_library(self):
        self.stack.setCurrentWidget(self.library_page)

    def show_playlists(self):
        self.stack.setCurrentWidget(self.playlists_page)
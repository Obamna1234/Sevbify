import os
import vlc
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QScrollArea, QPushButton, QFrame, QGridLayout,
    QDialog, QLineEdit, QListWidget, QAbstractItemView,
    QDialogButtonBox, QMessageBox, QSlider, QMenu, QInputDialog, QFileDialog
)
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QBrush, QPolygon, QColor, QKeySequence, QShortcut, QDesktopServices
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QPoint, QThread, QEvent, QUrl

from .sidebar import Sidebar
from .track_table import TrackTable
from .queue_panel import QueuePanel
from .now_playing_panel import NowPlayingPanel
from . import icons
from core.paths import (  # noqa: F401  (re-exported for older code/tests)
    PROJECT_ROOT, PLACEHOLDER_IMAGE, AUDIO_FOLDER, ALBUM_CACHE, ASSETS_FOLDER, normalise_path
)
from core.models import (  # noqa: F401
    Song, Playlist, SUPPORTED_EXTENSIONS, sanitize_filename, format_time, format_total
)
from core import paths as core_paths
from core.library import scan_folders
from core.storage import Storage, StoredPlaylist
from core.play_queue import PlayQueue
from core.canvas import find_canvas
from core.online.net import NetClient, OfflineError, OnlineDisabled
from core.online.providers import OnlineMusic
from core.online.models import OnlineTrack, build_match_index, find_local_match
from core.online.remote_song import RemoteSong
from .async_tasks import run_async
from .settings_dialog import SettingsDialog

# How long (ms) a track may sit in "opening/buffering" before we give up on it.
OPEN_TIMEOUT_MS = 10000
# Pressing "previous" more than this far into a track restarts it instead
# (same behaviour as Spotify).
PREV_RESTART_THRESHOLD_MS = 3000
SAMPLE_PLAYLIST_NAMES = ["Favorites", "Chill Hits", "Workout Mix"]
HOME_TILE_WIDTH = 170   # cover is 140 px; the extra room fits titles and artist names

MENU_STYLE = """
QMenu { background: #282828; color: white; border: 1px solid #3e3e3e; padding: 4px; font-size: 13px; }
QMenu::item { padding: 8px 24px 8px 12px; border-radius: 3px; }
QMenu::item:selected { background: #3e3e3e; }
QMenu::item:disabled { color: #6a6a6a; }
QMenu::separator { height: 1px; background: #3e3e3e; margin: 4px 0; }
"""
PILL_BUTTON = ("QPushButton { color: white; background: transparent; border: 1px solid #727272; "
               "padding: 6px 16px; border-radius: 16px; font-weight: bold; } "
               "QPushButton:hover { border-color: white; }")
GREEN_BUTTON = ("QPushButton { color: black; background: #1db954; padding: 8px 16px; border: none; "
                "border-radius: 18px; font-weight: bold; } QPushButton:hover { background: #1ed760; }")


def load_pixmap(path: str) -> QPixmap:
    """Load an image, falling back to the placeholder if it is missing/corrupt."""
    pixmap = QPixmap(path) if path and os.path.exists(path) else QPixmap()
    if pixmap.isNull():
        pixmap = QPixmap(PLACEHOLDER_IMAGE)
    if pixmap.isNull():
        # Even the placeholder is missing: use a plain dark square.
        pixmap = QPixmap(300, 300)
        pixmap.fill(QColor("#282828"))
    return pixmap


def draw_play_button(button_size: int = 48) -> QPixmap:
    pixmap = QPixmap(button_size, button_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(30, 215, 96)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, button_size, button_size)
    painter.setBrush(QBrush(Qt.GlobalColor.black))
    cx, cy = button_size // 2, button_size // 2
    s = button_size / 48
    points = QPolygon([QPoint(int(cx - 6 * s), int(cy - 10 * s)),
                       QPoint(int(cx - 6 * s), int(cy + 10 * s)),
                       QPoint(int(cx + 10 * s), cy)])
    painter.drawPolygon(points)
    painter.end()
    return pixmap


class ScanThread(QThread):
    """Scans music folders in the background so the window never freezes."""
    scanned = pyqtSignal(list, list)  # songs, problems

    def __init__(self, folders, parent=None):
        super().__init__(parent)
        self.folders = list(folders)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        songs, problems = scan_folders(self.folders, should_stop=lambda: self._stop)
        if not self._stop:
            self.scanned.emit(songs, problems)


class HoverableSongTile(QWidget):
    play_clicked = pyqtSignal(object)
    context_requested = pyqtSignal(object, object)  # song, global pos

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
        pixmap = load_pixmap(song.album_cover_path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
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
        artist.setText(artist.fontMetrics().elidedText(song.artist, Qt.TextElideMode.ElideRight, HOME_TILE_WIDTH - 6))
        layout.addWidget(artist)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{song.title} — {song.artist}\nClick to play · Right-click for more options")

    def update_play_button(self):
        self.play_button.setPixmap(draw_play_button(48))

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

    def contextMenuEvent(self, event):
        self.context_requested.emit(self.song, event.globalPos())


class HoverablePlaylistTile(QWidget):
    play_clicked = pyqtSignal(object)   # green play button: play the playlist
    open_clicked = pyqtSignal(object)   # anywhere else: open the playlist page

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
        pixmap = load_pixmap(playlist.cover_path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
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

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_play_button(self):
        self.play_button.setPixmap(draw_play_button(48))

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
            pos = self.container.mapFrom(self, event.position().toPoint())
            if self.play_button.geometry().contains(pos):
                self.play_clicked.emit(self.playlist)
            else:
                self.open_clicked.emit(self.playlist)
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    library_loaded = pyqtSignal()

    def __init__(self, audio_folder: str = None, vlc_args=(), data_dir: str = None):
        """
        audio_folder: scan only this folder for this session (used by tests).
                      Normally the folders saved in the user's settings are used.
        data_dir:     where library.json is saved (default: %APPDATA%).
        """
        super().__init__()
        self.setWindowTitle("Sevbify")
        self.setGeometry(100, 100, 1200, 800)
        # Dark, thin scrollbars everywhere (Spotify style).
        self.setStyleSheet(
            "QMainWindow { background-color: #121212; }"
            "QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }"
            "QScrollBar::handle:vertical { background: #4d4d4d; border-radius: 5px; min-height: 30px; }"
            "QScrollBar::handle:vertical:hover { background: #6a6a6a; }"
            "QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }"
            "QScrollBar::handle:horizontal { background: #4d4d4d; border-radius: 5px; min-width: 30px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }"
            "QScrollBar::add-page, QScrollBar::sub-page { background: none; }")

        self.vlc_instance = vlc.Instance(*vlc_args)
        if self.vlc_instance is None:
            raise RuntimeError(
                "libVLC could not be initialised. Make sure the 64-bit VLC media "
                "player is installed (https://www.videolan.org/vlc/)."
            )
        self.player = self.vlc_instance.media_player_new()

        # --- Saved user data ---------------------------------------------
        self.storage = Storage(data_dir)
        self.user_data = self.storage.load()
        if audio_folder is not None:
            self.user_data.music_folders = [str(audio_folder)]
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_now)

        # --- Online features (all optional; see Settings) -------------------
        self.net = NetClient(os.path.join(self.storage.data_dir, "cache"),
                             enabled=lambda: self.user_data.online_enabled)
        self.online = OnlineMusic(self.net, self.user_data.lastfm_api_key)

        # --- Library ------------------------------------------------------
        self.songs = []
        self.playlists = []
        self.library_ready = False
        self._scan_thread = None
        self._rescan_pending = False
        self.open_playlist = None   # playlist shown on the playlist page
        self.slider_being_moved = False

        # --- Playback state (single source of truth) ---------------------
        # PlayQueue (core/play_queue.py) decides what plays next: the context
        # (library, playlist, search results, radio), "Add to queue" songs,
        # shuffle, repeat and recently played.
        self.pq = PlayQueue()
        self.pq.shuffle = self.user_data.shuffle
        self.pq.repeat = self.user_data.repeat
        self.current_song = None
        self.is_playing = False
        self._track_handled = True      # end/error of current track already processed?
        self._reached_playing = False   # did the current track ever actually start?
        self._open_elapsed_ms = 0       # time spent waiting for the track to start
        self._consecutive_failures = 0  # stops endless skipping if every file is bad

        self.timer = QTimer(self)
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
        self.sidebar.settings_clicked.connect(self.open_settings)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #121212;")
        self.top_layout.addWidget(self.stack, 1)

        # Right-hand panel (Queue / Now playing), hidden until toggled.
        self.right_panel = QStackedWidget()
        self.right_panel.setObjectName("rightPanel")
        self.right_panel.setStyleSheet("#rightPanel { background-color: #121212; border-left: 1px solid #1f1f1f; }")
        self.queue_panel = QueuePanel(load_pixmap)
        self.queue_panel.close_requested.connect(lambda: self.set_right_panel(""))
        self.queue_panel.play_upcoming.connect(self._play_upcoming)
        self.queue_panel.play_recent.connect(lambda s: self.play_song(s, queue=list(self.pq.recent), source="Recently played"))
        self.queue_panel.remove_from_queue.connect(self._remove_from_user_queue)
        self.queue_panel.clear_user_queue.connect(self._clear_user_queue)
        self.right_panel.addWidget(self.queue_panel)
        self.now_playing_panel = NowPlayingPanel(load_pixmap)
        self.now_playing_panel.close_requested.connect(lambda: self.set_right_panel(""))
        self.right_panel.addWidget(self.now_playing_panel)
        self._artist_cards = {}          # artist name -> card dict (this session)
        self._online_hooks = [self._refresh_artist_card]
        self.right_panel.hide()
        self.top_layout.addWidget(self.right_panel)

        self.home_page = QWidget()
        self.search_page = QWidget()
        self.library_page = QWidget()
        self.playlists_page = QWidget()
        self.playlist_page = QWidget()

        for page in [self.home_page, self.search_page, self.library_page,
                     self.playlists_page, self.playlist_page]:
            self.stack.addWidget(page)

        self.setup_player_bar()
        self.setup_home_page()
        self.setup_search_page()
        self.setup_library_page()
        self.setup_playlists_page()
        self.setup_playlist_page()
        self.setup_shortcuts()

        self.stack.setCurrentWidget(self.home_page)

        if self.user_data.load_warning:
            self.show_status("⚠ " + self.user_data.load_warning, 20000)

        self.set_right_panel(self.user_data.right_panel, save=False)
        self._update_online_indicator()
        self.rescan_library()

    # --- Compatibility: older code/tests use .queue / .queue_index -------
    @property
    def queue(self):
        return self.pq.items

    @queue.setter
    def queue(self, songs):
        self.pq.replace_items(songs)

    @property
    def queue_index(self):
        return self.pq.index

    @queue_index.setter
    def queue_index(self, value):
        self.pq.index = value

    @property
    def current_index(self):
        return self.queue_index

    # ==================================================================
    # Library scanning
    # ==================================================================
    def scan_audio_folder(self, folder):
        """Synchronous scan of one folder (kept for compatibility)."""
        songs, _ = scan_folders([folder], recursive=False)
        return songs

    def rescan_library(self):
        """Scan the music folders in the background, then refresh every page."""
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._rescan_pending = True
            return
        self.library_count_label.setText("Scanning your music…")
        self._scan_thread = ScanThread(self.user_data.music_folders, self)
        self._scan_thread.scanned.connect(self._on_scan_finished)
        self._scan_thread.finished.connect(self._on_scan_thread_done)
        self._scan_thread.start()

    def _on_scan_thread_done(self):
        if self._rescan_pending:
            self._rescan_pending = False
            self.rescan_library()

    def _on_scan_finished(self, songs, problems):
        self.songs = songs
        by_key = {s.key: s for s in songs}
        first_load = not self.library_ready

        if first_load:
            self._build_playlists_from_storage(by_key)
        else:
            # Point playlists at the freshly scanned Song objects (new metadata).
            for pl in self.playlists:
                pl.songs = [by_key.get(s.key, s) for s in pl.songs]

        self.pq.rebind(by_key)
        if first_load:
            for path in reversed(self.user_data.recent):
                song = by_key.get(normalise_path(path))
                if song is not None:
                    self.pq.record_played(song)
        if self.current_song is not None:
            self.current_song = by_key.get(self.current_song.key, self.current_song)

        self.library_ready = True
        self.refresh_home()
        self.refresh_library_page()
        self.refresh_search_results()
        self.display_playlists()
        if self.open_playlist is not None:
            self.refresh_playlist_page()
        self._refresh_now_playing()
        self._queue_changed()

        if problems:
            self.show_status("⚠ " + problems[0] + (f" (+{len(problems) - 1} more)" if len(problems) > 1 else ""), 10000)
        if first_load and self.user_data.is_new:
            self.save_now()
        self.library_loaded.emit()

    def _build_playlists_from_storage(self, by_key):
        self.playlists = []
        if self.user_data.is_new:
            # First run: create the sample playlists once. They are normal
            # playlists after that and can be renamed or deleted.
            self.playlists = self.create_playlists()
            return
        for stored in self.user_data.playlists:
            pl = Playlist(stored.name)
            for path in stored.tracks:
                key = normalise_path(path)
                # Missing files are kept (shown greyed out) so nothing is lost
                # if a drive is disconnected or a file was renamed.
                pl.add_song(by_key.get(key) or Song(path))
            pl.generate_cover()
            self.playlists.append(pl)

    def create_playlists(self):
        """Sample playlists (only created on first run)."""
        playlists = []
        if not self.songs:
            return playlists
        for name in SAMPLE_PLAYLIST_NAMES:
            p = Playlist(name)
            for s in self.songs[:4]:
                p.add_song(s)
            p.generate_cover()
            playlists.append(p)
        return playlists

    # ------------------------------------------------------------------
    def add_music_folder(self, folder: str) -> bool:
        folder = os.path.abspath(folder)
        if not os.path.isdir(folder):
            self.show_status(f"⚠ Folder not found: {folder}")
            return False
        existing = {normalise_path(f) for f in self.user_data.music_folders}
        if normalise_path(folder) in existing:
            self.show_status("That folder is already in your library.", kind="info")
            return False
        self.user_data.music_folders.append(folder)
        self.save_now()
        self.refresh_folder_list()
        self.rescan_library()
        self.show_status(f"Added {folder} — scanning…", kind="info")
        return True

    def remove_music_folder(self, folder: str):
        key = normalise_path(folder)
        self.user_data.music_folders = [f for f in self.user_data.music_folders if normalise_path(f) != key]
        self.save_now()
        self.refresh_folder_list()
        self.rescan_library()

    def _choose_music_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Add a music folder", os.path.expanduser("~"))
        if folder:
            self.add_music_folder(folder)

    # ==================================================================
    # Saving
    # ==================================================================
    def schedule_save(self, delay_ms: int = 600):
        self._save_timer.start(delay_ms)

    def save_now(self):
        self._save_timer.stop()
        if self.library_ready:
            self.user_data.playlists = [
                StoredPlaylist(p.name, [s.file_path for s in p.songs]) for p in self.playlists
            ]
            self.user_data.recent = [s.file_path for s in self.pq.recent if s.file_path]
        try:
            self.storage.save(self.user_data)
        except Exception as e:
            self.show_status(f"⚠ Could not save your library: {e}", 10000)

    # ==================================================================
    # Playlist operations (each one saves immediately)
    # ==================================================================
    def _name_taken(self, name, ignore=None):
        return any(p is not ignore and p.name.casefold() == name.casefold() for p in self.playlists)

    def create_playlist(self, name: str, songs=()):
        name = name.strip()
        if not name:
            self.show_status("⚠ Please enter a playlist name.")
            return None
        if self._name_taken(name):
            self.show_status(f"⚠ You already have a playlist called \"{name}\".")
            return None
        pl = Playlist(name)
        for s in songs:
            pl.add_song(s)
        pl.generate_cover()
        self.playlists.append(pl)
        self._playlists_changed()
        return pl

    def rename_playlist(self, playlist, new_name: str) -> bool:
        new_name = new_name.strip()
        if not new_name or new_name == playlist.name:
            return False
        if self._name_taken(new_name, ignore=playlist):
            self.show_status(f"⚠ You already have a playlist called \"{new_name}\".")
            return False
        old_cover = playlist.cover_path
        playlist.name = new_name
        playlist.generate_cover()
        self._remove_generated_cover(old_cover)
        self._playlists_changed(playlist)
        return True

    def delete_playlist(self, playlist):
        if playlist not in self.playlists:
            return
        self.playlists.remove(playlist)
        self._remove_generated_cover(playlist.cover_path)
        if self.open_playlist is playlist:
            self.open_playlist = None
            self.show_playlists()
        self._playlists_changed()

    def add_to_playlist(self, playlist, songs) -> int:
        """Add songs, skipping ones already in the playlist. Returns number added."""
        existing = {s.key for s in playlist.songs}
        added = 0
        for s in songs:
            if s.key not in existing:
                playlist.add_song(s)
                existing.add(s.key)
                added += 1
        if added:
            playlist.generate_cover()
            self._playlists_changed(playlist)
            self.show_status(f"Added to {playlist.name}", kind="info", timeout_ms=3000)
        else:
            self.show_status(f"Already in {playlist.name}", kind="info", timeout_ms=3000)
        return added

    def remove_from_playlist(self, playlist, index: int):
        if 0 <= index < len(playlist.songs):
            del playlist.songs[index]
            playlist.generate_cover()
            self._playlists_changed(playlist)

    def move_in_playlist(self, playlist, index: int, delta: int):
        new = index + delta
        if 0 <= index < len(playlist.songs) and 0 <= new < len(playlist.songs):
            songs = playlist.songs
            songs[index], songs[new] = songs[new], songs[index]
            if min(index, new) < 4:
                playlist.generate_cover()
            self._playlists_changed(playlist)

    def _playlists_changed(self, playlist=None):
        self.save_now()
        self.display_playlists()
        if self.open_playlist is not None and (playlist is None or playlist is self.open_playlist):
            self.refresh_playlist_page()

    def _remove_generated_cover(self, path):
        # Only delete collages we generated, never user artwork/placeholder.
        if path and path.endswith("_cover.png") and os.path.dirname(os.path.abspath(path)) == os.path.abspath(core_paths.ALBUM_CACHE):
            if not any(p.cover_path == path for p in self.playlists):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ==================================================================
    # Menus
    # ==================================================================
    def _new_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        return menu

    def build_song_menu(self, song, queue=None, playlist=None, row=None, source=""):
        menu = self._new_menu()
        play = menu.addAction("▶  Play")
        play.setEnabled(song.exists)
        play.triggered.connect(lambda: self.play_song(song, queue=queue, source=source))
        add_q = menu.addAction("≡  Add to queue")
        add_q.triggered.connect(lambda: self.add_to_queue(song))
        radio = menu.addAction("◉  Go to song radio")
        has_artist = bool(song.artist) and song.artist != "Unknown Artist"
        radio.setEnabled(self.online_enabled and has_artist)
        if not self.online_enabled:
            radio.setText("◉  Go to song radio (turn on Online features)")
        radio.triggered.connect(lambda: self.start_radio(song))
        if has_artist:
            open_menu = menu.addMenu("↗  Open in")
            open_menu.setStyleSheet(MENU_STYLE)
            track = song.track if getattr(song, "is_remote", False) else OnlineTrack(song.title, song.artist)
            for label, url in track.links().items():
                open_menu.addAction(label).triggered.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))

        add_menu = menu.addMenu("➕  Add to playlist")
        add_menu.setStyleSheet(MENU_STYLE)
        new_action = add_menu.addAction("New playlist…")
        new_action.triggered.connect(lambda: self._new_playlist_with(song))
        if self.playlists:
            add_menu.addSeparator()
        for pl in self.playlists:
            if pl is playlist:
                continue
            act = add_menu.addAction(pl.name)
            act.triggered.connect(lambda _=False, p=pl: self.add_to_playlist(p, [song]))

        if playlist is not None and row is not None:
            menu.addSeparator()
            up = menu.addAction("↑  Move up")
            up.setEnabled(row > 0)
            up.triggered.connect(lambda: self.move_in_playlist(playlist, row, -1))
            down = menu.addAction("↓  Move down")
            down.setEnabled(row < len(playlist.songs) - 1)
            down.triggered.connect(lambda: self.move_in_playlist(playlist, row, 1))
            remove = menu.addAction("✕  Remove from this playlist")
            remove.triggered.connect(lambda: self.remove_from_playlist(playlist, row))
        return menu

    def _show_song_menu(self, song, global_pos, queue=None, playlist=None, row=None, source=""):
        self.build_song_menu(song, queue, playlist, row, source).exec(global_pos)

    def _new_playlist_with(self, song):
        name, ok = QInputDialog.getText(self, "New playlist", "Playlist name:")
        if ok:
            pl = self.create_playlist(name, [song])
            if pl:
                self.show_status(f"Created {pl.name}", kind="info", timeout_ms=3000)

    # ==================================================================
    # Player bar
    # ==================================================================
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

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self.song_info = QLabel("No song playing")
        self.song_info.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
        info_col.addWidget(self.song_info)

        # Small status line for errors and confirmations.
        self.status_label = QLabel("")
        self.status_label.hide()
        info_col.addWidget(self.status_label)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self.clear_status)

        top.addLayout(info_col)
        top.addStretch()

        btn_style = "QPushButton { border: none; color: white; font-size: 18px; padding: 5px 10px; background: transparent; } QPushButton:hover { color: #1db954; }"

        self.shuffle_btn = self._icon_button("Shuffle (Ctrl+S)", self.toggle_shuffle)
        top.addWidget(self.shuffle_btn)

        self.prev_btn = QPushButton("⏮")
        self.prev_btn.clicked.connect(self.prev_song)
        self.prev_btn.setStyleSheet(btn_style)
        self.prev_btn.setToolTip("Previous (Ctrl+Left)")
        top.addWidget(self.prev_btn)

        self.play_btn = QPushButton("▶️")
        self.play_btn.clicked.connect(self.play_pause_song)
        self.play_btn.setStyleSheet(btn_style)
        self.play_btn.setToolTip("Play / Pause (Space)")
        top.addWidget(self.play_btn)

        self.next_btn = QPushButton("⏭")
        self.next_btn.clicked.connect(self.next_song)
        self.next_btn.setStyleSheet(btn_style)
        self.next_btn.setToolTip("Next (Ctrl+Right)")
        top.addWidget(self.next_btn)

        self.repeat_btn = self._icon_button("Repeat (Ctrl+R)", self.cycle_repeat)
        top.addWidget(self.repeat_btn)
        self._update_mode_buttons()

        top.addSpacing(24)
        self.nowplaying_btn = self._icon_button("Now playing view", lambda: self.toggle_right_panel("nowplaying"))
        top.addWidget(self.nowplaying_btn)
        self.queue_btn = self._icon_button("Queue", lambda: self.toggle_right_panel("queue"))
        top.addWidget(self.queue_btn)
        top.addSpacing(6)

        # --- Volume -------------------------------------------------------
        self.mute_btn = QPushButton()
        self.mute_btn.setStyleSheet("QPushButton { border: none; color: #b3b3b3; font-size: 16px; padding: 4px; background: transparent; } QPushButton:hover { color: white; }")
        self.mute_btn.setToolTip("Mute / unmute")
        self.mute_btn.clicked.connect(self.toggle_mute)
        top.addWidget(self.mute_btn)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(110)
        self.volume_slider.setToolTip("Volume (Ctrl+Up / Ctrl+Down)")
        self.volume_slider.setStyleSheet("QSlider::groove:horizontal { border: none; height: 4px; background: #4d4d4d; border-radius: 2px; } QSlider::handle:horizontal { background: white; border: none; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; } QSlider::sub-page:horizontal { background: #1db954; border-radius: 2px; }")
        self.volume_slider.setValue(self.user_data.volume)
        self.volume_slider.valueChanged.connect(self.set_volume)
        top.addWidget(self.volume_slider)
        self._update_mute_icon()
        self._apply_volume()

        prog = QHBoxLayout()
        prog.setSpacing(10)
        main.addLayout(prog)

        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("color: #b3b3b3; font-size: 11px;")
        self.time_label.setFixedWidth(40)
        prog.addWidget(self.time_label)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderPressed.connect(self.slider_pressed)
        self.progress_slider.sliderReleased.connect(self.slider_released)
        self.progress_slider.setStyleSheet("QSlider::groove:horizontal { border: none; height: 4px; background: #4d4d4d; border-radius: 2px; } QSlider::handle:horizontal { background: white; border: none; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; } QSlider::sub-page:horizontal { background: #1db954; border-radius: 2px; }")
        prog.addWidget(self.progress_slider)

        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("color: #b3b3b3; font-size: 11px;")
        self.duration_label.setFixedWidth(40)
        prog.addWidget(self.duration_label)

        self.main_layout.addWidget(self.player_bar)

    def setup_shortcuts(self):
        def sc(keys, fn):
            s = QShortcut(QKeySequence(keys), self)
            s.activated.connect(fn)
            return s
        # Text boxes (e.g. Search) keep the Space key for typing.
        sc(Qt.Key.Key_Space, self.play_pause_song)
        sc("Ctrl+Right", self.next_song)
        sc("Ctrl+Left", self.prev_song)
        sc("Ctrl+Up", lambda: self.volume_slider.setValue(self.volume_slider.value() + 5))
        sc("Ctrl+Down", lambda: self.volume_slider.setValue(self.volume_slider.value() - 5))
        sc("Ctrl+F", self.show_search)
        sc("Ctrl+L", self.show_library)
        sc("Ctrl+S", self.toggle_shuffle)
        sc("Ctrl+R", self.cycle_repeat)

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------
    def set_volume(self, value: int):
        value = max(0, min(100, int(value)))
        self.user_data.volume = value
        if self.user_data.muted and value > 0:
            self.user_data.muted = False  # moving the slider unmutes, like Spotify
        self._apply_volume()
        self._update_mute_icon()
        self.schedule_save()

    def toggle_mute(self):
        self.user_data.muted = not self.user_data.muted
        self._apply_volume()
        self._update_mute_icon()
        self.schedule_save()

    def _apply_volume(self):
        try:
            self.player.audio_set_volume(0 if self.user_data.muted else self.user_data.volume)
        except Exception as e:
            print(f"Volume error: {e}")

    def _update_mute_icon(self):
        v = self.user_data.volume
        if self.user_data.muted or v == 0:
            self.mute_btn.setText("🔇")
        elif v < 50:
            self.mute_btn.setText("🔉")
        else:
            self.mute_btn.setText("🔊")

    # ------------------------------------------------------------------
    # Status / error feedback
    # ------------------------------------------------------------------
    def show_status(self, message: str, timeout_ms: int = 6000, kind: str = "error"):
        print(message)
        color = "#f15e6c" if kind == "error" else "#1db954"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status_label.setText(message)
        self.status_label.show()
        self._status_timer.start(timeout_ms)

    def clear_status(self):
        self.status_label.clear()
        self.status_label.hide()

    # ------------------------------------------------------------------
    # Seeking / progress
    # ------------------------------------------------------------------
    def slider_pressed(self):
        self.slider_being_moved = True

    def slider_released(self):
        self.slider_being_moved = False
        state = self.player.get_state()
        if state in (vlc.State.Playing, vlc.State.Paused):
            duration = self.player.get_length()
            if duration > 0:
                new_pos = (self.progress_slider.value() / 1000) * duration
                self.player.set_time(int(new_pos))

    def update_progress(self):
        """Runs every 100 ms on the UI thread. Only uses non-blocking VLC calls."""
        if self.current_song is None:
            return

        state = self.player.get_state()

        if state in (vlc.State.Playing, vlc.State.Paused):
            if not self._reached_playing:
                self._reached_playing = True
                self._apply_volume()  # VLC can reset volume when audio output starts
            self._open_elapsed_ms = 0
            if not self.slider_being_moved:
                current_time = self.player.get_time()
                duration = self.player.get_length()
                if duration > 0 and current_time >= 0:
                    self.time_label.setText(format_time(current_time))
                    self.duration_label.setText(format_time(duration))
                    self.progress_slider.setValue(int((current_time / duration) * 1000))
            return

        if self._track_handled:
            return

        if state == vlc.State.Ended and not self._reached_playing and self.player.get_length() > 0:
            # A very short song can start and finish between two progress checks.
            # VLC knew its length, so it really played (a broken file has length 0).
            self._reached_playing = True

        if state == vlc.State.Ended and self._reached_playing:
            # Natural end of the track: advance exactly once.
            self._track_handled = True
            self._consecutive_failures = 0
            self.progress_slider.setValue(1000)
            self._advance_after_current()
        elif state == vlc.State.Error or (state == vlc.State.Ended and not self._reached_playing):
            # VLC reports some unreadable files as "Ended" without ever playing.
            self._track_handled = True
            self._handle_failed_track("could not be played (unsupported or corrupt file)")
        elif state in (vlc.State.Opening, vlc.State.Buffering, vlc.State.NothingSpecial):
            self._open_elapsed_ms += self.timer.interval()
            if self._open_elapsed_ms >= OPEN_TIMEOUT_MS:
                self._track_handled = True
                self.player.stop()
                self._handle_failed_track("took too long to open")

    def set_album_cover(self, path):
        pixmap = load_pixmap(path).scaled(70, 70, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        mask = QPixmap(70, 70)
        mask.fill(Qt.GlobalColor.transparent)
        p = QPainter(mask)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(pixmap))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 70, 70)
        p.end()
        self.album_cover.setPixmap(mask)

    # ==================================================================
    # Pages
    # ==================================================================
    @staticmethod
    def _page_title(text):
        title = QLabel(text)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        return title

    @staticmethod
    def _muted_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #b3b3b3; font-size: 14px;")
        lbl.setWordWrap(True)
        return lbl

    # --- Home -------------------------------------------------------------
    def setup_home_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.home_page.setLayout(layout)
        layout.addWidget(self._page_title("🎧 Your Songs"))

        self.home_scroll = QScrollArea()
        self.home_scroll.setWidgetResizable(True)
        self.home_scroll.setStyleSheet("QScrollArea { border: none; background: #121212; }")
        self.home_scroll.setWidget(self._muted_label("Loading your music…"))
        self.home_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.home_scroll.installEventFilter(self)
        layout.addWidget(self.home_scroll)

    def refresh_home(self):
        if not self.songs:
            folders = "\n".join(self.user_data.music_folders) or "(none)"
            empty = self._muted_label(
                "No music found.\n\nAdd .mp3, .wav, .flac, .ogg or .m4a files to one of your "
                f"music folders, or add a folder in Your Library.\n\nMusic folders:\n{folders}"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.home_scroll.setWidget(empty)
            return

        content = QWidget()
        scroll_layout = QVBoxLayout()
        content.setLayout(scroll_layout)

        grid_widget = QWidget()
        grid = QGridLayout()
        grid.setSpacing(25)
        grid.setContentsMargins(0, 15, 0, 15)
        grid_widget.setLayout(grid)

        self._home_tiles = []
        for song in self.songs:
            tile = HoverableSongTile(song, 140)
            tile.setFixedWidth(HOME_TILE_WIDTH)
            tile.play_clicked.connect(lambda s: self.play_song(s, queue=self.songs, source="Your Songs"))
            tile.context_requested.connect(lambda s, pos: self._show_song_menu(s, pos, queue=self.songs, source="Your Songs"))
            self._home_tiles.append(tile)
        self._home_grid = grid
        self._home_cols = 0
        self._relayout_home()

        scroll_layout.addWidget(grid_widget, alignment=Qt.AlignmentFlag.AlignLeft)
        scroll_layout.addStretch()
        self.home_scroll.setWidget(content)

    def _relayout_home(self):
        """Fit as many tile columns as the window width allows (like Spotify)."""
        grid = getattr(self, "_home_grid", None)
        if grid is None:
            return
        width = self.home_scroll.viewport().width() - 30
        cols = max(1, width // (HOME_TILE_WIDTH + grid.spacing()))
        if cols == self._home_cols:
            return
        self._home_cols = cols
        for tile in self._home_tiles:
            grid.removeWidget(tile)
        for idx, tile in enumerate(self._home_tiles):
            grid.addWidget(tile, idx // cols, idx % cols)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "home_scroll", None) and event.type() == QEvent.Type.Resize:
            # The inner viewport is resized just after this event; measure it then.
            QTimer.singleShot(0, self._relayout_home)
        return super().eventFilter(obj, event)

    # --- Search -----------------------------------------------------------
    def setup_search_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.search_page.setLayout(layout)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  What do you want to play?")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet(
            "QLineEdit { background: #242424; color: white; border: 1px solid #242424; "
            "padding: 10px 16px; border-radius: 22px; font-size: 14px; } "
            "QLineEdit:hover { border-color: #3e3e3e; } QLineEdit:focus { border-color: white; }")
        self.search_input.setFixedHeight(44)
        self.search_input.setMaximumWidth(480)
        self.search_input.textChanged.connect(self.refresh_search_results)
        layout.addWidget(self.search_input)

        self.search_summary = self._muted_label("Search your library by song, artist or album.")
        layout.addWidget(self.search_summary)

        src = lambda: f"Search: {self.search_input.text().strip()}"
        self.search_lib_header = self._section_label("In your library")
        layout.addWidget(self.search_lib_header)
        self.search_table = TrackTable(sortable=False)
        self.search_table.play_requested.connect(lambda s, view: self.play_song(s, queue=view, source=src()))
        self.search_table.context_requested.connect(
            lambda s, row, pos: self._show_song_menu(s, pos, queue=self.search_table.songs_in_view(), source=src()))
        layout.addWidget(self.search_table)

        self.search_web_header = self._section_label("More from the web")
        layout.addWidget(self.search_web_header)
        self.search_web_status = self._muted_label("")
        layout.addWidget(self.search_web_status)
        self.web_table = TrackTable(sortable=False)
        self.web_table.play_requested.connect(lambda s, view: self.play_song(s, queue=view, source=src()))
        self.web_table.context_requested.connect(
            lambda s, row, pos: self._show_song_menu(s, pos, queue=self.web_table.songs_in_view(), source=src()))
        layout.addWidget(self.web_table, 1)
        layout.addStretch()

        self._web_search_timer = QTimer(self)
        self._web_search_timer.setSingleShot(True)
        self._web_search_timer.timeout.connect(self._run_web_search)
        self._web_query_shown = None
        for w in (self.search_lib_header, self.search_table, self.search_web_header,
                  self.search_web_status, self.web_table):
            w.hide()
        self._online_hooks.append(lambda: self.refresh_search_results())

    @staticmethod
    def _section_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: white; font-size: 18px; font-weight: bold; padding-top: 6px;")
        return lbl

    def search(self, query: str):
        query = query.strip()
        if not query:
            return []
        return [s for s in self.songs if s.matches(query)]

    def refresh_search_results(self, *_):
        query = self.search_input.text().strip()
        if not query:
            for w in (self.search_lib_header, self.search_table, self.search_web_header,
                      self.search_web_status, self.web_table):
                w.hide()
            self.search_summary.setText("Search your library by song, artist or album."
                                        + (" Online results appear too." if self.online_enabled else ""))
            self.search_summary.show()
            self._web_query_shown = None
            return

        results = self.search(query)
        self.search_table.set_songs(results)
        self.search_table.set_current(self.current_song)
        # Show at most ~6 library rows so web results stay visible below.
        rows = min(len(results), 6)
        self.search_table.setFixedHeight(36 + rows * self.search_table.verticalHeader().defaultSectionSize() + 4)
        self.search_lib_header.setVisible(bool(results))
        self.search_table.setVisible(bool(results))
        if results:
            self.search_lib_header.setText(f"In your library  ·  {len(results)}")

        if not self.online_enabled:
            self.search_summary.setVisible(not results)
            self.search_summary.setText(f"No results in your library for \"{query}\". "
                                        "Turn on Online features in Settings to search the web too.")
            for w in (self.search_web_header, self.search_web_status, self.web_table):
                w.hide()
            return

        self.search_summary.hide()
        self.search_web_header.show()
        if len(query) < 2:
            self.search_web_status.setText("Keep typing to search the web…")
            self.search_web_status.show()
            self.web_table.hide()
            return
        if query != self._web_query_shown:
            self.search_web_status.setText("Searching…")
            self.search_web_status.show()
            self._web_search_timer.start(450)          # wait until typing pauses

    def _run_web_search(self):
        query = self.search_input.text().strip()
        if len(query) < 2 or not self.online_enabled:
            return

        def done(tracks):
            if self.search_input.text().strip() != query:
                return                                  # user typed something else meanwhile
            self._web_query_shown = query
            items = self.radio_items(tracks)
            self.web_table.set_songs(items)
            self.web_table.set_current(self.current_song)
            self.web_table.setVisible(bool(items))
            if items:
                owned = sum(1 for s in items if not getattr(s, "is_remote", False))
                self.search_web_status.setText(
                    f"{len(items)} songs  ·  double-click to play"
                    + ("  ·  songs you own play in full, others as 30-second previews" if owned < len(items) else ""))
            else:
                self.search_web_status.setText(f"No web results for \"{query}\".")
            self.fetch_covers(items, limit=25)

        def failed(err):
            if self.search_input.text().strip() != query:
                return
            self.web_table.hide()
            if isinstance(err, OnlineDisabled):
                self.search_web_status.setText("Online features are off (Settings).")
            elif isinstance(err, OfflineError):
                self.search_web_status.setText("You're offline. Showing your library only.")
            else:
                self.search_web_status.setText(f"Web search isn't available right now ({err}).")

        self.online_call(self.online.search, query, 30, on_done=done, on_error=failed)

    # --- Your Library -----------------------------------------------------
    def setup_library_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.library_page.setLayout(layout)

        top = QHBoxLayout()
        top.addWidget(self._page_title("📚 Your Library"))
        top.addStretch()
        rescan_btn = QPushButton("⟳ Rescan")
        rescan_btn.setStyleSheet(PILL_BUTTON)
        rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rescan_btn.setFixedHeight(32)  # radius must be <= half the height or Qt draws square corners
        rescan_btn.clicked.connect(self.rescan_library)
        top.addWidget(rescan_btn)
        add_btn = QPushButton("➕ Add folder…")
        add_btn.setStyleSheet(GREEN_BUTTON)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(36)
        add_btn.clicked.connect(self._choose_music_folder)
        top.addWidget(add_btn)
        layout.addLayout(top)

        self.library_count_label = self._muted_label("Scanning your music…")
        layout.addWidget(self.library_count_label)

        self.folder_list_widget = QWidget()
        self.folder_list_layout = QVBoxLayout()
        self.folder_list_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_list_layout.setSpacing(2)
        self.folder_list_widget.setLayout(self.folder_list_layout)
        layout.addWidget(self.folder_list_widget)
        self.refresh_folder_list()

        self.library_table = TrackTable(sortable=True)
        self.library_table.play_requested.connect(lambda s, view: self.play_song(s, queue=view, source="Your Library"))
        self.library_table.context_requested.connect(
            lambda s, row, pos: self._show_song_menu(s, pos, queue=self.library_table.songs_in_view(), source="Your Library"))
        layout.addWidget(self.library_table, 1)

    def refresh_folder_list(self):
        while self.folder_list_layout.count():
            item = self.folder_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for folder in self.user_data.music_folders:
            row = QWidget()
            h = QHBoxLayout()
            h.setContentsMargins(0, 0, 0, 0)
            row.setLayout(h)
            missing = "" if os.path.isdir(folder) else "   (not found)"
            lbl = QLabel(f"📁 {folder}{missing}")
            lbl.setStyleSheet(f"color: {'#b3b3b3' if not missing else '#f15e6c'}; font-size: 12px;")
            h.addWidget(lbl)
            rm = QPushButton("✕")
            rm.setToolTip("Remove this folder from your library (files are not deleted)")
            rm.setFixedSize(22, 22)
            rm.setCursor(Qt.CursorShape.PointingHandCursor)
            rm.setStyleSheet("QPushButton { color: #6a6a6a; border: none; background: transparent; } QPushButton:hover { color: white; }")
            rm.clicked.connect(lambda _=False, f=folder: self.remove_music_folder(f))
            h.addWidget(rm)
            h.addStretch()
            self.folder_list_layout.addWidget(row)

    def refresh_library_page(self):
        total = sum(s.duration for s in self.songs)
        n = len(self.songs)
        self.library_count_label.setText(
            f"{n} song{'s' if n != 1 else ''}, {format_total(total)} · click a column to sort · double-click to play"
            if n else "No songs yet. Add a folder that contains music.")
        self.library_table.set_songs(self.songs)
        self.library_table.set_current(self.current_song)

    # --- Playlists grid ---------------------------------------------------
    def setup_playlists_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.playlists_page.setLayout(layout)

        top = QHBoxLayout()
        top.addWidget(self._page_title("🎶 Playlists"))

        btn = QPushButton("➕ Create Playlist")
        btn.setStyleSheet("color: white; background: #1db954; padding: 8px 16px; border-radius: 20px; font-weight: bold;")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(40)  # radius 20 needs height >= 40 or Qt draws square corners
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
        self.playlist_scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        content.setLayout(self.playlist_scroll_layout)
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def display_playlists(self):
        for i in reversed(range(self.playlist_scroll_layout.count())):
            w = self.playlist_scroll_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        if not self.playlists:
            self.playlist_scroll_layout.addWidget(
                self._muted_label("No playlists yet. Click ➕ Create Playlist to make one."), 0, 0)
            return

        for idx, pl in enumerate(self.playlists):
            tile = HoverablePlaylistTile(pl, 150)
            tile.play_clicked.connect(self.play_playlist)
            tile.open_clicked.connect(self.show_playlist)
            self.playlist_scroll_layout.addWidget(tile, idx // 4, idx % 4)

    def play_playlist(self, playlist):
        if playlist.songs:
            self.play_song(playlist.songs[0], queue=playlist.songs, source=playlist.name)
        else:
            self.show_status(f"\"{playlist.name}\" is empty.", kind="info")

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

        hint = QLabel("Pick songs now, or leave empty and add songs later (right-click any song).")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #b3b3b3; font-size: 11px;")
        layout.addWidget(hint)

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
            if not name:
                QMessageBox.warning(self, "Create Playlist", "Please enter a playlist name.")
                return
            if self._name_taken(name):
                QMessageBox.warning(self, "Create Playlist", f"You already have a playlist called \"{name}\".")
                return
            # Keep the order the songs appear in the list, not the click order.
            rows = sorted(idx.row() for idx in song_list.selectedIndexes())
            self.create_playlist(name, [self.songs[r] for r in rows])

    # --- Single playlist page --------------------------------------------
    def setup_playlist_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        self.playlist_page.setLayout(layout)

        header = QHBoxLayout()
        header.setSpacing(20)
        self.pl_cover = QLabel()
        self.pl_cover.setFixedSize(180, 180)
        header.addWidget(self.pl_cover)

        info = QVBoxLayout()
        info.addStretch()
        kind = QLabel("Playlist")
        kind.setStyleSheet("color: white; font-size: 12px;")
        info.addWidget(kind)
        self.pl_title = QLabel()
        self.pl_title.setStyleSheet("color: white; font-size: 40px; font-weight: 800;")
        info.addWidget(self.pl_title)
        self.pl_meta = QLabel()
        self.pl_meta.setStyleSheet("color: #b3b3b3; font-size: 13px;")
        info.addWidget(self.pl_meta)
        header.addLayout(info, 1)
        layout.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.pl_play_btn = QPushButton()
        self.pl_play_btn.setIcon(QIcon(draw_play_button(56)))
        self.pl_play_btn.setIconSize(QSize(56, 56))
        self.pl_play_btn.setFixedSize(60, 60)
        self.pl_play_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
        self.pl_play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pl_play_btn.setToolTip("Play")
        self.pl_play_btn.clicked.connect(lambda: self.open_playlist and self.play_playlist(self.open_playlist))
        actions.addWidget(self.pl_play_btn)
        rename_btn = QPushButton("Rename")
        rename_btn.setStyleSheet(PILL_BUTTON)
        rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rename_btn.setFixedHeight(32)
        rename_btn.clicked.connect(self._rename_open_playlist)
        actions.addWidget(rename_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(PILL_BUTTON)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setFixedHeight(32)
        delete_btn.clicked.connect(self._confirm_delete_open_playlist)
        actions.addWidget(delete_btn)
        actions.addStretch()
        layout.addLayout(actions)

        self.pl_empty = self._muted_label(
            "This playlist is empty. Right-click any song on Home, Search or Your Library and choose "
            "“Add to playlist”.")
        layout.addWidget(self.pl_empty)

        self.pl_table = TrackTable(sortable=False)
        self.pl_table.play_requested.connect(
            lambda s, view: self.open_playlist and self.play_song(s, queue=self.open_playlist.songs,
                                                                  source=self.open_playlist.name))
        self.pl_table.context_requested.connect(
            lambda s, row, pos: self.open_playlist and self._show_song_menu(
                s, pos, queue=self.open_playlist.songs, playlist=self.open_playlist, row=row,
                source=self.open_playlist.name))
        layout.addWidget(self.pl_table, 1)

    def show_playlist(self, playlist):
        self.open_playlist = playlist
        self.refresh_playlist_page()
        self.stack.setCurrentWidget(self.playlist_page)
        self.sidebar.set_active("playlists")

    def refresh_playlist_page(self):
        pl = self.open_playlist
        if pl is None:
            return
        self.pl_cover.setPixmap(load_pixmap(pl.cover_path).scaled(
            180, 180, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        self.pl_title.setText(pl.name)
        n = len(pl.songs)
        missing = sum(1 for s in pl.songs if not s.exists)
        meta = f"{n} song{'s' if n != 1 else ''}, {format_total(pl.total_duration)}"
        if missing:
            meta += f" · {missing} missing"
        self.pl_meta.setText(meta)
        self.pl_table.set_songs(pl.songs)
        self.pl_table.set_current(self.current_song)
        self.pl_table.setVisible(bool(pl.songs))
        self.pl_empty.setVisible(not pl.songs)

    def _rename_open_playlist(self):
        pl = self.open_playlist
        if pl is None:
            return
        name, ok = QInputDialog.getText(self, "Rename playlist", "New name:", text=pl.name)
        if ok:
            self.rename_playlist(pl, name)

    def _confirm_delete_open_playlist(self):
        pl = self.open_playlist
        if pl is None:
            return
        answer = QMessageBox.question(
            self, "Delete playlist",
            f"Delete \"{pl.name}\"?\n\nYour music files are not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_playlist(pl)

    # ==================================================================
    # Playback
    # ==================================================================
    def play_song(self, song: Song, queue=None, source=None):
        """Start playing a song. Never blocks the UI.

        queue:  the list of songs to continue with (the "context"). If omitted,
                the current context is kept when it contains the song,
                otherwise the whole library is used.
        source: name shown as "Next from: <source>" in the queue panel.
        """
        if queue is not None:
            self.pq.set_context(queue, song, source if source is not None else self.pq.source_name)
        elif song in self.pq.items:
            self.pq.index = self.pq.items.index(song)
        else:
            self.pq.set_context(self.songs, song, source or "Your Songs")
        self._consecutive_failures = 0
        self._start_current()

    def _start_current(self):
        if getattr(self, "_shut_down", False) or not self.queue:
            return
        song = self.pq.current
        if song is None:
            return
        self.current_song = song
        self.pq.record_played(song)
        self._queue_changed()
        self._update_now_playing(song)
        self.schedule_save(3000)

        # Show what we are trying to play straight away.
        self.song_info.setText(f"{song.title} - {song.artist}")
        self.set_album_cover(song.album_cover_path)
        self.time_label.setText("00:00")
        self.duration_label.setText(format_time(song.duration) if song.duration > 0 else "--:--")
        self.progress_slider.setValue(0)
        self._refresh_now_playing()

        self._reached_playing = False
        self._open_elapsed_ms = 0

        is_remote = getattr(song, "is_remote", False)
        if is_remote:
            if not self.online_enabled:
                self.player.stop()
                self._track_handled = True
                self._handle_failed_track("online features are switched off")
                return
            if not song.playable_url:
                self.player.stop()
                self._track_handled = True
                self._handle_failed_track("no preview available for this song")
                return
            if song.is_preview:
                self.song_info.setText(f"{song.title} - {song.artist}   ·   30-second preview")
        elif not song.exists:
            self.player.stop()
            self._track_handled = True
            self._handle_failed_track("file not found (moved or deleted?)")
            return

        try:
            self.player.stop()
            media = self.vlc_instance.media_new(song.playable_url if is_remote else song.file_path)
            self.player.set_media(media)
            if self.player.play() == -1:
                raise RuntimeError("VLC refused to start playback")
            self._apply_volume()
        except Exception as e:
            self._track_handled = True
            self._handle_failed_track(f"playback error: {e}")
            return

        self._track_handled = False
        self.is_playing = True
        self.play_btn.setText("⏸")
        # Note: any "Skipped …" message is left visible; it clears on its own timer.

    def _refresh_now_playing(self):
        for table in (self.library_table, self.search_table, self.pl_table):
            table.set_current(self.current_song)

    def _handle_failed_track(self, reason: str):
        song = self.current_song
        name = song.title if song else "Track"
        self.is_playing = False
        self.play_btn.setText("▶️")
        self._consecutive_failures += 1
        if self._consecutive_failures >= max(1, len(self.queue)):
            # Every song in the queue has failed: stop instead of looping forever.
            self._consecutive_failures = 0
            self.show_status(f"⚠ Can't play \"{name}\": {reason}. No playable songs left in the queue.", 10000)
            return
        self.show_status(f"⚠ Skipped \"{name}\": {reason}")
        # Skip on the next event-loop turn so the UI stays responsive.
        QTimer.singleShot(0, lambda: self._advance_after_current(auto=False))

    def _advance_after_current(self, auto=True):
        """auto=True: the song finished by itself (repeat rules apply)."""
        if self.pq.advance(auto=auto) is None:
            # End of the queue with repeat off: stop, like Spotify.
            self.is_playing = False
            self.play_btn.setText("▶️")
            self.progress_slider.setValue(0)
            self.time_label.setText("00:00")
            self._queue_changed()
            return
        self._start_current()

    def play_pause_song(self):
        try:
            if not self.pq.items:
                if not self.songs:
                    return
                self.pq.set_context(self.songs, self.songs[0], "Your Songs")

            state = self.player.get_state()

            if state == vlc.State.Playing:
                self.player.set_pause(1)
                self.play_btn.setText("▶️")
                self.is_playing = False
                self.now_playing_panel.set_playing(False)
            elif state == vlc.State.Paused:
                self.player.set_pause(0)
                self.play_btn.setText("⏸")
                self.is_playing = True
                self.now_playing_panel.set_playing(True)
            elif state in (vlc.State.Opening, vlc.State.Buffering):
                return  # still loading; ignore extra clicks
            else:
                self._consecutive_failures = 0
                self.queue_index = min(self.queue_index, len(self.queue) - 1)
                self._start_current()
        except Exception as e:
            self.show_status(f"⚠ Play/Pause error: {e}")

    def next_song(self):
        if self.pq.items or self.pq.user_queue:
            self._consecutive_failures = 0
            if self.pq.advance(auto=False) is not None:
                self._start_current()

    def prev_song(self):
        if not self.queue:
            return
        self._consecutive_failures = 0
        if self.player.get_state() in (vlc.State.Playing, vlc.State.Paused) and \
                self.player.get_time() > PREV_RESTART_THRESHOLD_MS:
            # Like Spotify: restart the current song if we're a few seconds in.
            self.player.set_time(0)
            return
        self.pq.previous()
        self._start_current()

    # ------------------------------------------------------------------
    # Queue, shuffle, repeat, right panel
    # ------------------------------------------------------------------
    def _icon_button(self, tooltip, slot):
        b = QPushButton()
        b.setToolTip(tooltip)
        b.setFixedSize(34, 34)
        b.setIconSize(QSize(20, 20))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet("QPushButton { border: none; background: transparent; border-radius: 17px; }"
                        "QPushButton:hover { background: #2a2a2a; }")
        b.clicked.connect(slot)
        return b

    def _update_mode_buttons(self):
        on = self.pq.shuffle
        self.shuffle_btn.setIcon(icons.shuffle(icons.GREEN if on else icons.GREY, dot=on))
        self.shuffle_btn.setToolTip(f"Shuffle: {'on' if on else 'off'} (Ctrl+S)")
        mode = self.pq.repeat
        self.repeat_btn.setIcon(icons.repeat(icons.GREY if mode == "off" else icons.GREEN,
                                             one=(mode == "one"), dot=(mode != "off")))
        label = {"off": "off", "all": "all songs", "one": "this song"}[mode]
        self.repeat_btn.setToolTip(f"Repeat: {label} (Ctrl+R)")
        if hasattr(self, "queue_btn") and hasattr(self, "right_panel"):
            shown = not self.right_panel.isHidden()
            q = shown and self.right_panel.currentWidget() is self.queue_panel
            n = shown and self.right_panel.currentWidget() is self.now_playing_panel
            self.queue_btn.setIcon(icons.queue(icons.GREEN if q else icons.GREY, dot=q))
            self.nowplaying_btn.setIcon(icons.now_playing(icons.GREEN if n else icons.GREY, dot=n))

    def toggle_shuffle(self):
        self.pq.set_shuffle(not self.pq.shuffle)
        self.user_data.shuffle = self.pq.shuffle
        self._update_mode_buttons()
        self._queue_changed()
        self.schedule_save()

    def cycle_repeat(self):
        self.user_data.repeat = self.pq.cycle_repeat()
        self._update_mode_buttons()
        self._queue_changed()
        self.schedule_save()

    def add_to_queue(self, song):
        self.pq.add_to_queue(song)
        self._queue_changed()
        self.show_status(f"Added to queue: {song.title}", kind="info", timeout_ms=2500)

    def _remove_from_user_queue(self, position):
        self.pq.remove_from_user_queue(position)
        self._queue_changed()

    def _clear_user_queue(self):
        self.pq.user_queue.clear()
        self._queue_changed()

    def _play_upcoming(self, position):
        if self.pq.jump_to_upcoming(position) is not None:
            self._consecutive_failures = 0
            self._start_current()

    def _update_now_playing(self, song):
        canvas = (find_canvas(song, self.storage.data_dir)
                  if song is not None and not getattr(song, "is_remote", False) else None)
        self.now_playing_panel.set_song(song, self.pq.source_name, canvas_path=canvas, playing=True)
        self._refresh_artist_card()

    def _refresh_artist_card(self):
        """Fill 'About the artist' for the current song (online, cached per artist)."""
        panel = self.now_playing_panel
        song = self.current_song
        if song is None or not song.artist or song.artist == "Unknown Artist":
            panel.set_card_message("")
            return
        if not self.online_enabled:
            panel.set_card_message("Artist info is off. Turn on Online features in Settings to see it.")
            return
        artist = song.artist
        if artist in self._artist_cards:
            self._show_artist_card(artist, self._artist_cards[artist])
            return
        panel.set_card_message("Loading artist info…")

        def done(card):
            self._artist_cards[artist] = card
            if self.current_song is not None and self.current_song.artist == artist:
                self._show_artist_card(artist, card)

        def failed(err):
            if self.current_song is not None and self.current_song.artist == artist:
                if isinstance(err, OnlineDisabled):
                    panel.set_card_message("Artist info is off. Turn on Online features in Settings to see it.")
                elif isinstance(err, OfflineError):
                    panel.set_card_message("You're offline. Artist info will show when you're back online.")
                else:
                    panel.set_card_message("")

        self.online_call(self.online.artist_card, artist, on_done=done, on_error=failed)

    def _show_artist_card(self, artist, card):
        panel = self.now_playing_panel
        if not any(card.get(k) for k in ("bio", "fans", "listeners", "picture_url")):
            panel.set_card_message("")
            return
        panel.set_artist_card(card)
        url = card.get("picture_url")
        if url:
            self.online_call(self.net.get_image, url,
                             on_done=lambda path: (self.current_song is not None and self.current_song.artist == artist
                                                   and panel.set_artist_image(path)))

    def _queue_changed(self):
        if not self.right_panel.isHidden() and self.right_panel.currentWidget() is self.queue_panel:
            user, upcoming = self.pq.upcoming(limit=QueuePanel.MAX_ROWS)
            self.queue_panel.refresh(self.current_song, user, upcoming, self.pq.source_name, list(self.pq.recent))

    def set_right_panel(self, name, save=True):
        """name: "" (hidden), "queue" or "nowplaying"."""
        widget = {"queue": self.queue_panel, "nowplaying": self.now_playing_panel}.get(name)
        if widget is None:
            self.right_panel.hide()
            name = ""
        else:
            self.right_panel.setCurrentWidget(widget)
            self.right_panel.show()
        self.user_data.right_panel = name
        self._update_mode_buttons()
        self._queue_changed()
        self.now_playing_panel.set_playing(self.is_playing)
        if save:
            self.schedule_save()

    def toggle_right_panel(self, name):
        showing = not self.right_panel.isHidden() and self.user_data.right_panel == name
        self.set_right_panel("" if showing else name)

    # ------------------------------------------------------------------
    # Online features
    # ------------------------------------------------------------------
    @property
    def online_enabled(self):
        return bool(self.user_data.online_enabled)

    def online_call(self, fn, *args, on_done=None, on_error=None):
        """Run an online request in the background; callbacks run on the UI thread.
        Does nothing (calls on_error with OnlineDisabled) when online features are off."""
        if not self.online_enabled:
            if on_error:
                on_error(OnlineDisabled("Online features are switched off in Settings."))
            return None

        def done(result):
            self._update_online_indicator()
            if on_done:
                on_done(result)

        def failed(err):
            self._update_online_indicator()
            if not isinstance(err, OfflineError):
                print(f"Online error: {err}\n{getattr(err, '__traceback_text__', '')}")
            if on_error:
                on_error(err)

        return run_async(self, fn, *args, on_done=done, on_error=failed)

    # ------------------------------------------------------------------
    # Go to Radio
    # ------------------------------------------------------------------
    def start_radio(self, seed):
        """Build a radio station from a song (online) and continue playing from it."""
        if not self.online_enabled:
            self.show_status("⚠ Radio needs Online features (Settings).")
            return
        name = f"{seed.title} Radio"
        self.show_status(f"Starting {name}…", kind="info", timeout_ms=15000)

        def done(tracks):
            if not tracks:
                self.show_status(f"⚠ Couldn't find songs similar to \"{seed.title}\".")
                return
            items = self.radio_items(tracks)
            playing_seed = self.current_song is not None and self.current_song == seed and self.is_playing
            self.pq.set_context([seed] + [s for s in items if s != seed], seed, name)
            if playing_seed:
                self._queue_changed()
            else:
                self._consecutive_failures = 0
                self._start_current()
            local = sum(1 for s in items if not getattr(s, "is_remote", False))
            self.show_status(f"{name}: {len(items)} songs ({local} from your library, others as previews)",
                             kind="info", timeout_ms=6000)
            if self.user_data.right_panel == "":
                self.set_right_panel("queue")
            self.fetch_covers(items)

        def failed(err):
            if isinstance(err, OfflineError):
                self.show_status("⚠ You're offline, so Radio can't find new songs right now.")
            else:
                self.show_status(f"⚠ Radio couldn't start: {err}")

        self.online_call(self.online.radio, seed.artist, seed.title, on_done=done, on_error=failed)

    def radio_items(self, tracks):
        """Turn online tracks into queue items: your own file if you have the song,
        otherwise an online (preview) song."""
        index = build_match_index(self.songs)
        out = []
        for t in tracks:
            local = find_local_match(t, self.songs, index)
            if local is not None:
                out.append(local)
            elif t.stream_url or t.preview_url:
                out.append(RemoteSong(t))
            # else: nothing we're allowed to play here, so leave it out
        return out

    def fetch_covers(self, songs, limit=40):
        """Download cover art for online songs in the background, then refresh views."""
        pending = [s for s in songs if getattr(s, "is_remote", False) and s.track.cover_url
                   and s.album_cover_path == PLACEHOLDER_IMAGE][:limit]
        for s in pending:
            def done(path, song=s):
                if path:
                    song.album_cover_path = path
                    self._schedule_view_refresh()
            self.online_call(self.net.get_image, s.track.cover_url, on_done=done)

    def _schedule_view_refresh(self):
        if not hasattr(self, "_view_refresh_timer"):
            self._view_refresh_timer = QTimer(self)
            self._view_refresh_timer.setSingleShot(True)
            self._view_refresh_timer.timeout.connect(self._refresh_online_views)
        self._view_refresh_timer.start(250)

    def _refresh_online_views(self):
        self._queue_changed()
        self.web_table.refresh_artwork()
        if self.current_song is not None and getattr(self.current_song, "is_remote", False):
            self.set_album_cover(self.current_song.album_cover_path)
            self.now_playing_panel.artwork.set_pixmap(load_pixmap(self.current_song.album_cover_path))

    def _update_online_indicator(self):
        if not self.online_enabled:
            state = "disabled"
        elif self.net.online is False:
            state = "offline"
        else:
            state = "online"
        self.sidebar.set_online_state(state)

    def open_settings(self):
        dlg = SettingsDialog(self.user_data, on_clear_cache=self.net.clear_cache, parent=self)
        if dlg.exec():
            self.apply_settings(dlg.values())

    def apply_settings(self, values):
        was_online = self.user_data.online_enabled
        self.user_data.online_enabled = values["online_enabled"]
        if values["lastfm_api_key"] != self.user_data.lastfm_api_key:
            self.user_data.lastfm_api_key = values["lastfm_api_key"]
            self.online.set_lastfm_key(values["lastfm_api_key"])
        self.user_data.jamendo_client_id = values["jamendo_client_id"]
        if was_online != self.user_data.online_enabled:
            self.net.online = None
            self._online_setting_changed()
        self._update_online_indicator()
        self.save_now()

    def _online_setting_changed(self):
        """Hook for pages/panels that show online content (refresh or hide it)."""
        for hook in getattr(self, "_online_hooks", []):
            hook()

    def closeEvent(self, event):
        """Save, stop audio and release VLC cleanly when the window closes."""
        if getattr(self, "_shut_down", False):
            # Already released; touching VLC again would crash.
            super().closeEvent(event)
            return
        self._shut_down = True
        try:
            if self._save_timer.isActive():
                self.save_now()
            if self._scan_thread is not None:
                self._scan_thread.stop()
                self._scan_thread.wait(3000)
            self.timer.stop()
            self.player.stop()
            self.player.release()
            self.vlc_instance.release()
        except Exception as e:
            print(f"Shutdown error: {e}")
        super().closeEvent(event)

    # ==================================================================
    # Navigation
    # ==================================================================
    def show_home(self):
        self.stack.setCurrentWidget(self.home_page)
        self.sidebar.set_active("home")

    def show_search(self):
        self.stack.setCurrentWidget(self.search_page)
        self.sidebar.set_active("search")
        self.search_input.setFocus()
        self.search_input.selectAll()

    def show_library(self):
        self.stack.setCurrentWidget(self.library_page)
        self.sidebar.set_active("library")

    def show_playlists(self):
        self.stack.setCurrentWidget(self.playlists_page)
        self.sidebar.set_active("playlists")

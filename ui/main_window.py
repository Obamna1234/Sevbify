import os
import vlc
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QScrollArea, QPushButton, QFrame, QGridLayout,
    QDialog, QLineEdit, QListWidget, QAbstractItemView,
    QDialogButtonBox, QMessageBox, QSlider, QMenu, QInputDialog, QFileDialog, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QBrush, QPolygon, QColor, QKeySequence, QShortcut, QDesktopServices
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QPoint, QThread, QEvent, QUrl, QFileSystemWatcher

from .top_bar import TopBar
from .library_panel import LibraryPanel, rounded
from .cards import Card, QuickTile
from . import theme
from .track_table import TrackTable
from .queue_panel import QueuePanel
from .now_playing_panel import NowPlayingPanel, dominant_colour
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
from .download_manager import DownloadManager
from core import downloader

# How long (ms) a track may sit in "opening/buffering" before we give up on it.
OPEN_TIMEOUT_MS = 10000
# Pressing "previous" more than this far into a track restarts it instead
# (same behaviour as Spotify).
PREV_RESTART_THRESHOLD_MS = 3000
SAMPLE_PLAYLIST_NAMES = ["Favorites", "Chill Hits", "Workout Mix"]
HOME_TILE_WIDTH = 170   # cover is 140 px; the extra room fits titles and artist names

# Spotify-style slider: thin grey track, white fill; green fill + white knob on hover.
SLIDER_STYLE = (
    "QSlider { min-height: 16px; }"
    "QSlider::groove:horizontal { border: none; height: 4px; background: #4d4d4d; border-radius: 2px; }"
    "QSlider::sub-page:horizontal { background: #ffffff; border-radius: 2px; }"
    "QSlider::sub-page:horizontal:hover { background: #1ed760; }"
    "QSlider::handle:horizontal { background: transparent; border: none; width: 12px; height: 12px;"
    " margin: -4px 0; border-radius: 6px; }"
    "QSlider::handle:horizontal:hover { background: #ffffff; }")

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


_thumb_cache = {}


def cover_thumb(path: str, size: int) -> QPixmap:
    """Cover art scaled down once and cached (cards and tiles never need full size)."""
    key = (path, size)
    pm = _thumb_cache.get(key)
    if pm is None:
        pm = load_pixmap(path).scaled(size * 2, size * 2, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                      Qt.TransformationMode.SmoothTransformation)
        if len(_thumb_cache) > 1500:
            _thumb_cache.clear()
        _thumb_cache[key] = pm
    return pm


HOME_SONGS_LIMIT = 30   # Home shows a taste; Your Songs (left panel) lists everything


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
        self.setGeometry(80, 60, 1360, 860)
        self.setMinimumSize(960, 600)
        theme.load_fonts()
        self.setStyleSheet(theme.base_stylesheet())

        # Audio only: VLC never opens a video window (canvas loops use Qt's own video player).
        self.vlc_instance = vlc.Instance("--no-video", *vlc_args)
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

        # --- Layout (Spotify): black window, top bar, three rounded panels, player bar
        central = QWidget()
        central.setObjectName("central")
        central.setStyleSheet(f"#central {{ background: {theme.BLACK}; }}")
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(8, 0, 8, 0)
        self.main_layout.setSpacing(0)

        self.top_bar = TopBar()
        self.top_bar.home_clicked.connect(self.show_home)
        self.top_bar.back_clicked.connect(self.go_back)
        self.top_bar.forward_clicked.connect(self.go_forward)
        self.top_bar.settings_clicked.connect(self.open_settings)
        self.top_bar.search_activated.connect(lambda: self.show_search(select=False))
        self.top_bar.downloads_clicked.connect(self._show_downloads_menu)
        self.main_layout.addWidget(self.top_bar)
        self.sidebar = self.top_bar        # older code/tests: .online_label, .set_online_state
        self._history, self._history_pos, self._replaying = [], -1, False

        self.top_layout = QHBoxLayout()
        self.top_layout.setSpacing(theme.GAP)
        self.main_layout.addLayout(self.top_layout, 1)

        self.library_panel = LibraryPanel(cover_thumb)
        self.library_panel.create_clicked.connect(self.create_playlist_dialog)
        self.library_panel.open_all_songs.connect(self.show_library)
        self.library_panel.open_saved.connect(self.show_saved)
        self.library_panel.open_playlist.connect(self.show_playlist)
        self.library_panel.play_playlist.connect(self.play_playlist)
        self.library_panel.playlist_menu.connect(self._playlist_context_menu)
        self.top_layout.addWidget(self.library_panel)

        self.center_panel = QFrame()
        self.center_panel.setObjectName("centerPanel")
        self.center_panel.setStyleSheet(theme.panel_style("centerPanel"))
        cl = QVBoxLayout(self.center_panel)
        cl.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        self.stack.setObjectName("pages")
        self.stack.setStyleSheet(f"#pages {{ background: transparent; }}")
        cl.addWidget(self.stack)
        self.top_layout.addWidget(self.center_panel, 1)

        # Right-hand panel (Queue / Now playing), hidden until toggled.
        self.right_panel = QStackedWidget()
        self.right_panel.setObjectName("rightPanel")
        self.right_panel.setStyleSheet(f"#rightPanel {{ background: {theme.PANEL}; border-radius: {theme.RADIUS}px; }}")
        self.right_panel.setMinimumWidth(300)
        self.right_panel.setMaximumWidth(380)
        self.queue_panel = QueuePanel(load_pixmap)
        self.queue_panel.close_requested.connect(lambda: self.set_right_panel(""))
        self.queue_panel.play_upcoming.connect(self._play_upcoming)
        self.queue_panel.play_recent.connect(lambda s: self.play_song(s, queue=list(self.pq.recent), source="Recently played"))
        self.queue_panel.remove_from_queue.connect(self._remove_from_user_queue)
        self.queue_panel.clear_user_queue.connect(self._clear_user_queue)
        self.queue_panel.save_as_playlist.connect(self.save_queue_as_playlist)
        self.right_panel.addWidget(self.queue_panel)
        self.now_playing_panel = NowPlayingPanel(load_pixmap)
        self.now_playing_panel.close_requested.connect(lambda: self.set_right_panel(""))
        self.right_panel.addWidget(self.now_playing_panel)
        self._artist_cards = {}          # artist name -> card dict (this session)
        self._online_hooks = [self._refresh_artist_card]

        # --- Downloads (SEVBY engine, in the background) ------------------
        self.downloads = DownloadManager(self)
        self._downloaded_paths = {}      # song key -> file the download manager saved
        self._downloads_refresh = QTimer(self)
        self._downloads_refresh.setSingleShot(True)
        self._downloads_refresh.timeout.connect(self._refresh_download_views)
        self._download_rescan = QTimer(self)
        self._download_rescan.setSingleShot(True)
        self._download_rescan.timeout.connect(self.rescan_library)
        self.downloads.changed.connect(lambda: self._downloads_refresh.start(150))
        self.downloads.song_done.connect(self._on_song_downloaded)
        self.downloads.run_finished.connect(self._on_downloads_finished)
        self.downloads.problem.connect(lambda text: self.show_status("⚠ Can't download: " + text, 15000))
        self.right_panel.hide()
        self.top_layout.addWidget(self.right_panel)

        self.home_page = QWidget()
        self.search_page = QWidget()
        self.library_page = QWidget()
        self.playlists_page = QWidget()
        self.playlist_page = QWidget()
        self.saved_page = QWidget()

        for page in [self.home_page, self.search_page, self.library_page,
                     self.playlists_page, self.playlist_page, self.saved_page]:
            page.setObjectName("page")
            page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            page.setStyleSheet("#page { background: transparent; }")
            self.stack.addWidget(page)

        self.setup_player_bar()
        self.setup_home_page()
        self.setup_search_page()
        self.setup_library_page()
        self.setup_playlists_page()
        self.setup_playlist_page()
        self.setup_saved_page()
        self.setup_shortcuts()
        for table in (self.pl_table, self.web_table):
            table.download_state = self.downloads.state

        self.show_home()

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
        filled = self._fill_pending_slots()
        self._watch_music_folders()
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
        if filled:
            names = ", ".join(f"\"{t}\"" for t in filled[:3]) + (f" and {len(filled) - 3} more" if len(filled) > 3 else "")
            self.show_status(f"⬇ Now in your library: {names}", kind="info", timeout_ms=8000)
            self.save_now()
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
            for entry in stored.tracks:
                if isinstance(entry, dict):
                    # A song added from Radio/Search that isn't downloaded yet.
                    pl.add_song(RemoteSong(OnlineTrack.from_dict(entry["pending"])))
                    continue
                key = normalise_path(entry)
                # Missing files are kept (shown greyed out) so nothing is lost
                # if a drive is disconnected or a file was renamed.
                pl.add_song(by_key.get(key) or Song(entry))
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
                StoredPlaylist(p.name, [{"pending": s.track.to_dict()} if getattr(s, "is_remote", False)
                                        else s.file_path for s in p.songs]) for p in self.playlists
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
        self._refresh_library_panel()
        if self.open_playlist is not None and (playlist is None or playlist is self.open_playlist):
            self.refresh_playlist_page()
        if self.stack.currentWidget() is self.saved_page:
            self.refresh_saved_page()

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

    def build_song_menu(self, song, queue=None, playlist=None, row=None, source="",
                        saved_genre=None, saved_index=None):
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
        if getattr(song, "is_remote", False):
            state, _note = self.downloads.state(song.track.key)
            if state in ("queued", "downloading"):
                act = menu.addAction("⬇  Downloading…" if state == "downloading" else "⬇  Queued to download")
                act.setEnabled(False)
                menu.addAction("■  Stop all downloads").triggered.connect(self.downloads.stop)
            else:
                text = "⬇  Retry download" if state == "failed" else "⬇  Download"
                menu.addAction(text).triggered.connect(lambda: self.download_songs([song]))
        if getattr(song, "is_remote", False) and saved_genre is None:
            menu.addAction("⬇  Save for later").triggered.connect(lambda: self.save_for_later(song))
        if saved_genre is not None and saved_index is not None:
            menu.addAction("✕  Remove from Saved for later").triggered.connect(
                lambda: self.remove_saved(saved_genre, saved_index))
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
        """Spotify layout: song on the left, controls + progress in the middle,
        view toggles and volume on the right."""
        self.player_bar = QFrame()
        self.player_bar.setObjectName("playerBar")
        self.player_bar.setFixedHeight(88)
        self.player_bar.setStyleSheet(f"#playerBar {{ background: {theme.BLACK}; }}")
        row = QHBoxLayout(self.player_bar)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(8)

        # --- Left: artwork, title, artist, status --------------------------
        left = QWidget()
        left.setMinimumWidth(180)
        lh = QHBoxLayout(left)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.setSpacing(12)
        self.album_cover = QLabel()
        self.album_cover.setFixedSize(56, 56)
        self.set_album_cover(PLACEHOLDER_IMAGE)
        lh.addWidget(self.album_cover)
        info = QVBoxLayout()
        info.setSpacing(2)
        info.addStretch()
        self.song_info = QLabel("No song playing")          # the title
        self.song_info.setStyleSheet(f"color: {theme.TEXT}; font-size: 14px; font-weight: 600;")
        self.artist_info = QLabel("")
        self.artist_info.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px;")
        for lbl in (self.song_info, self.artist_info):
            lbl.setMinimumWidth(0)
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info.addWidget(self.song_info)
        info.addWidget(self.artist_info)
        # Small status line for errors and confirmations.
        self.status_label = QLabel("")
        self.status_label.setMinimumWidth(0)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label.hide()
        info.addWidget(self.status_label)
        info.addStretch()
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self.clear_status)
        lh.addLayout(info, 1)
        row.addWidget(left, 3)

        # --- Middle: controls and progress ----------------------------------
        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(4)
        controls = QHBoxLayout()
        controls.setSpacing(14)
        controls.addStretch()
        self.shuffle_btn = self._icon_button("Shuffle (Ctrl+S)", self.toggle_shuffle)
        controls.addWidget(self.shuffle_btn)
        self.prev_btn = self._icon_button("Previous (Ctrl+Left)", self.prev_song)
        self.prev_btn.setIcon(icons.skip("prev", theme.SUBDUED))
        self.prev_btn.setIconSize(QSize(16, 16))
        controls.addWidget(self.prev_btn)
        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(34, 34)
        self.play_btn.setIconSize(QSize(14, 14))
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("QPushButton { background: white; border: none; border-radius: 17px; }"
                                    "QPushButton:hover { background: #f0f0f0; }"
                                    "QPushButton:pressed { background: #d0d0d0; }")
        self.play_btn.clicked.connect(self.play_pause_song)
        controls.addWidget(self.play_btn)
        self.next_btn = self._icon_button("Next (Ctrl+Right)", self.next_song)
        self.next_btn.setIcon(icons.skip("next", theme.SUBDUED))
        self.next_btn.setIconSize(QSize(16, 16))
        controls.addWidget(self.next_btn)
        self.repeat_btn = self._icon_button("Repeat (Ctrl+R)", self.cycle_repeat)
        controls.addWidget(self.repeat_btn)
        controls.addStretch()
        mv.addLayout(controls)

        prog = QHBoxLayout()
        prog.setSpacing(8)
        self.time_label = QLabel("00:00")
        self.duration_label = QLabel("00:00")
        for lbl, align in ((self.time_label, Qt.AlignmentFlag.AlignRight), (self.duration_label, Qt.AlignmentFlag.AlignLeft)):
            lbl.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 12px;")
            lbl.setFixedWidth(42)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderPressed.connect(self.slider_pressed)
        self.progress_slider.sliderReleased.connect(self.slider_released)
        self.progress_slider.setStyleSheet(SLIDER_STYLE)
        prog.addWidget(self.time_label)
        prog.addWidget(self.progress_slider, 1)
        prog.addWidget(self.duration_label)
        mv.addLayout(prog)
        row.addWidget(mid, 4)

        # --- Right: views and volume ---------------------------------------
        right = QWidget()
        right.setMinimumWidth(180)
        rh = QHBoxLayout(right)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(4)
        rh.addStretch()
        self.nowplaying_btn = self._icon_button("Now playing view", lambda: self.toggle_right_panel("nowplaying"))
        rh.addWidget(self.nowplaying_btn)
        self.queue_btn = self._icon_button("Queue", lambda: self.toggle_right_panel("queue"))
        rh.addWidget(self.queue_btn)
        self.mute_btn = self._icon_button("Mute / unmute", self.toggle_mute)
        rh.addWidget(self.mute_btn)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(96)
        self.volume_slider.setToolTip("Volume (Ctrl+Up / Ctrl+Down)")
        self.volume_slider.setStyleSheet(SLIDER_STYLE)
        self.volume_slider.setValue(self.user_data.volume)
        self.volume_slider.valueChanged.connect(self.set_volume)
        rh.addWidget(self.volume_slider)
        row.addWidget(right, 3)

        self._update_mode_buttons()
        self._set_play_icon(False)
        self._update_mute_icon()
        self._apply_volume()
        self.main_layout.addWidget(self.player_bar)

    def _set_play_icon(self, playing: bool):
        """Round white button with a black play or pause symbol."""
        self.play_btn.setIcon(icons.pause("#000000", 14) if playing else icons.play("#000000", 14))
        self.play_btn.setToolTip("Pause (Space)" if playing else "Play (Space)")
        self.play_btn.setProperty("state", "pause" if playing else "play")

    def _set_now_playing_text(self, title, artist, note=""):
        self.song_info.setText(self.song_info.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, 260))
        self.song_info.setToolTip(title)
        self.artist_info.setText(artist + (f"  ·  {note}" if note else ""))

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
        level = 0 if (self.user_data.muted or v == 0) else (1 if v < 50 else 2)
        self.mute_btn.setIcon(icons.volume(level, theme.SUBDUED))
        self.mute_btn.setProperty("level", ("muted", "low", "high")[level])
        self.mute_btn.setToolTip("Unmute" if level == 0 else "Mute")

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
        self.album_cover.setPixmap(rounded(load_pixmap(path), 56, 4))

    # ==================================================================
    # Pages
    # ==================================================================
    def _gradient_header(self, pixmap, kind, title, top_colour, play_slot, extra_buttons=()):
        """Spotify-style page header: big artwork, kind, huge title, meta line,
        green play button and pill buttons, over a colour gradient."""
        frame = QFrame()
        frame.setObjectName("gradHeader")
        frame.setStyleSheet(
            f"#gradHeader {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {top_colour},"
            f" stop:0.75 {QColor(top_colour).darker(260).name()}, stop:1 {theme.PANEL});"
            f" border-top-left-radius: {theme.RADIUS}px; border-top-right-radius: {theme.RADIUS}px; }}")
        hv = QVBoxLayout(frame)
        hv.setContentsMargins(24, 24, 24, 12)
        hv.setSpacing(18)
        row = QHBoxLayout()
        row.setSpacing(24)
        art = QLabel()
        art.setFixedSize(200, 200)
        art.setStyleSheet("background: transparent;")
        art.setPixmap(rounded(pixmap, 200, 6))
        row.addWidget(art)
        info = QVBoxLayout()
        info.addStretch()
        k = QLabel(kind)
        k.setStyleSheet("color: white; font-size: 14px; font-weight: 600; background: transparent;")
        t = QLabel(title)
        t.setStyleSheet("color: white; font-size: 56px; font-weight: 800; background: transparent;")
        meta = QLabel("")
        meta.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 14px; font-weight: 600; background: transparent;")
        meta.setWordWrap(True)
        for w in (k, t, meta):
            info.addWidget(w)
        row.addLayout(info, 1)
        hv.addLayout(row)
        actions = QHBoxLayout()
        actions.setSpacing(16)
        play = QPushButton()
        play.setIcon(icons.play("#000000", 22))
        play.setIconSize(QSize(22, 22))
        play.setFixedSize(56, 56)
        play.setToolTip("Play")
        play.setCursor(Qt.CursorShape.PointingHandCursor)
        play.setStyleSheet(f"QPushButton {{ border: none; background: {theme.GREEN}; border-radius: 28px; }}"
                           "QPushButton:hover { background: #3be477; }")
        play.clicked.connect(play_slot)
        actions.addWidget(play)
        for text, slot, green in extra_buttons:
            b = QPushButton(text)
            b.setStyleSheet(theme.GREEN_PILL if green else theme.PILL)
            b.setFixedHeight(36 if green else 32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            actions.addWidget(b)
        actions.addStretch()
        hv.addLayout(actions)
        return frame, meta

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
        layout = QVBoxLayout(self.home_page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.home_scroll = QScrollArea()
        self.home_scroll.setWidgetResizable(True)
        self.home_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.home_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.home_scroll.installEventFilter(self)
        layout.addWidget(self.home_scroll)
        self._home_shelves = []
        self._home_refresh_timer = QTimer(self)
        self._home_refresh_timer.setSingleShot(True)
        self._home_refresh_timer.timeout.connect(self.refresh_home)
        loading = self._muted_label("Loading your music…")
        loading.setContentsMargins(24, 24, 24, 24)
        self.home_scroll.setWidget(loading)

    @staticmethod
    def _greeting():
        import datetime
        h = datetime.datetime.now().hour
        return "Good morning" if h < 12 else ("Good afternoon" if h < 18 else "Good evening")

    def schedule_home_refresh(self):
        self._home_refresh_timer.start(300)

    def refresh_home(self):
        content = QWidget()
        content.setObjectName("homeContent")
        # Soft gradient at the top, like Spotify's Home.
        content.setStyleSheet("#homeContent { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                              " stop:0 #1f2a26, stop:0.28 #121212, stop:1 #121212); }")
        v = QVBoxLayout(content)
        v.setContentsMargins(24, 20, 24, 24)
        v.setSpacing(8)
        self._home_shelves = []
        self._home_tiles = []

        hello = QLabel(self._greeting())
        hello.setStyleSheet(f"color: {theme.TEXT}; font-size: 32px; font-weight: 800; background: transparent;")
        v.addWidget(hello)
        v.addSpacing(8)

        if not self.songs:
            folders = "\n".join(self.user_data.music_folders) or "(none)"
            v.addWidget(self._muted_label(
                "No music found yet.\n\nAdd .mp3, .wav, .flac, .ogg or .m4a files to one of your music folders, "
                f"or open Your Songs in Your Library and add a folder.\n\nMusic folders:\n{folders}"))
            v.addStretch()
            self.home_scroll.setWidget(content)
            return

        # Quick tiles: Your Songs, Saved for later, playlists.
        quick = QGridLayout()
        quick.setSpacing(8)
        tiles = [(self.library_panel._special_songs, "Your Songs", self.show_library,
                  lambda: self.play_song(self.songs[0], queue=self.songs, source="Your Songs"), "Your Songs")]
        if self.user_data.save_for_later:
            tiles.append((self.library_panel._special_saved, "Saved for later", self.show_saved,
                          lambda: self._play_saved(sorted(self.user_data.save_for_later)[0]), "Saved:"))
        for pl in self.playlists[:8 - len(tiles)]:
            tiles.append((cover_thumb(pl.cover_path, 64), pl.name, lambda p=pl: self.show_playlist(p),
                          lambda p=pl: self.play_playlist(p), pl.name))
        playing = self.pq.source_name if self.current_song is not None else ""
        for i, (pm, name, open_fn, play_fn, src) in enumerate(tiles):
            t = QuickTile(pm, name, playing=bool(playing) and (playing == src or playing.startswith(src)))
            t.clicked.connect(open_fn)
            t.play_clicked.connect(play_fn)
            quick.addWidget(t, i // 4, i % 4)
        self._home_quick = quick
        v.addLayout(quick)

        def shelf(title, cards, all_rows=False):
            if not cards:
                return
            v.addSpacing(18)
            head = QLabel(title)
            head.setStyleSheet(f"color: {theme.TEXT}; font-size: 22px; font-weight: 700; background: transparent;")
            v.addWidget(head)
            grid = QGridLayout()
            grid.setHorizontalSpacing(4)
            grid.setVerticalSpacing(4)
            grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            v.addLayout(grid)
            self._home_shelves.append({"grid": grid, "cards": cards, "all": all_rows, "cols": 0})

        recent = [s for s in list(self.pq.recent)[:20] if not getattr(s, "is_remote", False)]
        rc = []
        for song in recent:
            c = Card(cover_thumb(song.album_cover_path, 160), song.title, song.artist)
            c.clicked.connect(lambda s=song: self.play_song(s, queue=recent, source="Recently played"))
            c.play_clicked.connect(lambda s=song: self.play_song(s, queue=recent, source="Recently played"))
            c.context_requested.connect(lambda pos, s=song: self._show_song_menu(s, pos, queue=recent, source="Recently played"))
            rc.append(c)
        shelf("Recently played", rc)

        pc = []
        for pl in self.playlists:
            n = len(pl.songs)
            c = Card(cover_thumb(pl.cover_path, 160), pl.name, f"Playlist • {n} song{'s' if n != 1 else ''}")
            c.clicked.connect(lambda p=pl: self.show_playlist(p))
            c.play_clicked.connect(lambda p=pl: self.play_playlist(p))
            c.context_requested.connect(lambda pos, p=pl: self._playlist_context_menu(p, pos))
            pc.append(c)
        shelf("Your playlists", pc)

        sc = []
        for song in self.songs[:HOME_SONGS_LIMIT]:
            c = Card(cover_thumb(song.album_cover_path, 160), song.title, song.artist)
            c.clicked.connect(lambda s=song: self.play_song(s, queue=self.songs, source="Your Songs"))
            c.play_clicked.connect(lambda s=song: self.play_song(s, queue=self.songs, source="Your Songs"))
            c.context_requested.connect(lambda pos, s=song: self._show_song_menu(s, pos, queue=self.songs, source="Your Songs"))
            sc.append(c)
        self._home_tiles = sc
        shelf("Your songs", sc, all_rows=True)
        if len(self.songs) > HOME_SONGS_LIMIT:
            more = QPushButton(f"Show all {len(self.songs)} songs")
            more.setStyleSheet(theme.PILL)
            more.setFixedHeight(32)
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            more.clicked.connect(self.show_library)
            v.addWidget(more, alignment=Qt.AlignmentFlag.AlignLeft)
        v.addStretch()
        self.home_scroll.setWidget(content)
        self._relayout_home()

    def _relayout_home(self):
        """Fit as many card columns as the width allows. Shelves show one row;
        'Your songs' shows everything."""
        width = self.home_scroll.viewport().width() - 48
        card_w = 184 + 4
        cols = max(1, width // card_w)
        quick = getattr(self, "_home_quick", None)
        if quick is not None:
            qcols = 4 if width >= 900 else 2
            items = [quick.itemAt(i).widget() for i in range(quick.count())]
            for w in items:
                quick.removeWidget(w)
            for i, w in enumerate(items):
                quick.addWidget(w, i // qcols, i % qcols)
        for sh in getattr(self, "_home_shelves", []):
            if sh["cols"] == cols:
                continue
            sh["cols"] = cols
            grid = sh["grid"]
            for c in sh["cards"]:
                grid.removeWidget(c)
            for i, c in enumerate(sh["cards"]):
                if not sh["all"] and i >= cols:
                    c.hide()
                    continue
                c.show()
                grid.addWidget(c, i // cols, i % cols)

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

        # The search box itself is the pill in the top bar.
        self.search_input = self.top_bar.search_edit
        self.search_input.textChanged.connect(self.refresh_search_results)

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
        self.web_table.mark_pending = True      # songs you don't have: greyed with ⬇ (online or offline)
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
            # Songs already listed under "In your library" aren't repeated; any other song you own
            # comes first, then the ones you'd still need to download.
            shown = {s.key for s in self.search_table.songs_in_view()}
            items = [s for s in items if s.key not in shown]
            items.sort(key=lambda s: getattr(s, "is_remote", False))
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.library_page.setLayout(layout)

        from .library_panel import gradient_cover
        header, self.library_count_label = self._gradient_header(
            gradient_cover(200, "#450af5", "#c4efd9", "♪"), "Library", "Your Songs", "#5038a0",
            lambda: self.songs and self.play_song(self.library_table.songs_in_view()[0],
                                                   queue=self.library_table.songs_in_view(), source="Your Library"),
            extra_buttons=(("Add folder…", self._choose_music_folder, False),
                           ("Rescan", self.rescan_library, False)))
        self.library_count_label.setText("Scanning your music…")
        layout.addWidget(header)

        self.folder_list_widget = QWidget()
        self.folder_list_layout = QVBoxLayout()
        self.folder_list_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_list_layout.setSpacing(2)
        self.folder_list_widget.setLayout(self.folder_list_layout)
        self.folder_list_widget.setContentsMargins(24, 0, 24, 0)
        layout.addWidget(self.folder_list_widget)
        self.refresh_folder_list()

        self.library_table = TrackTable(sortable=True)
        self.library_table.play_requested.connect(lambda s, view: self.play_song(s, queue=view, source="Your Library"))
        self.library_table.context_requested.connect(
            lambda s, row, pos: self._show_song_menu(s, pos, queue=self.library_table.songs_in_view(), source="Your Library"))
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(16, 0, 16, 8)
        wl.addWidget(self.library_table)
        layout.addWidget(wrap, 1)

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
            f"{n} song{'s' if n != 1 else ''}, {format_total(total)}  ·  click a column to sort  ·  double-click to play"
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

    def _refresh_library_panel(self):
        if not hasattr(self, "library_panel"):
            return
        n_saved = len(self.songs_to_download())
        playing = self.pq.source_name if self.current_song is not None else ""
        self.library_panel.set_items(self.playlists, len(self.songs), n_saved, playing)

    def _playlist_context_menu(self, playlist, global_pos):
        menu = self._new_menu()
        menu.addAction("▶  Play").triggered.connect(lambda: self.play_playlist(playlist))
        menu.addAction("Open").triggered.connect(lambda: self.show_playlist(playlist))
        menu.addSeparator()
        menu.addAction("Rename…").triggered.connect(lambda: self._rename_playlist_dialog(playlist))
        menu.addAction("Delete…").triggered.connect(lambda: self._confirm_delete_playlist(playlist))
        menu.exec(global_pos)

    def display_playlists(self):
        self._refresh_library_panel()
        if self.library_ready:
            self.schedule_home_refresh()
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

    # --- Saved for later --------------------------------------------------
    def setup_saved_page(self):
        layout = QVBoxLayout(self.saved_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        from .library_panel import gradient_cover
        header, meta = self._gradient_header(
            gradient_cover(200, "#1ed760", "#0b5c33", "⬇"), "To download", "Saved for later", "#137a43",
            lambda: self.user_data.save_for_later and self._play_saved(sorted(self.user_data.save_for_later)[0]))
        meta.setText("Everything waiting to be downloaded: the ⬇ songs in your playlists, plus songs you saved "
                     "from Radio or Search (sorted by genre). When a song arrives it leaves this list and fills "
                     "its place in every playlist it was added to.")
        layout.addWidget(header)
        self.saved_scroll = QScrollArea()
        self.saved_scroll.setWidgetResizable(True)
        self.saved_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.saved_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.saved_scroll.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(self.saved_scroll, 1)
        self.refresh_saved_page()

    def saved_songs(self, genre):
        return [RemoteSong(OnlineTrack.from_dict(d)) for d in self.user_data.save_for_later.get(genre, [])]

    def refresh_saved_page(self):
        self._refresh_library_panel()
        content = QWidget()
        content.setObjectName("savedContent")
        content.setStyleSheet("#savedContent { background: transparent; }")
        v = QVBoxLayout(content)
        v.setContentsMargins(24, 0, 24, 12)
        v.setSpacing(6)
        genres = sorted(self.user_data.save_for_later, key=str.casefold)
        in_playlists = self.playlist_songs_to_download()
        everything = self.songs_to_download()
        if everything:
            top = QHBoxLayout()
            top.addWidget(self._muted_label(
                f"{len(everything)} song{'s' if len(everything) != 1 else ''} to download. Each one fills its "
                "place in its playlist when it arrives."), 1)
            all_btn = QPushButton(f"⬇ Download all {len(everything)}" if len(everything) > 1 else "⬇ Download")
            all_btn.setStyleSheet(GREEN_BUTTON)
            all_btn.setFixedHeight(36)
            all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            all_btn.clicked.connect(lambda: self.download_songs(self.songs_to_download()))
            top.addWidget(all_btn)
            v.addLayout(top)
        if not genres and not in_playlists:
            v.addWidget(self._muted_label("Nothing to download. Songs you add to a playlist from Radio or web "
                                          "search, or save with “Save for later”, show up here."))
        all_remote = []
        if in_playlists:
            head = QHBoxLayout()
            head.addWidget(self._section_label(f"In your playlists  ·  {len(in_playlists)}"))
            head.addStretch()
            v.addLayout(head)
            table = TrackTable(sortable=False)
            table.mark_pending = True
            table.download_state = self.downloads.state
            table.set_songs(in_playlists)
            table.setFixedHeight(36 + len(in_playlists) * table.verticalHeader().defaultSectionSize() + 4)
            table.play_requested.connect(lambda s, view: self.play_song(s, queue=view, source="To download"))
            table.context_requested.connect(
                lambda s, row, pos, t=table: self._show_song_menu(s, pos, queue=t.songs_in_view(),
                                                                   source="To download"))
            v.addWidget(table)
            all_remote += in_playlists
        for genre in genres:
            songs = self.saved_songs(genre)
            all_remote += songs
            head = QHBoxLayout()
            lbl = self._section_label(f"{genre}  ·  {len(songs)}")
            head.addWidget(lbl)
            head.addStretch()
            for text, slot in (("▶ Play", lambda _=False, g=genre: self._play_saved(g)),
                               ("⬇ Download all", lambda _=False, g=genre: self.download_songs(self.saved_songs(g))),
                               ("➕ Add all to playlist…", lambda _=False, g=genre: self._add_saved_to_playlist(g)),
                               ("Export…", lambda _=False, g=genre: self.export_song_list(self.saved_songs(g), g))):
                b = QPushButton(text)
                b.setStyleSheet(PILL_BUTTON)
                b.setFixedHeight(32)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(slot)
                head.addWidget(b)
            v.addLayout(head)
            table = TrackTable(sortable=False)
            table.mark_pending = True
            table.download_state = self.downloads.state
            table.set_songs(songs)
            table.setFixedHeight(36 + len(songs) * table.verticalHeader().defaultSectionSize() + 4)
            table.play_requested.connect(lambda s, view, g=genre: self.play_song(s, queue=view, source=f"Saved: {g}"))
            table.context_requested.connect(
                lambda s, row, pos, t=table, g=genre: self._show_song_menu(
                    s, pos, queue=t.songs_in_view(), source=f"Saved: {g}", saved_genre=g, saved_index=row))
            v.addWidget(table)
        v.addStretch()
        self.saved_scroll.setWidget(content)
        self.fetch_covers(all_remote)

    def save_for_later(self, song):
        if not getattr(song, "is_remote", False):
            self.show_status("That song is already in your library.", kind="info", timeout_ms=3000)
            return
        track = song.track
        if not hasattr(self, "_saving_keys"):
            self._saving_keys = set()          # saves still waiting for their genre lookup
        already = track.key in self._saving_keys or any(
            OnlineTrack.from_dict(d).key == track.key for items in self.user_data.save_for_later.values() for d in items)
        if already:
            self.show_status(f"\"{song.title}\" is already saved for later.", kind="info", timeout_ms=3000)
            return
        self._saving_keys.add(track.key)

        def add(genre):
            self._saving_keys.discard(track.key)
            genre = (genre or "Other").strip() or "Other"
            track.genre = genre
            self.user_data.save_for_later.setdefault(genre, []).append(track.to_dict())
            self.save_now()
            self.refresh_saved_page()
            self.show_status(f"⬇ Saved for later · {genre}: {song.title}", kind="info", timeout_ms=4000)

        self.online_call(self.online.genre_of, track, on_done=add, on_error=lambda _e: add(track.genre or "Other"))

    def remove_saved(self, genre, index):
        items = self.user_data.save_for_later.get(genre, [])
        if 0 <= index < len(items):
            del items[index]
            if not items:
                del self.user_data.save_for_later[genre]
            self.save_now()
            self.refresh_saved_page()

    def _play_saved(self, genre):
        songs = self.saved_songs(genre)
        if songs:
            self.play_song(songs[0], queue=songs, source=f"Saved: {genre}")

    def _add_saved_to_playlist(self, genre):
        songs = self.saved_songs(genre)
        if not songs:
            return
        new_label = "New playlist…"
        names = [new_label] + [p.name for p in self.playlists]
        choice, ok = QInputDialog.getItem(self, "Add to playlist",
                                          f"Add {len(songs)} {genre} songs to:", names, 0, False)
        if not ok:
            return
        if choice == new_label:
            name, ok = QInputDialog.getText(self, "New playlist", "Playlist name:", text=genre)
            if ok:
                self.create_playlist(name, songs)
        else:
            pl = next(p for p in self.playlists if p.name == choice)
            self.add_to_playlist(pl, songs)

    def export_song_list(self, songs, name="songs"):
        """Save a list as .txt ("Artist - Title" per line) or .m3u playlist."""
        default = os.path.join(os.path.expanduser("~"), sanitize_filename(name) + ".txt")
        path, chosen = QFileDialog.getSaveFileName(self, "Export list", default,
                                                   "Text list (*.txt);;M3U playlist (*.m3u)")
        if not path:
            return None
        return self.write_song_list(songs, path, m3u=path.lower().endswith(".m3u") or "m3u" in chosen.lower())

    @staticmethod
    def write_song_list(songs, path, m3u=False):
        lines = ["#EXTM3U"] if m3u else []
        for s in songs:
            if m3u:
                lines.append(f"#EXTINF:{int(s.duration / 1000) if s.duration else -1},{s.artist} - {s.title}")
                lines.append(s.file_path if s.file_path else f"# not downloaded yet: {s.artist} - {s.title}")
            else:
                lines.append(f"{s.artist} - {s.title}")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        return path

    # --- Single playlist page --------------------------------------------
    def setup_playlist_page(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.playlist_page.setLayout(layout)

        # Header with a colour gradient taken from the cover (set in refresh_playlist_page).
        self.pl_header = QFrame()
        self.pl_header.setObjectName("plHeader")
        hv = QVBoxLayout(self.pl_header)
        hv.setContentsMargins(24, 24, 24, 12)
        hv.setSpacing(18)
        header = QHBoxLayout()
        header.setSpacing(24)
        self.pl_cover = QLabel()
        self.pl_cover.setFixedSize(220, 220)
        self.pl_cover.setStyleSheet("background: transparent;")
        header.addWidget(self.pl_cover)

        info = QVBoxLayout()
        info.addStretch()
        kind = QLabel("Playlist")
        kind.setStyleSheet("color: white; font-size: 14px; font-weight: 600; background: transparent;")
        info.addWidget(kind)
        self.pl_title = QLabel()
        self.pl_title.setStyleSheet("color: white; font-size: 56px; font-weight: 800; background: transparent;")
        self.pl_title.setMinimumWidth(0)
        self.pl_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info.addWidget(self.pl_title)
        self.pl_meta = QLabel()
        self.pl_meta.setStyleSheet("color: rgba(255,255,255,0.75); font-size: 14px; font-weight: 600; background: transparent;")
        info.addWidget(self.pl_meta)
        header.addLayout(info, 1)
        hv.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(16)
        self.pl_play_btn = QPushButton()
        self.pl_play_btn.setIcon(icons.play("#000000", 22))
        self.pl_play_btn.setIconSize(QSize(22, 22))
        self.pl_play_btn.setFixedSize(56, 56)
        self.pl_play_btn.setStyleSheet(f"QPushButton {{ border: none; background: {theme.GREEN}; border-radius: 28px; }}"
                                       "QPushButton:hover { background: #3be477; }")
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
        self.pl_download_btn = QPushButton("⬇ Download")
        self.pl_download_btn.setStyleSheet(PILL_BUTTON)
        self.pl_download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pl_download_btn.setFixedHeight(32)
        self.pl_download_btn.setToolTip("Download every song in this playlist that isn't on your computer yet")
        self.pl_download_btn.clicked.connect(
            lambda: self.open_playlist and self.download_songs(self.open_playlist.songs))
        self.pl_download_btn.hide()
        actions.addWidget(self.pl_download_btn)
        actions.addStretch()
        hv.addLayout(actions)
        layout.addWidget(self.pl_header)

        self.pl_empty = self._muted_label(
            "This playlist is empty. Right-click any song on Home, Search or Your Library and choose "
            "“Add to playlist”.")
        self.pl_empty.setContentsMargins(24, 12, 24, 0)
        layout.addWidget(self.pl_empty)

        self.pl_table = TrackTable(sortable=False)
        self.pl_table.mark_pending = True
        self.pl_table.play_requested.connect(
            lambda s, view: self.open_playlist and self.play_song(s, queue=self.open_playlist.songs,
                                                                  source=self.open_playlist.name))
        self.pl_table.context_requested.connect(
            lambda s, row, pos: self.open_playlist and self._show_song_menu(
                s, pos, queue=self.open_playlist.songs, playlist=self.open_playlist, row=row,
                source=self.open_playlist.name))
        table_wrap = QWidget()
        tw = QVBoxLayout(table_wrap)
        tw.setContentsMargins(16, 0, 16, 8)
        tw.addWidget(self.pl_table)
        layout.addWidget(table_wrap, 1)

    def show_playlist(self, playlist):
        self.open_playlist = playlist
        self.refresh_playlist_page()
        self.stack.setCurrentWidget(self.playlist_page)
        self._set_nav("playlist", playlist)

    def refresh_playlist_page(self):
        pl = self.open_playlist
        if pl is None:
            return
        cover = load_pixmap(pl.cover_path)
        self.pl_cover.setPixmap(rounded(cover, 220, 6))
        c = dominant_colour(cover)
        top = QColor.fromHsv(c.hsvHue(), min(255, c.hsvSaturation() + 30), min(200, c.value() + 50))
        self.pl_header.setStyleSheet(
            f"#plHeader {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {top.name()},"
            f" stop:0.7 {c.darker(160).name()}, stop:1 {theme.PANEL}); border-top-left-radius: {theme.RADIUS}px;"
            f" border-top-right-radius: {theme.RADIUS}px; }}")
        self.pl_title.setText(pl.name)
        n = len(pl.songs)
        pending = sum(1 for s in pl.songs if getattr(s, "is_remote", False))
        missing = sum(1 for s in pl.songs if not s.exists and not getattr(s, "is_remote", False))
        meta = f"{n} song{'s' if n != 1 else ''}, {format_total(pl.total_duration)}"
        if pending:
            meta += (f" · ⬇ {pending} not downloaded yet (download to play offline)" if pending == 1 else
                     f" · ⬇ {pending} not downloaded yet (download them to play offline)")
        if missing:
            meta += f" · {missing} missing"
        self.pl_meta.setText(meta)
        self._update_playlist_download_button()
        self.pl_table.set_songs(pl.songs)
        self.pl_table.set_current(self.current_song)
        self.fetch_covers([s for s in pl.songs if getattr(s, "is_remote", False)])
        self.pl_table.setVisible(bool(pl.songs))
        self.pl_title.setText(pl.name)
        self.pl_empty.setVisible(not pl.songs)

    def _rename_playlist_dialog(self, pl):
        name, ok = QInputDialog.getText(self, "Rename playlist", "New name:", text=pl.name)
        if ok:
            self.rename_playlist(pl, name)

    def _confirm_delete_playlist(self, pl):
        answer = QMessageBox.question(
            self, "Delete playlist", f"Delete \"{pl.name}\"?\n\nYour music files are not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_playlist(pl)

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
        self._refresh_library_panel()
        self.schedule_save(3000)

        # Show what we are trying to play straight away.
        self._set_now_playing_text(song.title, song.artist)
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
                self._set_now_playing_text(song.title, song.artist, "30-second preview")
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
        self._set_play_icon(True)
        # Note: any "Skipped …" message is left visible; it clears on its own timer.

    def _refresh_now_playing(self):
        for table in (self.library_table, self.search_table, self.pl_table):
            table.set_current(self.current_song)

    def _handle_failed_track(self, reason: str):
        song = self.current_song
        name = song.title if song else "Track"
        self.is_playing = False
        self._set_play_icon(False)
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
            self._set_play_icon(False)
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
                self._set_play_icon(False)
                self.is_playing = False
                self.now_playing_panel.set_playing(False)
            elif state == vlc.State.Paused:
                self.player.set_pause(0)
                self._set_play_icon(True)
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
        b.setFixedSize(32, 32)
        b.setIconSize(QSize(18, 18))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet("QPushButton { border: none; background: transparent; border-radius: 16px; }"
                        "QPushButton:hover { background: rgba(255,255,255,0.08); }")
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
    # "Not downloaded yet" slots + watching music folders
    # ------------------------------------------------------------------
    FRESH_FILE_SECONDS = 8   # a file this new may still be being written

    def _fill_pending_slots(self):
        """Replace online placeholders with your own files once they exist.
        Each song keeps its exact position (e.g. #18 stays #18). Returns titles filled."""
        import time as _time
        index = build_match_index(self.songs)
        filled, too_new = [], False

        def local_for(song):
            nonlocal too_new
            if not getattr(song, "is_remote", False):
                return None
            saved = self._downloaded_paths.get(song.track.key)
            if saved:
                # Downloaded by Sevbify: the file is complete, and its name/tags may use the official
                # spelling, so link it directly instead of matching by name.
                for s in self.songs:
                    if s.key == saved:
                        return s
            match = find_local_match(song.track, self.songs, index)
            if match is None:
                return None
            try:
                if _time.time() - os.path.getmtime(match.file_path) < self.FRESH_FILE_SECONDS:
                    too_new = True          # still downloading/copying: try again shortly
                    return None
            except OSError:
                return None
            return match

        for pl in self.playlists:
            changed = False
            for i, s in enumerate(pl.songs):
                m = local_for(s)
                if m is not None:
                    pl.songs[i] = m
                    filled.append(m.title)
                    changed = True
            if changed:
                pl.generate_cover()
        for seq in (self.pq.items, self.pq.original, self.pq.user_queue):
            for i, s in enumerate(seq):
                m = local_for(s)
                if m is not None:
                    seq[i] = m
        # Saved-for-later songs you now own leave the list (they're in your library).
        for genre in list(self.user_data.save_for_later):
            kept = []
            for d in self.user_data.save_for_later[genre]:
                m = find_local_match(OnlineTrack.from_dict(d), self.songs, index)
                if m is None:
                    kept.append(d)
                elif m.title not in filled:
                    filled.append(m.title)
            if kept:
                self.user_data.save_for_later[genre] = kept
            else:
                del self.user_data.save_for_later[genre]
        if too_new:
            QTimer.singleShot((self.FRESH_FILE_SECONDS + 4) * 1000, self.rescan_library)
        if filled and hasattr(self, "saved_page"):
            self.refresh_saved_page()
        return list(dict.fromkeys(filled))

    def _watch_music_folders(self):
        """Rescan automatically when files are added to a music folder."""
        if not hasattr(self, "_watcher"):
            self._watcher = QFileSystemWatcher(self)
            self._watch_timer = QTimer(self)
            self._watch_timer.setSingleShot(True)
            self._watch_timer.timeout.connect(self.rescan_library)
            self._watcher.directoryChanged.connect(lambda _p: self._watch_timer.start(3000))
        old = self._watcher.directories()
        if old:
            self._watcher.removePaths(old)
        dirs = []
        for root in self.user_data.music_folders:
            if not os.path.isdir(root):
                continue
            for d, subdirs, _files in os.walk(root):
                dirs.append(d)
                if len(dirs) >= 1500:     # plenty for normal libraries; avoids OS limits
                    break
            if len(dirs) >= 1500:
                break
        if dirs:
            self._watcher.addPaths(dirs)

    # ------------------------------------------------------------------
    # Downloading "not downloaded yet" songs (SEVBY engine, background)
    # ------------------------------------------------------------------
    DOWNLOAD_SUBFOLDER = "Sevbify downloads"

    def playlist_songs_to_download(self):
        """Not-downloaded songs in any playlist (each song once), in playlist order."""
        seen, out = set(), []
        for pl in self.playlists:
            for s in pl.songs:
                if getattr(s, "is_remote", False) and s.track.key not in seen:
                    seen.add(s.track.key)
                    out.append(s)
        return out

    def songs_to_download(self):
        """Everything waiting to be downloaded: playlist slots plus Saved for later (each song once)."""
        out = self.playlist_songs_to_download()
        seen = {s.track.key for s in out}
        for genre in sorted(self.user_data.save_for_later, key=str.casefold):
            for s in self.saved_songs(genre):
                if s.track.key not in seen:
                    seen.add(s.track.key)
                    out.append(s)
        return out

    def download_folder(self):
        """Downloads go into a "Sevbify downloads" folder inside the first music folder, so the
        library already scans them. Without any music folder, ~/Music/Sevbify downloads is added."""
        for f in self.user_data.music_folders:
            if os.path.isdir(f):
                return os.path.join(f, self.DOWNLOAD_SUBFOLDER)
        folder = os.path.join(os.path.expanduser("~"), "Music", self.DOWNLOAD_SUBFOLDER)
        os.makedirs(folder, exist_ok=True)
        self.add_music_folder(folder)
        return folder

    DOWNLOAD_NOTICE = (
        "Sevbify looks for each song on Bandcamp first, then on YouTube, and saves it as an MP3 in:\n"
        "{folder}\n\n"
        "Only download music you have the right to download, for example songs you have bought or that "
        "the artist offers for free. Downloading from YouTube goes against YouTube's terms of service; "
        "you decide whether to use it.\n\n"
        "Sevbify is not affiliated with YouTube, Bandcamp, Apple, Spotify, Deezer or Sevby LLC (sevby.com).\n\n"
        "Continue?")

    def download_songs(self, songs):
        """Queue the not-downloaded songs among `songs` for download. Returns how many were queued."""
        tracks = [s.track for s in songs if getattr(s, "is_remote", False)]
        if not tracks:
            self.show_status("Those songs are already on your computer.", kind="info", timeout_ms=3000)
            return 0
        folder = self.download_folder()
        if not self.user_data.download_notice_accepted:
            answer = QMessageBox.question(self, "Download songs", self.DOWNLOAD_NOTICE.format(folder=folder))
            if answer != QMessageBox.StandardButton.Yes:
                return 0
            self.user_data.download_notice_accepted = True
            self.schedule_save()
        added = self.downloads.request(tracks, folder, self.user_data.download_source)
        if added:
            self.show_status(f"⬇ Downloading {added} song{'s' if added != 1 else ''} in the background…",
                             kind="info", timeout_ms=4000)
        else:
            self.show_status("Already downloading.", kind="info", timeout_ms=3000)
        return added

    def _on_song_downloaded(self, key, path, title):
        if path:
            self._downloaded_paths[key] = normalise_path(path)
        self._download_rescan.start(400)

    def _on_downloads_finished(self, result):
        ok, failed = result["ok"], result["failed"]
        if result["stopped"]:
            text = f"Downloads stopped · {ok} finished"
        else:
            text = f"⬇ Downloads finished · {ok} downloaded"
        if failed:
            text += f" · {len(failed)} failed (click the ⬇ button at the top to retry)"
        self.show_status(text, kind="error" if failed else "info", timeout_ms=10000)
        self._refresh_download_views()

    def _refresh_download_views(self):
        d = self.downloads
        if d.is_busy():
            tip = (d.step_text or "Downloading") + "\nClick to stop."
            self.top_bar.set_downloads(d.summary(), tip)
        elif d.failed_count():
            n = d.failed_count()
            self.top_bar.set_downloads(f"⬇ {n} failed", "Click to retry the songs that failed", failed=True)
        else:
            self.top_bar.set_downloads("")
        if self.open_playlist is not None:
            self._update_playlist_download_button()
            self.pl_table.set_songs(self.open_playlist.songs)
            self.pl_table.set_current(self.current_song)
        if self.web_table.rowCount():
            self.web_table.set_songs(self.web_table.songs_in_view())
            self.web_table.set_current(self.current_song)
        if self.user_data.save_for_later and self.stack.currentWidget() is self.saved_page:
            self.refresh_saved_page()

    def _update_playlist_download_button(self):
        pl = self.open_playlist
        waiting = [s for s in (pl.songs if pl else []) if getattr(s, "is_remote", False)
                   and self.downloads.state(s.track.key)[0] not in ("queued", "downloading")]
        self.pl_download_btn.setText(f"⬇ Download {len(waiting)}" if len(waiting) > 1 else "⬇ Download")
        self.pl_download_btn.setVisible(bool(waiting))

    def _show_downloads_menu(self):
        menu = self._new_menu()
        d = self.downloads
        if d.is_busy():
            info = menu.addAction(d.summary())
            info.setEnabled(False)
            if d.step_text:
                step = menu.addAction(d.step_text)
                step.setEnabled(False)
            menu.addAction("■  Stop downloads").triggered.connect(d.stop)
        if d.failed_count():
            menu.addAction(f"↻  Retry {d.failed_count()} failed").triggered.connect(
                lambda: d.retry_failed(self.download_folder(), self.user_data.download_source))
        btn = self.top_bar.downloads_btn
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

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

    def save_queue_as_playlist(self):
        """Keep the current Radio (or any queue source) as a normal playlist. Songs you don't have yet
        stay as "not downloaded" slots and show up under To download."""
        songs = list(self.pq.original)
        if not songs:
            return None
        base = self.pq.source_name or "New playlist"
        name, n = base, 2
        while self._name_taken(name):
            name, n = f"{base} {n}", n + 1
        pl = self.create_playlist(name, songs)
        if pl is not None:
            pending = sum(1 for s in songs if getattr(s, "is_remote", False))
            self.show_status(f"Saved “{pl.name}”" + (f" · {pending} to download" if pending else ""),
                             kind="info", timeout_ms=5000)
        return pl

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
        self.pl_table.refresh_artwork()
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
        self.top_bar.set_online_state(state)

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
        if values.get("download_source") in downloader.SOURCES:
            self.user_data.download_source = values["download_source"]
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
            # Stop downloading (finished songs are kept) and let the worker end before VLC is released.
            self.downloads.stop()
            self.downloads.wait(10000)
            if hasattr(self, "_watcher"):
                self._watcher.removePaths(self._watcher.directories() or [])
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
    def _record_history(self, entry):
        if self._replaying:
            return
        if 0 <= self._history_pos < len(self._history) and self._history[self._history_pos] == entry:
            return
        del self._history[self._history_pos + 1:]
        self._history.append(entry)
        self._history = self._history[-50:]
        self._history_pos = len(self._history) - 1
        self.top_bar.set_history(self._history_pos > 0, False)

    def _replay(self, pos):
        if not (0 <= pos < len(self._history)):
            return
        self._history_pos = pos
        kind, arg = self._history[pos]
        self._replaying = True
        try:
            if kind == "playlist":
                if arg in self.playlists:
                    self.show_playlist(arg)
                else:
                    self.show_home()
            else:
                {"home": self.show_home, "search": lambda: self.show_search(select=False),
                 "library": self.show_library, "playlists": self.show_playlists,
                 "saved": self.show_saved}.get(kind, self.show_home)()
        finally:
            self._replaying = False
        self.top_bar.set_history(pos > 0, pos < len(self._history) - 1)

    def go_back(self):
        self._replay(self._history_pos - 1)

    def go_forward(self):
        self._replay(self._history_pos + 1)

    def _set_nav(self, kind, arg=None):
        self.top_bar.set_home_active(kind == "home")
        self.library_panel.set_active(arg if kind == "playlist" else kind)
        self._record_history((kind, arg))

    def show_home(self):
        self.stack.setCurrentWidget(self.home_page)
        self._set_nav("home")

    def show_search(self, select=True):
        self.stack.setCurrentWidget(self.search_page)
        self._set_nav("search")
        self.search_input.setFocus()
        if select:
            self.search_input.selectAll()

    def show_library(self):
        self.stack.setCurrentWidget(self.library_page)
        self._set_nav("library")

    def show_playlists(self):
        self.stack.setCurrentWidget(self.playlists_page)
        self._set_nav("playlists")

    def show_saved(self):
        self.refresh_saved_page()
        self.stack.setCurrentWidget(self.saved_page)
        self._set_nav("saved")

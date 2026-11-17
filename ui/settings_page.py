"""Settings, as a page in the middle like Spotify's (opened with ⚙ or Ctrl+P).

Every change is applied at once and saved (no Save button). A few need a restart (zoom, graphics, proxy,
mono audio); the page then shows "Restart to apply" with a button.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QScrollArea, QFrame, QSlider,
    QRadioButton, QButtonGroup, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal

from . import theme
from .widgets import ToggleSwitch, EqualizerCurve, ZoomPreview
from core.audio_settings import BAND_LABELS, band_labels

RESTART_KEYS = ("zoom", "mono", "proxy_mode", "proxy_url", "hw_accel", "language")
SOURCES = ("Bandcamp + YouTube", "Bandcamp only", "YouTube only")

STYLE = f"""
QLabel {{ color: {theme.TEXT}; background: transparent; }}
QLabel#h1 {{ font-size: 32px; font-weight: 700; color: white; padding-bottom: 8px; }}
QLabel#h2 {{ font-size: 16px; font-weight: 700; color: white; padding-top: 26px; padding-bottom: 4px;
    margin-left: -4px; }}
QLabel#name {{ font-size: 14px; color: #b3b3b3; }}
QLabel#desc {{ color: #a7a7a7; font-size: 12px; }}
QLineEdit {{ background: #2a2a2a; color: white; border: 1px solid transparent; border-radius: 4px; padding: 7px 10px;
    font-size: 14px; }}
QLineEdit:hover {{ border-color: #535353; }}
QLineEdit:focus {{ border-color: white; }}
QComboBox {{ background: #2a2a2a; color: white; border: 1px solid transparent; border-radius: 4px; padding: 7px 12px;
    font-size: 14px; min-width: 170px; }}
QComboBox:hover {{ border-color: #535353; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: #282828; color: white; border: none; padding: 4px; outline: none;
    selection-background-color: #3e3e3e; font-size: 14px; }}
QPushButton {{ color: white; background: transparent; border: 1px solid #727272; border-radius: 16px; padding: 0 16px;
    min-height: 30px; font-weight: 700; font-size: 14px; }}
QPushButton:hover {{ border-color: white; }}
QPushButton:pressed {{ border-color: #b3b3b3; color: #b3b3b3; }}
QRadioButton {{ color: {theme.SUBDUED}; font-size: 12px; spacing: 4px; }}
QRadioButton:checked {{ color: {theme.TEXT}; }}
QSlider::groove:vertical {{ background: #4d4d4d; width: 4px; border-radius: 2px; }}
QSlider::sub-page:vertical {{ background: #4d4d4d; border-radius: 2px; }}
QSlider::add-page:vertical {{ background: {theme.GREEN}; border-radius: 2px; }}
QSlider::handle:vertical {{ background: white; height: 12px; width: 12px; margin: 0 -4px; border-radius: 6px; }}
"""


def _vlc_band_labels():
    try:
        import vlc
        return band_labels(vlc)
    except Exception:
        return BAND_LABELS


class SettingsPage(QWidget):
    changed = pyqtSignal(dict)            # one or more settings changed (apply + save)
    add_folder_requested = pyqtSignal()
    remove_folder_requested = pyqtSignal(str)
    restart_requested = pyqtSignal()
    clear_cache_requested = pyqtSignal()
    open_folder_requested = pyqtSignal(str)
    shortcuts_requested = pyqtSignal()
    import_requested = pyqtSignal()
    tour_requested = pyqtSignal()
    pair_requested = pyqtSignal()
    phone_remove_requested = pyqtSignal(str)
    profile_export_requested = pyqtSignal()
    profile_import_requested = pyqtSignal()
    check_updates_requested = pyqtSignal()
    go_back_requested = pyqtSignal()
    clear_canvas_requested = pyqtSignal()
    hidden_changed = pyqtSignal(str, str, object)      # kind ("song" | "artist"), key, on (True / False / None = remove)
    update_ytdlp_requested = pyqtSignal()
    server_add_requested = pyqtSignal(str)          # "jellyfin" | "webdav"
    server_refresh_requested = pyqtSignal(str)      # server id
    server_remove_requested = pyqtSignal(str)       # server id
    reset_requested = pyqtSignal(str)          # "appearance" or "all"
    eq_preview = pyqtSignal(list)              # the equaliser while a dot is dragged: heard at once, saved on release

    def __init__(self, eq_presets=None, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.setStyleSheet(STYLE)
        self.eq_presets = eq_presets or {"Flat": [0.0] * 10}
        self.needs_restart = False
        self.controls = {}                 # setting name -> widget (used by tests)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(self.scroll)

    # --- building -----------------------------------------------------------------------------------
    def build(self, user_data, info):
        """(Re)build the page for the current settings. info: version, cache_size, download_size,
        download_folder, can_start_at_login, can_make_shortcuts, private_session."""
        self.u, self.info = user_data, info
        self.controls = {}
        body = QWidget()
        body.setObjectName("settingsBody")
        body.setStyleSheet("#settingsBody { background: transparent; }")
        centre = QHBoxLayout(body)
        centre.setContentsMargins(24, 24, 24, 40)
        column = QWidget()
        column.setMaximumWidth(860)                 # a centred column, like Spotify's settings
        # The column never grows wider than the page (a long folder path or version line used to push the
        # switches and boxes off the right-hand edge in a narrow window); text wraps instead.
        from PyQt6.QtWidgets import QSizePolicy
        column.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        column.setMinimumWidth(0)
        v = QVBoxLayout(column)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        centre.addStretch()
        centre.addWidget(column, 100)
        centre.addStretch()
        self._v = v
        u = user_data

        from core.i18n import tr
        h1 = QLabel(tr("Settings"))
        h1.setObjectName("h1")
        v.addWidget(h1)
        self.restart_bar = QFrame()
        self.restart_bar.setStyleSheet(f"QFrame {{ background: {theme.ELEVATED}; border-radius: 8px; }}")
        rb = QHBoxLayout(self.restart_bar)
        rb.setContentsMargins(14, 10, 14, 10)
        rb.addWidget(QLabel("Restart Sevbify to apply your changes."), 1)
        restart = QPushButton("Restart now")
        restart.clicked.connect(self.restart_requested.emit)
        rb.addWidget(restart)
        self.restart_bar.setVisible(self.needs_restart)
        v.addWidget(self.restart_bar)

        # Like Spotify's: the language comes first.
        from core import i18n
        self._section("Language")
        names = ["Same as this computer"] + [n for _c, n in i18n.LANGUAGES]
        current = dict(i18n.LANGUAGES).get(getattr(u, "language", ""), "Same as this computer")
        self._combo("language", "Choose language", "Changes apply after Sevbify restarts. Search works in every "
                    "language either way.", names, current)

        self._section("Online and privacy")
        self._toggle("online_enabled", "Online features",
                     "Search the web, song radio, artist info, full songs and downloads. When off, Sevbify never "
                     "connects to the internet; your own music always works.", u.online_enabled)
        self._toggle("explicit_ok", "Allow explicit content",
                     "When off, songs marked explicit are left out of web search results and radios.", u.explicit_ok)
        self._toggle("private_session", "Private session",
                     "Songs you play aren't added to Recently played until you turn this off or close Sevbify.",
                     info.get("private_session", False))
        self._toggle("use_browser_cookies", "Let YouTube downloads use my Chrome sign-in",
                     "Off by default. When on, a download YouTube blocks is retried with the YouTube sign-in saved "
                     "in Chrome, which tells YouTube who you are.", u.use_browser_cookies)
        self._text(
            "Sevbify has no account, ads or tracking and sells nothing. With online features on it contacts only: "
            "Deezer (search, radio, previews), Wikipedia (artist info), DuckDuckGo (only a finished search whose results look wrong, for “Did you mean”), Apple iTunes (official song names), Bandcamp "
            "and YouTube (full songs and downloads), Spotify, Apple Music or Deezer only when you import a playlist link, "
            "LRCLIB for lyrics (song name and length only), song.link only when you share a song, "
            "and Last.fm / Jamendo if you add a key below. Those sites see "
            "your IP address and what you look up, like a web browser would. Sevbify only looks at the music folders "
            "you add; it never searches the rest of your computer.")
        self._toggle("spotify_full", "Read whole Spotify playlists (over 100 songs)",
                     "Without signing in, Spotify only shares the first 100 songs of a playlist link. On: Sevbify reads the rest the way Spotify's own web player does, with the same anonymous access any visitor gets (no sign-in, nothing about you is sent, only the playlist's id). Spotify could notice or change this, so it's off by default; off, you can still paste copied songs or use Chosic.", getattr(u, "spotify_full", False))
        self._line_edit("lastfm_api_key", "Last.fm API key (optional)",
                        "Makes song radio closer to Spotify's. Free at last.fm/api/account/create.", u.lastfm_api_key,
                        "e.g. 0123456789abcdef0123456789abcdef")
        self._line_edit("jamendo_client_id", "Jamendo client ID (optional)",
                        "Free Creative Commons music from Jamendo. Free at devportal.jamendo.com.",
                        u.jamendo_client_id, "e.g. 1a2b3c4d")

        self._section("Music servers")
        self._text("Play music from your own Jellyfin or Nextcloud server. Sevbify talks only to the address you type; "
                   "Jellyfin keeps just a revocable sign-in token, and for Nextcloud use an app password. The sign-in "
                   "stays on this computer (never in playlists or your profile file).")
        for srv in info.get("servers", []):
            row = QHBoxLayout()
            row.addLayout(self._name_desc(srv.get("name", "Server"), srv.get("url", ""), into=row), 1)
            for text, sig in (("Reload songs", self.server_refresh_requested), ("Remove", self.server_remove_requested)):
                b = QPushButton(text)
                b.clicked.connect(lambda _=False, s=sig, i=srv["id"]: s.emit(i))
                row.addWidget(b)
            self._v.addLayout(row)
        add_row = QHBoxLayout()
        for text, kind in (("Add Jellyfin…", "jellyfin"), ("Add Nextcloud…", "webdav")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, k=kind: self.server_add_requested.emit(k))
            add_row.addWidget(b)
            self.controls["add_" + kind] = b
        add_row.addStretch()
        self._v.addLayout(add_row)

        self._section("Your phone")
        self._text("Pair Sevbify on your phone with this computer to send songs and folders either way. It only works "
                   "on your own Wi-Fi: nothing goes through the internet, everything is encrypted, and you say yes to "
                   "every transfer before anything is saved.")
        for ph in info.get("phones", []):
            row = QHBoxLayout()
            state = "Connected" if ph.get("connected") else "Not connected"
            row.addLayout(self._name_desc(ph.get("name", "Phone"), f"{ph.get('platform', '').title()} · {state}".strip(" ·"),
                                          into=row), 1)
            b = QPushButton("Remove")
            b.clicked.connect(lambda _=False, i=ph["id"]: self.phone_remove_requested.emit(i))
            row.addWidget(b)
            self._v.addLayout(row)
        pair_row = QHBoxLayout()
        pb = QPushButton("Pair a phone…")
        pb.setEnabled(bool(info.get("phones_available", False)))
        pb.clicked.connect(self.pair_requested.emit)
        self.controls["pair_phone"] = pb
        pair_row.addWidget(pb)
        pair_row.addStretch()
        self._v.addLayout(pair_row)
        self._toggle("phone_remote", "Let paired phones control music here",
                     "Your paired phone can play, pause, skip and change the volume here, and add songs to the queue "
                     "(Jam: everyone whose phone you've paired can add songs in the same room). Only on your Wi-Fi.",
                     getattr(u, "phone_remote", True))
        self._toggle("phone_link", "Let paired phones connect",
                     "When off, this computer doesn't listen for your phone.", getattr(u, "phone_link", True))

        self._section("Your Library")
        self._toggle("library_compact", "Use compact library layout", "", u.library_view == "compact")
        imp_row = QHBoxLayout()
        imp_row.addLayout(self._name_desc("Import music from other apps",
                                          "Spotify, Apple Music, Deezer or Jamendo playlist links, or files from Exportify (.csv), "
                                          ".txt and .m3u.", into=imp_row), 1)
        imp = QPushButton("Import playlist")
        imp.clicked.connect(self.import_requested.emit)
        imp_row.addWidget(imp)
        self._v.addLayout(imp_row)
        prof_row = QHBoxLayout()
        prof_row.addLayout(self._name_desc("Your Sevbify profile",
                                           "One small file with your playlists, folders, podcasts, audiobooks, where you "
                                           "stopped, recently played, recent searches and settings. Open it in Sevbify on "
                                           "any device (Windows, Mac, Linux, Android, iPhone). It stays where you save it; "
                                           "Sevbify never uploads it.", into=prof_row), 1)
        exp = QPushButton("Export…")
        exp.clicked.connect(self.profile_export_requested.emit)
        prof_row.addWidget(exp)
        imp2 = QPushButton("Import…")
        imp2.clicked.connect(self.profile_import_requested.emit)
        prof_row.addWidget(imp2)
        self._v.addLayout(prof_row)
        self._name_desc("Show songs from", "Folders on your computer that Sevbify plays music from. Switch one off to "
                        "hide its songs without removing it.")
        for folder in u.music_folders:
            row = QHBoxLayout()
            lbl = QLabel(folder)
            lbl.setObjectName("desc")
            lbl.setStyleSheet(f"color: {theme.TEXT}; font-size: 13px;")
            lbl.setWordWrap(True)
            row.addWidget(lbl, 1)
            remove = QPushButton("Remove")
            remove.setToolTip("Stop using this folder (your files are not deleted)")
            remove.clicked.connect(lambda _=False, f=folder: self.remove_folder_requested.emit(f))
            row.addWidget(remove)
            switch = ToggleSwitch(folder not in u.disabled_folders)
            switch.toggled.connect(lambda on, f=folder: self._folder_toggled(f, on))
            self.controls[f"folder:{folder}"] = switch
            row.addWidget(switch)
            v.addLayout(row)
        add = QPushButton("Add a folder")
        add.clicked.connect(self.add_folder_requested.emit)
        v.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)

        self._section("Downloads")
        self._combo("download_source", "Download and stream from", "Where full songs are looked for.",
                    list(SOURCES), u.download_source)
        from core import quality as Q
        self._combo("download_quality", "Download quality",
                    "A song can't be better than its source (YouTube ~128-160 kbps, Bandcamp 128 kbps), so the "
                    "original audio is both the best quality and the smallest full-quality file. "
                    + Q.SONG_QUALITIES[Q.song_quality(u.download_quality)][1],
                    [v[0] for v in Q.SONG_QUALITIES.values()], Q.SONG_QUALITIES[Q.song_quality(u.download_quality)][0])
        self._toggle("save_space", "Save space",
                     "Keep downloaded podcast episodes and audiobook chapters as small Opus files (about a third of the "
                     "size; speech sounds the same). Your own music is never changed.", getattr(u, "save_space", True))
        self._combo("audiobook_quality", "Audiobook quality", "LibriVox records every chapter at both; speech "
                    "sounds the same at 64 kbps.", list(Q.AUDIOBOOK_QUALITIES.values()),
                    Q.AUDIOBOOK_QUALITIES.get(u.audiobook_quality, Q.AUDIOBOOK_QUALITIES["standard"]))
        self._combo("video_quality", "Video podcast quality", "When watching a video podcast. Windows' video "
                    "player needs picture and sound in one stream, which YouTube may only offer up to 360p for some "
                    "videos; the best available up to your choice is used.", list(Q.VIDEO_QUALITIES.values()),
                    Q.VIDEO_QUALITIES.get(u.video_quality, Q.VIDEO_QUALITIES["auto"]))
        folder_row = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        name = QLabel("Download location")
        name.setObjectName("name")
        self.download_folder_label = QLabel(info.get("download_folder", "") or "Automatic")
        self.download_folder_label.setObjectName("desc")
        self.download_folder_label.setWordWrap(True)
        box.addWidget(name)
        box.addWidget(self.download_folder_label)
        folder_row.addLayout(box, 1)
        change = QPushButton("Change location")
        change.clicked.connect(self._choose_download_folder)
        folder_row.addWidget(change)
        if u.download_folder:
            auto = QPushButton("Automatic")
            auto.setToolTip("Use a “Sevbify downloads” folder in your first music folder")
            auto.clicked.connect(lambda: self._emit({"download_folder": ""}))
            folder_row.addWidget(auto)
        v.addLayout(folder_row)
        self._toggle("playlist_files", "Save playlist files for phones",
                     "Keeps .m3u8 playlists next to your downloads, in your order, so copying the folder to a phone "
                     "keeps your playlists.", u.playlist_files)

        self._toggle("show_playlist_origin", "Show where playlists came from",
                     "A coloured border around playlist pictures in Your Library: grey = made in Sevbify, blue = "
                     "imported from a file (.txt / .csv / .m3u), green = Spotify link, white = Apple Music link, "
                     "purple = Deezer link, orange = Jamendo link.",
                     getattr(u, "show_playlist_origin", False))

        self._section("Playback")
        self._toggle("lyrics_enabled", "Lyrics",
                     "Shows the Lyrics button next to the queue. Lyrics come from a .lrc or .txt file next to your song "
                     "(works offline), otherwise from LRCLIB, a free lyrics database (only the song's name and length "
                     "are sent).", getattr(u, "lyrics_enabled", True))
        self._toggle("skip_sponsors", "Skip sponsor segments in YouTube episodes",
                     "Jumps over ad reads, \"like and subscribe\" reminders and self-promotion that viewers marked on "
                     "SponsorBlock. Private: the episode isn't named, only a 4-character code shared by many videos is "
                     "sent. YouTube's own ads never play in Sevbify.", getattr(u, "skip_sponsors", True))
        self._toggle("ad_free_podcasts", "Ad-free podcasts",
                     "Plays an episode's YouTube version when the show posts one: no ads stitched in by podcast "
                     "networks. The hosts' own sponsor reads stay, like on the radio. Episodes with no YouTube version "
                     "play from the feed as usual.", getattr(u, "ad_free_podcasts", True))
        self._toggle("autoplay", "Autoplay",
                     "When your music ends, keep playing similar songs (song radio from the last one).", u.autoplay)
        self._combo("fade_seconds", "Fade between songs",
                    "Fades the end of each song out and the next one in.",
                    ["Off"] + [f"{n} seconds" for n in range(1, 13)], "Off" if not u.fade_seconds else
                    f"{u.fade_seconds} seconds")
        self._toggle("normalize", "Volume levelling", "Plays every song at a similar loudness (each song is "
                     "measured once on this computer).", u.normalize)
        self._toggle("smart_downloads", "Smart downloads", "Songs you keep playing (3 times in a month) are "
                     "downloaded for you, so they play offline too. At most 20 a day.", getattr(u, "smart_downloads", False))
        self._toggle("mono", "Mono audio", "The same sound in both ears. Applies after a restart. Left/right balance "
                     "is in your computer's sound settings.", getattr(u, "mono", False))
        self._toggle("eq_enabled", "Equalizer", "Drag the dots: up makes those sounds louder, down quieter.",
                     u.eq_enabled)
        self.controls["eq_enabled"].toggled.connect(lambda on: self.eq_curve.setEnabled(on))
        self._equalizer(u)

        self._section("Hidden songs and artists")
        entries = list(info.get("hidden") or [])
        if not entries:
            self._text("Nothing hidden. A song's ••• menu has Hide song and Don't play this artist: they're then "
                       "skipped in playlists, albums, radio and mixes, and come back here with one switch.")
        else:
            self._text("Switched on = skipped when music plays by itself (you can still pick it yourself). Switch "
                       "one off to let it play again, or remove it from the list.")
            for kind, e in entries[:300]:
                name = (f"{e['title']} · {e['artist']}" if kind == "song" else f"{e['artist']} (artist)")
                row = QHBoxLayout()
                row.setSpacing(12)
                lbl = QLabel(name)
                lbl.setTextFormat(Qt.TextFormat.PlainText)
                lbl.setObjectName("name")
                lbl.setWordWrap(True)
                row.addWidget(lbl, 1)
                switch = ToggleSwitch(bool(e.get("on", True)))
                switch.setToolTip("Hidden" if e.get("on", True) else "Plays again")
                switch.toggled.connect(lambda on, k=kind, key=e["key"]: self.hidden_changed.emit(k, key, on))
                row.addWidget(switch, 0, Qt.AlignmentFlag.AlignVCenter)
                rm = QPushButton("Remove")
                rm.setToolTip("Take it off this list (it plays again)")
                rm.clicked.connect(lambda _c=False, k=kind, key=e["key"]: self.hidden_changed.emit(k, key, None))
                row.addWidget(rm)
                self._v.addLayout(row)
                self.controls[f"hidden:{kind}:{e['key']}"] = switch

        self._section("Display")
        self._toggle("np_on_play", "Show the now-playing panel on click of play", "", u.np_on_play)
        self._toggle("notify_track", "Show desktop notifications when the song changes", "", u.notify_track)
        self._toggle("canvas_enabled", "Canvas", "Short looping videos in the Now Playing view, when a song has one "
                     "(also: a song's ••• menu → Hide Canvas / Show Canvas).", u.canvas_enabled)
        self._toggle("canvas_auto", "Canvas from music videos",
                     "When a song has an official music video on YouTube, a silent 8-second loop of it (at most 720p, "
                     "about 1 MB) becomes its Canvas. Found with the same YouTube search Sevbify uses for songs. Your own "
                     "Canvas videos always come first.", getattr(u, "canvas_auto", True))
        self._toggle("canvas_keep_downloads", "Keep Canvas with downloaded songs",
                     "A downloaded song keeps its loop next to it (in a \"canvas\" folder), so it loops offline too.",
                     getattr(u, "canvas_keep_downloads", True))
        mb = info.get("canvas_cache_mb", 0.0)
        self._combo("canvas_cache_mb", "Canvas storage limit",
                    f"Loops for songs you stream are kept up to this size; the ones played longest ago go first. "
                    f"Using {mb:.0f} MB now.", ["50 MB", "100 MB", "200 MB", "500 MB", "1000 MB"],
                    f"{getattr(u, 'canvas_cache_mb', 200)} MB")
        row = QHBoxLayout()
        clear = QPushButton("Clear Canvas storage")
        clear.clicked.connect(self.clear_canvas_requested.emit)
        row.addWidget(clear)
        row.addStretch()
        self._v.addLayout(row)
        self._zoom(u.zoom)

        self._section("Startup and window behaviour")
        self._combo("startup", "Open Sevbify automatically after you log into the computer", "",
                    ["No", "Yes", "Minimized"], {"no": "No", "yes": "Yes", "minimized": "Minimized"}[u.startup],
                    enabled=info.get("can_start_at_login", False),
                    disabled_note="Available in the ready-made Windows app.")
        self._toggle("close_to_tray", "Close button should minimize the Sevbify window",
                     "Sevbify keeps playing from the system tray; quit it from the tray icon or ••• → File → Exit.",
                     u.close_to_tray)

        self._section("Storage")
        self.download_size_label = self._value_row("Downloads", info.get("download_size", "…"),
                                                   "Open folder", lambda: self.open_folder_requested.emit("downloads"))
        self.cache_size_label = self._value_row("Cache", info.get("cache_size", "…"), "Clear cache",
                                                self.clear_cache_requested.emit,
                                                "Cover art, artist info and search results kept for speed and for "
                                                "offline use. They download again when needed.")
        self._toggle("portable", "Keep my data next to the app (portable)",
                     "Your playlists, settings and caches live in a \"Sevbify data\" folder next to Sevbify instead of "
                     "your user folder, e.g. to carry Sevbify on a USB stick. Your data is copied across and used from "
                     "the next start. Now in: " + info.get("data_folder", ""), info.get("portable", False))

        self._section("Proxy settings")
        self._combo("proxy_mode", "Proxy type", "Applies after a restart.",
                    ["Automatic (system settings)", "No proxy", "HTTP proxy"],
                    {"auto": "Automatic (system settings)", "none": "No proxy", "http": "HTTP proxy"}[u.proxy_mode])
        self._line_edit("proxy_url", "HTTP proxy address", "Only used with “HTTP proxy”, e.g. http://127.0.0.1:8080",
                        u.proxy_url, "http://host:port")

        self._section("Compatibility")
        self._toggle("hw_accel", "Enable hardware acceleration",
                     "Turn off if the window flickers or stays black. Applies after a restart.", u.hw_accel)

        self._section("About and updates")
        self._text(f"Sevbify {info.get('version', '')}. Built with AI help. Not affiliated with Spotify, YouTube, "
                   "Bandcamp, Apple, Deezer or Sevby LLC.")
        self._toggle("auto_update_check", "Check for updates automatically",
                     "Once a day, when online: tells you when a new Sevbify is out, and keeps yt-dlp (what finds and "
                     "downloads songs on YouTube) up to date with the official, checksum-checked release.",
                     getattr(u, "auto_update_check", True))
        row = QHBoxLayout()
        check = QPushButton("Check for Sevbify updates")
        check.clicked.connect(self.check_updates_requested.emit)
        row.addWidget(check)
        row.addStretch()
        v.addLayout(row)
        self.controls["check_updates"] = check
        tour = QPushButton("Feature tour")
        tour.setToolTip("Shows what Sevbify can do, with pictures")
        tour.clicked.connect(self.tour_requested.emit)
        row.insertWidget(1, tour)
        self.controls["feature_tour"] = tour
        if info.get("has_previous"):
            back = QPushButton("Go back to the previous version")
            back.setToolTip("Sevbify keeps the version before the last update. This switches back to it (and keeps "
                            "this one, so you can switch forward again).")
            back.clicked.connect(self.go_back_requested.emit)
            row.insertWidget(2, back)
            self.controls["go_back"] = back
        self.app_update_label = QLabel(info.get("app_update", ""))
        self.app_update_label.setObjectName("desc")
        self.app_update_label.setWordWrap(True)
        self.app_update_label.setOpenExternalLinks(False)
        from . import open_web
        self.app_update_label.linkActivated.connect(open_web)
        v.addWidget(self.app_update_label)
        age = info.get("ytdlp_age")
        self._text(f"yt-dlp {info.get('ytdlp', '')} finds and downloads full songs and video podcasts. YouTube "
                   "changes often: if songs stop playing or downloading, update it."
                   + (f" This copy is {age} days old." if age and age > 45 else ""))
        row2 = QHBoxLayout()
        upd = QPushButton("Update yt-dlp")
        upd.clicked.connect(self.update_ytdlp_requested.emit)
        row2.addWidget(upd)
        row2.addStretch()
        v.addLayout(row2)
        self.controls["update_ytdlp"] = upd
        self.ytdlp_label = QLabel(info.get("ytdlp_update", ""))
        self.ytdlp_label.setObjectName("desc")
        self.ytdlp_label.setWordWrap(True)
        v.addWidget(self.ytdlp_label)
        if info.get("can_make_shortcuts"):
            sc = QPushButton("Add to Desktop and Start menu")
            sc.clicked.connect(lambda: (self.shortcuts_requested.emit()))
            v.addWidget(sc, 0, Qt.AlignmentFlag.AlignLeft)
            self.controls["shortcuts"] = sc
        self._reset_section()
        v.addStretch()
        theme.replace_scroll_widget(self.scroll, body)

    def set_update_status(self, app=None, ytdlp=None):
        for label, text in ((getattr(self, "app_update_label", None), app), (getattr(self, "ytdlp_label", None), ytdlp)):
            if label is not None and text is not None:
                try:
                    label.setText(text)
                except RuntimeError:
                    pass

    # --- pieces -------------------------------------------------------------------------------------
    def _section(self, title):
        from core.i18n import tr
        lbl = QLabel(tr(title))
        lbl.setObjectName("h2")
        self._v.addWidget(lbl)

    def _text(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("desc")
        lbl.setWordWrap(True)
        self._v.addWidget(lbl)

    def _name_desc(self, name, desc, into=None):
        box = QVBoxLayout()
        box.setSpacing(2)
        n = QLabel(name)
        n.setObjectName("name")
        n.setWordWrap(True)
        box.addWidget(n)
        if desc:
            d = QLabel(desc)
            d.setObjectName("desc")
            d.setWordWrap(True)
            box.addWidget(d)
        if into is None:
            self._v.addLayout(box)
        return box

    def _row(self, key, name, desc, control):
        from core.i18n import tr
        name = tr(name)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addLayout(self._name_desc(name, desc, into=row), 1)
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        self._v.addLayout(row)
        self.controls[key] = control
        return control

    def _toggle(self, key, name, desc, value):
        switch = ToggleSwitch(bool(value))
        switch.toggled.connect(lambda on, k=key: self._emit({k: on}))
        return self._row(key, name, desc, switch)

    def _combo(self, key, name, desc, options, current, enabled=True, disabled_note=""):
        combo = QComboBox()
        combo.addItems(options)
        combo.setCurrentText(current)
        combo.setEnabled(enabled)
        if not enabled and disabled_note:
            desc = (desc + " " if desc else "") + disabled_note
        combo.currentTextChanged.connect(lambda text, k=key: self._combo_changed(k, text))
        return self._row(key, name, desc, combo)

    def _line_edit(self, key, name, desc, value, placeholder):
        edit = QLineEdit(value)
        edit.setPlaceholderText(placeholder)
        edit.setMinimumWidth(260)
        edit.editingFinished.connect(lambda k=key, e=edit: self._emit({k: e.text().strip()}))
        return self._row(key, name, desc, edit)

    def _value_row(self, name, value, button_text, slot, desc=""):
        row = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        n = QLabel(f"{name}: {value}")
        n.setObjectName("name")
        box.addWidget(n)
        if desc:
            d = QLabel(desc)
            d.setObjectName("desc")
            d.setWordWrap(True)
            box.addWidget(d)
        row.addLayout(box, 1)
        b = QPushButton(button_text)
        b.clicked.connect(slot)
        row.addWidget(b)
        self._v.addLayout(row)
        n.setProperty("prefix", name)
        return n

    def _equalizer(self, u):
        """Spotify's equaliser: presets, and a curve with a dot to drag on each band."""
        panel = QFrame()
        panel.setObjectName("eqPanel")
        panel.setStyleSheet(f"#eqPanel {{ background: transparent; }}")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(0, 6, 0, 6)
        top = QHBoxLayout()
        lbl = QLabel("Presets")
        lbl.setObjectName("desc")
        top.addWidget(lbl)
        self.eq_combo = QComboBox()
        self.eq_combo.addItems(list(self.eq_presets) + ["Custom"])
        self.eq_combo.setCurrentText(u.eq_preset if u.eq_preset in self.eq_presets else "Custom")
        self.eq_combo.currentTextChanged.connect(self._eq_preset_chosen)
        top.addWidget(self.eq_combo)
        top.addStretch()
        reset = QPushButton("Reset")
        reset.clicked.connect(lambda: self.eq_combo.setCurrentText("Flat") if "Flat" in self.eq_presets
                              else self._eq_set([0.0] * 10, "Custom"))
        top.addWidget(reset)
        pv.addLayout(top)
        self.eq_curve = EqualizerCurve(u.eq_bands, _vlc_band_labels())
        self.eq_curve.setEnabled(bool(u.eq_enabled))
        self.eq_curve.released.connect(self._eq_curve_released)
        self.eq_curve.changed.connect(lambda bands: self.eq_preview.emit([float(b) for b in bands]))
        pv.addWidget(self.eq_curve)
        self.controls["eq_panel"] = panel
        self._v.addWidget(panel)

    def _zoom(self, current):
        """Spotify's zoom: three pictures (Dense / Default / Spacious), the exact levels, and Reset."""
        from core.storage import ZOOM_LEVELS
        self._name_desc("Zoom level", f"Now {current}%. You can also use Ctrl + and Ctrl − (Ctrl 0 resets).")
        pics = QHBoxLayout()
        pics.setSpacing(12)
        self.zoom_pictures = {}
        for label, z, scale in (("Dense", 80, 0.8), ("Default", 100, 1.0), ("Spacious", 125, 1.25)):
            pic = ZoomPreview(label, scale)
            pic.setChecked(current == z)
            pic.clicked.connect(lambda _=False, z=z: self._set_zoom(z))
            pics.addWidget(pic)
            self.zoom_pictures[z] = pic
        pics.addStretch()
        self._v.addLayout(pics)
        row = QHBoxLayout()
        group = QButtonGroup(self)
        for z in ZOOM_LEVELS:
            rb = QRadioButton(f"{z}%")
            rb.setChecked(z == current)
            group.addButton(rb, z)
            row.addWidget(rb)
        row.addStretch()
        reset = QPushButton("Reset")
        reset.setToolTip("Back to 100%")
        reset.clicked.connect(lambda: self._set_zoom(100))
        row.addWidget(reset)
        group.idClicked.connect(self._set_zoom)
        self.controls["zoom"] = group
        self._v.addLayout(row)

    def _set_zoom(self, z):
        group = self.controls.get("zoom")
        if group is not None and group.button(z) is not None and not group.button(z).isChecked():
            group.button(z).setChecked(True)
        for level, pic in getattr(self, "zoom_pictures", {}).items():
            pic.setChecked(level == z)
        live = getattr(self, "zoom_live", None)            # the main window: show the new size straight away
        if live is not None and live(z):
            self.changed.emit({"zoom": z})
            return
        self._emit({"zoom": z})

    def _reset_section(self):
        self._section("Reset")
        row = QHBoxLayout()
        row.addLayout(self._name_desc("Reset settings", "Puts settings back to how Sevbify starts. Your playlists, "
                                      "music folders, downloads and podcasts are kept.", into=row), 1)
        look = QPushButton("Reset appearance")
        look.setToolTip("Zoom, Your Library layout, panels and Canvas")
        look.clicked.connect(lambda: self.reset_requested.emit("appearance"))
        everything = QPushButton("Reset all settings")
        everything.clicked.connect(lambda: self.reset_requested.emit("all"))
        row.addWidget(look)
        row.addWidget(everything)
        self.controls["reset_appearance"], self.controls["reset_all"] = look, everything
        self._v.addLayout(row)

    # --- reactions ----------------------------------------------------------------------------------
    def _emit(self, values):
        if any(k in RESTART_KEYS for k in values):
            self.needs_restart = True
            if hasattr(self, "restart_bar"):
                self.restart_bar.show()
        self.changed.emit(values)

    def _combo_changed(self, key, text):
        if key == "language":
            from core import i18n
            self._emit({key: next((c for c, n in i18n.LANGUAGES if n == text), "")})
        elif key == "canvas_cache_mb":
            self._emit({key: int(text.split()[0])})
        elif key == "fade_seconds":
            self._emit({key: 0 if text == "Off" else int(text.split()[0])})
        elif key == "startup":
            self._emit({key: text.lower()})
        elif key in ("download_quality", "audiobook_quality", "video_quality"):
            from core import quality as Q
            table = {"download_quality": {v[0]: k for k, v in Q.SONG_QUALITIES.items()},
                     "audiobook_quality": {v: k for k, v in Q.AUDIOBOOK_QUALITIES.items()},
                     "video_quality": {v: k for k, v in Q.VIDEO_QUALITIES.items()}}[key]
            if text in table:
                self._emit({key: table[text]})
        elif key == "proxy_mode":
            self._emit({key: {"Automatic (system settings)": "auto", "No proxy": "none", "HTTP proxy": "http"}[text]})
        else:
            self._emit({key: text})

    def _folder_toggled(self, folder, on):
        disabled = [f for f in self.u.disabled_folders if f != folder]
        if not on:
            disabled.append(folder)
        self._emit({"disabled_folders": disabled})

    def _choose_download_folder(self):
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Download location", self.info.get("download_folder", ""))
        if folder:
            self._emit({"download_folder": folder})

    def _eq_preset_chosen(self, name):
        if name in self.eq_presets:
            self._eq_set(self.eq_presets[name], name)

    def _eq_set(self, bands, name):
        self.eq_curve.set_values(bands)
        self.eq_curve.setEnabled(True)
        self._emit({"eq_bands": [float(b) for b in bands], "eq_preset": name, "eq_enabled": True})
        sw = self.controls.get("eq_enabled")
        if sw is not None and not sw.isChecked():
            sw.blockSignals(True)
            sw.setChecked(True)
            sw.blockSignals(False)

    def _eq_curve_released(self, bands):
        bands = [float(b) for b in bands]
        self.eq_combo.blockSignals(True)
        self.eq_combo.setCurrentText("Custom")
        self.eq_combo.blockSignals(False)
        self._emit({"eq_bands": bands, "eq_preset": "Custom", "eq_enabled": True})

    def set_sizes(self, download_size=None, cache_size=None):
        for label, value in ((self.download_size_label, download_size), (self.cache_size_label, cache_size)):
            if value is not None:
                try:
                    label.setText(f"{label.property('prefix')}: {value}")
                except RuntimeError:          # page was rebuilt meanwhile
                    pass

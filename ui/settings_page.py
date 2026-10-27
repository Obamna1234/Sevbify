"""Settings, as a page in the middle like Spotify's (opened with ⚙ or Ctrl+P).

Every change is applied at once and saved (no Save button). A few need a restart (zoom, graphics, proxy,
volume normalising); the page then shows "Restart to apply" with a button.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QScrollArea, QFrame, QSlider,
    QRadioButton, QButtonGroup, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal

from . import theme
from .widgets import ToggleSwitch
from core.audio_settings import BAND_LABELS

RESTART_KEYS = ("zoom", "normalize", "proxy_mode", "proxy_url", "hw_accel")
SOURCES = ("Bandcamp + YouTube", "Bandcamp only", "YouTube only")

STYLE = f"""
QLabel {{ color: {theme.TEXT}; background: transparent; }}
QLabel#h1 {{ font-size: 32px; font-weight: 800; }}
QLabel#h2 {{ font-size: 16px; font-weight: 700; padding-top: 18px; }}
QLabel#name {{ font-size: 14px; }}
QLabel#desc {{ color: {theme.SUBDUED}; font-size: 12px; }}
QLineEdit {{ background: #2a2a2a; color: white; border: 1px solid #3e3e3e; border-radius: 4px; padding: 6px 8px;
    font-size: 13px; }}
QLineEdit:focus {{ border-color: {theme.TEXT}; }}
QComboBox {{ background: #2a2a2a; color: white; border: none; border-radius: 4px; padding: 6px 10px; font-size: 13px;
    min-width: 160px; }}
QComboBox QAbstractItemView {{ background: #282828; color: white; selection-background-color: #3e3e3e; }}
QPushButton {{ color: white; background: transparent; border: 1px solid #727272; border-radius: 16px; padding: 6px 16px;
    font-weight: 700; font-size: 13px; }}
QPushButton:hover {{ border-color: white; }}
QRadioButton {{ color: {theme.SUBDUED}; font-size: 12px; spacing: 4px; }}
QRadioButton:checked {{ color: {theme.TEXT}; }}
QSlider::groove:vertical {{ background: #4d4d4d; width: 4px; border-radius: 2px; }}
QSlider::sub-page:vertical {{ background: #4d4d4d; border-radius: 2px; }}
QSlider::add-page:vertical {{ background: {theme.GREEN}; border-radius: 2px; }}
QSlider::handle:vertical {{ background: white; height: 12px; width: 12px; margin: 0 -4px; border-radius: 6px; }}
"""


class SettingsPage(QWidget):
    changed = pyqtSignal(dict)            # one or more settings changed (apply + save)
    add_folder_requested = pyqtSignal()
    remove_folder_requested = pyqtSignal(str)
    restart_requested = pyqtSignal()
    clear_cache_requested = pyqtSignal()
    open_folder_requested = pyqtSignal(str)
    shortcuts_requested = pyqtSignal()

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
        column.setMaximumWidth(720)
        v = QVBoxLayout(column)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        centre.addStretch()
        centre.addWidget(column, 100)
        centre.addStretch()
        self._v = v
        u = user_data

        h1 = QLabel("Settings")
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

        self._section("Online and privacy")
        self._toggle("online_enabled", "Online features",
                     "Search the web, song radio, artist info, full songs and downloads. When off, Sevbify never "
                     "connects to the internet; your own music always works.", u.online_enabled)
        self._toggle("stream_full", "Play full songs you don't have yet",
                     "Songs from Search and Radio stream in full (Bandcamp first, then YouTube) instead of "
                     "30-second previews. They stay marked ⬇ until you download them.", u.stream_full)
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
            "Deezer (search, radio, previews), Wikipedia (artist info), Apple iTunes (official song names), Bandcamp "
            "and YouTube (full songs and downloads), and Last.fm / Jamendo if you add a key below. Those sites see "
            "your IP address and what you look up, like a web browser would. Sevbify only looks at the music folders "
            "you add; it never searches the rest of your computer.")
        self._line_edit("lastfm_api_key", "Last.fm API key (optional)",
                        "Makes song radio closer to Spotify's. Free at last.fm/api/account/create.", u.lastfm_api_key,
                        "e.g. 0123456789abcdef0123456789abcdef")
        self._line_edit("jamendo_client_id", "Jamendo client ID (optional)",
                        "Free Creative Commons music from Jamendo. Free at devportal.jamendo.com.",
                        u.jamendo_client_id, "e.g. 1a2b3c4d")

        self._section("Your Library")
        self._toggle("library_compact", "Use compact library layout", "", u.library_view == "compact")
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

        self._section("Playback")
        self._toggle("autoplay", "Autoplay",
                     "When your music ends, keep playing similar songs (song radio from the last one).", u.autoplay)
        self._combo("fade_seconds", "Fade between songs",
                    "Fades the end of each song out and the next one in.",
                    ["Off"] + [f"{n} seconds" for n in range(1, 13)], "Off" if not u.fade_seconds else
                    f"{u.fade_seconds} seconds")
        self._toggle("normalize", "Normalize volume", "Sets the same loudness for every song. Applies after a "
                     "restart.", u.normalize)
        self._toggle("eq_enabled", "Equalizer", "", u.eq_enabled)
        self._equalizer(u)

        self._section("Display")
        self._toggle("np_on_play", "Show the now-playing panel on click of play", "", u.np_on_play)
        self._toggle("notify_track", "Show desktop notifications when the song changes", "", u.notify_track)
        self._toggle("canvas_enabled", "Canvas", "Short looping videos next to the song, when you've added one.",
                     u.canvas_enabled)
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

        self._section("Proxy settings")
        self._combo("proxy_mode", "Proxy type", "Applies after a restart.",
                    ["Automatic (system settings)", "No proxy", "HTTP proxy"],
                    {"auto": "Automatic (system settings)", "none": "No proxy", "http": "HTTP proxy"}[u.proxy_mode])
        self._line_edit("proxy_url", "HTTP proxy address", "Only used with “HTTP proxy”, e.g. http://127.0.0.1:8080",
                        u.proxy_url, "http://host:port")

        self._section("Compatibility")
        self._toggle("hw_accel", "Enable hardware acceleration",
                     "Turn off if the window flickers or stays black. Applies after a restart.", u.hw_accel)

        self._section("About")
        self._text(f"Sevbify {info.get('version', '')}. Built with AI help. Not affiliated with Spotify, YouTube, "
                   "Bandcamp, Apple, Deezer or Sevby LLC.")
        if info.get("can_make_shortcuts"):
            sc = QPushButton("Add to Desktop and Start menu")
            sc.clicked.connect(lambda: (self.shortcuts_requested.emit()))
            v.addWidget(sc, 0, Qt.AlignmentFlag.AlignLeft)
            self.controls["shortcuts"] = sc
        v.addStretch()
        theme.replace_scroll_widget(self.scroll, body)

    # --- pieces -------------------------------------------------------------------------------------
    def _section(self, title):
        lbl = QLabel(title)
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
        panel = QFrame()
        panel.setObjectName("eqPanel")
        panel.setStyleSheet(f"#eqPanel {{ background: {theme.ELEVATED}; border-radius: 8px; }}")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(18, 14, 18, 14)
        top = QHBoxLayout()
        top.addWidget(QLabel("Presets"))
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
        bands = QHBoxLayout()
        self.eq_sliders = []
        for i, label in enumerate(BAND_LABELS):
            col = QVBoxLayout()
            s = QSlider(Qt.Orientation.Vertical)
            s.setRange(-200, 200)                   # tenths of a dB
            s.setValue(int(round(u.eq_bands[i] * 10)))
            s.setFixedHeight(140)
            s.setToolTip(f"{label}: {u.eq_bands[i]:+.1f} dB")
            s.sliderReleased.connect(self._eq_slider_moved)
            col.addWidget(s, 0, Qt.AlignmentFlag.AlignHCenter)
            lbl = QLabel(label)
            lbl.setObjectName("desc")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl)
            bands.addLayout(col)
            self.eq_sliders.append(s)
        pv.addLayout(bands)
        scale = QLabel("+20 dB at the top, −20 dB at the bottom")
        scale.setObjectName("desc")
        pv.addWidget(scale)
        self.controls["eq_panel"] = panel
        self._v.addWidget(panel)

    def _zoom(self, current):
        self._name_desc("Zoom level", "Makes everything bigger or smaller. Applies after a restart.")
        row = QHBoxLayout()
        group = QButtonGroup(self)
        for z in (70, 80, 90, 100, 110, 120, 130):
            rb = QRadioButton(f"{z}%")
            rb.setChecked(z == current)
            group.addButton(rb, z)
            row.addWidget(rb)
        row.addStretch()
        group.idClicked.connect(lambda z: self._emit({"zoom": z}))
        self.controls["zoom"] = group
        self._v.addLayout(row)

    # --- reactions ----------------------------------------------------------------------------------
    def _emit(self, values):
        if any(k in RESTART_KEYS for k in values):
            self.needs_restart = True
            if hasattr(self, "restart_bar"):
                self.restart_bar.show()
        self.changed.emit(values)

    def _combo_changed(self, key, text):
        if key == "fade_seconds":
            self._emit({key: 0 if text == "Off" else int(text.split()[0])})
        elif key == "startup":
            self._emit({key: text.lower()})
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
        for s, value in zip(self.eq_sliders, bands):
            s.blockSignals(True)
            s.setValue(int(round(value * 10)))
            s.blockSignals(False)
        self._emit({"eq_bands": [float(b) for b in bands], "eq_preset": name, "eq_enabled": True})
        sw = self.controls.get("eq_enabled")
        if sw is not None and not sw.isChecked():
            sw.blockSignals(True)
            sw.setChecked(True)
            sw.blockSignals(False)

    def _eq_slider_moved(self):
        bands = [s.value() / 10 for s in self.eq_sliders]
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

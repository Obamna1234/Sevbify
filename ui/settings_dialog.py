"""Settings window: online features switch, optional service keys and where downloads come from."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton, QFrame, QComboBox
)
from PyQt6.QtCore import Qt

STYLE = """
QDialog { background: #181818; }
QLabel { color: #e0e0e0; font-size: 13px; }
QLabel#h { color: white; font-size: 18px; font-weight: bold; }
QLabel#sub { color: #b3b3b3; font-size: 12px; }
QCheckBox { color: white; font-size: 14px; font-weight: 600; spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QLineEdit { background: #2a2a2a; color: white; border: 1px solid #3e3e3e; border-radius: 4px; padding: 7px; font-size: 13px; }
QLineEdit:focus { border-color: #1db954; }
QPushButton { color: white; background: transparent; border: 1px solid #727272; border-radius: 16px; padding: 6px 16px; font-weight: bold; }
QPushButton:hover { border-color: white; }
QPushButton#primary { color: black; background: #1db954; border: none; }
QPushButton#primary:hover { background: #1ed760; }
QFrame#line { background: #2a2a2a; max-height: 1px; }
QComboBox { background: #2a2a2a; color: white; border: 1px solid #3e3e3e; border-radius: 4px; padding: 6px 8px; font-size: 13px; }
QComboBox QAbstractItemView { background: #282828; color: white; selection-background-color: #3e3e3e; }
"""


class SettingsDialog(QDialog):
    def __init__(self, user_data, on_clear_cache=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(520)
        self.user_data = user_data
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(10)

        h = QLabel("Settings"); h.setObjectName("h")
        v.addWidget(h)

        self.online = QCheckBox("Online features")
        self.online.setChecked(user_data.online_enabled)
        v.addWidget(self.online)
        v.addWidget(self._sub(
            "Online search, Go to Radio, artist info, cover art for online songs, previews and "
            "in-app streaming. When this is off Sevbify never connects to the internet and only "
            "your own music is shown. Your local music always works either way."))

        v.addWidget(self._line())
        v.addWidget(self._label("Last.fm API key (optional)"))
        v.addWidget(self._sub(
            'Makes Radio recommendations better and adds artist bios. Free: '
            '<a style="color:#1db954" href="https://www.last.fm/api/account/create">create an API account</a>, '
            'then paste the "API key" here.'))
        self.lastfm = QLineEdit(user_data.lastfm_api_key)
        self.lastfm.setPlaceholderText("e.g. 0123456789abcdef0123456789abcdef")
        v.addWidget(self.lastfm)

        v.addWidget(self._label("Jamendo client ID (optional)"))
        v.addWidget(self._sub(
            'Lets you search, stream and download free Creative Commons music from Jamendo. Free: '
            '<a style="color:#1db954" href="https://devportal.jamendo.com/signup">sign up</a>, create an app, '
            'and paste its "Client ID" here.'))
        self.jamendo = QLineEdit(user_data.jamendo_client_id)
        self.jamendo.setPlaceholderText("e.g. 1a2b3c4d")
        v.addWidget(self.jamendo)

        v.addWidget(self._line())
        self.stream_full = QCheckBox("Play full songs you don't have yet")
        self.stream_full.setChecked(user_data.stream_full)
        v.addWidget(self.stream_full)
        v.addWidget(self._sub(
            "When online, songs from Search and Radio stream in full (found on Bandcamp first, then YouTube) "
            "instead of 30-second previews. They stay marked ⬇ until you download them for offline listening."))

        v.addWidget(self._line())
        v.addWidget(self._label("Downloads"))
        v.addWidget(self._sub(
            "Songs you choose to download are looked for here, saved as MP3s in a "
            "“Sevbify downloads” folder inside your first music folder, and fill their playlist slots. "
            "Only download music you have the right to download."))
        self.download_source = QComboBox()
        self.download_source.addItems(["Bandcamp + YouTube", "Bandcamp only", "YouTube only"])
        self.download_source.setCurrentText(user_data.download_source)
        v.addWidget(self.download_source)

        from core import shortcuts
        if shortcuts.can_create():
            v.addWidget(self._line())
            v.addWidget(self._label("Shortcuts"))
            v.addWidget(self._sub("Sevbify comes as a folder without an installer. Add it to your Desktop and "
                                  "Start menu so you can open it like any other app."))
            add = QPushButton("Add to Desktop and Start menu")
            add.clicked.connect(lambda: add.setText(shortcuts.create_windows_shortcuts()[1]))
            v.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)

        v.addWidget(self._line())
        row = QHBoxLayout()
        if on_clear_cache:
            clear = QPushButton("Clear online cache")
            clear.setToolTip("Delete saved cover art, artist info and search results (they download again when needed)")
            clear.clicked.connect(lambda: (on_clear_cache(), clear.setText("Cleared ✓")))
            row.addWidget(clear)
        row.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        save = QPushButton("Save"); save.setObjectName("primary"); save.clicked.connect(self.accept)
        save.setDefault(True)
        row.addWidget(cancel); row.addWidget(save)
        v.addLayout(row)

    @staticmethod
    def _label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: white; font-weight: 600; font-size: 14px; padding-top: 4px;")
        return lbl

    @staticmethod
    def _sub(text):
        lbl = QLabel(text)
        lbl.setObjectName("sub")
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setOpenExternalLinks(True)
        return lbl

    @staticmethod
    def _line():
        f = QFrame(); f.setObjectName("line"); f.setFrameShape(QFrame.Shape.HLine)
        return f

    def values(self):
        return {
            "online_enabled": self.online.isChecked(),
            "lastfm_api_key": self.lastfm.text().strip(),
            "jamendo_client_id": self.jamendo.text().strip(),
            "download_source": self.download_source.currentText(),
            "stream_full": self.stream_full.isChecked(),
        }

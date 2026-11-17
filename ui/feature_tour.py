"""The feature tour: a few pages with a picture each, showing what Sevbify can do that people might not find on their
own. It opens once on the first start; "Don't show this again" (ticked by default) keeps it closed after that, and
Settings → About → Feature tour (or Help → Feature tour) opens it again. The pictures are screenshots of Sevbify
itself, playing openly licensed music (tools/tour_images.py makes them from the showcase run)."""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton

from . import theme
from .dialogs import _Card

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tour")

# (picture, title, text). Short and practical: what it is and where to find it.
PAGES = [
    ("search.jpg", "Search everywhere at once",
     "One search box looks through YouTube, Bandcamp, SoundCloud, Deezer and your own music. Play any result straight "
     "away, full length; no account needed."),
    ("save.jpg", "Save with one click",
     "Click ⊕ next to a song to save it to Liked Songs, or pick any playlist. The green tick shows where it's saved."),
    ("expanded.jpg", "Now playing, bigger",
     "The ⤢ button in Now playing opens it over the whole window: the cover tilts as your mouse moves, the Canvas "
     "video plays wide, or the artist's picture fills the background, with credits and what's next."),
    ("import.jpg", "Bring your Spotify playlists",
     "Your Library → + → Import a playlist, and paste a link from Spotify, Apple Music or Deezer. More than 100 songs? "
     "In Spotify click a song, press Ctrl+A then Ctrl+C, and paste them in the second box, or turn on Settings → "
     "Read whole Spotify playlists. Your Spotify account is never signed in to."),
    ("radio.jpg", "Radio and previews",
     "Right-click any song → Go to song radio for an endless mix like it. Or scroll through quick previews of songs "
     "and save the ones you like."),
    ("podcast.jpg", "Podcasts and audiobooks",
     "Follow podcasts (with their video versions when they have one) and free audiobooks. Sevbify remembers where you "
     "stopped in each one."),
    ("pair.jpg", "Send music from your phone",
     "Settings → Your phone → Pair. Scan the code with Sevbify on your phone, and send songs and folders straight "
     "to this computer over your own Wi-Fi, encrypted. Nothing goes through the internet."),
    ("support.jpg", "Support the artist",
     "Right-click a song → Support the artist to buy their music straight from them: their own Bandcamp page or "
     "official shop, never an ad or a middleman."),
    ("mini.jpg", "Mini player and full screen",
     "A small always-on-top player for while you work, and a full-screen view with lyrics that follow the song."),
    ("private.jpg", "Private session",
     "Click your profile → Private session, and what you play isn't remembered. Sevbify never sends your listening "
     "anywhere either way."),
    ("settings.jpg", "Make it yours",
     "Ctrl + and Ctrl − zoom the whole app, the equaliser shapes the sound, and Settings has crossfade, downloads, "
     "languages and more. You can open this tour again from Settings."),
]


def available_pages():
    return [p for p in PAGES if os.path.isfile(os.path.join(HERE, p[0]))] or PAGES


class FeatureTour(_Card):
    """Back / Next through the pages; Done on the last one. done_with_tour() is True if it shouldn't open again."""

    def __init__(self, win, show_again_box=True):
        super().__init__(win, light=False)
        self.pages = available_pages()
        self.index = 0
        self.setMinimumWidth(720)
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setFixedSize(664, 400)
        self.picture.setStyleSheet("background: #181818; border-radius: 8px;")
        self.body.addWidget(self.picture)
        self.title = QLabel()
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setStyleSheet("font-size: 22px; font-weight: 800; padding-top: 6px;")
        self.body.addWidget(self.title)
        self.text = QLabel()
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.text.setWordWrap(True)
        self.text.setMinimumHeight(64)
        self.text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.text.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 14px;")
        self.body.addWidget(self.text)
        self.dots = QLabel()
        self.dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(self.dots)

        row = QHBoxLayout()
        self.body.addLayout(row)
        self.again = QCheckBox("Don't show this again")
        self.again.setChecked(True)
        self.again.setStyleSheet("QCheckBox { color: #b3b3b3; font-size: 13px; }")
        row.addWidget(self.again)
        self.again.setVisible(show_again_box)           # only once it has a parent (never its own window)
        row.addStretch()
        pill = ("QPushButton { color: white; background: transparent; border: 1px solid #7c7c7c; border-radius: 16px;"
                " padding: 6px 18px; font-weight: 700; } QPushButton:hover { border-color: white; }")
        green = ("QPushButton { color: black; background: #1ed760; border: none; border-radius: 16px;"
                 " padding: 6px 20px; font-weight: 700; } QPushButton:hover { background: #3be477; }")
        self.skip = QPushButton("Skip")
        self.back = QPushButton("Back")
        self.next = QPushButton("Next")
        for b, style in ((self.skip, pill), (self.back, pill), (self.next, green)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(style)
            row.addWidget(b)
        self.skip.clicked.connect(self.accept)
        self.back.clicked.connect(lambda: self.go(self.index - 1))
        self.next.clicked.connect(lambda: self.accept() if self.index >= len(self.pages) - 1 else self.go(self.index + 1))
        self.go(0)

    def go(self, i):
        self.index = max(0, min(i, len(self.pages) - 1))
        name, title, text = self.pages[self.index]
        pm = QPixmap(os.path.join(HERE, name))
        if pm.isNull():
            self.picture.setText("")
        else:
            ratio = self.devicePixelRatioF() or 1.0
            pm = pm.scaled(int(664 * ratio), int(400 * ratio), Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(ratio)
            self.picture.setPixmap(pm)
        self.title.setText(title)
        self.text.setText(text)
        self.dots.setText(" ".join("●" if k == self.index else "○" for k in range(len(self.pages))))
        self.dots.setStyleSheet("color: #b3b3b3; font-size: 10px; letter-spacing: 2px;")
        last = self.index == len(self.pages) - 1
        self.back.setEnabled(self.index > 0)
        self.skip.setVisible(not last)
        self.next.setText("Done" if last else "Next")

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self.go(self.index + 1)
            return
        if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self.go(self.index - 1)
            return
        super().keyPressEvent(e)

    def done_with_tour(self):
        return self.again.isChecked() or not self.again.isVisible()


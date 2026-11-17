"""Help → Help and questions: answers to what people ask most, in the app (no website needed)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QFrame, \
    QLineEdit

from . import theme

FAQ = [
    ("Songs", [
        ("Why does a song take a few seconds to start?",
         "Songs you haven't downloaded are found online first (Bandcamp, YouTube, then SoundCloud). Once found, "
         "Sevbify remembers where, and it looks up the next and previous songs while one plays, so skipping is "
         "quicker. Downloaded songs and your own files start at once."),
        ("Where do the songs come from?",
         "Search and radio use Deezer's catalogue for names and covers. The full song is played from Bandcamp, "
         "YouTube or SoundCloud. Help → Show activity log says where each song was found."),
        ("Why is a song I have listed as not downloaded?",
         "The playlist points at a song online (for example a playlist imported from Spotify), or the file moved. "
         "Open the playlist's ••• menu → Locate songs in a folder… and pick the folder the songs are in: matching "
         "songs play from there, nothing is downloaded again. Deleting the playlist and adding the folder again "
         "works too (drag the folder onto Your Library)."),
        ("A song plays the wrong version.",
         "Right-click it → Download, or play it from search instead: Sevbify picks by title, artist and length. "
         "Send a problem report (Help → Save a problem report…) so the matching can be improved."),
        ("What do the green and grey circles mean?",
         "Next to the artist: green = the song is on this computer, grey = not downloaded yet. Next to the length: "
         "a green tick = the song is in Liked Songs or one of your playlists; click it to change which ones."),
    ]),
    ("Your music and playlists", [
        ("How do I add my own music?",
         "Your Library → Your Songs → add a folder, or drag a folder from File Explorer onto Your Library: it becomes "
         "a playlist with the folder's songs in order and its cover picture."),
        ("Are my music files ever changed?",
         "No. Renaming or deleting a playlist only changes Sevbify's own list; your files stay where they are."),
        ("Can I use the same playlists on my phone?",
         "Export a playlist (••• → Share and export) or copy its songs to a folder or phone. Sevbify has no account, "
         "so nothing syncs through the internet."),
    ]),
    ("Privacy and connection", [
        ("Does Sevbify need an account? Does it sell my data?",
         "No account, no ads, no tracking. Nothing about you is sent anywhere; the sites Sevbify uses only see what "
         "you look up, like a web browser would. Settings lists every site it contacts."),
        ("What is a Private session?",
         "Click the lock at the top: what you play isn't added to Recently played or Recents and the activity log "
         "keeps no song names. It ends when you close Sevbify or after 6 hours."),
        ("Does it work with a VPN or proxy?",
         "Yes: Sevbify uses your computer's connection, so a VPN covers it. Settings → Proxy settings sets a proxy "
         "for Sevbify only. Some sites (YouTube, Bandcamp) are stricter with VPN addresses: if songs stop playing, "
         "try another VPN server or turn it off."),
        ("Can I use it offline?",
         "Yes: click Online at the top to go offline. Your own music and downloads keep playing; nothing is "
         "contacted."),
    ]),
    ("The app", [
        ("How do I update Sevbify?",
         "Settings → About and updates → Check for Sevbify updates. It also checks once a day by itself."),
        ("How do I uninstall it?",
         "Sevbify is portable: delete its folder. Your playlists and settings are in its data folder "
         "(Help → Open Sevbify's data folder); delete that too to remove everything."),
        ("Can a song have a looping video behind it?",
         "Yes: add your own short video to a song with its ••• menu → Canvas video (turn Canvas on in Settings). "
         "Sevbify never asks for any streaming-service sign-in."),
        ("How do I pair my phone?",
         "On the computer: Settings → Your phone → Pair a phone. On the phone: Settings → Your computer → Pair with "
         "a computer, and scan the code. Both need to be on the same Wi-Fi. If the computer asks whether Sevbify may "
         "use the network, choose Allow (private networks are enough)."),
        ("Something went wrong. What do I send?",
         "Help → Save a problem report… makes one text file with the activity and error logs (no passwords, "
         "your user folder's name hidden). Send that file."),
    ]),
]


def show(parent):
    d = QDialog(parent)
    d.setWindowTitle("Help and questions")
    d.resize(720, 640)
    d.setStyleSheet(f"QDialog {{ background: #121212; }} QLabel {{ background: transparent; color: white; }}"
                    f" QLineEdit {{ background: #2a2a2a; color: white; border: 1px solid transparent; border-radius: 18px;"
                    f" padding: 8px 14px; font-size: 14px; }} QLineEdit:focus {{ border-color: white; }}")
    v = QVBoxLayout(d)
    v.setContentsMargins(28, 24, 28, 20)
    title = QLabel("Help and questions")
    title.setStyleSheet("font-size: 28px; font-weight: 800;")
    v.addWidget(title)
    find = QLineEdit()
    find.setPlaceholderText("Search the questions")
    v.addWidget(find)
    body = QWidget()
    bl = QVBoxLayout(body)
    bl.setContentsMargins(0, 8, 0, 8)
    bl.setSpacing(6)
    items = []
    for section, qas in FAQ:
        head = QLabel(section)
        head.setStyleSheet("font-size: 18px; font-weight: 700; padding-top: 14px;")
        bl.addWidget(head)
        group = []
        for q, a in qas:
            box = QFrame()
            box.setStyleSheet("QFrame { background: #1f1f1f; border-radius: 8px; }")
            bv = QVBoxLayout(box)
            bv.setContentsMargins(16, 12, 16, 12)
            ql = QLabel(q)
            ql.setWordWrap(True)
            ql.setStyleSheet("font-size: 15px; font-weight: 700;")
            al = QLabel(a)
            al.setWordWrap(True)
            al.setStyleSheet(f"font-size: 14px; color: {theme.SUBDUED};")
            al.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            bv.addWidget(ql)
            bv.addWidget(al)
            bl.addWidget(box)
            group.append((box, (q + " " + a).casefold()))
        items.append((head, group))
    bl.addStretch()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QWidget { background: transparent; }")
    scroll.setWidget(body)
    v.addWidget(scroll, 1)

    def filter_(text):
        words = text.casefold().split()
        for head, group in items:
            shown = 0
            for box, hay in group:
                ok = all(w in hay for w in words)
                box.setVisible(ok)
                shown += ok
            head.setVisible(shown > 0)
    find.textChanged.connect(filter_)
    row = QHBoxLayout()
    row.addStretch()
    close = QPushButton("Close")
    close.setCursor(Qt.CursorShape.PointingHandCursor)
    close.setFixedHeight(40)
    close.setStyleSheet("QPushButton { color: black; background: white; border: none; border-radius: 20px;"
                        " font-weight: 700; font-size: 14px; padding: 0 24px; } QPushButton:hover { background: #f0f0f0; }")
    close.clicked.connect(d.accept)
    row.addWidget(close)
    v.addLayout(row)
    d.faq_filter = filter_
    d.faq_items = items
    if getattr(parent, "_auto_answer_dialogs", None) is not None:      # tests
        return d
    d.exec()
    return d

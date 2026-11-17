"""Screenshots of Sevbify for a showcase video: the real app with real online data, a page per feature.

Run on a test computer (the "Showcase screenshots" workflow):  python tools/showcase.py <folder>
It uses its own empty data folder (never yours), shows each page, waits for it to load and saves a PNG.
A step that fails is noted and skipped; the rest carry on.
"""
import os
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "showcase")
os.makedirs(OUT, exist_ok=True)
DATA = tempfile.mkdtemp(prefix="sevbify-showcase-")
os.environ["SEVBIFY_DATA_DIR"] = DATA

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import QPoint  # noqa: E402

app = QApplication(sys.argv)
from ui.main_window import MainWindow  # noqa: E402

W, H = 1600, 960
FAV_ARTISTS = ["Chris Zabriskie", "Kevin MacLeod", "Kai Engel", "Broke For Free", "Jahzzar", "Lee Rosevere"]   # all openly licensed
log = open(os.path.join(OUT, "showcase.log"), "w", encoding="utf-8")


def note(text):
    print(text, flush=True)
    log.write(text + "\n")
    log.flush()


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.03)


def wait(cond, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        try:
            if cond():
                return True
        except Exception:
            pass
        time.sleep(0.05)
    return False


n = [0]


def shot(name, widget=None):
    pump(1.5)
    n[0] += 1
    path = os.path.join(OUT, f"{n[0]:02d}-{name}.png")
    (widget or w).grab().save(path)
    note(f"shot {os.path.basename(path)}")


def step(name, fn):
    try:
        fn()
    except Exception:
        note(f"step {name} failed:\n{traceback.format_exc()}")


music = os.path.join(DATA, "music")
os.makedirs(music, exist_ok=True)
w = MainWindow(audio_folder=music, data_dir=DATA, vlc_args=("--aout=adummy", "--no-video", "--quiet"))
w.move(0, 0)
w.user_data.auto_update_check = False
w.user_data.download_notice_accepted = True
w.offer_update = lambda r: None
w.resize(W, H)
w.show()
wait(lambda: w.library_ready, 60)

# A listening history, so Home has "Made for you" (Discover Weekly, Daily Mixes) like after a few weeks of use.
now = int(time.time())
for i in range(120):
    w.user_data.listens.append([FAV_ARTISTS[i % len(FAV_ARTISTS)], f"Song {i}", now - i * 3600 * 5])

state = {}


def home():
    w.show_home()
    wait(lambda: getattr(w, "_mfy", None) and w._mfy.get("lists"), 150)
    w.show_home()
    pump(15)                                         # covers
    shot("home")
    w.home_scroll.verticalScrollBar().setValue(700) if hasattr(w, "home_scroll") else None
    pump(3)
    shot("home-more")


def search():
    w.show_search()
    w.search_input.setText("Chris Zabriskie")
    wait(lambda: w.web_table.isVisible() and len(w.web_table.songs_in_view()) >= 5, 60)
    pump(12)
    state["songs"] = w.web_table.songs_in_view()
    shot("search")


def play():
    songs = state.get("songs") or []
    hits = [s for s in songs if "candlepower" in s.title.lower()] or songs
    song = hits[0]
    w.set_right_panel("nowplaying")
    w.play_song(song, queue=songs[:20], source="Chris Zabriskie")
    wait(lambda: w._reached_playing, 120)
    pump(10)
    for s in songs[1:6]:
        w.toggle_like(s)
    w.toggle_like(song)
    pump(3)
    shot("now-playing")


def artist():
    w.show_web_artist("Chris Zabriskie")
    pump(20)
    shot("artist")


def album():
    a = w.online.deezer.find_artist("Chris Zabriskie")
    albums = w.online.deezer.artist_albums(a.get("id")).get("albums") or []
    pick = albums[0]
    w.open_web_album(pick)
    pump(15)
    shot("album")


def queue():
    w.set_right_panel("queue")
    pump(3)
    shot("queue")
    w.set_right_panel("nowplaying")


def liked():
    pl = w.liked_playlist(create=True)
    w.show_playlist(pl)
    pump(6)
    shot("liked-songs")


def save_picker():
    songs = state.get("songs") or []
    w.show_search()
    pump(2)
    w.open_save_picker(songs[2], w.mapToGlobal(QPoint(W // 2, 200)))
    pump(3)
    shot("save-picker")
    for top in QApplication.topLevelWidgets():
        if top is not w and top.isVisible() and type(top).__name__ == "SavePicker":
            shot("save-picker-popup", top)
            top.close()


def made_for_you():
    lists = (getattr(w, "_mfy", None) or {}).get("lists") or []
    if not lists:
        note("no Made for you lists")
        return
    note(f"Made for you: {[x[0] for x in lists]}")
    title, subtitle, tracks = lists[0]
    n = int(title.rsplit(" ", 1)[-1]) if title.startswith("Daily Mix") else 0
    w._open_made_for_you(title, subtitle, tracks, w._mfy_cover(title, n=n))
    pump(15)
    shot("discover-weekly")


def radio():
    songs = state.get("songs") or []
    w.start_radio(songs[0])
    pump(40)
    shot("radio")


def preview_feed():
    songs = state.get("songs") or []
    w.open_preview_feed(songs[:10], "Chris Zabriskie")
    pump(10)
    shot("preview-feed")
    feed = getattr(w, "_preview_feed", None)
    if feed is not None:
        feed.close_feed()
    pump(1)


def podcast():
    from core import podcasts
    found = podcasts.search(w.net, "Huberman Lab", 5, "us")
    w.open_show(found[0], follow=True)
    wait(lambda: w._show_ctx and w._show_ctx["items"], 60)
    pump(10)
    shot("podcast")


def lyrics_or_full():
    w.open_full_screen()
    fs = w.full_screen_view
    fs.showNormal()
    fs.resize(W, H)
    pump(8)
    shot("full-screen", fs)
    fs.close()
    pump(1)


def settings():
    w.open_settings()
    pump(3)
    shot("settings")


def private():
    w.apply_settings({"private_session": True})
    w.show_home()
    pump(4)
    shot("private-session")
    w.apply_settings({"private_session": False})


def zoom():
    w.show_home()
    pump(2)
    w.change_zoom(+1)
    w.change_zoom(+1)
    pump(0.3)
    shot("zoom-125")
    w.change_zoom(0)
    pump(2)


def mini():
    w.open_mini_player()
    mp = w.mini_player
    pump(5)
    shot("mini-player", mp)
    mp.close()
    w.showNormal()
    w.resize(W, H)


for name, fn in [("home", home), ("search", search), ("play", play), ("artist", artist), ("album", album),
                 ("queue", queue), ("liked", liked), ("save picker", save_picker), ("made for you", made_for_you),
                 ("radio", radio), ("preview feed", preview_feed), ("podcast", podcast),
                 ("full screen", lyrics_or_full), ("mini player", mini), ("private", private), ("zoom", zoom),
                 ("settings", settings)]:
    note(f"== {name}")
    step(name, fn)

w.close()
from ui.async_tasks import wait_for_all  # noqa: E402
wait_for_all(5000)
note("done")
log.close()
os._exit(0)

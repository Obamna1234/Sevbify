"""Walk through the Android app on an emulator and save a screenshot of each screen (plus screen recordings).

Run by .github/workflows/android-screens.yml (needs adb and a running emulator with Sevbify installed).
Finds buttons by their text / description (uiautomator), so it keeps working when layouts move.
Usage: python tools/android_screens.py <out_dir>
"""
import os
import re
import subprocess
import sys
import time

OUT = sys.argv[1] if len(sys.argv) > 1 else "screens"
PKG = "com.obamna1234.sevbify"
os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, "steps.txt"), "w")


def adb(*args, check=False):
    r = subprocess.run(["adb", *args], capture_output=True, timeout=120)
    return r.stdout


def sh(cmd):
    return adb("shell", cmd).decode(errors="replace")


def note(text):
    print(text, flush=True)
    log.write(text + "\n")
    log.flush()


n = [0]


def shot(name, wait=2.5):
    time.sleep(wait)
    clear_anr()
    n[0] += 1
    path = os.path.join(OUT, f"{n[0]:02d}_{name}.png")
    with open(path, "wb") as f:
        f.write(adb("exec-out", "screencap", "-p"))
    note(f"screenshot {path}")


def nodes():
    sh("uiautomator dump /sdcard/ui.xml >/dev/null 2>&1")
    xml = sh("cat /sdcard/ui.xml")
    out = []
    for m in re.finditer(r"<node [^>]*>", xml):
        a = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', m.group(0)))
        b = re.findall(r"\d+", a.get("bounds", ""))
        if len(b) == 4:
            x1, y1, x2, y2 = map(int, b)
            out.append((a.get("text", ""), a.get("content-desc", ""), (x1 + x2) // 2, (y1 + y2) // 2, y1))
    return out


def clear_anr(found=None):
    """The emulator is slow on GitHub's machines; Android may show "System UI isn't responding". Wait it out."""
    found = found if found is not None else nodes()
    if any("isn't responding" in nd[0] for nd in found):
        for nd in found:
            if nd[0] == "Wait":
                sh(f"input tap {nd[2]} {nd[3]}")
                note("dismissed an 'isn't responding' box")
                time.sleep(2)
                return True
    return False


def tap(label, exact=True, index=0, below=0, tries=4):
    for _ in range(tries):
        found = nodes()
        if clear_anr(found):
            found = nodes()
        hits = [nd for nd in found
                if (nd[0] == label or nd[1] == label if exact else label.lower() in (nd[0] + " " + nd[1]).lower())
                and nd[4] >= below]
        if len(hits) > index:
            _, _, x, y, _ = hits[index]
            sh(f"input tap {x} {y}")
            note(f"tap '{label}' at {x},{y}")
            return True
        time.sleep(2)
    note(f"!! couldn't find '{label}'")
    return False


def back():
    sh("input keyevent 4")
    time.sleep(1.5)


def type_text(text):
    sh("input text " + text.replace(" ", "%s"))
    time.sleep(0.5)
    sh("input keyevent 66")


def swipe_up():
    sh("input swipe 540 1700 540 700 300")


def step(name, fn):
    try:
        fn()
    except Exception as exc:          # one broken step must not lose the other screenshots
        note(f"!! step {name} failed: {exc}")


def hide_keyboard():
    if "mInputShown=true" in sh("dumpsys input_method | grep mInputShown"):
        back()


def screen_size():
    size = re.findall(r"(\d+)x(\d+)", sh("wm size"))
    return tuple(map(int, size[-1])) if size else (1080, 2400)


def tap_first_song():
    """The first song under the "Songs" heading of the search results."""
    found = nodes()
    heads = [nd for nd in found if nd[0] == "Songs" and nd[4] > 400]
    if not heads:
        note("!! no Songs heading")
        return False
    y0 = heads[-1][4] + 60
    rows = [nd for nd in found if nd[0] and nd[4] > y0 and nd[0] not in ("Songs", "More")]
    if not rows:
        note("!! no song rows")
        return False
    _, _, x, y, _ = rows[0]
    sh(f"input tap {x} {y}")
    note(f"tap first song '{rows[0][0]}'")
    return True


def open_now_playing():
    w, h = screen_size()
    found = nodes()
    bar = [nd for nd in found if nd[0] == "Home" and nd[4] > h * 0.8]
    top = bar[0][4] if bar else int(h * 0.92)
    mini = [nd for nd in found if nd[0] and top - 260 < nd[4] < top - 20]
    if mini:
        sh(f"input tap {mini[0][2]} {mini[0][3]}")
        note(f"open now playing via '{mini[0][0]}'")
    else:
        sh(f"input tap {w // 2} {top - 110}")
        note("open now playing (no mini player text found)")


def main():
    clear_anr()
    sh(f"monkey -p {PKG} -c android.intent.category.LAUNCHER 1")
    time.sleep(15)                    # first start unpacks Python
    clear_anr()
    shot("home", 4)

    def podcasts_chip():
        if tap("Podcasts"):
            shot("home_podcasts", 6)
        tap("Audiobooks")
        shot("home_audiobooks", 8)
        tap("All")
    step("home_chips", podcasts_chip)

    def search_and_play():
        tap("Search")
        shot("search_browse")
        tap("What do you want to listen to?")
        time.sleep(2)
        sh("input text daft%spunk")
        time.sleep(10)
        hide_keyboard()
        shot("search_results", 3)
        if tap_first_song():
            shot("after_tapping_song", 5)
            if tap("Play full songs", tries=2):
                note("accepted full songs")
            shot("playing_mini_player", 15)
    step("search_and_play", search_and_play)

    def now_playing():
        open_now_playing()
        shot("now_playing", 5)
        shot("now_playing_later", 15)          # does the time move? (playback really running)
        swipe_up()
        shot("now_playing_scrolled")
        if tap("Queue"):
            shot("queue")
            back()
        if tap("More"):
            shot("now_playing_menu")
            back()
        back()
        shot("after_closing_now_playing")
    step("now_playing", now_playing)

    def download_song():
        tap("Search")
        found = nodes()
        mores = [nd for nd in found if nd[1] == "More"]
        if mores:
            sh(f"input tap {mores[0][2]} {mores[0][3]}")
            shot("song_menu")
            if tap("Download", tries=2):
                shot("downloading", 10)
                shot("download_later", 60)
    step("download", download_song)

    def artist():
        tap("Search")
        if tap("Daft Punk", tries=2):
            shot("artist_page", 8)
            back()
    step("artist", artist)

    def genre():
        tap("Clear", tries=1)
        hide_keyboard()
        tap("Rock", tries=2)
        shot("genre_page", 10)
        back()
    step("genre", genre)

    def library():
        tap("Your Library")
        shot("library")
        tap("Your Songs")
        shot("your_songs", 3)
        if tap("More", index=1, tries=1):
            shot("your_songs_menu")
            back()
        back()
        tap("To download", tries=1) and (shot("to_download"), back())
    step("library", library)

    def create_playlist():
        tap("Create", below=1500)
        shot("create_sheet")
        if tap("Playlist", tries=1):
            shot("name_playlist")
            sh("input text Road%strip")
            time.sleep(1)
            tap("Save", tries=1) or tap("Create", tries=1)
            shot("new_playlist", 3)
            back()
    step("create", create_playlist)

    def import_link():
        sh(f"am start -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT "
           f"https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M {PKG}")
        shot("import_from_share", 6)
        tap("Import", tries=2)
        shot("import_result", 20)
        back()
    step("import", import_link)

    def podcast():
        tap("Home")
        tap("Podcasts")
        time.sleep(4)
        if tap("The Daily", tries=2):
            shot("podcast_show", 10)
            found = [nd for nd in nodes() if nd[1] == "Play"]
            if found:
                sh(f"input tap {found[0][2]} {found[0][3]}")
                shot("podcast_playing", 12)
            back()
        tap("All")
    step("podcast", podcast)

    def settings():
        tap("Home")
        tap("S")
        shot("settings")
        swipe_up()
        shot("settings_more")
        swipe_up()
        shot("settings_end")
        back()
    step("settings", settings)

    def offline():
        tap("Home")
        tap("S")
        found = [nd for nd in nodes() if nd[0] == "Online"]
        if found:
            w, _ = screen_size()
            sh(f"input tap {int(w * 0.9)} {found[0][3] + 30}")
            back()
            tap("Search")
            sh("input text radiohead")
            time.sleep(6)
            hide_keyboard()
            shot("offline_search", 2)
            tap("Home"); tap("S")
            sh(f"input tap {int(w * 0.9)} {found[0][3] + 30}")
            back()
    step("offline", offline)

    def background_and_return():
        sh("input keyevent 3")             # Home button: app goes to the background, music keeps playing
        time.sleep(5)
        sh("cmd statusbar expand-notifications")
        shot("notification_controls", 3)
        sh("cmd statusbar collapse")
        sh(f"am kill {PKG}")               # Android reclaims the app's memory (it's in the background)
        time.sleep(3)
        sh(f"monkey -p {PKG} -c android.intent.category.LAUNCHER 1")
        shot("reopened_after_kill", 12)
    step("background", background_and_return)

    def rotate():
        sh("settings put system accelerometer_rotation 0")
        sh("settings put system user_rotation 1")
        shot("landscape", 4)
        sh("settings put system user_rotation 0")
        time.sleep(2)
    step("rotate", rotate)


if __name__ == "__main__":
    main()
    log.close()

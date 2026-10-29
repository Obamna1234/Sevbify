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


def tap(label, exact=True, index=0, below=0, tries=4):
    for _ in range(tries):
        hits = [nd for nd in nodes()
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


def main():
    sh(f"monkey -p {PKG} -c android.intent.category.LAUNCHER 1")
    time.sleep(12)                    # first start unpacks Python
    shot("home", 4)

    def home_more():
        swipe_up()
        shot("home_scrolled")
        sh("input swipe 540 700 540 1700 300")
    step("home_more", home_more)

    def podcasts_chip():
        if tap("Podcasts"):
            shot("home_podcasts", 6)
            tap("Podcasts")
    step("podcasts_chip", podcasts_chip)

    def search():
        tap("Search")
        shot("search_browse")
        tap("What do you want to listen to?")
        time.sleep(1)
        type_text("daft punk")
        shot("search_results", 10)
    step("search", search)

    def play_online():
        tap("Get Lucky", exact=False) or tap("Harder", exact=False)
        shot("play_notice_or_playing", 4)
        if tap("Play full songs", tries=2):
            shot("after_notice", 8)
    step("play_online", play_online)

    def now_playing():
        # The mini player sits just above the bottom bar: tap its middle.
        size = re.findall(r"(\d+)x(\d+)", sh("wm size"))
        w, h = map(int, size[-1]) if size else (1080, 2400)
        sh(f"input tap {w // 2} {int(h * 0.865)}")
        shot("now_playing", 4)
        swipe_up()
        shot("now_playing_scrolled")
        if tap("Queue"):
            shot("queue")
            back()
        back()
    step("now_playing", now_playing)

    def artist_or_genre():
        tap("Search")
        back()
        tap("Search")
        swipe_up()
        shot("search_browse_scrolled")
    step("browse_scroll", artist_or_genre)

    def library():
        tap("Your Library")
        shot("library")
        tap("Your songs", exact=False)
        shot("your_songs", 3)
        if tap("More", index=1):
            shot("song_menu")
            back()
        back()
    step("library", library)

    def create():
        tap("Create", index=0, below=1500)
        shot("create_sheet")
        back()
    step("create", create)

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

    def audiobooks():
        tap("Home")
        tap("Audiobooks")
        shot("home_audiobooks", 8)
    step("audiobooks", audiobooks)


if __name__ == "__main__":
    main()
    log.close()

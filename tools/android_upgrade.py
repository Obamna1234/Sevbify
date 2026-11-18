"""Updating from the last release keeps your library: checked on an emulator before every release.

    python tools/android_upgrade.py before <out_dir>   (the LAST release is installed: add a song to a new playlist)
    python tools/android_upgrade.py after <out_dir>    (the NEW build was installed over it: is the playlist still there?)

Writes <out_dir>/upgrade.json, which android_journey.py adds to its report as the step "Update from the last
release keeps your library". Uses only buttons every recent version has (Search, a song's menu → Add to playlist →
New playlist, Your Library).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
MODE, OUT = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "android-journey")
sys.argv = [sys.argv[0], OUT]
import android_screens as ui   # noqa: E402

os.makedirs(OUT, exist_ok=True)
STATE = os.path.join(OUT, "upgrade-state.json")
RESULT = os.path.join(OUT, "upgrade.json")
STEP = "Update from the last release keeps your library"


def save(status, detail):
    json.dump({"step": STEP, "status": status, "detail": detail}, open(RESULT, "w"))
    print(f"[upgrade] {status.upper():8} {detail}")


def start_app():
    ui.sh(f"am start -W -n {ui.PKG}/com.sevbify.app.MainActivity")
    time.sleep(8)
    for _ in range(3):                                   # first-start screens of any version: say yes / skip
        for label in ("Got it", "Skip", "Start listening", "Done", "Not now", "Allow"):
            ui.tap(label, tries=1)
        time.sleep(1)


def before():
    start_app()
    ui.tap("Search", tries=3)
    if not ui.tap("What do you want to listen to?", tries=3):
        return save("fail", "the last release: couldn't open Search")
    ui.sh("input text kevin%smacleod")
    time.sleep(10)
    ui.hide_keyboard()
    end, rows = time.time() + 40, []
    while time.time() < end and not rows:
        rows = ui.song_rows()
        time.sleep(2)
    if not rows:
        return save("blocked", "the last release: no search results (online search unavailable here)")
    title, x, y = rows[0]
    ui.long_press(x, y)
    if not ui.tap("Add to playlist", tries=3) or not ui.tap("New playlist", tries=3):
        return save("fail", "the last release: couldn't add a song to a new playlist")
    time.sleep(3)
    ui.sh("input keyevent 4")
    ui.tap("Your Library", tries=3)
    time.sleep(3)
    names = [n[0] for n in ui.nodes() if n[0].startswith("My Playlist")]
    if not names:
        return save("fail", "the last release: the new playlist didn't appear in Your Library")
    json.dump({"playlist": names[0], "song": title}, open(STATE, "w"))
    ui.sh(f"am force-stop {ui.PKG}")
    print(f"[upgrade] made “{names[0]}” with “{title}” in the last release")


def after():
    if os.path.exists(RESULT):                            # "before" already failed: keep that result
        return
    try:
        state = json.load(open(STATE))
    except (OSError, ValueError):
        return save("fail", "nothing was set up in the last release")
    start_app()
    ui.tap("Your Library", tries=3)
    time.sleep(3)
    if not ui.tap(state["playlist"], tries=3):
        ui.shot("upgrade_lost", wait=0.5)
        return save("fail", f"after updating, “{state['playlist']}” is missing from Your Library")
    time.sleep(3)
    shown = ui.texts()
    ui.shot("upgrade_kept", wait=0.5)
    if state["song"].lower() not in shown:
        return save("fail", f"after updating, “{state['playlist']}” no longer has “{state['song']}”")
    save("pass", f"made “{state['playlist']}” with “{state['song']}” in the last release; still there after "
                 "installing this build over it")


if __name__ == "__main__":
    {"before": before, "after": after}[MODE]()

"""End-to-end check of the Android app on an emulator: what a person does first, checked for real.

Run by .github/workflows/e2e.yml with an emulator running and Sevbify installed:
    python tools/android_journey.py <out_dir>
Taps through the app like a person (buttons found by their text), and reads Android's own media session to see
whether a song is really playing (state PLAYING and the position moving on). Writes journey.json + journey.md and
a screenshot per step. Results: pass / fail / blocked (a website refused this cloud computer, e.g. YouTube's
"confirm you're not a bot") / skipped (needs a step that failed). Nothing passes on a guess.
"""
import json
import os
import re
import sys
import time

OUT = sys.argv[1] if len(sys.argv) > 1 else "android-journey"
sys.argv = [sys.argv[0], OUT]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import android_screens as ui   # noqa: E402  (adb helpers: tap by text, screenshots, ...)

PKG = ui.PKG
BOT_WORDS = ("not a bot", "confirm you", "sign in to confirm", "http error 429", "too many requests")
steps = []


def session():
    """(state, position_ms, title) of Sevbify's media session. state 3 = playing, 2 = paused."""
    text = ui.sh("dumpsys media_session")
    ours, state, pos, title = False, None, 0, ""
    for line in text.splitlines():
        if "package=" in line:
            if ours and state:
                break
            ours = ("package=" + PKG) in line
            continue
        if not ours:
            continue
        m = re.search(r"PlaybackState \{state=\w+\((\d+)\), position=(-?\d+)", line)
        if m and state is None:
            state, pos = m.group(1), int(m.group(2))
        d = re.search(r"description=(.*)", line)
        if d and not title:
            title = d.group(1).strip()
    return state, pos, title


def plays(seconds=6, wait=90):
    end = time.time() + wait
    while time.time() < end:
        s, p, t = session()
        if s == "3":
            break
        time.sleep(1)
    else:
        s, p, t = session()
        return False, f"never playing within {wait} s (state={s}, title={t})"
    time.sleep(2)
    _, p1, _ = session()
    time.sleep(seconds)
    s, p2, t = session()
    if s == "3" and p2 - p1 >= (seconds - 2) * 1000:
        return True, f"playing “{t}”, position moved {p2 - p1} ms in {seconds} s"
    return False, f"started but didn't keep playing (state={s}, moved {p2 - p1} ms in {seconds} s)"


def app_log(lines=15):
    log = ui.adb("logcat", "-d", "-t", "4000").decode(errors="replace").splitlines()
    mine = [l for l in log if "Sevbify" in l or "python" in l.lower() or "ExoPlayer" in l]
    return mine[-lines:]


def blocked_in_log():
    text = "\n".join(app_log(400)).lower()
    return any(w in text for w in BOT_WORDS)


def record(name, status, detail):
    ui.shot(re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"), wait=1)
    steps.append({"step": name, "status": status, "detail": str(detail)[:1500]})
    ui.note(f"[journey] {status.upper():8} {name}: {detail}")


def status_of(name):
    return next((s["status"] for s in steps if s["step"] == name), "missing")


def run(name, fn, needs=()):
    if any(status_of(n) != "pass" for n in needs):
        steps.append({"step": name, "status": "skipped", "detail": "needs: " + ", ".join(needs)})
        return
    try:
        status, detail = fn()
    except Exception as exc:
        status, detail = "fail", f"the test itself broke: {exc!r}"
    record(name, status, detail)


def search(text):
    ui.tap("Search")
    ui.tap("Clear", tries=1)
    if not ui.tap("What do you want to listen to?", tries=3):
        return False
    ui.sh("input text " + text.replace(" ", "%s"))
    time.sleep(8)
    return True


def stream(query, must_contain):
    if not search(query):
        return "fail", "couldn't find the search box"
    ui.hide_keyboard()
    end = time.time() + 40
    while time.time() < end and not any(must_contain.lower() in (n[0] + n[1]).lower() for n in ui.nodes()):
        time.sleep(2)
    if not any(must_contain.lower() in (n[0] + n[1]).lower() for n in ui.nodes()):
        return "fail", f"no “{must_contain}” in the search results after 40 s"
    ui.adb("logcat", "-c")
    if not ui.tap_first_song():
        return "fail", "couldn't tap the first song"
    if ui.tap("Play full songs", tries=1):          # a one-time "stream full songs?" question: a person says yes
        time.sleep(1)
    ok, how = plays()
    if ok:
        return "pass", how
    if blocked_in_log():
        return "blocked", "the website refused this cloud computer (“confirm you're not a bot”); " + how
    return "fail", how + " | app log: " + " / ".join(app_log(8))


def main():
    # Don't let other apps' "isn't responding" boxes cover the screen (Android's own setting for this).
    ui.sh("settings put global hide_error_dialogs 1")
    ui.clear_anr()
    installed = PKG in ui.sh("pm list packages")

    def opens():
        if not installed:
            return "fail", "Sevbify isn't installed on the emulator (the install step failed)"
        focus = ""
        for attempt in range(3):
            ui.sh(f"am start -W -n {PKG}/com.sevbify.app.MainActivity")
            for _ in range(30):                # the first start unpacks Python
                time.sleep(2)
                ui.clear_anr()
                focus = ui.sh("dumpsys window | grep mCurrentFocus")
                if PKG in focus:
                    break
            if PKG in focus:
                break
        if PKG not in focus:
            return "fail", f"Sevbify never came to the front ({focus.strip()[:200]})"
        time.sleep(8)
        # One-time questions a person answers on first start (e.g. the Android Auto tip): "Later" / "Not now".
        for _ in range(6):
            found = ui.nodes()
            if ui.clear_anr(found):
                continue
            texts = {n[0] for n in found}
            choice = next((t for t in ("Later", "Not now", "No thanks", "OK", "Got it") if t in texts), None)
            if not choice:
                break
            ui.tap(choice, tries=1)
            time.sleep(2)
        labels = [n[0] or n[1] for n in ui.nodes() if n[0] or n[1]][:25]
        return "pass", "on screen: " + ", ".join(labels)
    run("App opens", opens)
    run("Stream a song (Bandcamp)", lambda: stream("perturbator future club", "Future Club"), needs=["App opens"])
    run("Stream a song (YouTube)", lambda: stream("kevin macleod monkeys spinning monkeys", "Monkeys"),
        needs=["App opens"])
    playing = next((s for s in ("Stream a song (YouTube)", "Stream a song (Bandcamp)") if status_of(s) == "pass"),
                   "Stream a song (Bandcamp)")

    def pause_resume():
        ui.sh("input keyevent 127")        # media pause (headphone button)
        time.sleep(2)
        s1, p1, _ = session()
        time.sleep(3)
        s2, p2, _ = session()
        ui.sh("input keyevent 126")        # media play
        ok, how = plays(seconds=4, wait=15)
        held = s2 == "2" and abs(p2 - p1) < 500
        return ("pass" if held and ok else "fail"), f"paused: state={s2}, held={held}; resumed: {how}"
    run("Pause and resume", pause_resume, needs=[playing])

    def podcast():
        ui.tap("Home")
        if not ui.tap("Podcasts", tries=3):
            return "fail", "no Podcasts button on Home"
        time.sleep(6)
        found = ui.nodes()
        shows = [n for n in found if n[0] and n[4] > 500 and n[0] not in ("Podcasts", "All", "Music", "Audiobooks")]
        if not shows:
            return "fail", "no podcasts listed"
        ui.sh(f"input tap {shows[0][2]} {shows[0][3]}")
        time.sleep(8)
        ui.adb("logcat", "-c")
        if not (ui.tap("Play", tries=2) or ui.tap("Play latest episode", exact=False, tries=1)):
            return "fail", f"opened “{shows[0][0]}” but found no Play button"
        ok, how = plays()
        if ok:
            return "pass", f"{shows[0][0]}: {how}"
        return ("blocked" if blocked_in_log() else "fail"), f"{shows[0][0]}: {how} | " + " / ".join(app_log(6))
    run("Play a podcast episode", podcast, needs=["App opens"])

    def settings():
        ui.open_settings("Playback")
        texts = " ".join(n[0] for n in ui.nodes())
        return ("pass" if "Playback" in texts else "fail"), "Settings → Playback shown" if "Playback" in texts \
            else "Settings → Playback didn't open"
    run("Open Settings", settings, needs=["App opens"])

    log = ui.adb("logcat", "-d").decode(errors="replace")
    crashes = log.count("FATAL EXCEPTION") + log.count("ANR in " + PKG)
    steps.append({"step": "No crashes", "status": "pass" if crashes == 0 else "fail",
                  "detail": f"{crashes} crash(es) / not-responding in the log"})
    with open(os.path.join(OUT, "logcat.txt"), "w", encoding="utf-8") as f:
        f.write(log)
    with open(os.path.join(OUT, "journey.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps}, f, indent=1)
    icons = {"pass": "✅ pass", "fail": "❌ FAIL", "blocked": "🚫 blocked here", "skipped": "⏭ skipped"}
    md = ["### Sevbify end-to-end (Android emulator)", "", "| Step | Result | Details |", "|---|---|---|"]
    md += [f"| {s['step']} | {icons[s['status']]} | {s['detail'].replace('|', '/')[:400]} |" for s in steps]
    with open(os.path.join(OUT, "journey.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

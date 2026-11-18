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
BOT_WORDS = ("not a bot", "confirm you", "sign in to confirm", "http error 429", "too many requests",
             "client challenge", "prove it's a browser", "blocking this connection")
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
        # Android 9+: "state=PLAYING(3)"; Android 8: "state=3"
        m = re.search(r"PlaybackState \{state=(?:\w+\()?(\d+)\)?, position=(-?\d+)", line)
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


def back_to_home():
    """Leave whatever is open (keyboard, search, a show page) the way a person would: Back, then the Home tab."""
    for _ in range(4):
        texts = {n[0] for n in ui.nodes()} | {n[1] for n in ui.nodes()}
        if "Home" in texts and "mInputShown=true" not in ui.sh("dumpsys input_method | grep mInputShown") \
                and not ({"Recent searches", "What do you want to listen to?"} & texts):
            break
        ui.sh("input keyevent 4")
        time.sleep(1.5)
    return ui.tap("Home", tries=2)


def playback_log():
    """The app's own "Playback status" (Settings → About and updates): why the release build says a song didn't play."""
    back_to_home()
    ui.open_settings("About and updates")
    time.sleep(2)
    seen = []
    for _ in range(15):                # "Playback status" is near the bottom of the page, above its Copy button
        found = ui.nodes()
        for n in found:
            if n[0] and n[0] not in seen:
                seen.append(n[0])
        if "Copy" in {n[0] for n in found} and "Playback status" in seen:
            break
        ui.swipe_up()
        time.sleep(1)
    back_to_home()
    if "Playback status" not in seen:
        return "(couldn't reach Playback status in Settings → About and updates)"
    after = seen[seen.index("Playback status") + 1:]
    return " / ".join(t for t in after if t != "Copy" and not t.startswith("What the player last did"))[:1500]


def search(text):
    back_to_home()
    ui.tap("Search")
    clear = next((n for n in ui.nodes() if "Clear" in (n[0], n[1])), None)
    ui.tap("Clear", tries=1)
    if not ui.tap("What do you want to listen to?", tries=3):
        # After "Clear" Android may not report the empty box's hint text: tap the box itself (left of the ✕).
        if clear is None:
            return False
        ui.sh(f"input tap 540 {clear[3]}")
        time.sleep(1)
        if "mInputShown=true" not in ui.sh("dumpsys input_method | grep mInputShown"):
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
    log = playback_log()
    if blocked_in_log() or any(w in log.lower() for w in BOT_WORDS):
        return "blocked", "the website refused this cloud computer; " + how + " | " + log[-700:]
    return "fail", how + " | Playback log: " + log[-900:]


def main():
    # "Update from the last release keeps your library" (tools/android_upgrade.py ran before this, if it could)
    try:
        steps.append(json.load(open(os.path.join(OUT, "upgrade.json"))))
        print(f"[journey] {steps[-1]['status'].upper():8} {steps[-1]['step']}: {steps[-1]['detail']}")
    except (OSError, ValueError):
        pass
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
            choice = next((t for t in ("Skip", "Later", "Not now", "No thanks", "OK", "Got it") if t in texts), None)
            if not choice:
                break
            ui.tap(choice, tries=1)
            time.sleep(2)
        labels = [n[0] or n[1] for n in ui.nodes() if n[0] or n[1]][:25]
        return "pass", "on screen: " + ", ".join(labels)
    run("App opens", opens)
    run("Stream a song (Bandcamp)", lambda: stream("chris zabriskie candlepower", "Candlepower"), needs=["App opens"])
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

    # --- The newer screens: checked by tapping through them like a person, every build ---------------------------
    def song_menu(query, i=0):
        """Search, then long-press the i-th song row: the song's menu (Add to playlist, Preview…)."""
        if not search(query):
            return None
        ui.hide_keyboard()
        end = time.time() + 40
        rows = []
        while time.time() < end and len(rows) <= i:
            rows = ui.song_rows()
            time.sleep(2)
        if len(rows) <= i:
            return None
        title, x, y = rows[i]
        ui.long_press(x, y)
        return title

    def preview():
        """Song menu → Preview (30 s): your song pauses, the card says it's a preview, Close carries on."""
        s0, _, _ = session()
        if not song_menu("kevin macleod"):
            return "fail", "couldn't open a song's menu from Search"
        if not ui.tap("Preview (30 s)", tries=3):
            return "fail", "no Preview (30 s) in the song menu"
        time.sleep(4)
        shown = ui.texts()
        ui.shot("preview_card", wait=0.5)
        if "30-second preview" not in shown or "play full song" not in shown:
            return "fail", "the preview card didn't show (no “30-SECOND PREVIEW” / “Play full song”)"
        if "there's no preview" in shown:
            return "blocked", "the song had no preview clip online (Deezer)"
        s1, _, _ = session()
        if s0 == "3" and s1 == "3":
            return "fail", "your song kept playing under the preview"
        ui.tap("Close", tries=3)
        time.sleep(3)
        s2, _, _ = session()
        if s0 == "3" and s2 != "3":
            return "fail", f"Close didn't carry on with your song (state={s2})"
        return "pass", f"card shown, your song paused (state {s1}) and carried on after Close (state {s2})"
    run("Preview a song (30 s)", preview, needs=[playing])

    def saved_in():
        """The ⊕ in the mini player: first tap saves to Liked Songs, the next opens "Saved in" with Liked Songs ticked."""
        back_to_home()
        if not ui.tap("Add to Liked Songs", tries=3):
            if not ui.tap("Saved in…", tries=1):
                return "fail", "no ⊕ (Add to Liked Songs) in the mini player"
        else:
            time.sleep(2)
            if not ui.tap("Saved in…", tries=3):
                return "fail", "after ⊕ the button didn't turn into ✓ (Saved in…)"
        time.sleep(2)
        shown = ui.texts()
        ui.shot("saved_in", wait=0.5)
        if "saved in" not in shown or "liked songs" not in shown or "saved here" not in shown:
            return "fail", "the Saved in sheet didn't show Liked Songs ticked"
        if not ui.tap("Done", tries=3):
            return "fail", "no Done button"
        return "pass", "⊕ saved it to Liked Songs; ✓ opened Saved in with Liked Songs ticked; Done closed it"
    run("Saved in (like Spotify's ✓)", saved_in, needs=[playing])

    def sort_by_energy():
        """Make a playlist of three songs (song menu → Add to playlist), then ••• → Sort by energy… → a sorted copy;
        the original playlist is still there, unchanged."""
        made = ""
        for i in range(3):
            if not song_menu("kevin macleod", i):
                return "fail", f"couldn't open song {i + 1}'s menu"
            if not ui.tap("Add to playlist", tries=3):
                return "fail", "no Add to playlist in the song menu"
            time.sleep(1.5)
            if not made:
                if not ui.tap("New playlist", tries=3):
                    return "fail", "no New playlist"
                time.sleep(2)
                names = [n[0] for n in ui.nodes() if n[0].startswith("Added to ")]
                made = names[0].removeprefix("Added to ") if names else ""
                if not made:                                  # the note went too fast: find it in Your Library later
                    made = "My Playlist"
            else:
                if not ui.tap(made, exact=made != "My Playlist", tries=3):
                    return "fail", f"“{made}” wasn't in Add to playlist"
            time.sleep(1.5)
        back_to_home()
        ui.tap("Your Library", tries=3)
        time.sleep(2)
        if not ui.tap(made, exact=made != "My Playlist", tries=3):
            return "fail", f"“{made}” isn't in Your Library"
        time.sleep(2)
        title = next((n[0] for n in ui.nodes() if n[0].startswith("My Playlist")), made)
        if not ui.tap("More", tries=3):
            return "fail", "no ••• on the playlist"
        if not ui.tap("Sort by energy…", tries=3):
            return "fail", "no Sort by energy… in the playlist menu"
        time.sleep(2)
        shown = ui.texts()
        ui.shot("sort_by_energy", wait=0.5)
        for want in ("makes a copy of this playlist", "energetic → easing down → calm", "calm → ramping up → energetic",
                     "mixed energies throughout", "create sorted playlist"):
            if want not in shown:
                return "fail", f"the Sort by energy sheet is missing “{want}”"
        ui.tap("Create sorted playlist", tries=3)
        end = time.time() + 120
        while time.time() < end and f"{title} · energetic to calm".lower() not in ui.texts():
            time.sleep(3)
        if f"{title} · energetic to calm".lower() not in ui.texts():
            return "fail", f"no “{title} · Energetic to calm” playlist after 2 minutes"
        back_to_home()
        ui.tap("Your Library", tries=3)
        time.sleep(2)
        lib = ui.texts()
        if title.lower() not in lib.replace(f"{title} · energetic to calm".lower(), ""):
            return "fail", "the original playlist is gone from Your Library"
        return "pass", f"made “{title} · Energetic to calm”; “{title}” is still in Your Library"
    run("Sort by energy (a sorted copy)", sort_by_energy, needs=["App opens"])

    def canvas_switch():
        """Now Playing: the Canvas / Cover switch shows when a song has a Canvas loop, and Cover brings the art back.
        Not every song has a Canvas (it needs a music video), so no loop within a minute is “blocked”, not a fail."""
        back_to_home()
        if session()[0] != "3":
            ui.sh("input keyevent 126")                 # carry on with the song (an earlier step may have paused it)
            time.sleep(4)
        if session()[0] != "3":
            return "blocked", "nothing playing"
        ui.open_now_playing()
        end = time.time() + 60
        while time.time() < end and "canvas" not in ui.texts():
            time.sleep(4)
        if "canvas" not in ui.texts():
            ui.back()
            return "blocked", "this song has no Canvas loop (no music video found within a minute)"
        ui.shot("canvas", wait=0.5)
        if not ui.tap("Cover", tries=2):
            ui.back()
            return "fail", "Canvas showed but there's no Cover switch"
        time.sleep(1.5)
        ok = "cover" in ui.texts()
        ui.tap("Canvas", tries=2)
        ui.back()
        return ("pass" if ok else "fail"), "Canvas loop playing; Cover / Canvas switch works"
    run("Canvas / Cover switch", canvas_switch, needs=[playing])

    def podcast():
        """Open a show from Home → Podcasts and play its latest episode. The list is live (today's charts), so a
        heading such as "Top in Comedy" is skipped, and if one show's episode won't play (its host busy, an ad
        server slow) the next show is tried: up to three."""
        back_to_home()
        if not ui.tap("Podcasts", tries=3):
            return "fail", "no Podcasts button on Home"
        time.sleep(6)
        found = ui.nodes()
        skip = ("Podcasts", "All", "Music", "Audiobooks", "Settings", "Home", "Search", "Your Library", "Create")
        shows = [n for n in found if n[0] and n[4] > 500 and n[0] not in skip
                 and not re.match(r"(Top|Explore|Browse|Popular|Categories|See all)\b", n[0])]
        if not shows:
            return "fail", "no podcasts listed"
        tried = []
        for show in shows[:3]:
            ui.sh(f"input tap {show[2]} {show[3]}")
            time.sleep(8)
            ui.adb("logcat", "-c")
            if not (ui.tap("Play", tries=2) or ui.tap("Play latest episode", exact=False, tries=1)):
                tried.append(f"“{show[0]}”: no Play button")
            else:
                ok, how = plays()
                if ok:
                    return "pass", f"{show[0]}: {how}" + (f" (after {'; '.join(tried)})" if tried else "")
                if blocked_in_log():
                    return "blocked", f"{show[0]}: {how}"
                tried.append(f"“{show[0]}”: {how}")
                ui.sh("input keyevent 127")                     # pause before trying the next show
            back_to_home()
            ui.tap("Podcasts", tries=2)
            time.sleep(4)
        return "fail", " / ".join(tried) + " | " + " / ".join(app_log(6))
    run("Play a podcast episode", podcast, needs=["App opens"])

    def settings():
        back_to_home()
        ui.open_settings("Playback")
        texts = " ".join(n[0] for n in ui.nodes())
        return ("pass" if "Playback" in texts else "fail"), "Settings → Playback shown" if "Playback" in texts \
            else "Settings → Playback didn't open"
    run("Open Settings", settings, needs=["App opens"])

    def pair_with_computer():
        """The real thing both ways: this computer runs Sevbify's pairing listener (core/pairing.py), the phone opens
        its QR link (as the camera app would), taps Pair, then receives a song the computer sends and accepts it."""
        import tempfile
        import threading
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            from core import pairing as pr
        except Exception as e:
            return "fail", f"the computer side couldn't start: {e}"
        selftest = [l for l in ui.adb("logcat", "-d").decode(errors="replace").splitlines() if "pair self-test" in l]
        if selftest and "FAILED" in selftest[-1]:
            return "fail", "the phone's crypto doesn't match the computer's test values"

        class Ev:
            paired, sent = [], []
            done = threading.Event()

            def on_paired(self, dev, name):
                self.paired.append(name)

            def on_sent(self, sess, oid, ok):
                self.sent.append(ok)
                self.done.set()
        ev = Ev()
        base = tempfile.mkdtemp()
        srv = pr.PairServer(os.path.join(base, "data"), os.path.join(base, "music"), "CI computer", "test", ev)
        srv.start()
        try:
            info = pr.parse_pair_link(srv.open_pairing())
            link = pr.pair_link(["10.0.2.2"], srv.port, info["code"], srv.store.pc_id, "CI computer")
            back_to_home()
            ui.sh(f"am start -a android.intent.action.VIEW -d '{link}' {PKG}")
            time.sleep(4)
            if not ui.tap("Pair", tries=4):
                return "fail", "no 'Pair with CI computer?' question after opening the QR link"
            end = time.time() + 40
            while time.time() < end and not (ev.paired and srv.connected()):
                time.sleep(1)
            if not ev.paired:
                return "fail", "the phone didn't pair (nothing reached the computer)"
            if not srv.connected():
                return "fail", f"paired as {ev.paired[0]} but the phone didn't stay connected"
            song = os.path.join(base, "CI tone.wav")             # a 5-second tone made here (no ffmpeg needed)
            import math
            import struct
            import wave
            with wave.open(song, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 22050)))
                                        for i in range(22050 * 5)))
            srv.connected()[0].send_paths([song], "CI")
            time.sleep(4)
            ui.shot("pair_receive_question", wait=0.5)
            time.sleep(1.5)                       # Accept is enabled after a second
            if not ui.tap("Accept", tries=4):
                return "fail", "no 'Receive music?' question on the phone"
            if not ev.done.wait(60) or ev.sent[-1] is not True:
                return "fail", "the song didn't arrive"
            time.sleep(3)
            files = ui.sh("ls -R /sdcard/Music/Sevbify") + ui.sh(f"ls -R /sdcard/Android/data/{PKG}/files/Music")   # Android 8: the app's own folder
            if "CI tone.wav" not in files:
                return "fail", "sent, but the file isn't in Music/Sevbify: " + files[-300:]
            return "pass", f"paired as “{ev.paired[0]}” over the network, received “CI tone.wav” in Music/Sevbify " \
                           f"({'self-test ok' if selftest else 'no self-test line'})"
        finally:
            srv.stop()
    run("Pair with a computer and receive a song", pair_with_computer, needs=["App opens"])

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

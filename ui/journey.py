"""End-to-end check of the real, packaged app: what a person does in their first ten minutes.

Run by the automatic tests ("End-to-end" workflow) as  Sevbify --journey <report folder>  and then, after the app
has closed,  Sevbify --journey-again <report folder>  (checks what you did is still there after a restart).

It works the app through its own controls (typing in the search box, the same play/download/follow calls the
buttons make), waits for real results from the internet, takes a screenshot after every step, and writes
journey.json + journey.md. Every step ends as exactly one of:

  pass     it really happened (e.g. the song's position moved on for several seconds)
  fail     it didn't, and nothing outside Sevbify explains it
  blocked  a website refused this test computer (YouTube's "confirm you're not a bot" check refuses cloud
           computers); this says nothing either way about how it works on a home connection
  skipped  an earlier step it needs failed

Nothing is marked "pass" on a guess. Test computers have no speakers, so sound goes to VLC's silent output: the
check is that VLC decodes the stream and the position moves, which is what goes wrong when "songs don't play".
"""
import json
import os
import sys
import time
import traceback

from PyQt6.QtWidgets import QApplication

BOT_WORDS = ("not a bot", "confirm you", "sign in to confirm", "http error 429", "too many requests",
             "client challenge", "prove it's a browser", "blocking this connection")

# Songs picked because they are reliably online: one Bandcamp has (Bandcamp works from cloud computers), and one
# only on YouTube (tells us whether YouTube refuses this computer).
BANDCAMP_SONG = ("Chris Zabriskie", "Candlepower")   # openly licensed (CC BY)
YOUTUBE_SONG = ("Kevin MacLeod", "Monkeys Spinning Monkeys")
PODCAST_SEARCH = "NPR News Now"
OWN_SONG = ("Chris Zabriskie", "Candlepower")      # a song file of "your own" (a tone, tagged like this song)


def _make_tagged_wav(path, artist_title, seconds=20):
    import math
    import struct
    import wave
    rate = 22050
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                               for i in range(rate * seconds)))
    from mutagen.wave import WAVE
    from mutagen.id3 import TIT2, TPE1
    tagged = WAVE(path)
    tagged.add_tags()
    tagged.tags.add(TPE1(encoding=3, text=artist_title[0]))
    tagged.tags.add(TIT2(encoding=3, text=artist_title[1]))
    tagged.save()


class Journey:
    def __init__(self, window, out_dir):
        # If the app ever stops responding during the journey, print where every thread is stuck (every 5 minutes
        # of no progress), so a freeze on a test computer can be diagnosed instead of just timing out.
        try:
            import faulthandler
            import sys as _sys
            faulthandler.dump_traceback_later(300, repeat=True, file=_sys.stderr)
            self._watchdog = faulthandler
        except Exception:
            self._watchdog = None
        self.w = window
        self.app = QApplication.instance()
        self.out = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.steps = []
        self.started = time.time()
        self.dialogs = []
        # A box that pops up on its own (an update offer, a warning) would wait forever for a click here: it is
        # written down (a person would have seen it) and closed.
        from PyQt6.QtCore import QTimer
        self._dialog_timer = QTimer()
        self._dialog_timer.timeout.connect(self._close_dialogs)
        self._dialog_timer.start(1000)
        # Labels or buttons that flash up as their own little windows (the flicker when opening a podcast).
        from PyQt6.QtCore import QObject, QEvent, Qt
        from PyQt6.QtWidgets import QAbstractButton, QDialog, QFrame, QLabel
        self.strays = []
        strays = self.strays

        class Spy(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Show and isinstance(obj, (QLabel, QAbstractButton, QFrame)) \
                        and not isinstance(obj, QDialog) and obj.isWindow() \
                        and obj.windowType() == Qt.WindowType.Window:
                    strays.append(f"{type(obj).__name__} {obj.width()}x{obj.height()}")
                return False
        self._spy = Spy()
        self.app.installEventFilter(self._spy)

    def _close_dialogs(self):
        box = self.app.activeModalWidget()
        if box is None:
            return
        text = " ".join(filter(None, [box.windowTitle()] + [getattr(box, "text", lambda: "")()]))[:400]
        self.dialogs.append(text)
        print(f"[journey] dialog popped up and was closed: {text}", flush=True)
        box.reject() if hasattr(box, "reject") else box.close()

    # ------------------------------------------------------------------ helpers
    def wait(self, cond, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self.app.processEvents()
            try:
                if cond():
                    return True
            except Exception:
                pass
            time.sleep(0.05)
        self.app.processEvents()
        try:
            return bool(cond())
        except Exception:
            return False

    def shot(self, name):
        try:
            self.app.processEvents()
            path = os.path.join(self.out, f"{len(self.steps) + 1:02d}-{name}.png")
            self.w.grab().save(path)
            return os.path.basename(path)
        except Exception:
            return ""

    def record(self, name, status, detail, shot=None, seconds=None):
        self.steps.append({"step": name, "status": status, "detail": str(detail)[:1500],
                           "seconds": round(seconds, 1) if seconds is not None else None,
                           "screenshot": shot if shot is not None else self.shot(
                               "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-"))})
        print(f"[journey] {status.upper():8} {name}: {str(detail)[:300]}", flush=True)

    def run_step(self, name, fn, needs=None):
        if needs and any(self._status(n) not in ("pass",) for n in needs):
            self.record(name, "skipped", "needs: " + ", ".join(needs), shot="")
            return
        t0 = time.time()
        if getattr(self, "_watchdog", None):                 # a new step = progress: restart the 5-minute clock
            import sys as _sys
            self._watchdog.dump_traceback_later(300, repeat=True, file=_sys.stderr)
        print(f"[journey] starting {name}", flush=True)
        try:
            status, detail = fn()
        except Exception:
            status, detail = "fail", "crashed:\n" + traceback.format_exc()
        self.record(name, status, detail, seconds=time.time() - t0)

    def _status(self, name):
        return next((s["status"] for s in self.steps if s["step"] == name), "missing")

    def position_moves(self, seconds=6):
        """True when VLC really plays: playing state and the position moving forward."""
        w = self.w
        if not self.wait(lambda: w._reached_playing, 90):
            return False, "never started playing (90 s)"
        a = w.player.get_time()
        self.wait(lambda: False, seconds)
        b = w.player.get_time()
        if b - a < (seconds - 2) * 1000:
            return False, f"started, but the position only moved {b - a} ms in {seconds} s"
        return True, f"position moved {b - a} ms in {seconds} s"

    def blocked_reason(self, text):
        t = str(text).lower()
        return any(word in t for word in BOT_WORDS)

    # ------------------------------------------------------------------ steps
    def step_opens(self):
        ok = self.wait(lambda: self.w.isVisible(), 20)
        return ("pass" if ok else "fail"), f"window open, {len(self.w.songs)} songs in the library"

    def step_search(self):
        w = self.w
        w.show_search()
        w.search_input.setText(" ".join(reversed(BANDCAMP_SONG)) + " " + BANDCAMP_SONG[0])
        ok = self.wait(lambda: w.web_table.isVisible() and w.web_table.songs_in_view(), 45)
        if not ok:
            return "fail", "no web results after 45 s; status says: " + w.search_web_status.text()
        songs = w.web_table.songs_in_view()
        return "pass", f"{len(songs)} results, first: {songs[0].artist} - {songs[0].title}"

    def _find_song(self, artist, title):
        from core import streamer
        res, err = {}, []
        self.w.online_call(streamer.find_full_song, artist, title, 0, self.w.user_data.download_source,
                           on_done=res.update, on_error=err.append)
        self.wait(lambda: res or err, 180)
        return res, (err[0] if err else None)

    def _play_found(self, artist, title, want_source=None):
        """Look the song up the way playback does, then play it from the search results and check it plays."""
        w = self.w
        res, err = self._find_song(artist, title)
        if err is not None:
            if self.blocked_reason(err):
                return "blocked", f"refused by the website: {err}"
            return "fail", f"song not found: {err}"
        from core.online.models import OnlineTrack
        from core.online.remote_song import RemoteSong
        hits = [s for s in w.web_table.songs_in_view() if title.lower() in s.title.lower()] if w.web_table.isVisible() else []
        song = hits[0] if hits else RemoteSong(OnlineTrack(title, artist, source="deezer"))
        w.play_song(song, queue=[song], source="Journey")
        ok, how = self.position_moves()
        timings = res.get("timings")
        skipped = res.get("skipped") or {}
        detail = f"source: {res.get('source')}; {how}" + (f"; lookup timings: {timings}" if timings else "") + \
            (f"; not used: {skipped}" if skipped else "")
        if ok and want_source and res.get("source") != want_source:
            # It played, but from somewhere else: this step is about that one site, so say so honestly.
            why = skipped.get(want_source) or skipped.get(want_source + " link") or f"{want_source} didn't have it"
            if self.blocked_reason(why):
                return "blocked", f"{want_source} refused this computer ({why[:160]}); played from {res.get('source')} instead"
            return "fail", f"not from {want_source} ({why[:200]}); played from {res.get('source')} instead. {detail}"
        return ("pass" if ok else "fail"), detail

    def step_stream_bandcamp(self):
        return self._play_found(*BANDCAMP_SONG, want_source="Bandcamp")

    def step_stream_youtube(self):
        return self._play_found(*YOUTUBE_SONG, want_source="YouTube")

    def step_pause_resume_skip(self):
        w = self.w
        w.play_pause_song()
        paused_at = w.player.get_time()
        self.wait(lambda: False, 2)
        still = abs(w.player.get_time() - paused_at) < 500
        w.play_pause_song()
        resumed = self.wait(lambda: w.player.get_time() > paused_at + 1000, 10)
        if not (still and resumed):
            return "fail", f"pause held: {still}, resumed: {resumed}"
        w.player.set_time(60_000)
        moved = self.wait(lambda: w.player.get_time() >= 59_000, 10)
        return ("pass" if moved else "fail"), f"pause held, resumed, seek to 1:00 {'worked' if moved else 'did not move'}"

    def step_download(self):
        w = self.w
        from core.online.models import OnlineTrack
        from core.online.remote_song import RemoteSong
        song = RemoteSong(OnlineTrack(BANDCAMP_SONG[1], BANDCAMP_SONG[0], source="deezer"))
        folder = w.download_folder()
        added = w.download_songs([song])
        if not added:
            return "fail", "the download didn't start"
        done = self.wait(lambda: not w.downloads.is_busy(), 300)
        files = [os.path.join(r, f) for r, _d, fs in os.walk(folder) for f in fs
                 if f.lower().endswith((".mp3", ".m4a", ".flac", ".opus", ".ogg"))]
        if not done:
            notes = "; ".join(f"{t}: {state} {note}" for _k, state, t, _a, note in w.downloads.items())
            return "fail", f"still downloading after 5 minutes ({w.downloads.summary()}; {notes})"
        if not files:
            # Why: run the same download again by itself and keep its log (the app shows only a short note).
            lines = []
            try:
                from core import downloader
                e = downloader.engine()
                import tempfile
                bc = e.search_bandcamp(f"{BANDCAMP_SONG[0]} - {BANDCAMP_SONG[1]}")
                lines.append(f"Bandcamp search: {bc}")
                if bc.get("url"):
                    e.download_bandcamp_mp3(bc["url"], f"{BANDCAMP_SONG[0]} - {BANDCAMP_SONG[1]}", tempfile.mkdtemp(),
                                            lines.append)
            except Exception as exc:
                lines.append(f"diagnosis broke: {exc!r}")
            with open(os.path.join(self.out, "download-log.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(map(str, lines)))
            summary = "; ".join(f"{t}: {state} {note}" for _k, state, t, _a, note in w.downloads.items()) or "no notes"
            if self.blocked_reason(summary + " " + " ".join(map(str, lines))):
                return "blocked", (f"refused by the website (Bandcamp asked this test computer to prove it's a browser; "
                                   f"home connections aren't asked): " + " / ".join(map(str, lines))[-400:])
            return "fail", f"finished but no song file: {summary} | log: " + " / ".join(map(str, lines))[-900:]
        size = os.path.getsize(files[0])
        if size < 500_000:
            return "fail", f"{os.path.basename(files[0])} is only {size} bytes"
        return "pass", f"{os.path.basename(files[0])} ({size // 1024} KB) in {folder}"

    def step_podcast(self):
        w = self.w
        from core import podcasts
        found = []
        w.online_call(podcasts.search, w.net, PODCAST_SEARCH, 10, "us", on_done=found.extend,
                      on_error=lambda e: found.append(e))
        if not self.wait(lambda: found, 45) or isinstance(found[0], Exception) or not found:
            return "fail", f"podcast search gave nothing: {found[:1]}"
        show = found[0]
        w.open_show(show, follow=True)
        ok = self.wait(lambda: w._show_ctx and w._show_ctx["items"], 60)
        if not ok:
            return "fail", f"{show.title}: no episodes loaded"
        ep = w._show_ctx["items"][0]
        w.play_song(ep, queue=w._show_ctx["items"][:3], source=show.title)
        played, how = self.position_moves()
        followed = w.is_followed(w._show_ctx["obj"].key)
        return ("pass" if played and followed else "fail"), \
            f"{show.title}: {len(w._show_ctx['items'])} episodes, followed: {followed}, latest episode: {how}"

    def step_episode_tools(self):
        """Podcast page: All Episodes / Unplayed / In Progress, Find in this show, Newest/Oldest."""
        w = self.w
        ctx = w._show_ctx
        if not ctx or not ctx.get("items"):
            return "fail", "no podcast open"
        total = len(w.show_page.rows)
        w.show_page.filter_changed.emit("in_progress")
        in_progress = len(w.show_page.rows)
        w.show_page.filter_changed.emit("all")
        word = ctx["items"][0].title.split()[0]
        w.show_page.search_changed.emit(word)
        self.wait(lambda: False, 1)
        found = len(w.show_page.rows)
        w.show_page.search_changed.emit("")
        self.wait(lambda: False, 1)
        w.show_page.sort_changed.emit("oldest")
        oldest_first = w.show_page.sort_btn.text().startswith("Oldest")
        w.show_page.sort_changed.emit("newest")
        ok = total > 0 and in_progress <= 1 and 1 <= found <= total and oldest_first
        return ("pass" if ok else "fail"), (f"{total} episodes; in progress: {in_progress}; '{word}' finds {found}; "
                                           f"oldest-first sort: {oldest_first}")

    def step_episode_download(self):
        """Download the shortest of the latest episodes; it must land in Downloads/Podcasts as a real audio file."""
        w = self.w
        ctx = w._show_ctx
        if not ctx or not ctx.get("items"):
            return "fail", "no podcast open"
        from ui.shows_controller import item_key
        ep = min(ctx["items"][:4], key=lambda e: e.track.duration_ms or 10 ** 9)
        key = item_key(ep)
        if not w.download_items([ep]):
            return "fail", "the download didn't start"
        ok = self.wait(lambda: key in w.user_data.offline, 240)
        path = w.user_data.offline.get(key)
        if not ok or not isinstance(path, str) or not os.path.isfile(path):
            return "fail", f"no file after 4 minutes (status: {w.status_label.text() if hasattr(w, 'status_label') else '?'})"
        size = os.path.getsize(path)
        in_podcasts = os.path.normcase(os.path.join(w.download_folder(), "Podcasts")) in os.path.normcase(path)
        w.save_now()
        ok = size > 100_000 and in_podcasts
        return ("pass" if ok else "fail"), (f"“{ep.title}” saved as {os.path.basename(path)} ({size // 1024} KB), "
                                           f"in the Podcasts folder: {in_podcasts}")

    def step_own_music(self):
        """Add a music folder with a song in it (tagged like a downloaded song), put it in a playlist and play it."""
        w = self.w
        folder = os.path.join(self.out, "my music")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "my song.wav")
        _make_tagged_wav(path, OWN_SONG, seconds=20)
        if not w.add_music_folder(folder):
            return "fail", "the folder wasn't added"
        if not self.wait(lambda: any(s.file_path and os.path.normcase(s.file_path) == os.path.normcase(path)
                                     for s in w.songs), 60):
            return "fail", f"the song never showed up in Your Library ({len(w.songs)} songs)"
        song = next(s for s in w.songs if os.path.normcase(s.file_path) == os.path.normcase(path))
        if (song.artist, song.title) != OWN_SONG:
            return "fail", f"tags read as {song.artist} - {song.title}"
        w.create_playlist("Journey mine", [song])
        w.play_song(song, queue=[song], source="Your Library")
        played, how = self.position_moves(5)
        w.player.stop()
        w.save_now()
        return ("pass" if played else "fail"), f"{song.artist} - {song.title}: {how}"

    def delete_own_song(self):
        """Between the two runs: the song file is deleted, the way a person tidying their folders would."""
        path = os.path.join(self.out, "my music", "my song.wav")
        for _ in range(20):            # Windows: VLC may hold the file for a moment after stopping
            try:
                os.remove(path)
                return True
            except FileNotFoundError:
                return True
            except OSError:
                self.wait(lambda: False, 0.5)
        return False

    def step_activity_log(self):
        from core import activity_log
        try:
            text = open(activity_log.path(), encoding="utf-8").read()
        except OSError as e:
            return "fail", f"no activity log: {e}"
        ok = "play " in text and "start " in text and "googlevideo.com/videoplayback?" not in text
        return ("pass" if ok else "fail"), f"{len(text.splitlines())} lines, links shortened: {'?' not in text}"

    def step_settings(self):
        w = self.w
        w.open_settings()
        ok = self.wait(lambda: w.stack.currentWidget() is getattr(w, "settings_page", None), 5)
        return ("pass" if ok else "fail"), "settings page shown" if ok else "settings page didn't open"

    def step_zoom(self):
        """Ctrl + then Ctrl 0: the size changes straight away (no restart), and the window keeps its size."""
        w = self.w
        before = w.frameGeometry().size()
        w.change_zoom(+1)
        self.wait(lambda: w.isVisible(), 5)
        live = w._zoom_at_start == 110
        dpr = round(w.devicePixelRatio(), 2)
        self.shot("zoom-110")
        w.change_zoom(0)
        self.wait(lambda: w.isVisible(), 5)
        back = w._zoom_at_start == 100 and w.isVisible()
        after = w.frameGeometry().size()
        if not (live and back):
            return "fail", "zoom needed a restart (Qt's live zoom wasn't found here)"
        same = abs(after.width() - before.width()) <= 4 and abs(after.height() - before.height()) <= 4
        size = "kept" if same else f"{before.width()}x{before.height()} -> {after.width()}x{after.height()}"
        return "pass", f"zoomed live to 110% (pixel ratio {dpr}) and back; window size {size}"

    def step_playlist(self):
        w = self.w
        before = len(w.playlists)
        pl = w.create_playlist("Journey playlist", [w.current_song] if w.current_song is not None else ())
        if pl is None or len(w.playlists) != before + 1:
            return "fail", "no playlist was made"
        w.save_now()
        return "pass", f"playlist “{pl.name}” with {len(pl.songs)} song(s)"

    def run(self):
        w = self.w
        w.user_data.download_notice_accepted = True    # the one-time "I understand" box (a person clicks Yes)
        w.user_data.download_folder = os.path.join(self.out, "downloads")
        self.run_step("App opens", self.step_opens)
        self.run_step("Search the web", self.step_search, needs=["App opens"])
        self.run_step("Stream a song (Bandcamp)", self.step_stream_bandcamp, needs=["App opens"])
        self.run_step("Stream a song (YouTube)", self.step_stream_youtube, needs=["App opens"])
        playing = next((s for s in ("Stream a song (YouTube)", "Stream a song (Bandcamp)") if self._status(s) == "pass"), None)
        if playing is None and self.w._reached_playing and self.w.current_song is not None:
            # The site steps were refused here, but a song is playing (from another site): pause / seek can be
            # tested on that one.
            self.run_step("Pause, resume and seek", self.step_pause_resume_skip)
        else:
            self.run_step("Pause, resume and seek", self.step_pause_resume_skip,
                          needs=[playing or "Stream a song (Bandcamp)"])
        self.run_step("Make a playlist", self.step_playlist, needs=["App opens"])
        self.run_step("Download a song", self.step_download, needs=["App opens"])
        self.run_step("Find, follow and play a podcast", self.step_podcast, needs=["App opens"])
        self.run_step("Podcast filter, search and sort", self.step_episode_tools,
                      needs=["Find, follow and play a podcast"])
        self.run_step("Download a podcast episode", self.step_episode_download,
                      needs=["Find, follow and play a podcast"])
        self.run_step("Your own music plays", self.step_own_music, needs=["App opens"])
        self.run_step("Open Settings", self.step_settings, needs=["App opens"])
        self.run_step("Zoom instantly", self.step_zoom, needs=["App opens"])
        self.run_step("Activity log is written", self.step_activity_log, needs=["App opens"])
        w.save_now()
        if self._status("Your own music plays") == "pass" and not self.delete_own_song():
            self.record("Delete the song file for the next run", "fail", "the file couldn't be deleted")
        return self.finish("journey")

    # ------------------------------------------------------------------ after a restart
    def run_again(self):
        w = self.w
        before = self._load("journey")
        w.user_data.download_notice_accepted = True
        self.run_step("App opens again", self.step_opens)

        def kept():
            names = [p.name for p in w.playlists]
            shows = [d.get("title") for d in w.user_data.shows]
            problems = []
            if any(s["step"] == "Make a playlist" and s["status"] == "pass" for s in before) and "Journey playlist" not in names:
                problems.append(f"playlist gone (have {names})")
            if any(s["step"] == "Find, follow and play a podcast" and s["status"] == "pass" for s in before) and not shows:
                problems.append("followed podcast gone")
            downloaded = any(s["step"] == "Download a song" and s["status"] == "pass" for s in before)
            if downloaded and not self.wait(lambda: any(not getattr(s, "is_remote", False) and
                                                       BANDCAMP_SONG[1].lower() in s.title.lower() for s in w.songs), 60):
                problems.append("downloaded song isn't in Your Library")
            if problems:
                return "fail", "; ".join(problems)
            return "pass", f"playlists {names}, podcasts {shows}, {len(w.songs)} songs in the library"
        self.run_step("Everything is still there after a restart", kept, needs=["App opens again"])
        local = [s for s in w.songs if not getattr(s, "is_remote", False)]

        def play_local():
            if not local:
                return "skipped", "no downloaded song to play"
            w.play_song(local[0], queue=local, source="Your Library")
            ok, how = self.position_moves()
            return ("pass" if ok else "fail"), f"{local[0].title}: {how}"
        self.run_step("Play the downloaded song", play_local, needs=["App opens again"])

        def episode_offline():
            if not any(s["step"] == "Download a podcast episode" and s["status"] == "pass" for s in before):
                return "skipped", "no episode was downloaded"
            from core.online.models import OnlineTrack
            from core.online.remote_song import RemoteSong
            key, path = next(iter(w.user_data.offline.items()), (None, None))
            info = w.user_data.offline_info.get(key) or {}
            if not path or not os.path.isfile(path) or not info.get("track"):
                return "fail", f"the downloaded episode is gone after the restart ({key}: {path})"
            ep = RemoteSong(OnlineTrack.from_dict(info["track"]))
            w.play_song(ep, queue=[ep], source="Downloaded")
            ok, how = self.position_moves()
            media = w.player.get_media()
            mrl = media.get_mrl() if media is not None else ""
            local = mrl.startswith("file:")
            return ("pass" if ok and local else "fail"), \
                f"“{ep.title}”: {how}; played from {'the downloaded file' if local else 'the internet: ' + mrl[:80]}"
        self.run_step("Play the downloaded episode", episode_offline, needs=["App opens again"])

        def deleted_song():
            if not any(s["step"] == "Your own music plays" and s["status"] == "pass" for s in before):
                return "skipped", "no song was added before the restart"
            pl = next((p for p in w.playlists if p.name == "Journey mine"), None)
            if pl is None or not pl.songs:
                return "fail", "the playlist with the deleted song is gone"
            gone = pl.songs[0]
            if gone.exists:
                return "fail", "the file wasn't deleted between the runs"
            if (gone.artist, gone.title) != OWN_SONG:
                return "fail", f"the deleted song came back as “{gone.artist} - {gone.title}”, so it can't be found online"
            w.show_playlist(pl)
            row = w.pl_table.item(0, 1)
            shown = row.text() if row is not None else ""
            queued = w.download_again([gone])
            ok = shown.endswith("⬇") and queued == 1
            return ("pass" if ok else "fail"), (f"shown as “{shown}” ({'missing' if not gone.exists else 'present'}), "
                                               f"remembered as {gone.artist} - {gone.title}, Download again queued {queued}")
        self.run_step("A deleted song is remembered and can be downloaded again", deleted_song,
                      needs=["App opens again"])
        return self.finish("again")

    # ------------------------------------------------------------------ report
    def _load(self, name):
        try:
            with open(os.path.join(self.out, name + ".json"), encoding="utf-8") as f:
                return json.load(f)["steps"]
        except (OSError, ValueError, KeyError):
            return []

    def finish(self, name):
        import platform
        info = {"system": f"{platform.system()} {platform.release()} ({platform.version()})", "python": sys.version.split()[0],
                "frozen": bool(getattr(sys, "frozen", False)), "seconds": round(time.time() - self.started)}
        try:
            from core import downloader
            info["yt_dlp"] = downloader.engine().ytdlp_version()
        except Exception:
            pass
        self._dialog_timer.stop()
        self.steps.append({"step": "No windows flashing up", "status": "fail" if self.strays else "pass",
                           "detail": (f"{len(self.strays)} flashed up, e.g. " + ", ".join(self.strays[:5]))
                           if self.strays else "none", "seconds": None, "screenshot": ""})
        with open(os.path.join(self.out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"info": info, "steps": self.steps, "dialogs": self.dialogs}, f, indent=1)
        failed = [s for s in self.steps if s["status"] == "fail"]
        return 1 if failed else 0


def write_markdown(out_dir, title):
    """journey.md: both runs as one table (also shown on the workflow's summary page)."""
    icons = {"pass": "✅ pass", "fail": "❌ FAIL", "blocked": "🚫 blocked here", "skipped": "⏭ skipped"}
    lines, info = [f"### {title}", "", "| Step | Result | Details |", "|---|---|---|"], {}
    for name in ("journey", "again"):
        try:
            with open(os.path.join(out_dir, name + ".json"), encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            if name == "again":
                lines.append("| Restart check | ❌ FAIL | the app didn't run a second time |")
            continue
        info = info or d["info"]
        for s in d["steps"]:
            detail = s["detail"].replace("|", "\\|").replace("\n", " ")[:400]
            secs = f" ({s['seconds']} s)" if s.get("seconds") else ""
            lines.append(f"| {s['step']}{secs} | {icons.get(s['status'], s['status'])} | {detail} |")
        for text in d.get("dialogs", []):
            lines.append(f"| A box popped up by itself | ⚠ note | {text.replace('|', '/')} |")
    if info:
        lines += ["", f"{info.get('system')} · yt-dlp {info.get('yt_dlp', '?')}"]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(out_dir, "journey.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return text

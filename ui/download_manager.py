"""Downloads songs in the background with SEVBY's engine (core/downloader.py), one at a time.

Songs found with Search or Radio sit in playlists / Saved for later as "not downloaded yet" slots.
Choosing Download puts them in this manager's queue. A worker thread fetches them (Bandcamp first,
then YouTube) into the download folder while the music keeps playing; the main window then rescans
and the slot fills in with the new file.

Only download music you have the right to download.
"""
import os
import threading
from collections import deque

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core import downloader

QUEUED, DOWNLOADING, FAILED, STOPPED = "queued", "downloading", "failed", "stopped"

import re as _re
# Failures that aren't the song's fault: the internet dropped, or the download drive is missing or full.
# Like UniFetcher's queue guard, the queue then pauses (the song waits) instead of failing song after song.
_NO_INTERNET = _re.compile(r"getaddrinfo|name resolution|timed out|timeout|connection (?:reset|refused|aborted)|"
                           r"network is unreachable|no route to host|temporary failure|urlopen error|"
                           r"unable to download webpage", _re.I)
_DRIVE = _re.compile(r"no space left|disk full|not enough space|errno 28|winerror 112|"
                     r"cannot find the path|no such file or directory|winerror 3\b|device is not ready|winerror 21", _re.I)


def pause_reason(note):
    """"internet" / "drive" when a failure means the queue should wait rather than the song fail, else ""."""
    note = note or ""
    if _DRIVE.search(note):
        return "drive"
    if _NO_INTERNET.search(note):
        return "internet"
    return ""


class _Worker(QThread):
    song_started = pyqtSignal(str)              # key
    song_finished = pyqtSignal(str, dict)       # key, engine result
    tools_missing = pyqtSignal(str)             # readable problem, nothing can be downloaded

    def __init__(self, manager):
        super().__init__()
        self.m = manager

    def run(self):
        problems = self.m.check_tools()
        if problems:
            self.tools_missing.emit(problems[0])
            return
        while True:
            job = self.m._take_next()
            if job is None:
                return
            key, line, folder, source = job
            self.song_started.emit(key)
            out = {}
            res = downloader.run_download(
                [line], folder, source, process=self.m.process,
                on_step=lambda t: setattr(self.m, "step_text", t),
                on_result=lambda _i, _n, _s, r: out.update(r))
            if res["stopped"]:
                out = {"status": "fail", "note": "stopped"}
            self.song_finished.emit(key, out or {"status": "fail", "note": "couldn't be downloaded"})
            if res["stopped"]:
                if self.m._cancel_one == key:          # only this song was cancelled: carry on with the rest
                    self.m._cancel_one = ""
                    downloader.Controls.reset()
                    continue
                return


class DownloadManager(QObject):
    changed = pyqtSignal()                       # anything about the queue changed (refresh the views)
    song_done = pyqtSignal(str, str, str)        # key, saved file path ("" if it was already there), title
    run_finished = pyqtSignal(dict)              # {"ok", "failed", "stopped", "titles"} when the queue empties
    problem = pyqtSignal(str)                    # e.g. yt-dlp / ffmpeg missing

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None                      # tests replace the real per-song download with a fake
        self.check_tools = downloader.check_tools
        self.step_text = ""
        self._lock = threading.Lock()
        self._queue = deque()                    # (key, line, folder, source)
        self._states = {}                        # key -> {"state", "title", "artist", "note"}
        self._current = ""
        self._worker = None
        self._jobs = {}                          # key -> job, kept so stopped / failed songs can be resumed
        self._cancel_one = ""
        self.paused = False
        self.pause_why = ""                      # "", "you", "internet" or "drive"
        from PyQt6.QtCore import QTimer
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._auto_resume)
        self._batch = self._new_batch()

    @staticmethod
    def _new_batch():
        return {"total": 0, "done": 0, "ok": 0, "failed": [], "titles": [], "stopped": False}

    # --- asking -----------------------------------------------------------------------------------
    def request(self, tracks, folder, source=downloader.SOURCE_BOTH, by_artist=True) -> int:
        """Queue OnlineTrack objects for download into `folder`. Returns how many were added
        (songs already queued or downloading are skipped)."""
        added = 0
        with self._lock:
            for t in tracks:
                key = t.key
                if self._states.get(key, {}).get("state") in (QUEUED, DOWNLOADING):
                    continue
                self._states[key] = {"state": QUEUED, "title": t.title, "artist": t.artist, "note": ""}
                # Filed by main artist: <download folder>/<Artist>/<Artist - Title>.mp3
                out_dir = os.path.join(folder, downloader.artist_folder(t.artist)) if by_artist else folder
                job = (key, downloader.song_line(t.artist, t.title), out_dir, source)
                self._jobs[key] = job
                self._queue.append(job)
                added += 1
            if added:
                self._batch["total"] += added
        if added:
            self._kick()
            self.changed.emit()
        return added

    def _kick(self):
        if self._worker is None or not self._worker.isRunning():
            downloader.Controls.reset()
            downloader.Controls.set_paused(self.paused)
            self._start_worker()

    def stop(self):
        """Stop all downloads. Songs that were waiting (and the one being downloaded) stay listed as "Stopped"
        and can be resumed; finished files are kept. A stopped song starts again from its beginning."""
        with self._lock:
            for key, *_ in self._queue:
                if key in self._states:
                    self._states[key].update(state=STOPPED, note="stopped")
            self._queue.clear()
            busy = bool(self._current)
            if busy and self._current in self._states:
                self._states[self._current].update(state=STOPPED, note="stopped")
        if busy:
            downloader.Controls.stop()
        self._batch["stopped"] = True
        self.changed.emit()
        if not busy:
            self._finish_batch()

    def pause(self, why="you"):
        """Hold the queue: the song being downloaded finishes, the next ones wait until Resume."""
        self.paused = True
        self.pause_why = why
        downloader.Controls.set_paused(True)
        self.changed.emit()

    def resume(self):
        """Resume after Pause, and restart songs that were stopped."""
        self.paused = False
        self.pause_why = ""
        self._retry_timer.stop()
        downloader.Controls.set_paused(False)
        self.resume_stopped()
        if self._queue:
            self._kick()                         # songs put back after "no internet" while the worker ended
        self.changed.emit()

    def resume_stopped(self):
        with self._lock:
            keys = [k for k, st in self._states.items() if st["state"] == STOPPED and k in self._jobs]
            for k in keys:
                self._states[k].update(state=QUEUED, note="")
                self._queue.append(self._jobs[k])
            if keys:
                self._batch["total"] += len(keys)
        if keys:
            self._kick()
            self.changed.emit()
        return len(keys)

    def cancel(self, key):
        """Take one song off the list (stops it if it is downloading); the rest carry on."""
        with self._lock:
            before = len(self._queue)
            self._queue = deque(j for j in self._queue if j[0] != key)
            removed = before != len(self._queue)
            current = self._current == key
            if not current:
                self._states.pop(key, None)
                if removed:
                    self._batch["total"] = max(0, self._batch["total"] - 1)
        if current:
            self._cancel_one = key
            downloader.Controls.stop()
        self.changed.emit()

    def retry(self, key):
        """Try one failed or stopped song again."""
        with self._lock:
            st = self._states.get(key)
            if not st or st["state"] not in (FAILED, STOPPED) or key not in self._jobs:
                return False
            st.update(state=QUEUED, note="")
            self._queue.append(self._jobs[key])
            self._batch["total"] += 1
        self._kick()
        self.changed.emit()
        return True

    def retry_failed(self, folder, source=downloader.SOURCE_BOTH) -> int:
        from core.online.models import OnlineTrack
        failed = [OnlineTrack(s["title"], s["artist"]) for s in self._states.values() if s["state"] == FAILED]
        return self.request(failed, folder, source)

    def stopped_count(self):
        return sum(1 for s in self._states.values() if s["state"] == STOPPED)

    def items(self):
        """[(key, state, title, artist, note)] for the downloads menu, in queue order."""
        with self._lock:
            order = ([self._current] if self._current else []) + [j[0] for j in self._queue]
            rest = [k for k in self._states if k not in order]
            return [(k, self._states[k]["state"], self._states[k]["title"], self._states[k]["artist"],
                     self._states[k]["note"]) for k in order + rest if k in self._states]

    def wait(self, ms=8000):
        if self._worker is not None:
            self._worker.wait(ms)

    # --- reading ----------------------------------------------------------------------------------
    def state(self, key):
        """(state, note) for a song key, or (None, "") if it was never asked for."""
        s = self._states.get(key)
        return (s["state"], s["note"]) if s else (None, "")

    def is_busy(self):
        return bool(self._current) or bool(self._queue)

    def failed_count(self):
        return sum(1 for s in self._states.values() if s["state"] == FAILED)

    def summary(self):
        """Short text for the top bar, e.g. "⬇ 2 of 5 · Song title" ("" when nothing is happening)."""
        if not self.is_busy():
            return ""
        b = self._batch
        cur = self._states.get(self._current, {}).get("title", "")
        text = f"⬇ {min(b['done'] + 1, b['total'])} of {b['total']}" + (f" · {cur}" if cur else "")
        why = {"internet": " · paused: no internet (tries again every minute)",
               "drive": " · paused: the download drive is missing or full"}.get(self.pause_why, " · paused")
        return text + (why if self.paused else "")

    # --- worker -----------------------------------------------------------------------------------
    def _start_worker(self):
        self._worker = _Worker(self)
        self._worker.song_started.connect(self._on_started)
        self._worker.song_finished.connect(self._on_finished)
        self._worker.tools_missing.connect(self._on_tools_missing)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _take_next(self):
        with self._lock:
            if not self._queue:
                return None
            job = self._queue.popleft()
            self._current = job[0]
            return job

    def _on_started(self, key):
        if key in self._states and self._states[key]["state"] == QUEUED:     # not if Stop came first
            self._states[key]["state"] = DOWNLOADING
        self.changed.emit()

    def _on_finished(self, key, res):
        with self._lock:
            self._current = ""
        info = self._states.get(key, {"title": "", "artist": ""})
        status = res.get("status")
        b = self._batch
        b["done"] += 1
        if status in ("ok", "skip", "dup"):
            self._states.pop(key, None)
            b["ok"] += 1
            b["titles"].append(info["title"])
            self.song_done.emit(key, res.get("path") or "", info["title"])
        elif res.get("note") == "stopped":
            if self._states.get(key, {}).get("state") != STOPPED:
                self._states.pop(key, None)          # cancelled: forget it
        elif pause_reason(res.get("note")) and key in self._jobs:
            # Not this song's fault: put it back at the front and wait, then try again by itself.
            why = pause_reason(res.get("note"))
            with self._lock:
                self._queue.appendleft(self._jobs[key])
            self._states[key] = {**info, "state": QUEUED, "note": res.get("note") or ""}
            b["done"] -= 1
            self.pause(why)
            self._retry_timer.start(60_000)
        else:
            self._states[key] = {**info, "state": FAILED, "note": res.get("note") or "couldn't be downloaded"}
            b["failed"].append(info["title"])
        self.changed.emit()

    def _auto_resume(self):
        if self.paused and self.pause_why in ("internet", "drive"):
            self.resume()

    def _on_tools_missing(self, text):
        with self._lock:
            for key, *_ in self._queue:
                if key in self._states:
                    self._states[key].update(state=FAILED, note=text)
                    self._batch["failed"].append(self._states[key]["title"])
            self._queue.clear()
        self.problem.emit(text)
        self.changed.emit()

    def _on_worker_finished(self):
        if self._queue:                       # songs were added just as the worker was ending
            self._start_worker()
            return
        self._finish_batch()

    def _finish_batch(self):
        b = self._batch
        if b["total"]:
            self.run_finished.emit({"ok": b["ok"], "failed": list(b["failed"]), "stopped": b["stopped"],
                                    "titles": list(b["titles"])})
        self._batch = self._new_batch()
        self.step_text = ""
        self.changed.emit()

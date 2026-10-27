"""Downloads songs in the background with SEVBY's engine (core/downloader.py), one at a time.

Songs found with Search or Radio sit in playlists / Saved for later as "not downloaded yet" slots.
Choosing Download puts them in this manager's queue. A worker thread fetches them (Bandcamp first,
then YouTube) into the download folder while the music keeps playing; the main window then rescans
and the slot fills in with the new file.

Only download music you have the right to download.
"""
import threading
from collections import deque

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core import downloader

QUEUED, DOWNLOADING, FAILED = "queued", "downloading", "failed"


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
        self._batch = self._new_batch()

    @staticmethod
    def _new_batch():
        return {"total": 0, "done": 0, "ok": 0, "failed": [], "titles": [], "stopped": False}

    # --- asking -----------------------------------------------------------------------------------
    def request(self, tracks, folder, source=downloader.SOURCE_BOTH) -> int:
        """Queue OnlineTrack objects for download into `folder`. Returns how many were added
        (songs already queued or downloading are skipped)."""
        added = 0
        with self._lock:
            for t in tracks:
                key = t.key
                if self._states.get(key, {}).get("state") in (QUEUED, DOWNLOADING):
                    continue
                self._states[key] = {"state": QUEUED, "title": t.title, "artist": t.artist, "note": ""}
                self._queue.append((key, downloader.song_line(t.artist, t.title), folder, source))
                added += 1
            if added:
                self._batch["total"] += added
        if added:
            downloader.Controls.reset()
            if self._worker is None or not self._worker.isRunning():
                self._start_worker()
            self.changed.emit()
        return added

    def stop(self):
        """Cancel everything still waiting and stop the song being downloaded (finished files are kept)."""
        with self._lock:
            for key, *_ in self._queue:
                self._states.pop(key, None)
            self._queue.clear()
            busy = bool(self._current)
        if busy:
            downloader.Controls.stop()
        self._batch["stopped"] = True
        self.changed.emit()
        if not busy:
            self._finish_batch()

    def retry_failed(self, folder, source=downloader.SOURCE_BOTH) -> int:
        from core.online.models import OnlineTrack
        failed = [OnlineTrack(s["title"], s["artist"]) for s in self._states.values() if s["state"] == FAILED]
        return self.request(failed, folder, source)

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
        return f"⬇ {min(b['done'] + 1, b['total'])} of {b['total']}" + (f" · {cur}" if cur else "")

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
        if key in self._states:
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
            self._states.pop(key, None)
        else:
            self._states[key] = {**info, "state": FAILED, "note": res.get("note") or "couldn't be downloaded"}
            b["failed"].append(info["title"])
        self.changed.emit()

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

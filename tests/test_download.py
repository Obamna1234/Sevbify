"""Tests for downloading "not downloaded yet" songs with SEVBY's engine.

No internet is used: the per-song download is replaced by a fake that writes a short WAV file
(or reports a failure). So these check Sevbify's own logic: the download runner (counting, stopping,
pausing, failures), the background download manager, and the window (Download actions, slots
filling in, the one-time notice, stopping on close). The real Bandcamp/YouTube download is not
tested here.
"""
import os
import threading
import time
from pathlib import Path

import pytest

from conftest import make_wav, wait_until
from core import downloader


def fake_ok(song, out_dir, opts, state, say, step=lambda _t: None):
    step("Pretending to download…")
    path = os.path.join(out_dir, song.replace("/", "-") + ".wav")
    make_wav(Path(path), 0.2)
    return {"status": "ok", "source": "Bandcamp", "path": path, "note": "Bandcamp"}


def fake_mixed(song, out_dir, opts, state, say, step=lambda _t: None):
    if "bad" in song:
        return {"status": "fail", "note": "not on Bandcamp"}
    if "have" in song:
        return {"status": "skip", "note": "already downloaded"}
    return fake_ok(song, out_dir, opts, state, say, step)


def blocking(gate, started=None):
    """A fake download that waits for `gate` (or Stop) before finishing."""
    def process(song, out_dir, opts, state, say, step=lambda _t: None):
        if started is not None:
            started.set()
        e = downloader.engine()
        while not gate.is_set():
            if e.STOP_EVENT.is_set():
                return {"status": "fail", "note": "stopped"}
            time.sleep(0.02)
        return fake_ok(song, out_dir, opts, state, say, step)
    return process


@pytest.fixture(autouse=True)
def reset_controls():
    downloader.Controls.reset()
    yield
    downloader.Controls.reset()


def remote(title, artist):
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    return RemoteSong(OnlineTrack(title, artist, source="deezer", preview_url="https://cdn/x.mp3"))


# --- the download runner (core/downloader.py) --------------------------------------------------------------------

def test_song_line_and_parse_lines():
    assert downloader.song_line(" Vogel ", "Night City ") == "Vogel - Night City"
    assert downloader.song_line("", "Untitled") == "Untitled"
    songs = downloader.parse_lines("Perturbator - Future Club\n\n  Carpenter Brut - Turbo Killer  \nhttps://x.y/z\n")
    assert songs == ["Perturbator - Future Club", "Carpenter Brut - Turbo Killer"]


def test_counts_paths_and_failures(tmp_path):
    songs = ["A - one", "A - bad", "A - have", "A - two"]
    res = downloader.run_download(songs, str(tmp_path / "Music"), process=fake_mixed)
    assert (res["ok"], res["skip"], res["fail"]) == (2, 1, 1)
    assert res["failed"] == ["A - bad"]
    assert len(res["paths"]) == 2 and all(os.path.isfile(p) for p in res["paths"])
    assert not res["stopped"]
    assert downloader.summary_text(res) == "Done · 2 downloaded · 1 already there · 1 failed"


def test_source_choice_sets_what_is_searched(tmp_path):
    seen = {}

    def spy(song, out_dir, opts, state, say, step=lambda _t: None):
        seen[song] = dict(opts)
        return {"status": "skip", "note": "x"}

    downloader.run_download(["a - b"], str(tmp_path), downloader.SOURCE_BANDCAMP, process=spy)
    downloader.run_download(["c - d"], str(tmp_path), downloader.SOURCE_YOUTUBE, process=spy)
    downloader.run_download(["e - f"], str(tmp_path), downloader.SOURCE_BOTH, process=spy)
    assert seen["a - b"]["use_bc"] and not seen["a - b"]["use_yt"]
    assert not seen["c - d"]["use_bc"] and seen["c - d"]["use_yt"]
    assert seen["e - f"]["use_bc"] and seen["e - f"]["use_yt"]
    assert not any(o["free"] for o in seen.values())


def test_one_crashing_song_does_not_stop_the_rest(tmp_path):
    def boom(song, out_dir, opts, state, say, step=lambda _t: None):
        if "x" in song:
            raise RuntimeError("kaboom")
        return {"status": "ok", "path": "", "note": "ok"}

    res = downloader.run_download(["a - x", "b - y"], str(tmp_path), process=boom)
    assert (res["ok"], res["fail"]) == (1, 1)


def test_stop_ends_the_run_and_keeps_finished_songs(tmp_path):
    songs = [f"Artist - {i}" for i in range(6)]
    done = []

    def slow(song, out_dir, opts, state, say, step=lambda _t: None):
        if len(done) == 2:
            downloader.Controls.stop()
        done.append(song)
        return {"status": "ok", "path": "", "note": "ok"}

    res = downloader.run_download(songs, str(tmp_path), process=slow)
    assert res["stopped"] and res["ok"] == 3 and len(done) == 3


def test_pause_holds_until_resumed(tmp_path):
    started = []
    downloader.Controls.set_paused(True)
    t = threading.Thread(target=lambda: downloader.run_download(
        ["a - b"], str(tmp_path), on_start=lambda *a: started.append(a), process=fake_ok))
    t.start()
    time.sleep(0.6)
    assert not started, "must not start a song while paused"
    downloader.Controls.set_paused(False)
    t.join(5)
    assert started and not t.is_alive()


def test_missing_tools_are_reported(monkeypatch):
    e = downloader.engine()
    monkeypatch.setattr(e, "have_ytdlp", lambda: False)
    assert any("yt-dlp" in p for p in downloader.check_tools())


def test_engine_has_no_window_code():
    """core/ must stay free of UI code (the engine is generated from SEVBY with its window removed)."""
    import ast
    src = (Path(__file__).resolve().parent.parent / "core" / "sevby_engine.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"customtkinter", "tkinter", "tkinterdnd2", "PyQt6", "PyQt5"}
    assert "SetCurrentProcessExplicitAppUserModelID" not in src     # would steal SEVBY's taskbar identity


# --- the background download manager (ui/download_manager.py) ------------------------------------------------------

def make_manager(process):
    from ui.download_manager import DownloadManager
    m = DownloadManager()
    m.process = process
    m.check_tools = lambda: []
    return m


def track(title, artist="Artist"):
    from core.online.models import OnlineTrack
    return OnlineTrack(title, artist)


def test_manager_downloads_in_background_and_reports(qapp, tmp_path):
    m = make_manager(fake_mixed)
    done, finished = [], []
    m.song_done.connect(lambda key, path, title: done.append((title, path)))
    m.run_finished.connect(finished.append)
    assert m.request([track("one"), track("bad"), track("two")], str(tmp_path)) == 3
    assert m.is_busy()
    assert wait_until(qapp, lambda: finished, 10)
    m.wait()
    assert [t for t, _ in done] == ["one", "two"]
    assert all(os.path.isfile(p) for _, p in done)
    assert finished[0]["ok"] == 2 and finished[0]["failed"] == ["bad"]
    assert m.state(track("bad").key) == ("failed", "not on Bandcamp")
    assert m.state(track("one").key) == (None, "")
    assert m.failed_count() == 1 and not m.is_busy() and m.summary() == ""


def test_manager_skips_songs_already_queued_and_retries_failures(qapp, tmp_path):
    gate = threading.Event()
    m = make_manager(blocking(gate))
    finished = []
    m.run_finished.connect(finished.append)
    assert m.request([track("a"), track("b")], str(tmp_path)) == 2
    assert m.request([track("a")], str(tmp_path)) == 0           # already queued
    assert wait_until(qapp, lambda: m.state(track("a").key)[0] == "downloading")
    assert m.summary().startswith("⬇ 1 of 2")
    gate.set()
    assert wait_until(qapp, lambda: finished, 10)
    m.wait()

    calls = []
    m.process = lambda song, *a, **k: calls.append(song) or {"status": "fail", "note": "not found on YouTube"}
    finished.clear()
    m.request([track("c")], str(tmp_path))
    assert wait_until(qapp, lambda: finished, 10)
    m.wait()
    assert m.failed_count() == 1
    m.process = fake_ok
    finished.clear()
    assert m.retry_failed(str(tmp_path)) == 1
    assert wait_until(qapp, lambda: finished, 10)
    m.wait()
    assert calls == ["Artist - c"] and m.failed_count() == 0


def test_manager_stop_cancels_waiting_songs(qapp, tmp_path):
    gate, started = threading.Event(), threading.Event()
    m = make_manager(blocking(gate, started))
    finished = []
    m.run_finished.connect(finished.append)
    folder = tmp_path / "dl"
    m.request([track(str(i)) for i in range(4)], str(folder))
    assert started.wait(5)
    m.stop()
    assert wait_until(qapp, lambda: finished, 10)
    m.wait()
    assert finished[0]["stopped"] and finished[0]["ok"] == 0
    assert not m.is_busy() and m.failed_count() == 0
    assert not [p for p in folder.rglob("*") if p.is_file()]    # nothing half-finished left behind
    assert m.stopped_count() == 4                                # still listed, ready to resume
    # Resume: all four come back and finish
    gate.set()
    finished.clear()
    assert m.resume() is None and m.stopped_count() == 0
    assert wait_until(qapp, lambda: finished, 10)
    m.wait()
    assert finished[0]["ok"] == 4 and not finished[0]["stopped"]


def test_manager_cancel_one_keeps_the_rest_going(qapp, tmp_path):
    gate, started = threading.Event(), threading.Event()
    m = make_manager(blocking(gate, started))
    done = []
    m.song_done.connect(lambda k, p, t: done.append(t))
    finished = []
    m.run_finished.connect(finished.append)
    m.request([track(str(i)) for i in range(3)], str(tmp_path))
    assert started.wait(5)
    m.cancel(track("0").key)                     # the one being downloaded
    m.cancel(track("2").key)                     # one still waiting
    wait_until(qapp, lambda: False, 0.3)
    gate.set()
    assert wait_until(qapp, lambda: finished, 10)
    m.wait()
    assert done == ["1"] and m.state(track("0").key) == (None, "") and m.state(track("2").key) == (None, "")


def test_manager_pause_holds_the_next_song(qapp, tmp_path):
    m = make_manager(fake_ok)
    done = []
    m.song_done.connect(lambda k, p, t: done.append(t))
    m.pause()
    m.request([track("a"), track("b")], str(tmp_path))
    wait_until(qapp, lambda: False, 0.8)
    assert done == [] and m.is_busy() and "paused" in m.summary()
    m.resume()
    assert wait_until(qapp, lambda: len(done) == 2, 10)
    m.wait()


def test_manager_reports_missing_tools(qapp, tmp_path):
    m = make_manager(fake_ok)
    m.check_tools = lambda: ["yt-dlp is not installed"]
    problems = []
    m.problem.connect(problems.append)
    m.request([track("x")], str(tmp_path))
    assert wait_until(qapp, lambda: problems)
    m.wait()
    assert problems == ["yt-dlp is not installed"]
    assert m.state(track("x").key) == ("failed", "yt-dlp is not installed")


# --- inside the real window (needs VLC, like the other window tests) -------------------------------------------------

def prepare(window, process):
    window.downloads.process = process
    window.downloads.check_tools = lambda: []
    window.user_data.download_notice_accepted = True


def test_download_fills_the_playlist_slot(window, audio_dir, qapp):
    """The engine may save the file under the official spelling; the slot must still fill in its place."""
    def official_name(song, out_dir, opts, state, say, step=lambda _t: None):
        path = os.path.join(out_dir, "Vogel - Night City (Official Spelling).wav")
        make_wav(Path(path), 0.3)
        return {"status": "ok", "source": "YouTube", "path": path, "note": "YouTube"}

    prepare(window, official_name)
    pl = window.create_playlist("Mix", [window.songs[0], remote("Night City", "Vogel"), window.songs[1]])
    window.show_playlist(pl)
    assert window.pl_download_btn.isEnabled()
    assert window.download_songs(pl.songs) == 1                 # local songs are ignored
    assert wait_until(qapp, lambda: not getattr(pl.songs[1], "is_remote", False), 15)
    assert pl.songs[1].file_path.endswith("Night City (Official Spelling).wav")
    assert os.path.dirname(pl.songs[1].file_path) == str(audio_dir / "Sevbify downloads" / "Vogel")   # artist folder
    assert len(pl.songs) == 3                                   # still in the same place
    assert wait_until(qapp, lambda: not window.pl_download_btn.isEnabled()
                      and "every song" in window.pl_download_btn.toolTip())          # green: all downloaded


def test_not_downloaded_rows_show_their_state(window, qapp):
    gate, started = threading.Event(), threading.Event()
    prepare(window, blocking(gate, started))
    pl = window.create_playlist("Later", [remote("Fresh", "Someone"), remote("Other", "Someone")])
    window.show_playlist(pl)
    assert window.pl_table.item(0, 1).text().endswith("⬇")
    assert window.pl_download_btn.toolTip() == "Download 2 songs"
    window.download_songs(pl.songs)
    assert started.wait(5)
    assert wait_until(qapp, lambda: window.pl_table.item(0, 1).text().endswith("Downloading…"))
    assert window.pl_table.item(1, 1).text().endswith("Queued to download")
    assert not window.top_bar.downloads_btn.isHidden()
    assert "1 of 2" in window.top_bar.downloads_btn.text()

    menu = window.build_song_menu(pl.songs[0], playlist=pl, row=0)
    texts = [a.text() for a in menu.actions()]
    assert "⬇  Downloading…" in texts and "■  Stop all downloads" in texts
    gate.set()
    assert wait_until(qapp, lambda: not any(getattr(s, "is_remote", False) for s in pl.songs), 15)
    assert wait_until(qapp, lambda: window.top_bar.downloads_btn.isHidden())
    assert wait_until(qapp, lambda: "Downloads finished" in window.status_label.text()
                      or "Now in your library" in window.status_label.text())


def test_download_action_only_on_songs_not_downloaded(window):
    texts = [a.text() for a in window.build_song_menu(window.songs[0]).actions()]
    assert not any("Download" in t for t in texts)
    texts = [a.text() for a in window.build_song_menu(remote("Web", "Result"), source="Search").actions()]
    assert "⬇  Download" in texts


def test_failed_download_can_be_retried(window, qapp):
    prepare(window, lambda song, *a, **k: {"status": "fail", "note": "not found on YouTube"})
    song = remote("Nowhere", "Nobody")
    pl = window.create_playlist("Fails", [song])
    window.show_playlist(pl)
    window.download_songs([song])
    assert wait_until(qapp, lambda: window.downloads.failed_count() == 1, 10)
    assert wait_until(qapp, lambda: window.pl_table.item(0, 1).text().endswith("Download failed"))
    assert "failed" in window.top_bar.downloads_btn.text()
    texts = [a.text() for a in window.build_song_menu(song, playlist=pl, row=0).actions()]
    assert "⬇  Retry download" in texts
    assert getattr(pl.songs[0], "is_remote", False)            # the slot stays, nothing is lost


def test_notice_is_shown_once_and_can_be_declined(window, qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    window.downloads.process = fake_ok
    window.downloads.check_tools = lambda: []
    asked = []
    answer = [QMessageBox.StandardButton.No]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or answer[0])
    assert window.download_songs([remote("A", "B")]) == 0
    assert not window.downloads.is_busy() and not window.user_data.download_notice_accepted
    assert "not affiliated" in asked[0] and "Sevby LLC" in asked[0]
    answer[0] = QMessageBox.StandardButton.Yes
    assert window.download_songs([remote("A", "B")]) == 1
    assert window.user_data.download_notice_accepted
    assert wait_until(qapp, lambda: not window.downloads.is_busy(), 10)
    window.download_songs([remote("C", "D")])
    assert len(asked) == 2                                       # not asked again


def test_download_settings_are_saved(open_window, audio_dir, data_dir):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    w.apply_settings({"online_enabled": True, "lastfm_api_key": "", "jamendo_client_id": "",
                      "download_source": downloader.SOURCE_BANDCAMP})
    w.user_data.download_notice_accepted = True
    w.save_now()
    w.close()
    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    assert w2.user_data.download_source == downloader.SOURCE_BANDCAMP
    assert w2.user_data.download_notice_accepted


def test_closing_the_window_stops_a_download(open_window, audio_dir, data_dir, qapp):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    gate, started = threading.Event(), threading.Event()
    prepare(w, blocking(gate, started))
    w.download_songs([remote("Long", "Song"), remote("Longer", "Song")])
    assert started.wait(5)
    t = time.time()
    w.close()
    assert time.time() - t < 8
    assert not w.downloads._worker.isRunning()


def test_radio_saved_as_playlist_downloads_into_the_same_places(window, qapp):
    """Like Spotify: Radio -> Save as playlist. Songs you don't have wait under "To download";
    "Download all" fetches them and each one fills its own # even if more songs were added later."""
    prepare(window, fake_ok)
    seed = window.songs[0]
    radio = [seed, remote("Explorers", "Zombie Hyperdrive"), window.songs[1], remote("Space Warp", "Juno Dreams")]
    window.pq.set_context(radio, seed, f"{seed.title} Radio")
    pl = window.save_queue_as_playlist()
    assert pl.name == f"{seed.title} Radio" and len(pl.songs) == 4
    window.add_to_playlist(pl, [window.songs[2], remote("Nemesis", "Zombie Hyperdrive")])   # added afterwards
    assert [s.title for s in window.songs_to_download()] == ["Explorers", "Space Warp", "Nemesis"]

    window.show_saved()
    assert "3 songs to download" in window.saved_scroll.widget().findChildren(type(window.status_label))[0].text()
    window.download_songs(window.songs_to_download())
    assert wait_until(qapp, lambda: not any(getattr(s, "is_remote", False) for s in pl.songs), 15)
    assert [s.title for s in pl.songs][1] == "Zombie Hyperdrive - Explorers"      # #2 stays #2
    assert pl.songs[3].title == "Juno Dreams - Space Warp"                         # #4 stays #4
    assert pl.songs[4] == window.songs[2] or pl.songs[4].file_path == window.songs[2].file_path
    assert pl.songs[5].title == "Zombie Hyperdrive - Nemesis"                      # #6 stays #6
    assert window.songs_to_download() == []


def test_queue_panel_offers_save_for_radio_only(window, qapp):
    from PyQt6.QtWidgets import QPushButton
    seed = window.songs[0]
    window.set_right_panel("queue")

    def buttons():
        window.queue_panel.refresh(seed, [], [window.songs[1]], window.pq.source_name, [])
        return [b.text() for b in window.queue_panel.scroll.widget().findChildren(QPushButton)]

    window.pq.set_context(window.songs, seed, "Your Songs")
    assert "Save as playlist" not in buttons()
    window.pq.set_context(window.songs, seed, "first Radio")
    assert "Save as playlist" in buttons()


def test_ffmpeg_from_imageio_is_used_when_none_installed(tmp_path, monkeypatch):
    """Run Sevbify.bat (from source) must work without installing ffmpeg separately."""
    pytest.importorskip("imageio_ffmpeg")
    import shutil
    e = downloader.engine()
    monkeypatch.setattr(e, "ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert shutil.which("ffmpeg") is None
    downloader._ensure_ffmpeg(e, cache_dir=str(tmp_path / "ff"))
    found = shutil.which("ffmpeg")
    assert found and os.path.dirname(found) == str(tmp_path / "ff")


def test_manager_waits_instead_of_failing_when_the_internet_drops(qapp, tmp_path):
    from ui.download_manager import pause_reason
    assert pause_reason("<urlopen error [Errno 11001] getaddrinfo failed>") == "internet"
    assert pause_reason("[Errno 28] No space left on device") == "drive"
    assert pause_reason("not found on YouTube") == ""
    calls = []

    def flaky(song, *a, **k):
        calls.append(song)
        if len(calls) == 1:
            return {"status": "fail", "note": "Unable to download webpage: timed out"}
        return fake_ok(song, *a, **k)
    m = make_manager(flaky)
    done = []
    m.song_done.connect(lambda k, p, t: done.append(t))
    m.request([track("a"), track("b")], str(tmp_path))
    assert wait_until(qapp, lambda: m.paused and m.pause_why == "internet", 5)
    assert m.failed_count() == 0 and m.state(track("a").key)[0] == "queued"
    assert "no internet" in m.summary()
    m._retry_timer.stop()
    m.resume()                                   # (normally by itself a minute later)
    assert wait_until(qapp, lambda: len(done) == 2, 10)
    m.wait()
    assert calls.count("Artist - a") == 2 and m.failed_count() == 0


def test_failed_download_leftovers_are_removed_but_songs_kept(tmp_path):
    from core import downloader
    for name in ("Band - Song.mp3.part", "Band - Song.webm.part", "Band - Song.jpg", "Band - Song.f251.webm.ytdl",
                 "Band - Song.m4a", "Band - Other.part", "Band - Song.webm"):
        (tmp_path / name).write_text("x")
    downloader.cleanup_partial(str(tmp_path), "Band - Song")
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["Band - Other.part", "Band - Song.m4a", "Band - Song.webm"]


def test_quality_settings_reach_the_engine():
    from core import downloader, quality
    e = downloader.engine()
    quality.apply_to_engine(e, "small")
    assert e.QUALITY["best"] and "abr<=72" in e.AUDIO_FORMAT_ORIGINAL
    quality.apply_to_engine(e, "mp3")
    assert not e.QUALITY["best"] and e.MP3_QUALITY == "160"
    quality.apply_to_engine(e, "nonsense")
    assert e.QUALITY["best"] and "abr<=72" not in e.AUDIO_FORMAT_ORIGINAL

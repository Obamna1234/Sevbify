"""Automated playback regression tests.

Run from the project folder:
    python -m pytest tests -v

The tests use short generated WAV files, a hidden window and VLC's silent
"dummy" audio output, so they make no sound and don't need your music files.
They DO need VLC (libVLC) installed, exactly like the app itself.
"""
import math
import os
import shutil
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication  # noqa: E402

VLC_TEST_ARGS = ("--aout=adummy", "--no-video", "--quiet")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def make_wav(path: Path, seconds: float = 1.0, freq: int = 440):
    rate = 22050
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / rate)))
            for i in range(int(rate * seconds))
        )
        w.writeframes(frames)


def wait_until(app, condition, timeout=8.0):
    """Process Qt events until condition() is true or the timeout expires."""
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    app.processEvents()
    return condition()


@pytest.fixture
def window(qapp, tmp_path):
    from ui.main_window import MainWindow

    audio = tmp_path / "audio"
    audio.mkdir()
    make_wav(audio / "01 - first.wav", 1.0, 440)
    make_wav(audio / "02 - second.wav", 1.0, 550)
    make_wav(audio / "03 - third.wav", 1.0, 660)
    w = MainWindow(audio_folder=str(audio), vlc_args=VLC_TEST_ARGS)
    yield w
    w.close()


def titles(w):
    return [s.title for s in w.queue]


def test_library_scanned(window):
    assert [s.title for s in window.songs] == ["01 - first", "02 - second", "03 - third"]
    assert all(s.duration > 900 for s in window.songs)


def test_play_song_does_not_block(window, qapp):
    start = time.perf_counter()
    window.play_song(window.songs[0])
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5, f"play_song blocked the UI for {elapsed:.2f}s"
    assert wait_until(qapp, lambda: window._reached_playing)
    assert window.play_btn.text() == "⏸"


def test_track_end_advances_exactly_once(window, qapp):
    window.play_song(window.songs[0])
    assert wait_until(qapp, lambda: window.current_song is window.songs[1] and window._reached_playing)
    # Second track is now playing; it must not have skipped straight to the third.
    assert window.queue_index == 1


def test_pause_and_resume(qapp, tmp_path):
    from ui.main_window import MainWindow
    import vlc

    audio = tmp_path / "audio"
    audio.mkdir()
    make_wav(audio / "long.wav", 6.0)
    w = MainWindow(audio_folder=str(audio), vlc_args=VLC_TEST_ARGS)
    try:
        w.play_song(w.songs[0])
        assert wait_until(qapp, lambda: w.player.get_state() == vlc.State.Playing)
        w.play_pause_song()
        assert wait_until(qapp, lambda: w.player.get_state() == vlc.State.Paused)
        assert w.play_btn.text() == "▶️"
        w.play_pause_song()
        assert wait_until(qapp, lambda: w.player.get_state() == vlc.State.Playing)
        assert w.play_btn.text() == "⏸"
    finally:
        w.close()


def test_missing_file_is_skipped_with_message(window, qapp):
    os.remove(window.songs[1].file_path)
    window.play_song(window.songs[1])
    assert "Skipped" in window.status_label.text()
    assert wait_until(qapp, lambda: window.current_song is window.songs[2] and window._reached_playing)


def test_corrupt_file_is_skipped_with_message(window, qapp):
    Path(window.songs[0].file_path).write_bytes(b"this is not audio")
    window.play_song(window.songs[0])
    assert wait_until(qapp, lambda: "Skipped" in window.status_label.text())
    assert wait_until(qapp, lambda: window.current_song is window.songs[1] and window._reached_playing)


def test_all_bad_files_stop_instead_of_looping(window, qapp):
    for s in window.songs:
        os.remove(s.file_path)
    start = time.perf_counter()
    window.play_song(window.songs[0])
    assert wait_until(qapp, lambda: "No playable songs" in window.status_label.text(), timeout=5)
    assert time.perf_counter() - start < 5
    assert window.play_btn.text() == "▶️"


def test_playlist_queue_stays_in_playlist(window, qapp):
    from ui.main_window import Playlist

    pl = Playlist("Test")
    pl.add_song(window.songs[2])
    pl.add_song(window.songs[0])
    window.play_playlist(pl)
    assert titles(window) == ["03 - third", "01 - first"]
    window.next_song()
    assert window.current_song is window.songs[0]
    window.next_song()
    assert window.current_song is window.songs[2]  # wraps within the playlist


def test_finds_music_when_launched_from_another_folder(qapp, tmp_path, monkeypatch):
    from ui import main_window

    monkeypatch.chdir(tmp_path)
    w = main_window.MainWindow(vlc_args=VLC_TEST_ARGS)
    try:
        assert len(w.songs) > 0, "bundled audio/ folder not found from another working directory"
        assert not (tmp_path / "album_covers").exists()
    finally:
        w.close()

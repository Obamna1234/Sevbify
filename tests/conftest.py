"""Shared test helpers.

The tests use short generated WAV files, a hidden window, VLC's silent
"adummy" audio output and a temporary save folder, so they make no sound and
never touch your real music or saved playlists.
"""
import math
import os
import struct
import sys
import time
import wave

os.environ["LANGUAGE"] = "en"          # tests read English labels, whatever this computer's language is
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
    # Let background (online) tasks finish before Python shuts down;
    # Windows crashes if a worker thread outlives the interpreter.
    from ui.async_tasks import wait_for_all
    wait_for_all(15000)


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


@pytest.fixture(autouse=True)
def isolated_cover_cache(tmp_path, monkeypatch):
    """Keep generated artwork out of the real album_covers folder."""
    from core import paths
    cache = tmp_path / "album_covers"
    cache.mkdir()
    monkeypatch.setattr(paths, "ALBUM_CACHE", str(cache))
    os.makedirs(cache, exist_ok=True)
    return cache


@pytest.fixture
def audio_dir(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    make_wav(audio / "01 - first.wav", 1.0, 440)
    make_wav(audio / "02 - second.wav", 1.0, 550)
    make_wav(audio / "03 - third.wav", 1.0, 660)
    return audio


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "userdata"
    d.mkdir()
    return d


@pytest.fixture
def open_window(qapp):
    """Factory: open_window(audio_folder=..., data_dir=...) -> loaded MainWindow."""
    from ui.main_window import MainWindow
    windows = []

    def _open(**kwargs):
        kwargs.setdefault("vlc_args", VLC_TEST_ARGS)
        w = MainWindow(**kwargs)
        # Tests never use the real internet: the default "web" is offline.
        # Tests that need online data install their own FakeWeb.
        from online_fixtures import FakeWeb
        w.net._opener = FakeWeb(offline=True)
        # The app always streams full songs; tests never search the real web, so a song's preview link stands
        # in for its "full song" (and a song without one is "not found", like a failed lookup).
        w.user_data.auto_update_check = False          # tests never ask GitHub for updates
        w.user_data.download_notice_accepted = True
        w.offer_update = lambda r: None                 # never a modal "Update Sevbify?" box in tests

        def fake_full_song(song, _w=w):
            if song.track.preview_url:
                _w._set_now_playing_text(song.title, song.artist, "Full song · test · not downloaded")
                _w._play_media(song.track.preview_url)
            else:
                _w._track_handled = True
                _w._handle_failed_track("full song not found")
        if not getattr(w, "_real_full_song_test", False):
            w._stream_full_song = fake_full_song
        windows.append(w)
        assert wait_until(qapp, lambda: w.library_ready), "library scan did not finish"
        return w

    yield _open
    from ui.async_tasks import wait_for_all
    for w in windows:
        w.close()
    wait_for_all(10000)


@pytest.fixture
def window(open_window, audio_dir, data_dir):
    return open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))


def pytest_runtest_logreport(report):
    """On GitHub, report each failing test as a readable annotation."""
    if os.environ.get("GITHUB_ACTIONS") and report.failed:
        msg = (report.longreprtext or "").strip().splitlines()
        tail = " | ".join(line.strip() for line in msg[-12:] if line.strip())
        print(f"\n::error title=TEST FAILED {report.nodeid} ({report.when})::{tail[:900]}")

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
        windows.append(w)
        assert wait_until(qapp, lambda: w.library_ready), "library scan did not finish"
        return w

    yield _open
    for w in windows:
        w.close()


@pytest.fixture
def window(open_window, audio_dir, data_dir):
    return open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))

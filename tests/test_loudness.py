"""Volume levelling (core/loudness.py) and Mono audio on the PC."""
import shutil
import wave

import numpy as np
import pytest

from conftest import wait_until
from core import loudness


def _tone(path, amp, seconds=3.0, sr=44100):
    t = np.arange(int(sr * seconds)) / sr
    x = (np.sin(2 * np.pi * 440 * t) * amp * 32767).astype(np.int16)
    w = wave.open(str(path), "wb")
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(np.column_stack([x, x]).tobytes())
    w.close()


def test_gain_and_parse():
    assert loudness.gain_db(-14) == 0 and loudness.gain_db(-6) == -8 and loudness.gain_db(-40) == loudness.MAX_BOOST_DB
    assert loudness.gain_db(None) == 0
    assert abs(loudness.volume_factor(0) - 1) < 1e-9 and loudness.volume_factor(-12) < 1 < loudness.volume_factor(3)
    assert loudness.parse("Summary:\n\n  Integrated loudness:\n    I:         -9.3 LUFS\n") == -9.3
    assert loudness.parse("Integrated loudness:\n I: -70.0 LUFS") is None and loudness.parse("") is None
    store = {}
    for i in range(loudness.MAX_REMEMBERED + 5):
        loudness.remember(store, f"k{i}", -10)
    assert len(store) == loudness.MAX_REMEMBERED and "k0" not in store


def test_only_files_and_web_streams_are_measured(tmp_path):
    assert loudness.measure("file:///etc/passwd", "ffmpeg") is None
    assert loudness.measure("", "ffmpeg") is None and loudness.measure("x.wav", "") is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_loud_and_quiet_songs_end_up_close(tmp_path):
    _tone(tmp_path / "loud.wav", 0.9)
    _tone(tmp_path / "quiet.wav", 0.05)
    loud = loudness.measure(str(tmp_path / "loud.wav"), shutil.which("ffmpeg"))
    quiet = loudness.measure(str(tmp_path / "quiet.wav"), shutil.which("ffmpeg"))
    assert loud > quiet + 20
    after = [l + loudness.gain_db(l) for l in (loud, quiet)]
    assert abs(after[0] - loudness.TARGET_LUFS) < 0.5           # the loud one is turned down to the target


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_window_levels_a_song_and_remembers_it(window, qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("core.sevby_engine.ffmpeg_path", lambda: shutil.which("ffmpeg"))
    window.user_data.normalize = True
    window.user_data.volume = 80
    song = window.songs[0]
    window.current_song = song
    _tone(tmp_path / "loud.wav", 0.95)
    window._start_levelling(str(tmp_path / "loud.wav"))
    assert wait_until(qapp, lambda: song.key in window.user_data.loudness, timeout=20)
    assert window._level_factor < 1 and window._effective_volume() < 80
    window._start_levelling(str(tmp_path / "loud.wav"))              # known now: no second measurement
    assert window._level_factor < 1
    window.apply_settings({"normalize": False})
    assert window._effective_volume() == 80

"""The equaliser really changes the sound, and each dot moves the band its label says (measured on VLC's output)."""
import math
import os
import struct
import subprocess
import time
import wave

import pytest

vlc = pytest.importorskip("vlc")

from core.audio_settings import BAND_LABELS, band_labels, make_equalizer  # noqa: E402


def test_labels_are_the_bands_vlc_uses():
    assert band_labels(vlc) == BAND_LABELS
    freqs = [vlc.libvlc_audio_equalizer_get_band_frequency(i) for i in range(10)]
    assert round(freqs[BAND_LABELS.index("1 kHz")]) == 1000


def _rms_db(path, a, b):
    w = wave.open(path)
    fr = w.getframerate()
    w.setpos(int(a * fr))
    data = w.readframes(int((b - a) * fr))
    v = struct.unpack("<%dh" % (len(data) // 2), data)
    return 20 * math.log10(math.sqrt(sum(x * x for x in v) / max(1, len(v))) + 1e-9)


def _play(tone, eq, out):
    inst = vlc.Instance("--aout=afile", f"--audiofile-file={out}", "--audiofile-format=s16", "--no-video", "--quiet")
    p = inst.media_player_new()
    if eq is not None:
        p.set_equalizer(eq)
    p.set_media(inst.media_new(tone))
    p.play()
    end = time.time() + 8
    while time.time() < end and str(p.get_state()) != "State.Ended":
        time.sleep(0.05)
    p.stop()
    p.release()
    inst.release()
    return _rms_db(out, 0.5, 2.5)


def test_the_1khz_dot_changes_a_1khz_tone(tmp_path):
    tone = str(tmp_path / "tone.wav")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=1000:d=3", "-af", "volume=0.3",
                        "-ar", "44100", "-ac", "2", tone], check=True, timeout=30)
    except Exception:
        pytest.skip("ffmpeg not available")
    flat = _play(tone, None, str(tmp_path / "flat.wav"))
    bands = [0.0] * 10
    bands[BAND_LABELS.index("1 kHz")] = -12.0
    cut = _play(tone, make_equalizer(vlc, bands), str(tmp_path / "cut.wav"))
    assert flat - cut > 8, (flat, cut)          # about 12 dB quieter

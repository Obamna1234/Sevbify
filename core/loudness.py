"""Volume levelling ("Normalize volume"), worked out on this computer: how loud a song is (EBU R128 integrated
loudness, measured by ffmpeg from the first minute), then a gain so every song plays near the same loudness, like
Spotify's. Nothing is sent anywhere; a stream is read from the same place the player reads it.

Results are remembered per song (UserData.loudness: key -> LUFS) so each song is measured once.
"""
import re
import subprocess

TARGET_LUFS = -14.0           # Spotify's "Normal"
MAX_CUT_DB = -12.0
MAX_BOOST_DB = 4.0            # small, so quiet songs don't distort
SECONDS = 60
MAX_REMEMBERED = 5000

_RESULT = re.compile(r"Integrated loudness:\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", re.S)


def parse(stderr_text):
    """The integrated loudness from ffmpeg's ebur128 summary, or None."""
    m = _RESULT.search(stderr_text or "")
    if not m:
        return None
    v = float(m.group(1))
    return v if -70.0 < v < 10.0 else None           # -70 = silence / nothing measured


def measure(location, ffmpeg, headers=None, seconds=SECONDS, timeout=60):
    """LUFS of a file or http(s) stream (first `seconds`), or None if it can't be measured."""
    if not ffmpeg or not location:
        return None
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-nostdin"]
    if "://" in str(location):
        if not str(location).startswith(("https://", "http://")):
            return None                               # only web streams and plain files
        hdr = "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items()
                      if k and v and "\n" not in f"{k}{v}" and "\r" not in f"{k}{v}")
        if hdr:
            cmd += ["-headers", hdr]
        cmd += ["-protocol_whitelist", "https,http,tls,tcp,crypto"]
    else:
        cmd += ["-protocol_whitelist", "file"]
        location = "file:" + str(location)          # a plain file (never "concat:", "subfile:", ...)
    cmd += ["-t", str(int(seconds)), "-i", str(location), "-vn", "-sn", "-af", "ebur128", "-f", "null", "-"]
    try:
        kw = {}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW    # no console window flashing up on Windows
        out = subprocess.run(cmd, capture_output=True, timeout=timeout, **kw)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse(out.stderr.decode("utf-8", "replace"))


def gain_db(lufs, target=TARGET_LUFS):
    if lufs is None:
        return 0.0
    return max(MAX_CUT_DB, min(MAX_BOOST_DB, target - lufs))


def volume_factor(db):
    """What to multiply VLC's volume number by for this gain. VLC turns its volume number into loudness on a cube
    curve, so an amplitude change of 10^(dB/20) is a volume-number change of its cube root."""
    return (10 ** (db / 20.0)) ** (1 / 3)


def remember(store, key, lufs):
    if not key or lufs is None:
        return
    store.pop(key, None)
    store[key] = round(float(lufs), 1)
    while len(store) > MAX_REMEMBERED:
        store.pop(next(iter(store)))

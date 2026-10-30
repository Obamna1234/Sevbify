"""Save space: downloaded podcast episodes and audiobook chapters are kept as small Opus files.

Speech sounds the same at 40 kbps mono Opus, so a typical 128 kbps MP3 episode shrinks to about a third. Only files
Sevbify downloaded into its own folder are converted; your music library is never touched. The original is removed
only after the new file has been checked (it opens and is as long as the original); if anything goes wrong the
original download is simply kept.
"""
import os
import subprocess
import sys

SPEECH_KBPS = 40


def _ffmpeg():
    try:
        from core import downloader
        ff = downloader.engine().ffmpeg_path()
        return ff or "ffmpeg"
    except Exception:
        return "ffmpeg"


def _length(path):
    try:
        from mutagen import File
        f = File(path)
        return float(f.info.length) if f is not None and getattr(f, "info", None) else 0.0
    except Exception:
        return 0.0


def _bitrate(path):
    try:
        from mutagen import File
        f = File(path)
        return int(getattr(f.info, "bitrate", 0) or 0) // 1000
    except Exception:
        return 0


def shrink_speech(path, kbps=SPEECH_KBPS, ffmpeg=None, run=subprocess.run):
    """Convert one downloaded episode / chapter to Opus. Returns the path to use (the new file, or the original)."""
    if not path or not os.path.isfile(path) or path.lower().endswith(".opus"):
        return path
    rate = _bitrate(path)
    if rate and rate <= kbps * 1.3:
        return path                                    # already small: nothing to gain
    before = _length(path)
    out = os.path.splitext(path)[0] + ".opus"
    part = out + ".part.opus"
    cmd = [ffmpeg or _ffmpeg(), "-v", "error", "-y", "-i", path, "-vn", "-map_metadata", "0", "-c:a", "libopus",
           "-b:a", f"{int(kbps)}k", "-ac", "1", "-application", "voip", part]
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.PIPE, "timeout": 3600}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x08000000                 # no console window
    try:
        r = run(cmd, **kw)
        ok = getattr(r, "returncode", 1) == 0 and os.path.isfile(part) and os.path.getsize(part) > 0
        after = _length(part) if ok else 0.0
        if not ok or (before and abs(after - before) > max(3.0, before * 0.02)):
            raise RuntimeError("the converted file didn't check out")
        os.replace(part, out)
        if os.path.abspath(out) != os.path.abspath(path):
            os.remove(path)
        return out
    except Exception:
        try:
            os.remove(part)
        except OSError:
            pass
        return path

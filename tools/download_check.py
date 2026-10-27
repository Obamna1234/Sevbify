"""Live check of the real download engine, run by GitHub Actions (reports only, never fails the build).

Downloads one Creative Commons song (Kevin MacLeod, "Monkeys Spinning Monkeys", CC BY 4.0) into a
temporary folder with the same code Sevbify uses, and reports the result as a GitHub notice/warning.
YouTube often blocks cloud servers, so a failure here doesn't necessarily mean downloads fail on a home PC.
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import downloader  # noqa: E402

SONG = "Kevin MacLeod - Monkeys Spinning Monkeys"


def _use_bundled_ffmpeg():
    """Use the same ffmpeg the built app bundles (from imageio-ffmpeg) when none is installed."""
    import shutil
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
    except ImportError:
        return
    folder = tempfile.mkdtemp()
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), os.path.join(folder, name))
    os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")


def main():
    _use_bundled_ffmpeg()
    problems = downloader.check_tools()
    if problems:
        print(f"::warning title=Download check: tools missing::{' | '.join(problems)}")
        return
    e = downloader.engine()
    with tempfile.TemporaryDirectory() as folder:
        log = []
        started = time.time()
        res = downloader.run_download([SONG], folder, log=log.append)
        took = time.time() - started
        print("\n".join(log))
        if res["paths"] and os.path.getsize(res["paths"][0]) > 100_000:
            path = res["paths"][0]
            tags = e.read_tags(path)
            print(f"::notice title=Download OK::{os.path.basename(path)} · {os.path.getsize(path) // 1024} KB"
                  f" · {took:.0f}s · tags: {tags} · yt-dlp {e.ytdlp_version()}")
        else:
            tail = " | ".join(line.strip() for line in log[-6:] if line.strip())
            print(f"::warning title=Download check failed (cloud servers are often blocked)::{tail[:900]}")


if __name__ == "__main__":
    main()

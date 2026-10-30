"""Save space: downloaded episodes become small Opus files; the original stays if anything goes wrong."""
import os
import shutil
import subprocess

import pytest

from core import space

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def make_mp3(path, secs=20):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=300:duration={secs}",
                    "-b:a", "128k", str(path)], check=True)


@pytest.mark.skipif(not HAVE_FFMPEG, reason="needs ffmpeg")
def test_episode_is_shrunk_and_checked(tmp_path):
    src = tmp_path / "ep.mp3"
    make_mp3(src)
    before = os.path.getsize(src)
    out = space.shrink_speech(str(src), ffmpeg="ffmpeg")
    assert out.endswith(".opus") and not src.exists()
    assert os.path.getsize(out) < before / 2
    assert abs(space._length(out) - 20) < 1


def test_original_is_kept_when_conversion_fails(tmp_path):
    src = tmp_path / "ep.mp3"
    src.write_bytes(b"ID3" + b"\0" * 4000)

    class Failed:
        returncode = 1
    out = space.shrink_speech(str(src), ffmpeg="ffmpeg", run=lambda *a, **k: Failed())
    assert out == str(src) and src.exists()
    assert not any(p.name.endswith(".part.opus") for p in tmp_path.iterdir())

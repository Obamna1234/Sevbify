"""In-app updates: download (only from Sevbify's releases, checksum-checked), unpack safely, swap and reopen."""
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import time
import zipfile

import pytest

from core import app_update
from core.sevby_engine import app_pick_release

URL = app_update.ALLOWED_PREFIX + "v5.0.0-beta.21/Sevbify-Linux.tar.gz"


class Resp(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def tgz(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_release_picks_each_platforms_file_and_its_checksum():
    rel = [{"tag_name": "v5.0.0-beta.21", "prerelease": True, "html_url": "https://x", "assets": [
        {"name": "Sevbify-Windows.zip", "browser_download_url": "https://w", "digest": "sha256:AB", "size": 5},
        {"name": "Sevbify-Android-debug-signed.apk", "browser_download_url": "https://d"},
        {"name": "Sevbify-Android.apk", "browser_download_url": "https://a", "digest": "sha256:cd", "size": 7},
        {"name": "Sevbify-iOS.ipa", "browser_download_url": "https://i"},
        {"name": "Sevbify-Linux.tar.gz", "browser_download_url": "https://l"}]}]
    assert app_pick_release(rel, True, "android")["url"] == "https://a"
    assert app_pick_release(rel, True, "android")["sha256"] == "cd"
    assert app_pick_release(rel, True, "windows")["sha256"] == "ab"
    assert app_pick_release(rel, True, "ios")["url"] == "https://i"
    assert app_pick_release(rel, True, "linux")["url"] == "https://l"
    assert app_pick_release(rel, False, "linux") is None                    # betas only for beta users


def test_download_only_from_sevbifys_releases_and_checks_the_checksum(tmp_path):
    tmp_path = tmp_path / "dl"
    data = b"new sevbify"
    good = hashlib.sha256(data).hexdigest()
    with pytest.raises(app_update.UpdateError):
        app_update.download("https://evil.example/Sevbify.zip", str(tmp_path), good)
    with pytest.raises(app_update.UpdateError):
        app_update.download(URL, str(tmp_path), "0" * 64, opener=lambda u: Resp(data))
    assert not tmp_path.exists() or not os.listdir(tmp_path)                # bad file thrown away
    seen = []
    path = app_update.download(URL, str(tmp_path), good, len(data), progress=seen.append, opener=lambda u: Resp(data))
    assert open(path, "rb").read() == data and seen[-1] == 1.0


def test_unpack_refuses_files_outside_its_folder(tmp_path):
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(tgz({"../evil": b"x"}))
    with pytest.raises(app_update.UpdateError):
        app_update.unpack(str(bad), str(tmp_path / "out"))
    z = tmp_path / "bad.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../../evil", "x")
    with pytest.raises(app_update.UpdateError):
        app_update.unpack(str(z), str(tmp_path / "out2"))
    assert not (tmp_path / "evil").exists()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Unix-style paths")
def test_install_target_is_the_app_bundle_on_a_mac_and_the_folder_elsewhere():
    assert app_update.install_target("/Applications/Sevbify.app/Contents/MacOS/Sevbify", "darwin") == \
        "/Applications/Sevbify.app"
    assert app_update.install_target("/opt/Sevbify/Sevbify", "linux") == "/opt/Sevbify"


def test_windows_script_waits_swaps_and_restores_on_failure(tmp_path):
    cmd = app_update.restart_command(r"C:\data\update\new\Sevbify", r"D:\Apps\Sevbify", 1234, str(tmp_path), "win32")
    text = open(cmd[2], encoding="utf-8").read()
    assert 'PID eq 1234' in text and r'move "D:\Apps\Sevbify" "D:\Apps\Sevbify.old"' in text
    assert "robocopy" in text and r'start "" "D:\Apps\Sevbify\Sevbify.exe"' in text


@pytest.mark.skipif(sys.platform.startswith("win"), reason="runs the shell script")
def test_linux_update_swaps_the_folder_after_the_app_closes(tmp_path):
    target = tmp_path / "install" / "Sevbify"
    target.mkdir(parents=True)
    (target / "Sevbify").write_text("#!/bin/sh\necho started > \"$(dirname \"$0\")/started\"\n")
    os.chmod(target / "Sevbify", 0o755)
    (target / "old-only.txt").write_text("old")
    archive = tmp_path / "Sevbify-Linux.tar.gz"
    archive.write_bytes(tgz({"Sevbify/Sevbify": b"#!/bin/sh\necho started > \"$(dirname \"$0\")/started\"\n",
                             "Sevbify/_internal/new.txt": b"new"}))
    new_app = app_update.unpack(str(archive), str(tmp_path / "data" / "update" / "new"))
    app = subprocess.Popen(["sleep", "1"])                                  # stands in for the running Sevbify
    cmd = app_update.restart_command(new_app, str(target), app.pid, str(tmp_path / "data"), "linux")
    subprocess.Popen(cmd)
    app.wait()
    deadline = time.time() + 15
    while time.time() < deadline and not (target / "started").exists():
        time.sleep(0.2)
    assert (target / "_internal" / "new.txt").read_text() == "new"
    assert not (target / "old-only.txt").exists() and not (tmp_path / "install" / "Sevbify.old").exists()
    assert (target / "started").exists()                                   # reopened

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
    assert 'PID eq 1234' in text and r'move "D:\Apps\Sevbify" "D:\Apps\Sevbify.sevbify-old-' in text
    assert "chcp 65001" in text and "rmdir /s /q \"D:\\Apps\\Sevbify\"" not in text
    assert "robocopy" in text and r'start "" "D:\Apps\Sevbify\Sevbify.exe"' in text


def _fake_app(folder, data, works=True):
    """A stand-in Sevbify: when it starts it notes that, and (if it 'works') tells the updater it opened."""
    confirm = f'cp "{data}/update/start-pending" "{data}/update/start-ok" 2>/dev/null; rm -f "{data}/update/start-pending"'
    return ("#!/bin/sh\necho started >> \"$(dirname \"$0\")/started\"\n" + (confirm + "\n" if works else "")).encode()


def _install(tmp_path, works=True):
    data = tmp_path / "data"
    target = tmp_path / "install" / "Sevbify"
    target.mkdir(parents=True)
    (target / "Sevbify").write_bytes(_fake_app(target, data))
    os.chmod(target / "Sevbify", 0o755)
    (target / "old-only.txt").write_text("old")
    archive = tmp_path / "Sevbify-Linux.tar.gz"
    archive.write_bytes(tgz({"Sevbify/Sevbify": _fake_app(target, data, works), "Sevbify/_internal/new.txt": b"new"}))
    new_app = app_update.unpack(str(archive), str(data / "update" / "new"))
    return data, target, new_app


def _run(cmd, seconds, done):
    app = subprocess.Popen(["sleep", "1"])                                  # stands in for the running Sevbify
    cmd = cmd(app.pid)
    proc = subprocess.Popen(cmd)
    app.wait()
    deadline = time.time() + seconds
    while time.time() < deadline and not done():
        time.sleep(0.2)
    return proc


@pytest.mark.skipif(sys.platform.startswith("win"), reason="runs the shell script")
def test_linux_update_swaps_the_folder_keeps_the_previous_one_and_checks_it_opened(tmp_path):
    data, target, new_app = _install(tmp_path)
    proc = _run(lambda pid: app_update.restart_command(new_app, str(target), pid, str(data / "update"), "linux"), 15,
                lambda: (data / "update" / "start-ok").exists())
    proc.wait(timeout=10)                                                   # it saw the new version open: done
    assert (target / "_internal" / "new.txt").read_text() == "new"
    assert not (target / "old-only.txt").exists()
    prev = tmp_path / "install" / "Sevbify.sevbify-previous"
    assert (prev / "old-only.txt").read_text() == "old"                     # the old version is kept
    assert sorted(p.name for p in (tmp_path / "install").iterdir()) == ["Sevbify", "Sevbify.sevbify-previous"]
    assert app_update.has_previous(str(target))
    assert app_update.take_rollback_note(str(data)) == ""


@pytest.mark.skipif(sys.platform.startswith("win"), reason="runs the shell script")
def test_a_new_version_that_never_opens_is_rolled_back(tmp_path, monkeypatch):
    monkeypatch.setattr(app_update, "START_WAIT", 2)
    data, target, new_app = _install(tmp_path, works=False)
    proc = _run(lambda pid: app_update.restart_command(new_app, str(target), pid, str(data / "update"), "linux"), 40,
                lambda: (data / "update" / "rolled-back").exists())
    proc.wait(timeout=20)
    assert (target / "old-only.txt").read_text() == "old"                   # the previous version is back
    assert not (target / "_internal").exists()
    assert [p.name for p in (tmp_path / "install").iterdir()] == ["Sevbify"]
    assert "previous version was put back" in app_update.take_rollback_note(str(data))
    assert app_update.take_rollback_note(str(data)) == ""                   # said once


@pytest.mark.skipif(sys.platform.startswith("win"), reason="runs the shell script")
def test_going_back_to_the_previous_version_by_hand_and_forward_again(tmp_path):
    data, target, new_app = _install(tmp_path)
    proc = _run(lambda pid: app_update.restart_command(new_app, str(target), pid, str(data / "update"), "linux"), 15,
                lambda: (data / "update" / "start-ok").exists())
    proc.wait(timeout=10)
    proc = _run(lambda pid: app_update.rollback_command(pid, str(data / "update"), str(target), "linux"), 15,
                lambda: (target / "old-only.txt").exists())
    proc.wait(timeout=10)
    assert (target / "old-only.txt").exists()                                # back on the old one
    assert (tmp_path / "install" / "Sevbify.sevbify-previous" / "_internal" / "new.txt").exists()   # new one kept


def test_confirm_started_only_answers_a_waiting_update(tmp_path):
    assert not app_update.confirm_started(str(tmp_path))
    (tmp_path / "update").mkdir()
    (tmp_path / "update" / "start-pending").write_text("abc123")
    assert app_update.confirm_started(str(tmp_path))
    assert (tmp_path / "update" / "start-ok").read_text() == "abc123"
    assert not (tmp_path / "update" / "start-pending").exists()


def test_windows_script_checks_the_new_version_opened_and_rolls_back(tmp_path):
    cmd = app_update.restart_command(r"C:\data\update\new\Sevbify", r"D:\Apps\Sevbify", 1234, str(tmp_path), "win32")
    text = open(cmd[2], encoding="utf-8").read()
    assert r'move "D:\Apps\Sevbify.sevbify-old-' in text and r'"D:\Apps\Sevbify.sevbify-previous"' in text
    assert "start-ok" in text and 'taskkill /F /IM "Sevbify.exe"' in text and "rolled-back" in text
    assert (tmp_path / "start-pending").read_text() in text                 # the token it waits for


def test_percent_signs_in_windows_paths_are_kept(tmp_path):
    cmd = app_update.restart_command(r"C:\data\new\Sevbify", r"C:\Tools\100%\Sevbify", 1, str(tmp_path), "win32")
    assert r"C:\Tools\100%%\Sevbify" in open(cmd[2], encoding="utf-8").read()


def test_only_a_real_sevbify_folder_is_ever_replaced(tmp_path):
    good = tmp_path / "Sevbify"
    (good / "_internal").mkdir(parents=True)
    (good / "Sevbify").write_text("x")
    assert app_update.looks_like_sevbify(str(good), "linux")
    (good / "My holiday photos").mkdir()                     # someone keeps other things in that folder
    assert not app_update.looks_like_sevbify(str(good), "linux")
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Sevbify").write_text("x")
    assert not app_update.looks_like_sevbify(str(desktop), "linux")


def test_the_shipped_folder_layout_can_be_updated(tmp_path):
    """What the release build ships (README, CHANGELOG; Linux: menu entry, installer, icon) must pass the check,
    or nobody gets updates."""
    from core import app_update
    for plat, exe, extra in (("win32", "Sevbify.exe", ["README.md", "CHANGELOG.md"]),
                             ("linux", "Sevbify", ["README.md", "CHANGELOG.md", "sevbify.desktop", "install.sh",
                                                   "sevbify.png"])):
        d = tmp_path / plat
        (d / "_internal").mkdir(parents=True)
        (d / exe).write_text("x")
        for n in extra:
            (d / n).write_text("x")
        assert app_update.looks_like_sevbify(str(d), platform=plat)
        (d / "my holiday photos").mkdir()
        assert not app_update.looks_like_sevbify(str(d), platform=plat)


def test_settings_offers_going_back_only_when_a_previous_version_is_kept(window, monkeypatch):
    from core import app_update as au
    window.open_settings()
    assert "go_back" not in window.settings_page.controls
    monkeypatch.setattr(au, "can_install", lambda: True)
    monkeypatch.setattr(au, "has_previous", lambda target=None: True)
    window.open_settings()
    assert "go_back" in window.settings_page.controls

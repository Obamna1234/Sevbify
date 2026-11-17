"""Regression tests for the beta.48 security review's findings."""
import os
import time

import pytest

from core import share_playlist as SP


def test_shared_names_are_never_markup():
    got = SP.read(SP.playlist_link('<b style="font-size:90px">Pwn</b>', [{"title": "&lt;a href=x&gt;", "artist": "A"}]))
    assert "<b" not in got["name"] and "</b" not in got["name"] and "&lt;" not in got["songs"][0]["title"]
    assert SP.clean_text("I <3 Rock & Roll", 100) == "I <3 Rock & Roll"            # ordinary text unchanged


def test_merge_is_fast_and_deep_files_fail_cleanly():
    theirs = [{"artist": f"A{i}", "title": f"T{i}"} for i in range(5000)]
    t = time.time()
    assert len(SP.merge([], theirs)["add"]) == 5000
    assert time.time() - t < 1.0
    with pytest.raises(SP.ShareError):
        SP.read('{"sevbify": 1, "x": ' + "[" * 200000)


def test_only_pages_from_our_own_soundcloud_search_are_remembered(monkeypatch):
    from core import streamer
    page = "https://soundcloud.com/someone/a-track"
    monkeypatch.setattr(streamer, "_save_pages", lambda: None)
    assert streamer.remember_page("Famous", "Song", "SoundCloud", page) is False    # e.g. from a shared link
    streamer._searched.add(page)
    assert streamer.remember_page("Famous", "Song", "SoundCloud", page) is True


def test_installed_copies_can_update_and_pkill_pattern_is_literal(tmp_path):
    from core import app_update
    d = tmp_path / "Sevbify"
    (d / "_internal").mkdir(parents=True)
    for n in ("Sevbify.exe", "unins000.exe", "unins000.dat"):
        (d / n).write_text("x")
    assert app_update.looks_like_sevbify(str(d), platform="win32")
    (d / "notes.docx").write_text("x")
    assert not app_update.looks_like_sevbify(str(d), platform="win32")
    target = str(tmp_path / "Apps (x86)" / "Sevbify.v2+")
    os.makedirs(target)
    cmd = app_update.restart_command(str(tmp_path / "new"), target, 1, str(tmp_path / "s"), platform="linux")
    script = open(cmd[-1]).read()
    assert "Apps \\(x86\\)" in script and "Sevbify\\.v2\\+" in script     # (any path separator)


def test_loudness_reads_only_a_plain_file(monkeypatch):
    from core import loudness
    import subprocess
    seen = {}

    class R:
        stderr = b""
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: seen.setdefault("cmd", cmd) and R())
    loudness.measure("concat:/a|/b", "ffmpeg")
    assert "file:concat:/a|/b" in seen["cmd"] and "file" in seen["cmd"]
    seen.clear()
    loudness.measure("https://x.example/a", "ffmpeg", headers={"User-Agent": "a\rX-Injected: 1"})
    assert "-headers" not in seen["cmd"]


def test_log_hides_keys_in_bare_links():
    from core.activity_log import _short
    out = _short("api.example.com/v1/a?api_key=SECRET and token=abc and me@example.org")
    assert "SECRET" not in out and "abc" not in out and "me@example.org" not in out

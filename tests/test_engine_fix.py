"""When YouTube or SoundCloud stop working: a fix is looked for at once, and you're told what's happening."""
from core import engine_fix, source_status


def setup_function(_):
    engine_fix.reset()
    source_status.reset()


def test_a_fix_is_downloaded_and_you_are_told_to_restart():
    assert engine_fix.start_if_due("SoundCloud", update=lambda: (True, "yt-dlp 2026.11.20 downloaded."))
    r = engine_fix.wait(5)
    assert r["fixed"] and "Restart Sevbify" in r["text"] and r["source"] == "SoundCloud"
    assert "your own music files and downloaded songs play as normal" in r["text"]      # the app isn't unusable


def test_already_newest_says_an_update_usually_follows():
    assert engine_fix.start_if_due("YouTube", update=lambda: (False, "yt-dlp 2026.11.1 is the newest version."))
    r = engine_fix.wait(5)
    assert not r["fixed"] and "already has the newest" in r["text"] and "Bandcamp" in r["text"]


def test_offline_check_says_try_later():
    assert engine_fix.start_if_due("YouTube", update=lambda: (False, "Couldn't reach GitHub to check yt-dlp."))
    assert "couldn't check" in engine_fix.wait(5)["text"]


def test_only_youtube_and_soundcloud_and_at_most_every_six_hours():
    assert not engine_fix.start_if_due("Deezer", update=lambda: (True, ""))
    assert engine_fix.start_if_due("YouTube", update=lambda: (False, "newest"), now=1000)
    engine_fix.wait(5)
    assert not engine_fix.start_if_due("SoundCloud", update=lambda: (False, "newest"), now=1000 + 3600)
    assert engine_fix.start_if_due("SoundCloud", update=lambda: (False, "newest"), now=1000 + 7 * 3600)
    engine_fix.wait(5)


def test_bridge_failure_starts_the_check_and_reports_it(monkeypatch):
    import json, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "android", "app", "src", "main", "python"))
    import sevbify_bridge as b
    calls = []
    monkeypatch.setattr(engine_fix, "start_if_due",
                        lambda src, update=None, now=None: calls.append(src) or True)
    monkeypatch.setattr(engine_fix, "wait", lambda timeout=120: engine_fix.explain("YouTube", True, ""))
    out = None
    for _ in range(source_status.THRESHOLD):
        out = json.loads(b._fail(RuntimeError("ERROR: [youtube] abc: Sign in to confirm you're not a bot"), "resolve"))
    assert out["engine_check"] is True and calls == ["YouTube"]
    res = json.loads(b.engine_fix_result())
    assert res["ok"] and res["value"]["fixed"]


def test_computer_shows_what_was_found(window, qapp, monkeypatch):
    from conftest import wait_until
    from PyQt6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append((self.text(), self.informativeText())) or 0)
    monkeypatch.setattr(engine_fix, "start_if_due", lambda src, update=None, now=None: src == "YouTube")
    monkeypatch.setattr(engine_fix, "wait", lambda timeout=120: engine_fix.explain("YouTube", False, "newest"))
    window._check_engine_fix("Deezer")
    window._check_engine_fix("YouTube")
    assert wait_until(qapp, lambda: shown)
    assert shown[0][0] == "YouTube isn't working right now" and "downloaded songs play as normal" in shown[0][1]

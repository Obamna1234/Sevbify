"""Update checks for Sevbify and yt-dlp. No internet: GitHub's answers are faked."""
from online_fixtures import FakeWeb


def release(tag, pre=False, assets=True):
    return {"tag_name": tag, "prerelease": pre, "draft": False, "html_url": f"https://github.com/x/releases/tag/{tag}",
            "assets": [{"name": "Sevbify-Windows.zip", "browser_download_url": f"https://dl/{tag}.zip"}] if assets else []}


def net_with(tmp_path, routes, offline=False):
    from core.online.net import NetClient
    return NetClient(str(tmp_path / "c"), enabled=lambda: True, opener=FakeWeb(routes, offline=offline))


def test_newer_beta_is_found_by_beta_testers(tmp_path):
    from core import updates
    net = net_with(tmp_path, {"api.github.com/repos/Obamna1234/Sevbify/releases": [
        release("v5.0.0-beta.7", pre=True), release("v5.0.0-beta.9", pre=True, assets=False),  # still building
        release("v5.0.0-beta.5", pre=True)]})
    r = updates.check_app(net, current="5.0.0-beta.6")
    assert r["checked"] and r["newer"] and r["latest"] == "5.0.0-beta.7"
    assert "5.0.0-beta.7 is available" in r["message"]
    r = updates.check_app(net, current="5.0.0-beta.7")
    assert not r["newer"] and "newest" in r["message"]


def test_private_repo_or_offline_says_so(tmp_path):
    from core import updates
    r = updates.check_app(net_with(tmp_path, {}), current="5.0.0-beta.6")        # GitHub answers 404 (private)
    assert not r["checked"] and "isn't public yet" in r["message"]
    r = updates.check_app(net_with(tmp_path, {}, offline=True), current="5.0.0-beta.6")
    assert not r["checked"]


def test_ytdlp_update(monkeypatch):
    from core import updates, downloader
    e = downloader.engine()
    monkeypatch.setattr(e, "ytdlp_version", lambda: "2026.10.26")
    assert updates.check_ytdlp("2026.11.02")["newer"] and not updates.check_ytdlp("2026.10.26")["newer"]
    monkeypatch.setattr(e, "ytdlp_latest_tag", lambda: "2026.11.02")
    got = []
    changed, msg = updates.update_ytdlp(download=lambda tag: got.append(tag) or (True, "ok"))
    assert changed and got == ["2026.11.02"] and "Restart Sevbify" in msg
    monkeypatch.setattr(e, "ytdlp_latest_tag", lambda: None)
    assert updates.update_ytdlp(download=lambda tag: (True, "ok"))[0] is False


def test_settings_buttons(window, qapp, tmp_path, monkeypatch):
    from core import updates
    window.net = net_with(tmp_path, {"api.github.com/repos/Obamna1234/Sevbify/releases": [release("v9.0.0")]})
    monkeypatch.setattr(updates, "check_ytdlp", lambda latest_tag=None: {"current": "1", "latest": "2", "newer": True})
    window.open_settings()
    window.settings_page.controls["check_updates"].click()
    from conftest import wait_until
    assert wait_until(qapp, lambda: "9.0.0 is available" in window.settings_page.app_update_label.text())
    assert wait_until(qapp, lambda: "yt-dlp 2 is available" in window.settings_page.ytdlp_label.text())
    assert window.user_data.last_update_check > 0


def test_ytdlp_update_is_checked_against_the_official_checksum(tmp_path):
    import hashlib
    from core import updates
    good = b"PK\x03\x04 pretend yt-dlp"
    sums = f"{hashlib.sha256(good).hexdigest()}  yt-dlp\n{'0' * 64}  yt-dlp.exe\n".encode()

    def fetch(body):
        return lambda url: sums if url.endswith("SHA2-256SUMS") else body

    ok, msg = updates.download_verified_ytdlp("2026.10.26", fetch=fetch(good), dest_dir=str(tmp_path))
    assert ok and (tmp_path / "yt-dlp").read_bytes() == good
    (tmp_path / "yt-dlp").unlink()
    ok, msg = updates.download_verified_ytdlp("2026.10.26", fetch=fetch(b"tampered"), dest_dir=str(tmp_path))
    assert not ok and "checksum" in msg and not (tmp_path / "yt-dlp").exists()
    ok, msg = updates.download_verified_ytdlp("../../evil", fetch=fetch(good), dest_dir=str(tmp_path))
    assert not ok

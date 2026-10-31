"""Security hardening from the full review (October 2026)."""
import os
import urllib.request

import pytest

from core.online import net


def test_links_never_reach_your_own_network():
    for host in ("127.0.0.1", "192.168.1.1", "10.0.0.5", "169.254.169.254", "localhost", "router.local", "[::1]"):
        assert not net.is_public_host(host.strip("[]")), host
        with pytest.raises(net.ServiceError):
            net.check_public_url(f"http://{host}/x")
    with pytest.raises(net.ServiceError):
        net.check_public_url("file:///etc/passwd")


def test_redirects_only_to_public_web_addresses():
    h = net._SafeRedirect()
    req = urllib.request.Request("https://feeds.example.com/x")
    for bad in ("file:///etc/passwd", "ftp://x.example.com/a", "http://192.168.1.1/admin", "http://127.0.0.1:8080/"):
        with pytest.raises(urllib.error.HTTPError):
            h.redirect_request(req, None, 302, "Found", {}, bad)


def test_clear_cache_also_removes_saved_pages(tmp_path):
    c = net.NetClient(str(tmp_path / "c"))
    os.makedirs(tmp_path / "c" / "pages")
    (tmp_path / "c" / "pages" / "feed.html").write_text("my podcast feed")
    c.clear_cache()
    assert not os.listdir(tmp_path / "c" / "pages")


def test_every_spelling_of_a_network_path_is_caught():
    from core.importers import is_network_path
    for p in ("\\\\evil\\s\\a.mp3", "//evil/s/a.mp3", "/\\evil\\s\\a.mp3", "\\/evil/s/a.mp3"):
        assert is_network_path(p), p
    for p in ("C:\\Music\\a.mp3", "/home/me/a.mp3", "a.mp3", "Music/a.mp3"):
        assert not is_network_path(p), p


def test_feeds_with_entities_anywhere_are_refused():
    from core import podcasts
    bomb = b'<?xml version="1.0"?>' + b"<!--" + b"x" * 300_000 + b"-->" + b'<!DOCTYPE r [<!ENTITY a "x">]><rss/>'
    with pytest.raises(ValueError):
        podcasts.parse_feed(bomb)


def test_podcast_youtube_only_reads_youtube():
    from core import podcasts
    with pytest.raises(ValueError):
        podcasts.fetch_youtube_channel("https://evil.example.com/videos", extract=lambda u: {})
    with pytest.raises(ValueError):
        podcasts.youtube_stream("https://evil.example.com/watch?v=x", extract=lambda u: {"url": "x"})
    assert podcasts.is_youtube_video("https://www.youtube.com/watch?v=abc")
    assert not podcasts.is_youtube_video("https://youtube.com.evil.example/watch?v=abc")


def test_a_profile_file_never_switches_online_features_on():
    from core import profile
    on = profile.normalise({"settings": {"online": True, "autoplay": False}})
    assert "online" not in on["settings"] and on["settings"]["autoplay"] is False
    off = profile.normalise({"settings": {"online": False}})
    assert off["settings"]["online"] is False


@pytest.mark.skipif(os.name != "posix", reason="file modes are a Mac/Linux thing")
def test_your_data_is_readable_only_by_you(tmp_path):
    from core.storage import Storage, UserData, keep_private, write_private
    s = Storage(str(tmp_path / "Sevbify"))
    s.save(UserData())
    assert os.stat(s.path).st_mode & 0o077 == 0
    other = tmp_path / "Sevbify" / "old.json"
    other.write_text("{}")
    os.chmod(other, 0o644)
    keep_private(str(tmp_path / "Sevbify"))
    assert os.stat(other).st_mode & 0o077 == 0 and os.stat(tmp_path / "Sevbify").st_mode & 0o077 == 0
    write_private(str(tmp_path / "x.json"), "{}")
    assert os.stat(tmp_path / "x.json").st_mode & 0o077 == 0


def test_a_small_song_file_is_kept_not_deleted(tmp_path):
    from core import sevby_engine
    small = tmp_path / "Song.mp3"
    small.write_bytes(b"short jingle")
    assert sevby_engine.existing_song(str(tmp_path), "Song") is None
    assert not small.exists() and (tmp_path / "Song.mp3.incomplete").read_bytes() == b"short jingle"
    small.write_bytes(b"again")
    sevby_engine.existing_song(str(tmp_path), "Song")
    assert (tmp_path / "Song.mp3.incomplete2").read_bytes() == b"again"


def test_cover_pictures_use_a_private_temporary_folder():
    import tempfile
    from core import sevby_engine
    p = sevby_engine._tmp_path("cover.jpg")
    folder = os.path.dirname(p)
    assert folder != tempfile.gettempdir() and os.path.basename(folder).startswith("sevbify-")
    if os.name == "posix":
        assert os.stat(folder).st_mode & 0o077 == 0
    assert not sevby_engine._image_url_ok("http://192.168.1.1/cover.jpg")
    assert not sevby_engine._image_url_ok("file:///etc/passwd")


def test_only_web_links_are_opened(monkeypatch):
    import ui
    from PyQt6.QtGui import QDesktopServices
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda u: opened.append(u.toString()))
    for bad in ("file:///C:/Windows/System32/calc.exe", "smb://evil/share", "ms-settings:", "javascript:alert(1)",
                "\\\\evil\\share\\x.exe", ""):
        assert not ui.open_web(bad)
    assert ui.open_web("https://example.com/a") and opened == ["https://example.com/a"]


def test_message_boxes_never_read_names_as_html(qapp):
    import ui  # noqa: F401  (installs the plain-text rule)
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QMessageBox
    box = QMessageBox(QMessageBox.Icon.Question, "t", "<img src='file:///x'>")
    assert box.textFormat() == Qt.TextFormat.PlainText
    box.deleteLater()
    qapp.processEvents()


def test_windows_programs_are_run_by_full_path(monkeypatch):
    from core import shortcuts
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    assert shortcuts.system_program("powershell").lower().endswith(r"system32\windowspowershell\v1.0\powershell.exe")
    assert shortcuts.system_program("cmd").lower().endswith(r"system32\cmd.exe")


def test_rebinding_to_your_network_is_caught_when_connecting(monkeypatch):
    """Even if the name looked public when checked, the connection itself is refused if it reaches a home
    address (DNS rebinding)."""
    import http.server
    import threading
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        monkeypatch.delenv(k, raising=False)
    srv = http.server.HTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    opener = urllib.request.build_opener(net._CheckedHTTP)
    with pytest.raises(Exception, match="own network"):
        opener.open(f"http://127.0.0.1:{srv.server_port}/", timeout=5)
    srv.server_close()


def test_carrier_nat_and_unknown_hosts_are_not_public(monkeypatch):
    assert not net.is_public_ip("100.64.1.2")          # carrier NAT / Tailscale
    assert not net.is_public_ip("::ffff:192.168.0.1")
    assert net.is_public_ip("8.8.8.8")
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        monkeypatch.delenv(k, raising=False)
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(OSError("SERVFAIL")))
    net._HOST_OK.clear()
    assert not net.is_public_host("feeds.example.org")   # can't look it up: refused, not assumed public


def test_feed_links_to_your_own_network_are_dropped():
    from core import podcasts
    feed = b"""<?xml version="1.0"?><rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
      <title>Pod</title><itunes:image href="http://192.168.1.1/cgi-bin/reboot"/>
      <item><title>Router</title><enclosure url="http://192.168.1.1/apply.cgi?x=1" type="audio/mpeg"/></item>
      <item><title>Nas</title><enclosure url="http://nas.local/a.mp3" type="audio/mpeg"/></item>
      <item><title>Real</title><enclosure url="https://cdn.example.com/ep.mp3" type="audio/mpeg"/></item>
    </channel></rss>"""
    show, eps = podcasts.parse_feed(feed, "https://feeds.example.com/rss")
    assert [e.track.title for e in eps] == ["Real"] and show.image_url == ""


def test_profiles_leave_out_songs_from_your_own_server():
    from core import profile
    d = profile.normalise({"playlists": [{"name": "Mine", "tracks": [
        {"title": "A", "artist": "B", "source": "jellyfin", "stream_url": "https://jf.home.example/Audio/1"},
        {"title": "C", "artist": "D", "cover_url": "http://10.0.0.2/c.jpg"}]}]})
    assert d["playlists"][0]["tracks"] == [{"title": "C", "artist": "D"}]


def test_song_lookups_only_use_bandcamp_and_youtube():
    from core import sevby_engine
    assert sevby_engine.SONG_EXTRACTORS == ["Bandcamp", "youtube", "youtube:.*"]


def test_tooltips_show_titles_as_written(qapp):
    import ui
    from PyQt6.QtWidgets import QLabel
    lbl = QLabel()
    lbl.setToolTip('<a href="file:///x">click</a>')
    assert "&lt;a" in lbl.toolTip()
    lbl.setToolTip("Queue")
    assert lbl.toolTip() == "Queue"
    assert ui.as_plain("a & b") == "<qt>a &amp; b</qt>"

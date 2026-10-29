"""Links from outside (podcast feeds, imported playlists) can only point at the web, and feeds can't blow up."""
import pytest

from core.online.net import NetClient, ServiceError, is_web_url
from core import podcasts


def test_only_web_addresses_count():
    assert is_web_url("https://example.com/a.mp3") and is_web_url("http://example.com")
    for bad in ("file:///C:/Windows/System32/calc.exe", "file:///etc/passwd", "\\\\server\\share\\x.exe",
                "javascript:alert(1)", "ftp://example.com/x", "https://", "", None, "C:\\x.mp3"):
        assert not is_web_url(bad), bad


def test_net_refuses_local_files(tmp_path):
    net = NetClient(str(tmp_path / "cache"))
    secret = tmp_path / "secret.txt"
    secret.write_text("private")
    with pytest.raises(ServiceError):
        net.get_text(secret.as_uri())
    with pytest.raises(ServiceError):
        net.download(secret.as_uri(), str(tmp_path / "copy.txt"))
    assert not (tmp_path / "copy.txt").exists()


FEED = """<?xml version="1.0"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
<title>Show</title><link>file:///C:/evil.exe</link><itunes:image href="file:///etc/passwd"/>
<item><title>Good</title><link>https://example.com/ep1</link><enclosure url="https://example.com/ep1.mp3"/></item>
<item><title>Local file</title><link>file:///C:/evil.exe</link><enclosure url="file:///C:/Users/me/secret.mp3"/></item>
</channel></rss>"""


def test_feed_keeps_only_web_links():
    show, episodes = podcasts.parse_feed(FEED, "https://example.com/feed")
    assert show.link == "" and show.image_url == ""
    assert [e.track.title for e in episodes] == ["Good"]
    assert episodes[0].track.page_url == "https://example.com/ep1"


def test_feed_with_entities_is_refused():
    bomb = ('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;">]>'
            '<rss><channel><title>&b;</title></channel></rss>')
    with pytest.raises(ValueError):
        podcasts.parse_feed(bomb)

"""Bandcamp read directly: the track page's player data gives the full song's MP3 link."""
import html
import json

import pytest

from core import bandcamp

PAGE = "https://perturbator.bandcamp.com/track/future-club"


def page_with(data):
    return f'<html><script data-tralbum="{html.escape(json.dumps(data))}" data-x="1"></script></html>'


def test_reads_the_mp3_link_title_and_length():
    data = {"artist": "Perturbator", "album_title": "Dangerous Days", "art_id": 123,
            "trackinfo": [{"title": "Future Club", "duration": 288.5,
                           "file": {"mp3-128": "https://t4.bcbits.com/stream/abc/mp3-128/1?p=0&ts=1&t=x"}}]}
    url, headers, secs = bandcamp.stream(PAGE, opener=lambda u: page_with(data))
    assert url.startswith("https://t4.bcbits.com/stream/") and "&ts=1" in url and secs == 288.5
    info = bandcamp.track_info(PAGE, opener=lambda u: page_with(data))
    assert info["artist"] == "Perturbator" and info["cover"].endswith("a123_10.jpg")


def test_tracks_bandcamp_wont_stream_and_odd_pages_are_refused():
    with pytest.raises(bandcamp.NotPlayable):
        bandcamp.stream(PAGE, opener=lambda u: page_with({"trackinfo": [{"title": "x", "file": None}]}))
    with pytest.raises(bandcamp.NotPlayable):
        bandcamp.stream(PAGE, opener=lambda u: "<html>changed</html>")
    with pytest.raises(bandcamp.NotPlayable):
        bandcamp.stream("https://evil.example.com/track/x", opener=lambda u: "")
    assert not bandcamp.is_track_page("https://bandcamp.com.evil.com/track/x")


def test_streaming_uses_bandcamp_directly(monkeypatch):
    from core import streamer, downloader
    monkeypatch.setattr(bandcamp, "stream", lambda page, opener=None: ("https://t4.bcbits.com/s", {"User-Agent": "x"}, 200))
    url, headers, secs = streamer._extract(downloader.engine(), PAGE)
    assert url == "https://t4.bcbits.com/s" and secs == 200


def test_mp3_link_must_be_bandcamps_own_file_server():
    import json, html
    from core import bandcamp
    data = {"trackinfo": [{"file": {"mp3-128": "https://192.168.1.1/x.mp3"}, "duration": 3, "title": "t"}]}
    page = f'<div data-tralbum="{html.escape(json.dumps(data))}"></div>'
    with pytest.raises(bandcamp.NotPlayable):
        bandcamp.parse_track_page(page)


def test_app_api_is_used_first_so_the_client_challenge_page_is_avoided(monkeypatch):
    """Windows report: Bandcamp showed a home connection its "Client Challenge" page. The search gives the band and
    track ids; Bandcamp's app API (as NewPipe uses) then gives the MP3 without the web page."""
    import io
    import json
    from core import bandcamp
    page = "https://earmake.bandcamp.com/track/im-the-law-3"
    bandcamp.remember_ids(page, "123", 456)
    asked = []

    def urlopen(req, timeout=0):
        asked.append(req.full_url)
        body = {"tracks": [{"title": "I'm the Law", "band_name": "Earmake", "duration": 242.5,
                            "streaming_url": {"mp3-128": "https://t4.bcbits.com/stream/abc/mp3-128/1?p=0"}}]}
        r = io.BytesIO(json.dumps(body).encode())
        r.__enter__ = lambda *a: r
        r.__exit__ = lambda *a: False
        return r
    monkeypatch.setattr(bandcamp.urllib.request, "urlopen", urlopen)
    url, headers, secs = bandcamp.stream(page)
    assert url.startswith("https://t4.bcbits.com/") and secs == 242.5
    assert asked[0].startswith(bandcamp.MOBILE_API) and "band_id=123" in asked[0] and "tralbum_id=456" in asked[0]
    # a link anywhere but Bandcamp's file servers is never used
    import pytest
    with pytest.raises(bandcamp.NotPlayable):
        bandcamp.parse_mobile_details({"tracks": [{"streaming_url": {"mp3-128": "https://evil.example/a.mp3"}}]})
    bandcamp.remember_ids("https://evil.example/track/x", 1, 2)          # only real track pages are remembered
    assert "https://evil.example/track/x" not in bandcamp._ids

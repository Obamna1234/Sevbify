"""The relay that streams song links to the player through yt-dlp's networking (beta.47 Windows log: YouTube
refused the player's own requests for links that downloaded fine)."""
import io
import urllib.error
import urllib.request

import pytest

from core import stream_relay


class _Resp(io.BytesIO):
    def __init__(self, data, status=206, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


def test_relay_passes_ranges_through_and_only_relays_song_servers(monkeypatch):
    asked = []

    def fake_open(url, headers):
        asked.append((url, headers))
        return _Resp(b"abcd", 206, {"Content-Type": "audio/mp4", "Content-Length": "4",
                                    "Content-Range": "bytes 10-13/100"})
    monkeypatch.setattr(stream_relay, "_open", fake_open)
    local = stream_relay.local_address("https://rr3---sn-x.googlevideo.com/videoplayback?id=1", {"User-Agent": "UA"})
    assert local.startswith("http://127.0.0.1:")
    req = urllib.request.Request(local, headers={"Range": "bytes=10-13"})
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 206 and r.read() == b"abcd" and r.headers["Content-Range"] == "bytes 10-13/100"
    assert asked[0][0].startswith("https://rr3---sn-x.googlevideo.com/") and asked[0][1] == {
        "User-Agent": "UA", "Range": "bytes=10-13"}
    # a wrong secret / unknown id: nothing
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(local.rsplit("/", 2)[0] + "/nope/x", timeout=5)
    # only https links on the song sites' servers are ever relayed
    for bad in ("http://rr3.googlevideo.com/x", "https://evil.example/a.m4a", "https://googlevideo.com.evil.example/x",
                "https://127.0.0.1/x"):
        assert stream_relay.local_address(bad) == ""
    stream_relay.stop()

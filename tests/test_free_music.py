"""Free-music sources: only Creative Commons / public domain items are used."""
from core.online.free_music import FreeMusic, _seconds


class FakeNet:
    def __init__(self, routes):
        self.routes = routes

    def get_json(self, url, params=None, ttl=0):
        for key, value in self.routes.items():
            if key in url:
                return value
        return {}


def test_seconds_parsing():
    assert _seconds("183.4") == 183
    assert _seconds("03:03") == 183
    assert _seconds("") == 0
    assert _seconds("bad") == 0


def test_jamendo_needs_client_id():
    assert FreeMusic(FakeNet({}), "").jamendo("anything") == []


def test_jamendo_respects_download_permission():
    net = FakeNet({"jamendo": {"headers": {"status": "success"}, "results": [
        {"id": 1, "name": "Song A", "artist_name": "Artist", "duration": 200, "audio": "s1",
         "audiodownload": "d1", "audiodownload_allowed": True},
        {"id": 2, "name": "Song B", "artist_name": "Artist", "duration": 100, "audio": "s2",
         "audiodownload": "d2", "audiodownload_allowed": False}]}})
    a, b = FreeMusic(net, "key").jamendo("artist")
    assert a.download_url == "d1" and a.duration_ms == 200000
    assert b.download_url == "" and b.stream_url == "s2"


def test_archive_skips_closed_licences():
    net = FakeNet({"metadata/closed": {"metadata": {"licenseurl": "", "title": "X"},
                                       "files": [{"name": "a.mp3", "format": "VBR MP3"}]},
                   "metadata/open": {"metadata": {"licenseurl": "https://creativecommons.org/licenses/by/4.0/",
                                                  "title": "Album", "creator": "Band"},
                                     "files": [{"name": "01 - Tune.mp3", "format": "VBR MP3", "length": "02:00"},
                                               {"name": "cover.jpg", "format": "JPEG"}]}})
    fm = FreeMusic(net)
    assert fm.archive_item("closed") == []
    tracks = fm.archive_item("open")
    assert len(tracks) == 1
    t = tracks[0]
    assert t.title == "Tune" and t.artist == "Band" and t.duration_ms == 120000
    assert t.download_url.endswith("/open/01%20-%20Tune.mp3")

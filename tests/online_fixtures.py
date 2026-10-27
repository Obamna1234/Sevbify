"""Fake web responses for online tests (shapes follow each service's documented API)."""
import json


def deezer_track(i, title, artist, artist_id, album="Album", duration=200, readable=True):
    return {"id": 1000 + i, "readable": readable, "title": title, "title_short": title,
            "link": f"https://www.deezer.com/track/{1000 + i}", "duration": duration,
            "preview": f"https://cdnt-preview.dzcdn.net/{i}.mp3",
            "artist": {"id": artist_id, "name": artist, "link": f"https://www.deezer.com/artist/{artist_id}",
                       "picture_xl": f"https://e-cdns-images.dzcdn.net/artist/{artist_id}.jpg", "type": "artist"},
            "album": {"id": 500 + i, "title": album, "cover_xl": f"https://e-cdns-images.dzcdn.net/cover/{i}.jpg",
                      "type": "album"},
            "type": "track"}


ROUTES = {
    "api.deezer.com/search/artist": {"data": [
        {"id": 77, "name": "Mega Drive 2", "nb_fan": 10, "link": "https://www.deezer.com/artist/77"},
        {"id": 42, "name": "Mega Drive", "nb_fan": 85860, "picture_xl": "https://img/megadrive.jpg",
         "link": "https://www.deezer.com/artist/42", "type": "artist"}], "total": 2},
    "api.deezer.com/search": {"data": [
        deezer_track(1, "NARC", "Mega Drive", 42, "198XAD", 284),
        deezer_track(2, "Locked Track", "Someone", 9, readable=False),
        deezer_track(3, "Gamechanger", "Fury Weekend", 43, "Escape From Neon City", 257)], "total": 3},
    "api.deezer.com/artist/42/radio": {"data": [
        deezer_track(10, "Raining Steel", "Perturbator", 50),
        deezer_track(11, "NARC", "Mega Drive", 42),                     # seed song: must be dropped
        deezer_track(12, "Sometimes", "Orax", 51),
        deezer_track(13, "Remoteness", "Donbor", 52),
        deezer_track(14, "Remoteness", "Donbor", 52),                   # duplicate: dropped
        deezer_track(15, "Track A", "Mega Drive", 42),
        deezer_track(16, "Track B", "Mega Drive", 42),
        deezer_track(17, "Track C", "Mega Drive", 42),
        deezer_track(18, "Track D", "Mega Drive", 42)]},                # 4th song by seed artist: capped
    "api.deezer.com/artist/42/related": {"data": [{"id": 60, "name": "Dan Terminus"}, {"id": 61, "name": "DEADLIFE"}]},
    "api.deezer.com/artist/60/top": {"data": [deezer_track(20, "Avalanche", "Dan Terminus", 60)]},
    "api.deezer.com/artist/61/top": {"data": [deezer_track(21, "A Dream Drawn from Darkness", "DEADLIFE", 61)]},
    "api.deezer.com/track/1001": {"id": 1001, "album": {"id": 501}},
    "api.deezer.com/album/501": {"id": 501, "genres": {"data": [{"id": 106, "name": "Electro"}]}},
    "ws.audioscrobbler.com/2.0/?method=artist.getInfo": {"artist": {
        "name": "Mega Drive", "url": "https://www.last.fm/music/Mega+Drive",
        "stats": {"listeners": "123456", "playcount": "999"},
        "tags": {"tag": [{"name": "synthwave"}, {"name": "darksynth"}]},
        "bio": {"summary": 'Mega Drive is a darksynth producer from Texas. <a href="https://www.last.fm/music/Mega+Drive">Read more on Last.fm</a>'}}},
    "ws.audioscrobbler.com/2.0/?method=track.getSimilar": {"similartracks": {"track": [
        {"name": "Turbo Killer", "duration": 240, "url": "https://www.last.fm/music/Carpenter+Brut/_/Turbo+Killer",
         "artist": {"name": "Carpenter Brut"}}]}},
    "en.wikipedia.org/api/rest_v1/page/summary/Perturbator_(band)": {"type": "disambiguation", "extract": "may refer to"},
    "en.wikipedia.org/api/rest_v1/page/summary/Perturbator_(musician)": {
        "type": "standard", "extract": "James Kent, known as Perturbator, is a French synthwave musician.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Perturbator"}}},
}


class FakeWeb:
    """Callable used as NetClient(opener=...). Longest matching route wins."""

    def __init__(self, routes=None, offline=False):
        self.routes = dict(ROUTES if routes is None else routes)
        self.offline = offline
        self.calls = []

    def __call__(self, url):
        import urllib.error
        self.calls.append(url)
        if self.offline:
            raise urllib.error.URLError("network unreachable")
        bare = url.split("://", 1)[-1]
        best = None
        for k in self.routes:
            if bare.startswith(k) or k in bare:
                if best is None or len(k) > len(best):
                    best = k
        if best is None:
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)
        value = self.routes[best]
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):                 # a web page (HTML / XML / text)
            return value.encode("utf-8")
        return json.dumps(value).encode("utf-8")

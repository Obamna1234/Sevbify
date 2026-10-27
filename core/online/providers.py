"""Online music data sources.

Deezer        public API, no key needed: catalogue search, cover art, artist
              photos and fan counts, 30-second previews, artist radio,
              related artists. Limit ~50 requests / 5 s (NetClient spaces them).
Last.fm       optional (free API key in Settings): similar tracks, artist
              bios, listener counts, tags/genres.
Wikipedia     artist summaries when Last.fm has no bio.

All functions are blocking: call them from a background task.
"""
import random
import re

from .models import OnlineTrack
from .net import ServiceError

DEEZER = "https://api.deezer.com"
LASTFM = "https://ws.audioscrobbler.com/2.0/"
WIKI = "https://en.wikipedia.org/api/rest_v1/page/summary/"


# ---------------------------------------------------------------------------
class Deezer:
    def __init__(self, net):
        self.net = net

    def _get(self, path, params=None, ttl=24 * 3600):
        data = self.net.get_json(DEEZER + path, params, ttl=ttl)
        if isinstance(data, dict) and "error" in data:
            err = data["error"] or {}
            if err.get("code") == 800:          # "no data"
                return {"data": []}
            raise ServiceError(f"Deezer: {err.get('message', 'error')}")
        return data

    @staticmethod
    def track_from(d, genre=""):
        artist = d.get("artist") or {}
        album = d.get("album") or {}
        return OnlineTrack(
            title=d.get("title") or d.get("title_short") or "",
            artist=artist.get("name", ""),
            album=album.get("title", ""),
            duration_ms=int(d.get("duration") or 0) * 1000,
            cover_url=album.get("cover_xl") or album.get("cover_big") or album.get("cover_medium") or "",
            preview_url=d.get("preview") or "",
            source="deezer",
            source_id=str(d.get("id", "")),
            artist_id=str(artist.get("id", "")),
            page_url=d.get("link") or "",
            genre=genre,
        )

    def search(self, query, limit=25):
        data = self._get("/search", {"q": query, "limit": limit}, ttl=6 * 3600)
        return [self.track_from(d) for d in data.get("data", []) if d.get("readable", True)]

    def find_track(self, artist, title):
        q = f'artist:"{artist}" track:"{title}"'
        data = self._get("/search", {"q": q, "limit": 5}, ttl=7 * 24 * 3600)
        items = data.get("data", [])
        if not items:
            items = self._get("/search", {"q": f"{artist} {title}", "limit": 5}, ttl=7 * 24 * 3600).get("data", [])
        return self.track_from(items[0]) if items else None

    def find_artist(self, name):
        data = self._get("/search/artist", {"q": name, "limit": 5}, ttl=7 * 24 * 3600)
        items = data.get("data", [])
        wanted = name.casefold()
        for a in items:
            if a.get("name", "").casefold() == wanted:
                return a
        return items[0] if items else None

    def artist(self, artist_id):
        return self._get(f"/artist/{artist_id}", ttl=7 * 24 * 3600)

    def related(self, artist_id, limit=10):
        return self._get(f"/artist/{artist_id}/related", {"limit": limit}, ttl=7 * 24 * 3600).get("data", [])

    def top_tracks(self, artist_id, limit=5):
        data = self._get(f"/artist/{artist_id}/top", {"limit": limit}, ttl=24 * 3600)
        return [self.track_from(d) for d in data.get("data", [])]

    def artist_radio(self, artist_id, limit=25):
        data = self._get(f"/artist/{artist_id}/radio", {"limit": limit}, ttl=6 * 3600)
        return [self.track_from(d) for d in data.get("data", [])]

    def album_genre(self, album_id):
        data = self._get(f"/album/{album_id}", ttl=30 * 24 * 3600)
        genres = (data.get("genres") or {}).get("data") or []
        return genres[0].get("name", "") if genres else ""

    def track_genre(self, track_id):
        data = self._get(f"/track/{track_id}", ttl=30 * 24 * 3600)
        album_id = (data.get("album") or {}).get("id")
        return self.album_genre(album_id) if album_id else ""


# ---------------------------------------------------------------------------
class LastFm:
    def __init__(self, net, api_key):
        self.net = net
        self.api_key = (api_key or "").strip()

    @property
    def available(self):
        return bool(self.api_key)

    def _get(self, method, ttl=7 * 24 * 3600, **params):
        if not self.available:
            raise ServiceError("Last.fm API key not set")
        data = self.net.get_json(LASTFM, {"method": method, "api_key": self.api_key,
                                          "format": "json", "autocorrect": 1, **params}, ttl=ttl)
        if isinstance(data, dict) and "error" in data:
            if data.get("error") in (6, 7):     # not found
                return {}
            raise ServiceError(f"Last.fm: {data.get('message', 'error')}")
        return data

    def similar_tracks(self, artist, title, limit=40):
        data = self._get("track.getSimilar", artist=artist, track=title, limit=limit)
        out = []
        for t in ((data.get("similartracks") or {}).get("track") or []):
            a = t.get("artist") or {}
            out.append(OnlineTrack(title=t.get("name", ""), artist=a.get("name", "") if isinstance(a, dict) else str(a),
                                   duration_ms=int(t.get("duration") or 0) * 1000, source="lastfm",
                                   page_url=t.get("url", "")))
        return out

    def artist_info(self, name):
        a = self._get("artist.getInfo", artist=name).get("artist") or {}
        if not a:
            return {}
        stats = a.get("stats") or {}
        tags = [t.get("name") for t in ((a.get("tags") or {}).get("tag") or []) if t.get("name")]
        bio = ((a.get("bio") or {}).get("summary") or "").strip()
        bio = re.sub(r"<a [^>]*>Read more on Last\.fm</a>\.?", "", bio).strip()
        bio = re.sub(r"<[^>]+>", "", bio).strip()
        return {"listeners": int(stats.get("listeners") or 0), "tags": tags[:5], "bio": bio,
                "url": a.get("url", "")}

    def track_tags(self, artist, title):
        data = self._get("track.getTopTags", artist=artist, track=title)
        return [t.get("name") for t in ((data.get("toptags") or {}).get("tag") or [])[:5] if t.get("name")]


# ---------------------------------------------------------------------------
class Wikipedia:
    MUSIC_WORDS = ("band", "musician", "singer", "rapper", "producer", "dj", "duo", "group",
                   "songwriter", "composer", "artist", "music", "record")

    def __init__(self, net):
        self.net = net

    def artist_summary(self, name):
        for title in (f"{name} (band)", f"{name} (musician)", f"{name} (rapper)", name):
            try:
                data = self.net.get_json(WIKI + title.replace(" ", "_").replace("/", "%2F"), ttl=14 * 24 * 3600)
            except ServiceError:
                continue
            if not isinstance(data, dict) or data.get("type") == "disambiguation":
                continue
            extract = (data.get("extract") or "").strip()
            if extract and any(w in extract.casefold() for w in self.MUSIC_WORDS):
                url = ((data.get("content_urls") or {}).get("desktop") or {}).get("page", "")
                return {"bio": extract, "url": url,
                        "picture_url": (data.get("thumbnail") or {}).get("source", "")}
        return {}


# ---------------------------------------------------------------------------
class OnlineMusic:
    """One entry point for the app: combines the sources above."""

    def __init__(self, net, lastfm_key=""):
        self.net = net
        self.deezer = Deezer(net)
        self.lastfm = LastFm(net, lastfm_key)
        self.wiki = Wikipedia(net)

    def set_lastfm_key(self, key):
        self.lastfm = LastFm(self.net, key)

    def search(self, query, limit=25):
        return self.deezer.search(query, limit)

    def artist_card(self, name):
        """Everything for the 'About the artist' card. Missing parts are just left out."""
        card = {"name": name}
        a = self.deezer.find_artist(name)
        if a:
            card.update(picture_url=a.get("picture_xl") or a.get("picture_big") or "",
                        fans=int(a.get("nb_fan") or 0), deezer_url=a.get("link", ""),
                        deezer_id=str(a.get("id", "")))
        if self.lastfm.available:
            try:
                card.update({k: v for k, v in self.lastfm.artist_info(name).items() if v})
                card["bio_source"] = "Last.fm"
            except ServiceError:
                pass
        if not card.get("bio"):
            w = self.wiki.artist_summary(name)
            if w:
                card["bio"], card["bio_source"], card["wiki_url"] = w["bio"], "Wikipedia", w["url"]
                card.setdefault("picture_url", w.get("picture_url", ""))
        return card

    def radio(self, seed_artist, seed_title="", limit=50, rng=None):
        """Songs similar to a seed song, like Spotify's 'Go to song radio'.

        Candidates, best first: Last.fm 'similar tracks' for this exact song (what listeners play together;
        needs a free key), Deezer's radio for the artist, then top songs of related artists. They're ordered
        by how close they are (with a little randomness, so each radio is a bit different), the seed artist is
        limited to 3 songs and others to 2, and the same artist never plays twice in a row where avoidable.
        """
        rng = rng or random.Random()
        scored = []                                   # (score, track)
        if seed_title and self.lastfm.available:
            try:
                for i, t in enumerate(self.lastfm.similar_tracks(seed_artist, seed_title, limit=40)):
                    scored.append((3.0 - i / 40, t))
            except ServiceError:
                pass
        artist = self.deezer.find_artist(seed_artist)
        if artist:
            aid = artist.get("id")
            try:
                for i, t in enumerate(self.deezer.artist_radio(aid, limit=25)):
                    scored.append((2.2 - i / 25, t))
            except ServiceError:
                pass
            for r, rel in enumerate(self.deezer.related(aid, limit=8)[:8]):
                try:
                    for i, t in enumerate(self.deezer.top_tracks(rel.get("id"), limit=3)):
                        scored.append((1.9 - r / 10 - i / 6, t))
                except ServiceError:
                    continue
        scored = [(sc + rng.uniform(0, 0.6), t) for sc, t in scored]
        scored.sort(key=lambda x: x[0], reverse=True)
        seen, out, per_artist = set(), [], {}
        seed_key = (seed_artist.casefold(), seed_title.casefold())
        for _sc, t in scored:
            if not t.title or not t.artist:
                continue
            k = t.key
            if k in seen or (t.artist.casefold(), t.title.casefold()) == seed_key:
                continue
            a = t.artist.casefold()
            if per_artist.get(a, 0) >= (3 if a == seed_artist.casefold() else 2):
                continue
            seen.add(k)
            per_artist[a] = per_artist.get(a, 0) + 1
            out.append(t)
            if len(out) >= limit:
                break
        out = spread_artists(out, first_artist=seed_artist)
        # Last.fm suggestions only have artist + title: add cover art and a preview.
        for i, t in enumerate(out):
            if t.source != "deezer":
                try:
                    out[i] = self.enrich(t)
                except ServiceError:
                    pass
        return out

    def enrich(self, track):
        """Fill in cover art / preview / album for a track that only has artist + title
        (e.g. a Last.fm recommendation)."""
        if track.source == "deezer" and track.cover_url:
            return track
        found = self.deezer.find_track(track.artist, track.title)
        # Only accept the same song: search engines happily return "close" ones.
        if found and found.key == track.key:
            found.genre = found.genre or track.genre
            return found
        return track

    def genre_of(self, track):
        """A single genre name for sorting 'Save for later' lists."""
        if track.genre:
            return track.genre
        if track.source == "deezer" and track.source_id:
            try:
                g = self.deezer.track_genre(track.source_id)
                if g:
                    return g
            except ServiceError:
                pass
        if self.lastfm.available:
            try:
                tags = self.lastfm.track_tags(track.artist, track.title)
                if tags:
                    return tags[0].title()
            except ServiceError:
                pass
        return "Other"


def spread_artists(tracks, first_artist=""):
    """Keep the order as much as possible, but never put the same artist twice in a row (or right after the
    seed song's artist) when another song can go there instead."""
    rest = list(tracks)
    out = []
    last = (first_artist or "").casefold()
    while rest:
        pick = next((i for i, t in enumerate(rest) if t.artist.casefold() != last), 0)
        t = rest.pop(pick)
        out.append(t)
        last = t.artist.casefold()
    return out

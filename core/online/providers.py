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
            explicit=bool(d.get("explicit_lyrics")),
        )

    def genres(self):
        """Music genres for Browse: [{"id", "name", "picture"}] (Deezer's own list, without "All")."""
        data = self._get("/genre", ttl=7 * 24 * 3600)
        return [{"id": g.get("id"), "name": g.get("name", ""), "picture": g.get("picture_xl") or g.get("picture_big") or ""}
                for g in data.get("data", []) if g.get("id") and g.get("name")]

    def genre_chart(self, genre_id, limit=50):
        """Popular songs right now in a genre (Deezer's chart for it)."""
        data = self._get(f"/chart/{genre_id}/tracks", {"limit": limit}, ttl=12 * 3600)
        return [self.track_from(d) for d in data.get("data", []) if d.get("readable", True)]

    def genre_overview(self, genre_id):
        """Everything on a Browse genre page, from Deezer's chart for that genre (refreshed by Deezer every day;
        Sevbify keeps it 6 hours): {"tracks", "albums", "artists", "playlists"}. "releases" comes from the
        genre's editorial new-release list when Deezer has one."""
        data = self._get(f"/chart/{genre_id}", {"limit": 25}, ttl=6 * 3600)
        out = {"tracks": [self.track_from(d) for d in (data.get("tracks") or {}).get("data", [])
                          if d.get("readable", True)],
               "albums": [a for a in (data.get("albums") or {}).get("data", []) if a.get("title")],
               "artists": [a for a in (data.get("artists") or {}).get("data", []) if a.get("name")],
               "playlists": [p for p in (data.get("playlists") or {}).get("data", []) if p.get("title")]}
        try:
            rel = self._get(f"/editorial/{genre_id}/releases", {"limit": 20}, ttl=12 * 3600)
            out["releases"] = [a for a in rel.get("data", []) if a.get("title")]
        except Exception:
            out["releases"] = []
        return out

    def playlist_tracks(self, playlist_id, limit=100):
        data = self._get(f"/playlist/{playlist_id}/tracks", {"limit": limit}, ttl=6 * 3600)
        return [self.track_from(d) for d in data.get("data", []) if d.get("readable", True)]

    def album_tracks(self, album):
        """Songs of an album dict from Deezer (its tracks don't repeat the cover, so it's added)."""
        data = self._get(f"/album/{album.get('id')}/tracks", {"limit": 100}, ttl=7 * 24 * 3600)
        out = []
        for d in data.get("data", []):
            if not d.get("readable", True):
                continue
            t = self.track_from(d)
            t.album = t.album or album.get("title", "")
            t.cover_url = t.cover_url or album.get("cover_xl") or album.get("cover_big") or ""
            if not t.artist:
                t.artist = (album.get("artist") or {}).get("name", "")
            out.append(t)
        return out

    def genre_artists(self, genre_id, limit=12):
        data = self._get(f"/genre/{genre_id}/artists", {"limit": limit}, ttl=24 * 3600)
        return [{"id": a.get("id"), "name": a.get("name", ""), "picture": a.get("picture_xl") or a.get("picture_big") or ""}
                for a in data.get("data", []) if a.get("name")]

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

    def find_album(self, artist, album):
        """The album (Deezer dict: id, title, cover_xl, artist, nb_tracks...) a song is on, or None. Only an album
        with the same name by the same artist counts ("Deluxe" / "Remastered" editions too)."""
        import re

        def norm(text):
            text = re.sub(r"\s*[\(\[][^)\]]*(deluxe|remaster|edition|version|expanded|anniversary)[^)\]]*[\)\]]", "",
                          (text or "").casefold())
            return " ".join(re.findall(r"\w+", text))
        want_album, want_artist = norm(album), norm(artist)
        if not want_album:
            return None
        data = self._get("/search/album", {"q": f'artist:"{artist}" album:"{album}"', "limit": 10}, ttl=7 * 24 * 3600)
        items = data.get("data", []) or \
            self._get("/search/album", {"q": f"{artist} {album}", "limit": 10}, ttl=7 * 24 * 3600).get("data", [])
        same = [a for a in items if norm(a.get("title")) == want_album]
        by_artist = [a for a in same if norm((a.get("artist") or {}).get("name")) == want_artist] or \
            [a for a in same if want_artist and want_artist in norm((a.get("artist") or {}).get("name"))]
        return (by_artist or [None])[0]

    def search_artists(self, query, limit=10):
        """Artists matching a search (dicts with name, picture_xl, nb_fan), best known first."""
        data = self._get("/search/artist", {"q": query, "limit": limit}, ttl=24 * 3600)
        return [a for a in data.get("data", []) if a.get("name")]

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

    def artist_albums(self, artist_id, limit=100):
        """An artist's releases, newest first, sorted like Spotify's Releases page:
        {"albums": [...], "singles": [...], "compilations": [...]} (Deezer album dicts with release_date)."""
        data = self._get(f"/artist/{artist_id}/albums", {"limit": limit}, ttl=24 * 3600)
        out = {"albums": [], "singles": [], "compilations": []}
        seen = set()
        items = sorted((a for a in data.get("data", []) if a.get("title")),
                       key=lambda a: a.get("release_date") or "", reverse=True)
        for a in items:
            key = (a["title"].casefold(), a.get("record_type"))
            if key in seen:
                continue
            seen.add(key)
            kind = a.get("record_type") or "album"
            group = "singles" if kind in ("single", "ep") else ("compilations" if kind == "compile" else "albums")
            out[group].append(a)
        return out

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

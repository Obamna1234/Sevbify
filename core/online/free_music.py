"""Music you are allowed to stream in full and download: Jamendo and the
Internet Archive (Creative Commons / public domain only).

Jamendo          needs a free client ID (Settings). Every track is Creative
                 Commons; only tracks the artist allows to be downloaded get a
                 download link.
Internet Archive no key. Only items whose licence is Creative Commons or
                 public domain are used.
"""
import re
import urllib.parse

from .models import OnlineTrack
from .net import ServiceError

JAMENDO = "https://api.jamendo.com/v3.0/tracks/"
IA_SEARCH = "https://archive.org/advancedsearch.php"
IA_META = "https://archive.org/metadata/"
IA_DOWNLOAD = "https://archive.org/download/"

AUDIO_FORMATS = ("VBR MP3", "MP3", "128Kbps MP3", "64Kbps MP3", "Flac", "FLAC", "Ogg Vorbis")
OPEN_LICENCE = re.compile(r"creativecommons\.org|publicdomain", re.I)


def _seconds(value):
    """Internet Archive lengths are '183.4' or '03:03'."""
    if not value:
        return 0
    try:
        if ":" in str(value):
            parts = [float(p) for p in str(value).split(":")]
            secs = 0
            for p in parts:
                secs = secs * 60 + p
            return int(secs)
        return int(float(value))
    except ValueError:
        return 0


def _first(v):
    return v[0] if isinstance(v, list) and v else (v or "")


class FreeMusic:
    def __init__(self, net, jamendo_client_id=""):
        self.net = net
        self.jamendo_id = (jamendo_client_id or "").strip()

    # ------------------------------------------------------------------ Jamendo
    def jamendo(self, query, limit=20):
        if not self.jamendo_id:
            return []
        data = self.net.get_json(JAMENDO, {"client_id": self.jamendo_id, "format": "json", "limit": limit,
                                           "search": query, "audioformat": "mp32", "include": "musicinfo"},
                                 ttl=6 * 3600)
        head = data.get("headers") or {}
        if head.get("status") not in (None, "success"):
            raise ServiceError(f"Jamendo: {head.get('error_message') or head.get('status')}")
        out = []
        for r in data.get("results", []) or []:
            genres = ((r.get("musicinfo") or {}).get("tags") or {}).get("genres") or []
            out.append(OnlineTrack(
                title=r.get("name", ""), artist=r.get("artist_name", ""), album=r.get("album_name", ""),
                duration_ms=int(r.get("duration") or 0) * 1000, cover_url=r.get("image") or r.get("album_image", ""),
                stream_url=r.get("audio", ""),
                download_url=r.get("audiodownload", "") if r.get("audiodownload_allowed", True) else "",
                source="jamendo", source_id=str(r.get("id", "")), page_url=r.get("shareurl", ""),
                license=r.get("license_ccurl", ""), genre=genres[0].title() if genres else ""))
        return out

    # --------------------------------------------------------- Internet Archive
    def archive(self, query, items=6, per_item=8):
        q = (f"({query}) AND mediatype:audio AND (licenseurl:*creativecommons* OR licenseurl:*publicdomain*)")
        params = [("q", q), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "creator"),
                  ("fl[]", "licenseurl"), ("rows", str(items)), ("output", "json"), ("sort[]", "downloads desc")]
        url = IA_SEARCH + "?" + urllib.parse.urlencode(params)
        docs = ((self.net.get_json(url, ttl=24 * 3600) or {}).get("response") or {}).get("docs") or []
        out = []
        for doc in docs:
            if not OPEN_LICENCE.search(_first(doc.get("licenseurl"))):
                continue
            try:
                out += self.archive_item(doc["identifier"], limit=per_item, query=query)
            except (ServiceError, KeyError):
                continue
        return out

    def archive_item(self, identifier, limit=8, query=""):
        meta = self.net.get_json(IA_META + urllib.parse.quote(identifier), ttl=7 * 24 * 3600) or {}
        info = meta.get("metadata") or {}
        licence = _first(info.get("licenseurl"))
        if not OPEN_LICENCE.search(licence):
            return []
        album = _first(info.get("title"))
        creator = _first(info.get("creator"))
        page = f"https://archive.org/details/{identifier}"
        cover = f"https://archive.org/services/img/{urllib.parse.quote(identifier)}"
        words = [w for w in query.casefold().split() if w]
        tracks = []
        files = meta.get("files") or []
        # Prefer the original upload; skip duplicates of the same song in other formats.
        files.sort(key=lambda f: (f.get("source") != "original", f.get("format") not in ("Flac", "FLAC")))
        seen = set()
        for f in files:
            if f.get("format") not in AUDIO_FORMATS:
                continue
            name = f.get("name", "")
            title = f.get("title") or re.sub(r"^\d+[\s._-]*", "", name.rsplit(".", 1)[0]).replace("_", " ")
            artist = f.get("creator") or f.get("artist") or creator or "Unknown Artist"
            k = (artist.casefold(), title.casefold())
            if k in seen:
                continue
            seen.add(k)
            if words and not all(w in f"{title} {artist} {album}".casefold() for w in words) and len(tracks) >= 3:
                continue
            url = IA_DOWNLOAD + urllib.parse.quote(identifier) + "/" + urllib.parse.quote(name)
            tracks.append(OnlineTrack(
                title=title, artist=artist, album=f.get("album") or album,
                duration_ms=_seconds(f.get("length")) * 1000, cover_url=cover,
                stream_url=url, download_url=url, source="archive", source_id=f"{identifier}/{name}",
                page_url=page, license=licence))
            if len(tracks) >= limit:
                break
        return tracks

    # ------------------------------------------------------------------ both
    def search(self, query):
        """Jamendo first (single songs), then Internet Archive."""
        results, errors = [], []
        for fn in (self.jamendo, self.archive):
            try:
                results += fn(query)
            except ServiceError as e:
                errors.append(str(e))
        if not results and errors:
            raise ServiceError("; ".join(errors))
        return results

    def find_download(self, artist, title):
        """A permitted download for exactly this song, or None."""
        from .models import match_key
        want = match_key(artist, title)
        for t in self.search(f"{artist} {title}"):
            if t.download_url and t.key == want:
                return t
        return None

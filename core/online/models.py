"""Online song data, and matching online songs to files in the local library."""
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field, asdict


@dataclass
class OnlineTrack:
    title: str
    artist: str
    album: str = ""
    duration_ms: int = 0
    cover_url: str = ""
    preview_url: str = ""        # ~30-second preview (Deezer)
    stream_url: str = ""         # full-length stream the source permits (Jamendo, Internet Archive)
    download_url: str = ""       # only set for sources that allow downloading
    source: str = ""             # "deezer", "lastfm", "jamendo", "archive"
    source_id: str = ""
    artist_id: str = ""          # Deezer artist id when known
    page_url: str = ""           # the song's page on its source website
    license: str = ""            # e.g. Creative Commons licence URL
    genre: str = ""
    youtube_id: str = ""         # set once an official YouTube video has been chosen for in-app playback

    # --- identity -------------------------------------------------------
    @property
    def key(self):
        return match_key(self.artist, self.title)

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v not in ("", 0, None)}

    @classmethod
    def from_dict(cls, d):
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})

    @property
    def query(self):
        return f"{self.artist} {self.title}".strip()

    # --- "Open in…" links (search pages; work without any account) -------
    def links(self):
        q = urllib.parse.quote(self.query)
        q_plus = urllib.parse.quote_plus(self.query)
        links = {
            "Spotify": f"https://open.spotify.com/search/{q}",
            "YouTube Music": f"https://music.youtube.com/search?q={q_plus}",
            "YouTube": f"https://www.youtube.com/results?search_query={q_plus}",
            "Apple Music": f"https://music.apple.com/search?term={q_plus}",
            "Bandcamp": f"https://bandcamp.com/search?q={q_plus}&item_type=t",
        }
        if self.page_url:
            label = {"deezer": "Deezer", "jamendo": "Jamendo", "archive": "Internet Archive",
                     "lastfm": "Last.fm"}.get(self.source, "Source")
            links = {label: self.page_url, **links}
        return links

    @property
    def can_download(self):
        return bool(self.download_url)


# ---------------------------------------------------------------------------
_FEAT = re.compile(r"\s*[\(\[](feat\.?|ft\.?|featuring|with)\b[^\)\]]*[\)\]]", re.I)
_SUFFIX = re.compile(r"\s+-\s+(\d{4}\s+)?(remaster(ed)?|single version|radio edit|original mix|mono|stereo)\b.*$", re.I)
_BRACKETED_VERSION = re.compile(r"\s*[\(\[][^\)\]]*(remaster(ed)?|version|edit|mix)\b[^\)\]]*[\)\]]", re.I)


def normalise_text(text: str, strip_versions=True) -> str:
    """Lower-case, accent-free, punctuation-free text used to compare songs."""
    t = unicodedata.normalize("NFKC", text or "").casefold()
    t = _FEAT.sub("", t)
    if strip_versions:
        t = _SUFFIX.sub("", t)
        t = _BRACKETED_VERSION.sub("", t)
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    t = t.replace("&", " and ")
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"^the\s+", "", t.strip())
    return re.sub(r"\s+", " ", t).strip()


def match_key(artist: str, title: str) -> str:
    first_artist = re.split(r"\s*(,|;| x | feat\.? | ft\.? |&)\s*", artist or "", maxsplit=1, flags=re.I)[0]
    return f"{normalise_text(first_artist)}|{normalise_text(title)}"


def find_local_match(track: OnlineTrack, songs, index=None):
    """Return the library Song that is the same recording as `track`, or None.

    index: optional dict match_key -> [songs] (build with build_match_index for speed).
    Durations must agree within 10 seconds when both are known, so a live or
    extended version is not mistaken for the album version.
    """
    candidates = (index or build_match_index(songs)).get(track.key, [])
    for song in candidates:
        if not song.exists:
            continue
        if track.duration_ms and song.duration and abs(track.duration_ms - song.duration) > 10_000:
            continue
        return song
    return None


def build_match_index(songs):
    index = {}
    for s in songs:
        index.setdefault(match_key(s.artist, s.title), []).append(s)
        # Many files are named "Artist - Title" but have no tags.
        if s.artist == "Unknown Artist":
            name = re.sub(r"^\d+\s*[-.]\s*", "", s.title)   # drop a leading track number ("019 - ")
            if " - " in name:
                a, t = name.split(" - ", 1)
                index.setdefault(match_key(a, t), []).append(s)
    return index

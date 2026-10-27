"""Albums and artists built from the songs in your music folders (for Your Library). No UI code."""
import os
import re

UNKNOWN_ALBUM = "Unknown Album"
UNKNOWN_ARTIST = "Unknown Artist"
_SPLIT = re.compile(r"\s+(?:feat\.?|ft\.?|featuring|x|vs\.?)\s+|\s*[\(\[](?:feat\.?|ft\.?|featuring)\b", re.I)


def main_artist(artist):
    """'A feat. B' / 'A ft. B' / 'A x B' -> 'A'. Bands like 'Simon & Garfunkel' stay whole."""
    return _SPLIT.split(artist or "", maxsplit=1)[0].strip() or UNKNOWN_ARTIST


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def build_index(songs):
    """Return (albums, artists) as lists of dicts.
    album:  key, title, artist, cover_path, songs (in file order), added
    artist: key, name, cover_path, songs, added
    "added" is the newest file time, for the "Recently added" sort."""
    albums, artists = {}, {}
    for s in songs:
        if not getattr(s, "exists", False):
            continue
        added = _mtime(s.file_path)
        name = main_artist(s.artist)
        if s.artist and s.artist != UNKNOWN_ARTIST:
            a = artists.setdefault(name.casefold(), dict(key=name.casefold(), name=name, cover_path=s.album_cover_path,
                                                         songs=[], added=0.0))
            a["songs"].append(s)
            a["added"] = max(a["added"], added)
        if s.album and s.album != UNKNOWN_ALBUM:
            key = (s.album.casefold(), name.casefold())
            al = albums.setdefault(key, dict(key=key, title=s.album, artist=name, cover_path=s.album_cover_path,
                                             songs=[], added=0.0))
            al["songs"].append(s)
            al["added"] = max(al["added"], added)
            if "placeholder" in os.path.basename(al["cover_path"]).lower():
                al["cover_path"] = s.album_cover_path
    return list(albums.values()), list(artists.values())


def with_recents(items, recent_songs):
    """Copy items adding "recent": higher for albums/artists whose songs you played more recently."""
    rank = {}
    total = len(recent_songs)
    for i, s in enumerate(recent_songs):          # most recent first
        rank.setdefault(s.key, total - i)
    out = []
    for it in items:
        d = dict(it)
        d["recent"] = max([rank.get(s.key, 0) for s in it["songs"]] or [0])
        out.append(d)
    return out

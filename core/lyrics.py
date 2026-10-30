"""Song lyrics (no UI code), shared by the Windows and Android apps.

Where they come from, in order:
1. A .lrc (time-synced) or .txt file next to your own song with the same name: works offline, nothing sent.
2. LRCLIB (lrclib.net): a free, open lyrics database run by volunteers, no account or key. Only the song's
   artist, title, album and length are sent, and only when lyrics are switched on and Sevbify is online.

Synced lyrics ("[01:23.45] a line") let the apps highlight the line being sung, like Spotify.
"""
import os
import re

from core.online.net import OfflineError, ServiceError

LRCLIB = "https://lrclib.net/api"
_TIME = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


class Lyrics:
    def __init__(self, lines=None, plain="", source="", instrumental=False):
        self.lines = lines or []          # [(ms, text)] when synced, else []
        self.plain = plain                # the whole text (always filled when there are lyrics)
        self.source = source              # "your file", "LRCLIB"
        self.instrumental = instrumental

    @property
    def synced(self):
        return bool(self.lines)

    @property
    def found(self):
        return bool(self.plain.strip()) or self.instrumental

    def line_at(self, ms):
        """Index of the line being sung at `ms` (-1 before the first line)."""
        idx = -1
        for i, (start, _text) in enumerate(self.lines):
            if start <= ms:
                idx = i
            else:
                break
        return idx

    def to_dict(self):
        return {"lines": [[ms, text] for ms, text in self.lines], "plain": self.plain, "source": self.source,
                "instrumental": self.instrumental, "synced": self.synced}


def parse_lrc(text):
    """[(ms, line)] from LRC text (lines with several time tags appear once per tag), sorted by time."""
    out = []
    for raw in (text or "").splitlines():
        stamps = list(_TIME.finditer(raw))
        if not stamps:
            continue
        line = _TIME.sub("", raw).strip()
        for m in stamps:
            frac = m.group(3) or "0"
            ms = (int(m.group(1)) * 60 + int(m.group(2))) * 1000 + int(frac.ljust(3, "0")[:3])
            out.append((ms, line))
    out.sort(key=lambda p: p[0])
    return out


def _plain_from_lines(lines):
    return "\n".join(text for _ms, text in lines)


def from_file(song_path):
    """Lyrics saved next to a song file (Song.lrc / Song.txt), or None."""
    if not song_path:
        return None
    base = os.path.splitext(song_path)[0]
    for ext in (".lrc", ".LRC", ".txt"):
        path = base + ext
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                    text = f.read(512 * 1024)
            except OSError:
                continue
            lines = parse_lrc(text) if ext.lower() == ".lrc" else []
            plain = _plain_from_lines(lines) if lines else text.strip()
            if plain:
                return Lyrics(lines, plain, "your file")
    return None


def _from_record(rec):
    if not isinstance(rec, dict):
        return None
    synced = rec.get("syncedLyrics") or ""
    plain = rec.get("plainLyrics") or ""
    lines = parse_lrc(synced)
    if not plain and lines:
        plain = _plain_from_lines(lines)
    lyr = Lyrics(lines, plain, "LRCLIB", bool(rec.get("instrumental")))
    return lyr if lyr.found else None


def from_lrclib(net, artist, title, album="", duration_ms=0):
    """Lyrics from LRCLIB, or None when it doesn't have the song."""
    params = {"artist_name": artist, "track_name": title}
    if album:
        params["album_name"] = album
    if duration_ms:
        params["duration"] = int(round(duration_ms / 1000))
    try:
        found = _from_record(net.get_json(f"{LRCLIB}/get", params, ttl=30 * 86400))
        if found:
            return found
    except ServiceError as e:            # 404: not an exact match; try a search below
        if "404" not in str(e):
            raise
    results = net.get_json(f"{LRCLIB}/search", {"artist_name": artist, "track_name": title}, ttl=7 * 86400)
    if not isinstance(results, list):
        return None
    secs = (duration_ms or 0) / 1000
    # Same song: the length must be close (live versions and remixes are skipped).
    ranked = sorted((r for r in results if isinstance(r, dict)),
                    key=lambda r: (not r.get("syncedLyrics"), abs((r.get("duration") or 0) - secs) if secs else 0))
    for rec in ranked:
        if secs and rec.get("duration") and abs(rec["duration"] - secs) > 8:
            continue
        found = _from_record(rec)
        if found:
            return found
    return None


def find(net, artist, title, album="", duration_ms=0, song_path=""):
    """Lyrics for a song: your own .lrc/.txt file first, then LRCLIB (when online). None if there are none."""
    local = from_file(song_path)
    if local:
        return local
    if net is None or not artist or not title:
        return None
    try:
        return from_lrclib(net, artist, title, album, duration_ms)
    except OfflineError:
        return None

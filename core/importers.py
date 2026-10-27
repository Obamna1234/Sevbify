"""Bring playlists in from other apps (no UI code).

- A Spotify playlist or album link: read from Spotify's public embed page (what any browser loads for a shared
  link). No Spotify login, nothing is changed on the user's account. The embed page lists up to 100 songs; for
  longer playlists, export a CSV with Exportify (exportify.net) and import the file.
- An Apple Music playlist or album link (public): SEVBY's reader.
- A file: .csv (Exportify, TuneMyMusic, Soundiiz...), .txt ("Artist - Title" per line), .m3u / .m3u8.

Songs come back as OnlineTrack slots in the playlist's order; the app fills them with your own files when it
finds them in your music folders, streams them while online, and they can be downloaded.
"""
import json
import os
import re

from core.online.models import OnlineTrack

SPOTIFY_RE = re.compile(r"(?:open\.spotify\.com/(?:intl-[a-z]{2}/)?(?:embed/)?|spotify:)(playlist|album)[/:]([A-Za-z0-9]{10,})")
APPLE_RE = re.compile(r"https?://music\.apple\.com/\S+")
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
DASHES = (" - ", " – ", " — ", " － ", "－", " —", " –")


class ImportError_(Exception):
    """Something the user should see, e.g. "That isn't a Spotify playlist link"."""


def parse_link(text):
    """("spotify", kind, id) / ("apple", url, None) / None."""
    text = (text or "").strip()
    m = SPOTIFY_RE.search(text)
    if m:
        return ("spotify", m.group(1), m.group(2))
    m = APPLE_RE.search(text)
    if m:
        return ("apple", m.group(0), None)
    return None


def spotify_embed_url(kind, item_id):
    return f"https://open.spotify.com/embed/{kind}/{item_id}"


def parse_spotify_embed(html):
    """Name, cover and songs from a Spotify embed page. Raises ImportError_ when the page has no list."""
    m = NEXT_DATA_RE.search(html or "")
    if not m:
        raise ImportError_("Spotify's page didn't contain a song list (the link may be private, or Spotify "
                           "changed its page). Try exporting the playlist with Exportify and importing the file.")
    try:
        entity = json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    except (ValueError, KeyError, TypeError):
        raise ImportError_("Spotify's page format wasn't recognised. Try exporting with Exportify instead.")
    cover = ""
    for src in ((entity.get("coverArt") or {}).get("sources") or []):
        if isinstance(src, dict) and src.get("url"):
            cover = src["url"]
            break
    album_name = entity.get("name") if entity.get("type") == "album" else ""
    tracks = []
    for row in entity.get("trackList") or []:
        if not isinstance(row, dict) or row.get("entityType") not in (None, "track"):
            continue
        title = row.get("title") or row.get("name") or ""
        artist = ", ".join(a.strip() for a in (row.get("subtitle") or "").replace(" ", " ").split(",") if a.strip())
        if not title:
            continue
        uri = row.get("uri") or ""
        tracks.append(OnlineTrack(title=title, artist=artist, album=album_name,
                                  duration_ms=int(row.get("duration") or 0), source="spotify",
                                  page_url=("https://open.spotify.com/track/" + uri.split(":")[-1]) if uri else "",
                                  explicit=bool(row.get("isExplicit"))))
    if not tracks:
        raise ImportError_("That Spotify link has no songs Sevbify can read.")
    return {"name": entity.get("name") or entity.get("title") or "Spotify playlist", "cover_url": cover,
            "tracks": tracks, "owner": entity.get("subtitle") or "", "truncated": len(tracks) >= 100}


def fetch_from_link(net, text):
    """Read a playlist from a Spotify / Apple Music link (network). Returns the same dict as parse_spotify_embed."""
    link = parse_link(text)
    if link is None:
        raise ImportError_("Paste a Spotify or Apple Music playlist or album link, e.g. "
                           "https://open.spotify.com/playlist/…")
    if link[0] == "spotify":
        return parse_spotify_embed(net.get_text(spotify_embed_url(link[1], link[2]), ttl=600))
    from core import downloader
    try:
        name, lines = downloader.engine().fetch_apple_playlist(link[1])
    except ValueError as e:
        raise ImportError_(str(e))
    tracks = [track_from_line(line) for line in lines]
    return {"name": name or "Apple Music playlist", "cover_url": "", "tracks": [t for t in tracks if t],
            "owner": "", "truncated": False}


# --- files ------------------------------------------------------------------------------------------------
def decode_text(data: bytes) -> str:
    """Text files saved by any Windows app: UTF-8 (with or without BOM), UTF-16, or the older "ANSI" encodings
    Chinese / Japanese / Korean / Western Windows use (GB18030, Shift-JIS, CP949, CP1252)."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    for enc in ("utf-8-sig", "gb18030", "shift_jis", "cp949"):
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc != "utf-8-sig" and re.search(r"[\u0080-ÿ]{3,}", text):
            continue                       # looks like mis-decoded Western text
        return text
    return data.decode("cp1252", errors="replace")


def split_line(line):
    """("artist", "title") from "Artist - Title". Also "Artist-Title" without spaces and the full-width dash
    "－" used in Chinese and Japanese text. No dash: ("", line)."""
    line = line.strip()
    for sep in DASHES:
        if sep in line:
            a, t = line.split(sep, 1)
            if a.strip() and t.strip():
                return a.strip(), t.strip()
    if line.count("-") == 1 and not re.search(r"\d-\d", line):
        a, t = line.split("-", 1)
        if a.strip() and t.strip():
            return a.strip(), t.strip()
    return "", line


def track_from_line(line):
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None
    artist, title = split_line(line)
    return OnlineTrack(title=title, artist=artist)


def read_playlist_file(path):
    """Returns {"name", "tracks": [OnlineTrack], "files": [local paths in order, None for slots]}.
    For .m3u files the order mixes local files and slots: items is a list of ("file", path) / ("track", t)."""
    with open(path, "rb") as f:
        text = decode_text(f.read())
    name = os.path.splitext(os.path.basename(path))[0]
    items = []
    if path.lower().endswith((".m3u", ".m3u8")):
        base = os.path.dirname(os.path.abspath(path))
        pending_info = ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.upper().startswith("#EXTINF:"):
                pending_info = line.split(",", 1)[1] if "," in line else ""
                continue
            if line.startswith("# not downloaded yet:"):
                t = track_from_line(line.split(":", 1)[1])
                if t:
                    items.append(("track", t))
                continue
            if line.startswith("#"):
                continue
            p = line if os.path.isabs(line) else os.path.normpath(os.path.join(base, line.replace("/", os.sep)))
            if os.path.exists(p):
                items.append(("file", p))
            elif pending_info:
                t = track_from_line(pending_info)
                if t:
                    items.append(("track", t))
            pending_info = ""
        return {"name": name, "items": items}
    from core import downloader
    lines = None
    try:
        lines = downloader.engine()._structured_to_lines(text)       # CSV exports (Exportify etc.)
    except Exception:
        lines = None
    if lines is None:
        lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(("http", "==="))]
    for line in lines:
        t = track_from_line(line)
        if t:
            items.append(("track", t))
    return {"name": name, "items": items}

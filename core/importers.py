"""Bring playlists in from other apps (no UI code).

- A Spotify playlist or album link: read from Spotify's public embed page (what any browser loads for a shared
  link). No Spotify login, nothing is changed on the user's account. The embed page lists up to 100 songs; for
  longer playlists, export a CSV with Exportify (exportify.net) and import the file.
- Spotify song links copied from the Spotify app (select songs, Ctrl+A, Ctrl+C): one public embed page per
  song. This is how a playlist longer than 100 songs comes in complete, in order, still without a login.
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
DEEZER_RE = re.compile(r"(?:www\.)?deezer\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?(playlist|album)/(\d+)", re.I)
JAMENDO_RE = re.compile(r"(?:www\.)?jamendo\.com/(?:[a-z]{2}/)?(playlist|album)/(?:[a-z]\d*/)?(\d+)", re.I)
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
DASHES = (" - ", " – ", " — ", " － ", "－", " —", " –")


class ImportError_(Exception):
    """Something the user should see, e.g. "That isn't a Spotify playlist link"."""


def parse_link(text):
    """("spotify", kind, id) / ("apple", url, None) / ("deezer", kind, id) / ("jamendo", kind, id) / None."""
    text = (text or "").strip()
    m = SPOTIFY_RE.search(text)
    if m:
        return ("spotify", m.group(1), m.group(2))
    m = DEEZER_RE.search(text)
    if m:
        return ("deezer", m.group(1).lower(), m.group(2))
    m = JAMENDO_RE.search(text)
    if m:
        return ("jamendo", m.group(1).lower(), m.group(2))
    m = APPLE_RE.search(text)
    if m:
        return ("apple", m.group(0), None)
    return None


def origin_of(text):
    """Where an imported playlist came from, for the optional coloured border:
    "spotify", "apple", "deezer" or "jamendo" (pasted Spotify song links count as Spotify)."""
    found = parse_link(text)
    if found:
        return found[0]
    return "spotify"


TRACK_LINK_RE = re.compile(r"(?:open\.spotify\.com/(?:intl-[a-z]{2}/)?(?:embed/)?track/|spotify:track:)([A-Za-z0-9]{22})")


def parse_track_links(text):
    """Spotify song ids, in the pasted order, from links / spotify:track: URIs (one or many per line)."""
    return TRACK_LINK_RE.findall(text or "")


def parse_spotify_track_embed(html, track_id=""):
    """One song (OnlineTrack) from a Spotify song's embed page, or None."""
    m = NEXT_DATA_RE.search(html or "")
    if not m:
        return None
    try:
        entity = json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    except (ValueError, KeyError, TypeError):
        return None
    title = entity.get("name") or entity.get("title") or ""
    artists = entity.get("artists")
    if isinstance(artists, list) and artists:
        artist = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name"))
    else:
        artist = entity.get("subtitle") or ""
    artist = ", ".join(a.strip() for a in artist.replace("\u00a0", " ").split(",") if a.strip())
    if not title:
        return None
    cover = ""
    images = (entity.get("visualIdentity") or {}).get("image") or []
    for src in ((entity.get("coverArt") or {}).get("sources") or []) + list(images):
        if isinstance(src, dict) and src.get("url"):
            cover = src["url"]
            break
    album = (entity.get("album") or {}).get("name", "") if isinstance(entity.get("album"), dict) else ""
    uri = entity.get("uri") or (f"spotify:track:{track_id}" if track_id else "")
    return OnlineTrack(title=title, artist=artist, album=album, duration_ms=int(entity.get("duration") or 0),
                       source="spotify", cover_url=cover,
                       page_url=("https://open.spotify.com/track/" + uri.split(":")[-1]) if uri else "",
                       explicit=bool(entity.get("isExplicit")))


def fetch_tracks_from_links(net, text, progress=None, should_stop=lambda: False):
    """Read every pasted Spotify song link (network, one small page each, cached for a month).
    Returns {"tracks": [...], "failed": n}. progress(done, total) is called as it goes."""
    import time as _t
    ids = parse_track_links(text)
    tracks, failed = [], 0
    for i, tid in enumerate(ids):
        if should_stop():
            break
        try:
            t = parse_spotify_track_embed(net.get_text(spotify_embed_url("track", tid), ttl=30 * 86400), tid)
        except Exception:
            t = None
        if t is None:
            failed += 1
        else:
            tracks.append(t)
        if progress is not None:
            progress(i + 1, len(ids))
        _t.sleep(0.05)
    return {"tracks": tracks, "failed": failed}


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
    token = ""
    m2 = re.search(r'"accessToken":\s*"([A-Za-z0-9_\-]{20,})"', m.group(1))
    if m2:
        token = m2.group(1)
    return {"name": entity.get("name") or entity.get("title") or "Spotify playlist", "cover_url": cover,
            "tracks": tracks, "owner": entity.get("subtitle") or "", "truncated": len(tracks) >= 100,
            "_token": token}


LINK_HELP = "Paste a Spotify, Apple Music, Deezer or Jamendo playlist or album link"
DEEZER_API = "https://api.deezer.com"
JAMENDO_API = "https://api.jamendo.com/v3.0"
MAX_IMPORT = 2000


def fetch_deezer(net, kind, item_id):
    """A public Deezer playlist or album, from Deezer's free public API (no account, no key)."""
    from core.online.providers import Deezer
    def get(path, params=None):
        data = net.get_json(DEEZER_API + path, params, ttl=600)
        if not isinstance(data, dict) or "error" in data:
            raise ImportError_("Deezer couldn't find that " + kind + " (it may be private or deleted).")
        return data
    head = get(f"/{kind}/{item_id}")
    tracks, index = [], 0
    while len(tracks) < MAX_IMPORT:
        page = get(f"/{kind}/{item_id}/tracks", {"limit": 100, "index": index})
        rows = [d for d in page.get("data") or [] if isinstance(d, dict)]
        for d in rows:
            t = Deezer.track_from(d)
            if kind == "album":
                t.album = t.album or head.get("title", "")
                t.cover_url = t.cover_url or head.get("cover_xl") or head.get("cover_big") or ""
                t.artist = t.artist or (head.get("artist") or {}).get("name", "")
            if t.title and t.artist:
                tracks.append(t)
        index += len(rows)
        if not rows or not page.get("next"):
            break
    if not tracks:
        raise ImportError_("That Deezer link has no songs Sevbify can read.")
    owner = (head.get("creator") or head.get("artist") or {}).get("name", "")
    return {"name": head.get("title") or "Deezer " + kind, "tracks": tracks, "owner": owner, "truncated": False,
            "cover_url": head.get("picture_xl") or head.get("cover_xl") or head.get("picture_big") or ""}


def fetch_jamendo(net, kind, item_id, client_id):
    """A Jamendo playlist or album (free, Creative Commons music). Jamendo's API needs the free client ID
    from Settings → Online."""
    if not (client_id or "").strip():
        raise ImportError_("Importing from Jamendo needs a free Jamendo client ID: add it in Settings "
                           "(Online → Jamendo client ID).")
    data = net.get_json(f"{JAMENDO_API}/{kind}s/tracks/", {"client_id": client_id.strip(), "format": "json",
                                                           "id": item_id, "limit": 200, "audioformat": "mp32"},
                        ttl=600)
    head = (data or {}).get("headers") or {}
    if head.get("status") not in (None, "success"):
        raise ImportError_(f"Jamendo: {head.get('error_message') or head.get('status')}")
    results = (data or {}).get("results") or []
    if not results:
        raise ImportError_("Jamendo couldn't find that " + kind + ".")
    info = results[0]
    tracks = []
    for r in info.get("tracks") or []:
        if not isinstance(r, dict) or not r.get("name"):
            continue
        tracks.append(OnlineTrack(
            title=r.get("name", ""), artist=r.get("artist_name") or info.get("artist_name", ""),
            album=r.get("album_name") or (info.get("name", "") if kind == "album" else ""),
            duration_ms=int(r.get("duration") or 0) * 1000,
            cover_url=r.get("image") or r.get("album_image") or info.get("image", ""),
            stream_url=r.get("audio", ""), source="jamendo", source_id=str(r.get("id", "")),
            download_url=r.get("audiodownload", "") if r.get("audiodownload_allowed", True) else "",
            page_url=r.get("shareurl", "")))
    if not tracks:
        raise ImportError_("That Jamendo link has no songs Sevbify can read.")
    return {"name": info.get("name") or "Jamendo " + kind, "cover_url": info.get("image", ""), "tracks": tracks,
            "owner": info.get("artist_name") or info.get("user_name", ""), "truncated": False}


CHOSIC_EXPORTER = "https://www.chosic.com/spotify-playlist-exporter/"


def fetch_spotify_rest(net, playlist_id, token, have, opener=None):
    """Songs after the first `have` of a public Spotify playlist, read with the embed page's anonymous key.
    Raises on any refusal (the caller falls back to Chosic)."""
    import urllib.request
    if not token or not re.fullmatch(r"[A-Za-z0-9]{10,40}", playlist_id or ""):
        raise ImportError_("no key")
    out, offset = [], have
    while offset < MAX_IMPORT:
        url = (f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?offset={offset}&limit=100"
               "&fields=next,items(track(name,duration_ms,explicit,id,artists(name),album(name,images)))")
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "User-Agent": "Mozilla/5.0"})
        if opener is not None:
            body = opener(url)
        else:
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read(5_000_000)
        data = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        items = data.get("items") or []
        for it in items:
            t = (it or {}).get("track") or {}
            if not t.get("name"):
                continue
            images = (t.get("album") or {}).get("images") or []
            out.append(OnlineTrack(title=t["name"], artist=", ".join(a.get("name", "") for a in t.get("artists") or []),
                                   album=(t.get("album") or {}).get("name") or "",
                                   duration_ms=int(t.get("duration_ms") or 0), source="spotify",
                                   cover_url=images[0].get("url", "") if images else "",
                                   page_url=f"https://open.spotify.com/track/{t['id']}" if t.get("id") else "",
                                   explicit=bool(t.get("explicit"))))
        if not data.get("next") or not items:
            break
        offset += len(items)
    return out


def fetch_from_link(net, text, jamendo_client_id=""):
    """Read a playlist from a Spotify / Apple Music / Deezer / Jamendo link (network). Returns the same dict as
    parse_spotify_embed."""
    link = parse_link(text)
    if link is None:
        raise ImportError_(LINK_HELP + ", e.g. https://open.spotify.com/playlist/…")
    if link[0] == "spotify":
        res = parse_spotify_embed(net.get_text(spotify_embed_url(link[1], link[2]), ttl=600))
        token = res.pop("_token", "")
        if res["truncated"] and link[1] == "playlist":
            # More than 100 songs: try the rest with the embed player's own anonymous key (no account). Spotify
            # often refuses this ("quota exceeded"); then the app offers Chosic's exporter instead.
            try:
                more = fetch_spotify_rest(net, link[2], token, len(res["tracks"]))
                if more:
                    res["tracks"] = res["tracks"] + more
                    res["truncated"] = len(res["tracks"]) >= MAX_IMPORT
            except Exception:
                pass
        res["chosic_url"] = CHOSIC_EXPORTER if res["truncated"] and link[1] == "playlist" else ""
        return res
    if link[0] == "deezer":
        return fetch_deezer(net, link[1], link[2])
    if link[0] == "jamendo":
        return fetch_jamendo(net, link[1], link[2], jamendo_client_id)
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

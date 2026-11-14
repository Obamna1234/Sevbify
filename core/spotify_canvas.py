"""Spotify's Canvas (the short looping videos behind some songs), fetched without any account.

How (all in the background, only while online, only when Settings → Canvas and Settings → "Canvas from Spotify"
are on):
1. Spotify's track ID: from the song's Spotify link when it was imported from Spotify, otherwise song.link is asked
   with the song's Deezer page (the same lookup Share uses).
2. A short-lived anonymous key from Spotify's public embed player page for that track (no login, no account: the
   same page any website showing a Spotify player loads).
3. Spotify's Canvas service is asked for that one track; if it has a video, the .mp4 is saved in
   <data folder>/canvas-cache and plays in the Now Playing view, looping and muted.

What leaves this computer: the song's name (to Deezer/song.link) and its Spotify ID (to Spotify), like opening
the song's Spotify page in a browser. Nothing about you, no account. This isn't an official Spotify feature for
other apps, so it can stop working if Spotify changes something: the daily health check
(.github/workflows/health.yml) tries it every day and fails loudly when it does.
"""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.error
import urllib.request

from core.online.net import is_web_url

CANVAS_API = "https://spclient.wg.spotify.com/canvaz-cache/v0/canvases"
EMBED = "https://open.spotify.com/embed/track/{}"
VIDEO_RE = re.compile(rb"https://canvaz\.scdn\.co/[\x21-\x7e]+?\.mp4")
TOKEN_RE = re.compile(r'"accessToken"\s*:\s*"([A-Za-z0-9_\-]{20,})"')
ID_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]{22})")
NONE_FOR = 7 * 24 * 3600            # a song with no Canvas is asked about again after a week
MAX_FILES = 200                     # the cache keeps the most recent videos only

_lock = threading.Lock()
_token = {"value": "", "until": 0.0}


class NoCanvas(Exception):
    """This song has no Canvas (or Spotify didn't give one)."""


ANY_TRACK = "4uLU6hMCjMI75M1A2tKUQC"      # any public track: its embed page hands out the anonymous key


def search_id(net, artist, title, isrc="", opener=None):
    """Spotify's ID for a song via Spotify's own search (anonymous key): by ISRC (the song's barcode, exact) when
    known, else by title and artist, accepting only a result whose title and artist match."""
    from core.online.models import normalise_text
    token = _anonymous_token(net, ANY_TRACK)
    q = f"isrc:{isrc}" if isrc else f'track:"{title}" artist:"{artist}"'
    url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode({"q": q, "type": "track", "limit": 5})
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "User-Agent": "Mozilla/5.0"})
    if opener is not None:
        body = opener(req)
    else:
        with net._web.open(req, timeout=15) as r:
            body = r.read(1_000_000)
    items = ((json.loads(body) or {}).get("tracks") or {}).get("items") or []
    for it in items:
        if isrc:
            return it.get("id") or ""
        names = normalise_text(" ".join(a.get("name", "") for a in it.get("artists") or []))
        if (normalise_text(it.get("name", ""), strip_versions=False) == normalise_text(title, strip_versions=False)
                and normalise_text(artist) in names):
            return it.get("id") or ""
    return ""


def _isrc(net, deezer_page):
    m = re.search(r"deezer\.com/(?:[a-z]{2}/)?track/(\d+)", deezer_page or "")
    if not m:
        return ""
    try:
        return (net.get_json(f"https://api.deezer.com/track/{m.group(1)}", ttl=30 * 86400) or {}).get("isrc") or ""
    except Exception:
        return ""


def track_id(net, artist, title, page_url="", deezer_page=""):
    """Spotify's 22-character ID for a song, or "": from its Spotify link, else Spotify's search (by the ISRC
    Deezer knows, else by title and artist). (song.link now wants a key, so it isn't used.)"""
    m = ID_RE.search(page_url or "")
    if m:
        return m.group(1)
    try:
        return search_id(net, artist, title, _isrc(net, deezer_page)) or ""
    except Exception:
        return ""


def _anonymous_token(net, tid):
    with _lock:
        if _token["value"] and time.time() < _token["until"]:
            return _token["value"]
    html = net.get_text(EMBED.format(tid), ttl=0)
    m = TOKEN_RE.search(html or "")
    if not m:
        raise NoCanvas("Spotify's player page had no key (Spotify may have changed it)")
    with _lock:
        _token.update(value=m.group(1), until=time.time() + 40 * 60)
    return m.group(1)


def _request_body(tid):
    """EntityCanvazRequest { entities: [{ entity_uri: "spotify:track:<id>" }] } in protobuf."""
    uri = f"spotify:track:{tid}".encode()
    entity = b"\x0a" + bytes([len(uri)]) + uri
    return b"\x0a" + bytes([len(entity)]) + entity


def canvas_url(net, tid, opener=None):
    """The Canvas video link for a Spotify track, or raise NoCanvas."""
    if not re.fullmatch(r"[A-Za-z0-9]{22}", tid or ""):
        raise NoCanvas("no Spotify ID")
    token = _anonymous_token(net, tid)
    req = urllib.request.Request(CANVAS_API, data=_request_body(tid), method="POST", headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/x-protobuf",
        "Accept": "application/protobuf", "User-Agent": "Mozilla/5.0"})
    try:
        if opener is not None:
            body = opener(req)
        else:
            with net._web.open(req, timeout=15) as r:
                body = r.read(200_000)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            with _lock:
                _token.update(value="", until=0)          # the key ran out: a fresh one next time
        raise NoCanvas(f"Spotify said HTTP {e.code}")
    m = VIDEO_RE.search(body or b"")
    if not m:
        raise NoCanvas("this song has no Canvas")
    return m.group(0).decode()


def _cache_dir(data_dir):
    d = os.path.join(data_dir, "canvas-cache")
    os.makedirs(d, exist_ok=True)
    return d


def _misses(data_dir):
    try:
        with open(os.path.join(_cache_dir(data_dir), "none.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _remember_miss(data_dir, key):
    misses = _misses(data_dir)
    misses[key] = time.time()
    if len(misses) > 5000:
        misses = dict(sorted(misses.items(), key=lambda kv: kv[1])[-4000:])
    try:
        with open(os.path.join(_cache_dir(data_dir), "none.json"), "w", encoding="utf-8") as f:
            json.dump(misses, f)
    except OSError:
        pass


def cached(data_dir, tid):
    p = os.path.join(_cache_dir(data_dir), f"{tid}.mp4")
    return p if os.path.isfile(p) and os.path.getsize(p) > 10_000 else None


def find(net, data_dir, artist, title, page_url="", deezer_lookup=None):
    """The local path of this song's Spotify Canvas (downloaded if needed), or None. `deezer_lookup()` gives the
    song's Deezer page when it has no Spotify link (called only when needed)."""
    key = f"{artist}\t{title}".casefold()
    miss = _misses(data_dir).get(key)
    if miss and time.time() - miss < NONE_FOR:
        return None
    tid = ID_RE.search(page_url or "")
    tid = tid.group(1) if tid else ""
    if not tid:
        tid = track_id(net, artist, title, deezer_page=(deezer_lookup() or "") if deezer_lookup else "")
    if not tid:
        _remember_miss(data_dir, key)
        return None
    hit = cached(data_dir, tid)
    if hit:
        os.utime(hit)
        return hit
    try:
        url = canvas_url(net, tid)
    except NoCanvas:
        _remember_miss(data_dir, key)
        return None
    if not is_web_url(url):
        return None
    dest = os.path.join(_cache_dir(data_dir), f"{tid}.mp4")
    net.download(url, dest)
    _trim(data_dir)
    return dest


def _trim(data_dir):
    d = _cache_dir(data_dir)
    files = sorted((os.path.join(d, f) for f in os.listdir(d) if f.endswith(".mp4")), key=os.path.getmtime)
    for old in files[:-MAX_FILES]:
        try:
            os.remove(old)
        except OSError:
            pass

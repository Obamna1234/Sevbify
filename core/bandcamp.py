"""Bandcamp track pages read directly (no yt-dlp).

yt-dlp's Bandcamp reader now insists on "impersonating" a browser with an extra library (curl_cffi) that the apps
don't have (it has native parts that don't exist for phones), so every Bandcamp stream and download failed with
"no impersonate target is available". Bandcamp's own track page carries the song's 128 kbps MP3 link (what its
web player plays) in a data-tralbum attribute, so Sevbify reads that itself, on every platform.
"""
import html
import json
import re
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
PAGE_RE = re.compile(r"^https://[a-z0-9-]+\.bandcamp\.com/track/[A-Za-z0-9_-]+/?(\?.*)?$")
TRALBUM_RE = re.compile(r'data-tralbum="([^"]+)"')
MAX_PAGE = 3_000_000


class NotPlayable(Exception):
    """Bandcamp doesn't let this track be played in full (or the page changed)."""


def is_track_page(url):
    return bool(PAGE_RE.match(url or ""))


def parse_track_page(page_html):
    """{"url", "duration", "title", "artist", "album", "cover"} from a Bandcamp track page."""
    m = TRALBUM_RE.search(page_html or "")
    if not m:
        raise NotPlayable("Bandcamp's page had no player data (it may have changed)")
    try:
        data = json.loads(html.unescape(m.group(1)))
    except ValueError:
        raise NotPlayable("Bandcamp's player data wasn't readable")
    tracks = data.get("trackinfo") or []
    if not tracks:
        raise NotPlayable("no track on this page")
    t = tracks[0]
    url = ((t.get("file") or {}).get("mp3-128") or "")
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith("https://"):
        raise NotPlayable("Bandcamp doesn't stream this track in full")
    current = data.get("current") or {}
    art = data.get("art_id")
    return {"url": url, "duration": float(t.get("duration") or 0), "title": t.get("title") or current.get("title", ""),
            "artist": data.get("artist") or "", "album": (data.get("album_title") or ""),
            "cover": f"https://f4.bcbits.com/img/a{art}_10.jpg" if art else ""}


def track_info(page, opener=None):
    if not is_track_page(page):
        raise NotPlayable("not a Bandcamp track page")
    if opener is not None:
        return parse_track_page(opener(page))
    text = ""
    try:
        # Looking like a real browser (curl_cffi, on the computer apps): Bandcamp shows some connections a
        # "Client Challenge" page instead of the song.
        from curl_cffi import requests as cr
        r = cr.get(page, impersonate="chrome", timeout=20, headers={"Accept-Language": "en"})
        text = r.text[:MAX_PAGE]
    except ImportError:
        pass
    except Exception:
        text = ""
    if "data-tralbum" not in text:
        req = urllib.request.Request(page, headers={"User-Agent": UA, "Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read(MAX_PAGE).decode("utf-8", errors="replace")
    if "data-tralbum" not in text and "challenge" in text.lower():
        raise NotPlayable("Bandcamp asked this connection to prove it's a browser (a Client Challenge)")
    return parse_track_page(text)


def stream(page, opener=None):
    """(link, headers, seconds) for a Bandcamp track: same shape as the yt-dlp path."""
    info = track_info(page, opener)
    return info["url"], {"User-Agent": UA}, info["duration"]


def download(page, dest_mp3, opener=None, max_bytes=60_000_000):
    """Save the track's MP3 to dest_mp3. Returns the info dict."""
    import os
    info = track_info(page, opener)
    tmp = dest_mp3 + ".part"
    req = urllib.request.Request(info["url"], headers={"User-Agent": UA})
    got = 0
    with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
        while True:
            block = r.read(65536)
            if not block:
                break
            got += len(block)
            if got > max_bytes:
                raise NotPlayable("the file was far bigger than a song")
            f.write(block)
    if got < 50_000:
        os.remove(tmp)
        raise NotPlayable("Bandcamp sent too little audio")
    os.replace(tmp, dest_mp3)
    return info

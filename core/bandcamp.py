"""Bandcamp track pages read directly (no yt-dlp).

yt-dlp's Bandcamp reader now insists on "impersonating" a browser with an extra library (curl_cffi) that the apps
don't have (it has native parts that don't exist for phones), so every Bandcamp stream and download failed with
"no impersonate target is available". Bandcamp's own track page carries the song's 128 kbps MP3 link (what its
web player plays) in a data-tralbum attribute, so Sevbify reads that itself, on every platform.
"""
import html
import json
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
PAGE_RE = re.compile(r"^https://[a-z0-9-]+\.bandcamp\.com/track/[A-Za-z0-9_-]+/?(\?.*)?$")
TRALBUM_RE = re.compile(r'data-tralbum="([^"]+)"')
MAX_PAGE = 3_000_000


class NotPlayable(Exception):
    """Bandcamp doesn't let this track be played in full (or the page changed)."""


def urlsplit_host(url):
    from urllib.parse import urlsplit
    return (urlsplit(url).hostname or "").lower()


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
    from urllib.parse import urlsplit
    host = (urlsplit(url).hostname or "").lower()
    if not (host == "bcbits.com" or host.endswith(".bcbits.com")):     # Bandcamp's own file servers only
        raise NotPlayable("Bandcamp's player pointed somewhere unexpected")
    current = data.get("current") or {}
    art = data.get("art_id")
    return {"url": url, "duration": float(t.get("duration") or 0), "title": t.get("title") or current.get("title", ""),
            "artist": data.get("artist") or "", "album": (data.get("album_title") or ""),
            "cover": f"https://f4.bcbits.com/img/a{art}_10.jpg" if art else ""}


MOBILE_API = "https://bandcamp.com/api/mobile/24/tralbum_details"
_ids = {}                      # track page -> (band id, track id), from the search


def remember_ids(page, band_id, track_id):
    try:
        band_id, track_id = int(band_id), int(track_id)
    except (TypeError, ValueError):
        return
    if is_track_page(page) and band_id > 0 and track_id > 0:
        _ids[page.split("?")[0].rstrip("/")] = (band_id, track_id)


def _ids_from_search(page):
    """The band and track ids for a track page, from Bandcamp's search (its app API needs them). Used when the
    page was found another way (remembered from before, or guessed) and Bandcamp's web page is refusing us."""
    try:
        u = urllib.parse.urlsplit(page)
        band = (u.hostname or "").split(".")[0]
        slug = u.path.rstrip("/").split("/")[-1]
        from core import downloader
        e = downloader.engine()
        words = re.sub(r"-\d+$", "", slug).replace("-", " ")
        for query in (f"{band.replace('-', ' ')} {words}", words):
            results, _err = e._bandcamp_request(query)
            for r in results or []:
                url = (e.fix_bc_url(r.get("url") or "") or "").split("?")[0].rstrip("/")
                if r.get("type") == "t" and url == page and r.get("band_id") and r.get("id"):
                    remember_ids(page, r["band_id"], r["id"])
                    return _ids.get(page)
    except Exception:
        return None
    return None


def parse_mobile_details(data):
    """Bandcamp's app API reply → the same info as a track page. The MP3 must be on Bandcamp's own file servers."""
    tracks = (data or {}).get("tracks") or []
    if not tracks:
        raise NotPlayable("Bandcamp's app API had no track")
    t = tracks[0]
    url = ((t.get("streaming_url") or {}).get("mp3-128") or "")
    host = urlsplit_host(url)
    if url.startswith("http://") and (host == "bcbits.com" or host.endswith(".bcbits.com")
                                      or host in ("bandcamp.com", "popplers5.bandcamp.com")):
        url = "https://" + url[len("http://"):]
    ok = url.startswith("https://") and (host == "bcbits.com" or host.endswith(".bcbits.com")
                                         or (host == "bandcamp.com" and urllib.parse.urlsplit(url).path.startswith("/stream_redirect")))
    if not ok:
        raise NotPlayable("this Bandcamp track can't be streamed"
                          + (f" (its link is on {host or 'nothing'})" if url else " (no link)"))
    return {"url": url, "duration": float(t.get("duration") or 0), "title": t.get("title") or "",
            "artist": t.get("band_name") or (data.get("band") or {}).get("name") or ""}


def _mobile_info(page):
    """Like NewPipe and Bandcamp's own phone app: the track's details from the app API, which doesn't show the
    "Client Challenge" page that the website shows some connections (seen on a home connection on Windows)."""
    key = page.split("?")[0].rstrip("/")
    ids = _ids.get(key) or _ids_from_search(key)
    if not ids:
        return None
    import json
    q = urllib.parse.urlencode({"band_id": ids[0], "tralbum_type": "t", "tralbum_id": ids[1]})
    req = urllib.request.Request(f"{MOBILE_API}?{q}", headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return parse_mobile_details(json.loads(r.read(MAX_PAGE).decode("utf-8", errors="replace")))


def track_info(page, opener=None):
    if not is_track_page(page):
        raise NotPlayable("not a Bandcamp track page")
    if opener is not None:
        return parse_track_page(opener(page))
    try:
        info = _mobile_info(page)
        if info:
            return info
    except Exception:
        pass                                          # the web page below
    text = ""
    try:
        # Looking like a real browser (curl_cffi, on the computer apps): Bandcamp shows some connections a
        # "Client Challenge" page instead of the song.
        from curl_cffi import requests as cr
        r = cr.get(page, impersonate="chrome", timeout=20, headers={"Accept-Language": "en"}, stream=True)
        body = b""
        for chunk in r.iter_content():
            body += chunk
            if len(body) > MAX_PAGE:
                break
        r.close()
        text = body[:MAX_PAGE].decode("utf-8", errors="replace")
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
    try:
        with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
            final = (urlsplit_host(r.geturl()))
            if not (final == "bcbits.com" or final.endswith(".bcbits.com")):
                raise NotPlayable("Bandcamp's file link went somewhere unexpected")
            while True:
                block = r.read(65536)
                if not block:
                    break
                got += len(block)
                if got > max_bytes:
                    raise NotPlayable("the file was far bigger than a song")
                f.write(block)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    if got < 50_000:
        os.remove(tmp)
        raise NotPlayable("Bandcamp sent too little audio")
    os.replace(tmp, dest_mp3)
    return info

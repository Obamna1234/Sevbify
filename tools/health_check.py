"""Daily health check of every outside service Sevbify depends on (run by .github/workflows/health.yml).

Each service is tried for real, the way the app uses it. If one that works from GitHub's computers stops working
(Spotify changed its player page, Bandcamp its search, Apple its podcast directory...), this exits with an error,
the workflow fails and GitHub emails the repository owner, so it can be fixed before people notice.

YouTube refuses GitHub's computers ("confirm you're not a bot"), so a YouTube refusal is reported but doesn't
fail the check; any other YouTube error does.
"""
import os
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.online.net import NetClient  # noqa: E402
from core.online.providers import OnlineMusic  # noqa: E402

net = NetClient(tempfile.mkdtemp())
om = OnlineMusic(net)
failed, results = [], []
BOT = ("not a bot", "confirm you", "sign in to confirm", "429", "client challenge", "prove it's a browser")


def check(name, fn, blocked_ok=False, info_only=False):
    t0 = time.time()
    try:
        detail = fn()
        results.append((name, "ok", detail))
        print(f"::notice title=OK: {name}::{detail} ({time.time() - t0:.1f} s)")
    except Exception as e:
        text = f"{type(e).__name__}: {e}"
        if info_only:
            results.append((name, "info", text))
            print(f"::notice title=Not available (information only): {name}::{text[:300]}")
            return
        if blocked_ok and any(w in text.lower() for w in BOT):
            results.append((name, "blocked", text))
            print(f"::notice title=Blocked here: {name}::{text[:300]}")
            return
        failed.append(name)
        results.append((name, "FAILED", text))
        print(f"::error title=FAILED: {name}::{text[:500]}")
        traceback.print_exc()


def spotify_import():
    from core import importers
    res = importers.fetch_from_link(net, "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
    assert len(res["tracks"]) >= 20, len(res["tracks"])
    return f"{res['name']}: {len(res['tracks'])} songs, first {res['tracks'][0].artist} - {res['tracks'][0].title}"


def spotify_canvas():
    from core import spotify_canvas as sc
    seen = {}

    def opener(req):
        import urllib.request
        try:
            with net._web.open(req, timeout=15) as r:
                body = r.read(200_000)
                seen["status"], seen["body"] = r.status, body
                return body
        except Exception as e:
            seen["error"] = repr(e)
            raise
    # Variants tried while finding out what Spotify needs (printed, not failing on their own).
    import urllib.request
    tid = "0VjIjW4GlUZAMYd2vXMi3b"
    token = sc._anonymous_token(net, tid)
    for name, extra in (("web-player headers", {"app-platform": "WebPlayer", "Origin": "https://open.spotify.com",
                                                "Referer": "https://open.spotify.com/", "Accept-Language": "en"}),
                        ("android headers", {"User-Agent": "Spotify/9.0.0 Android/34 (Pixel 7)", "app-platform": "Android"})):
        req = urllib.request.Request(sc.CANVAS_API, data=sc._request_body(tid), method="POST", headers={
            "Authorization": "Bearer " + token, "Content-Type": "application/x-protobuf",
            "Accept": "application/protobuf", **extra})
        try:
            with net._web.open(req, timeout=15) as r:
                b = r.read(5000)
            print(f"::notice title=Canvas variant {name}::HTTP {r.status} {len(b)} bytes {b[:200]!r}")
        except Exception as e:
            print(f"::notice title=Canvas variant {name}::{e!r}")
    ids = ["0VjIjW4GlUZAMYd2vXMi3b", "0yLdNVWF3Srea0uzk55zFn", "4Dvkj6JhhA12EX05fT7y2e", "7MXVkk9YMctZqd1Srtv4MB",
           "0V3wPSX9ygBnCm8psDIegu"]
    body = b""
    for i in ids:
        uri = f"spotify:track:{i}".encode()
        ent = b"\x0a" + bytes([len(uri)]) + uri
        body += b"\x0a" + bytes([len(ent)]) + ent
    req = urllib.request.Request(sc.CANVAS_API, data=body, method="POST", headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/x-protobuf", "Accept": "application/protobuf"})
    try:
        with net._web.open(req, timeout=15) as r:
            b = r.read(20000)
        print(f"::notice title=Canvas 5 hits::HTTP {r.status} {len(b)} bytes {b[:300]!r}")
    except Exception as e:
        print(f"::notice title=Canvas 5 hits::{e!r}")
    import json, base64
    try:
        payload = token.split(".")[1] if token.count(".") == 2 else ""
        print(f"::notice title=Token kind::{len(token)} chars, jwt={bool(payload)}")
    except Exception:
        pass
    try:
        return sc.canvas_url(net, tid, opener=opener)      # Blinding Lights has a Canvas
    except Exception as e:
        body = seen.get("body", b"")
        raise RuntimeError(f"{e}; HTTP {seen.get('status')} {seen.get('error', '')} {len(body)} bytes: "
                           + body[:400].decode("latin-1").encode("unicode_escape").decode()[:600])


def bandcamp():
    from core import downloader
    e = downloader.engine()
    r = e.search_bandcamp("Perturbator - Future Club")
    assert r.get("found") and r.get("url"), r
    from core import streamer
    url, _h, secs = streamer._extract(e, r["url"])
    assert url.startswith("http"), url
    return f"{r['url']} streams ({int(secs)} s)"


def bandcamp_app_api():
    """Bandcamp's app API (what the app tries first, so the website's Client Challenge page isn't hit)."""
    from core import downloader, bandcamp as bc
    e = downloader.engine()
    r = e.search_bandcamp("Perturbator - Future Club")
    assert r.get("found") and r.get("url"), r
    info = bc._mobile_info(r["url"])
    assert info and info["url"].startswith("https://"), f"no ids from the search for {r['url']}"
    return f"{info['title']} ({int(info['duration'])} s) from the app API"


def soundcloud():
    from core import streamer
    found = streamer.search_soundcloud("Perturbator Future Club", 5)
    assert found, "no SoundCloud results"
    url, _h, secs = streamer._extract(__import__("core.downloader", fromlist=["x"]).engine(), found[0].page_url)
    assert url.startswith("http"), url
    return f"{found[0].artist} - {found[0].title} streams ({int(secs)} s)"


def soundcloud_albums():
    from core import streamer
    albums = streamer.soundcloud_albums("Perturbator", 5)
    assert albums, "no albums found"
    tracks = streamer.soundcloud_album_tracks(albums[0])
    assert tracks, f"no songs in {albums[0]['url']}"
    return f"{len(albums)} albums; {albums[0]['title']}: {len(tracks)} songs"


def bandcamp_download():
    from core import downloader
    e = downloader.engine()
    out = tempfile.mkdtemp()
    log = []
    r = e.search_bandcamp("Perturbator - Future Club")
    ok = e.download_bandcamp_mp3(r["url"], "Perturbator - Future Club", out, log.append)
    files = [f for f in os.listdir(out) if f.endswith((".mp3", ".m4a"))]
    assert ok and files, " | ".join(map(str, log))[-600:]
    return f"{files[0]} {os.path.getsize(os.path.join(out, files[0])) // 1024} KB"


def youtube():
    from core import streamer
    res = streamer.find_full_song("Kevin MacLeod", "Monkeys Spinning Monkeys", 0, "YouTube only")
    return f"{res['source']} link found"


def podcasts():
    from core import podcasts as pc
    shows = pc.search(net, "NPR News Now", 5, "us")
    show, eps = pc.fetch_show(net, shows[0])
    assert eps and eps[0].track.stream_url, show
    return f"{show.title}: {len(eps)} episodes"


def lyrics():
    from core import lyrics as L
    lyr = L.find(net, "Rick Astley", "Never Gonna Give You Up", "", 213000)
    assert lyr is not None and lyr.plain.strip()
    return f"{len(lyr.plain.splitlines())} lines"


def song_link():
    from core import share
    t = om.search("Daft Punk Get Lucky", limit=1)[0]
    try:
        net.get_json(share.ODESLI, {"url": t.page_url, "userCountry": "US"}, use_cache=False)
    except Exception as e:
        raise RuntimeError(f"song.link said: {e} (page {t.page_url})")
    out = share.links(net, t.artist, t.title, page_url=t.page_url)
    assert out["exact"]["spotify"], out
    return out["spotify"]


def deezer():
    r = om.search("Mega Drive NARC", limit=5)
    assert r and r[0].preview_url
    return f"{len(r)} results"


def ytdlp_current():
    from core import updates, downloader
    return f"bundled yt-dlp {downloader.engine().ytdlp_version()}"


check("Deezer search", deezer)
check("Spotify playlist import (no account)", spotify_import)
def spotify_search():
    from core import spotify_canvas as sc
    tid = sc.search_id(net, "The Weeknd", "Blinding Lights")
    assert len(tid) == 22, tid
    return tid


# Not used by the app (Spotify keeps these for signed-in accounts); watched in case that changes.
check("Spotify search (no account)", spotify_search, info_only=True)
check("Spotify Canvas (no account)", spotify_canvas, info_only=True)
check("Bandcamp search + stream link", bandcamp, blocked_ok=True)
check("Bandcamp download", bandcamp_download, blocked_ok=True)
check("Bandcamp app API (no Client Challenge)", bandcamp_app_api, blocked_ok=True)
check("SoundCloud search + stream link", soundcloud, blocked_ok=True)
check("SoundCloud albums (artist pages)", soundcloud_albums, blocked_ok=True)
check("YouTube full song", youtube, blocked_ok=True)
check("Podcasts (Apple directory + feed)", podcasts)
check("Lyrics (LRCLIB)", lyrics)
check("song.link (Share; now wants a key, Share uses search links)", song_link, info_only=True)
check("yt-dlp", ytdlp_current)

summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as f:
        f.write("### Sevbify health check\n\n| Service | Result | Details |\n|---|---|---|\n")
        for name, status, detail in results:
            icon = {"ok": "✅", "blocked": "🚫 blocked here", "FAILED": "❌ FAILED", "info": "ℹ not available"}[status]
            f.write(f"| {name} | {icon} | {str(detail).replace('|', '/')[:300]} |\n")
print(f"{len(results) - len(failed)}/{len(results)} fine; failed: {failed or 'none'}")
sys.exit(1 if failed else 0)

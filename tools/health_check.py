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


def bandcamp():
    from core import downloader
    e = downloader.engine()
    r = e.search_bandcamp("Chris Zabriskie - Candlepower")
    assert r.get("found") and r.get("url"), r
    from core import streamer
    url, _h, secs = streamer._extract(e, r["url"])
    assert url.startswith("http"), url
    return f"{r['url']} streams ({int(secs)} s)"


def bandcamp_app_api():
    """Bandcamp's app API (what the app tries first, so the website's Client Challenge page isn't hit)."""
    from core import downloader, bandcamp as bc
    e = downloader.engine()
    r = e.search_bandcamp("Chris Zabriskie - Candlepower")
    assert r.get("found") and r.get("url"), r
    info = bc._mobile_info(r["url"])
    assert info and info["url"].startswith("https://"), f"no ids from the search for {r['url']}"
    return f"{info['title']} ({int(info['duration'])} s) from the app API"


def soundcloud():
    from core import streamer
    found = streamer.search_soundcloud("Chris Zabriskie Candlepower", 5)
    assert found, "no SoundCloud results"
    url, _h, secs = streamer._extract(__import__("core.downloader", fromlist=["x"]).engine(), found[0].page_url)
    assert url.startswith("http"), url
    return f"{found[0].artist} - {found[0].title} streams ({int(secs)} s)"


def soundcloud_albums():
    from core import streamer
    albums = streamer.soundcloud_albums("Chris Zabriskie", 5)
    assert albums, "no albums found"
    tracks = streamer.soundcloud_album_tracks(albums[0])
    assert tracks, f"no songs in {albums[0]['url']}"
    return f"{len(albums)} albums; {albums[0]['title']}: {len(tracks)} songs"


def country_charts():
    from core.online.providers import country_top_songs
    au = country_top_songs(net, "au", 10)
    assert au, "no songs"
    return f"{len(au)} songs, first: {au[0].artist} - {au[0].title}"


def genre_playlists():
    more = om.deezer.genre_playlists("Jazz", "Australia")
    n = sum(len(v) for v in more.values())
    assert n >= 20, more
    return {k: len(v) for k, v in more.items()}


def bandcamp_download():
    from core import downloader
    e = downloader.engine()
    out = tempfile.mkdtemp()
    log = []
    r = e.search_bandcamp("Chris Zabriskie - Candlepower")
    ok = e.download_bandcamp_mp3(r["url"], "Chris Zabriskie - Candlepower", out, log.append)
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
    t = om.search("Chris Zabriskie Candlepower", limit=1)[0]
    try:
        net.get_json(share.ODESLI, {"url": t.page_url, "userCountry": "US"}, use_cache=False)
    except Exception as e:
        raise RuntimeError(f"song.link said: {e} (page {t.page_url})")
    out = share.links(net, t.artist, t.title, page_url=t.page_url)
    assert out["exact"]["spotify"], out
    return out["spotify"]


def support_links():
    from core import support
    links = support.for_song(net, "Chris Zabriskie", "Candlepower",
                             "https://chriszabriskie.bandcamp.com/track/candlepower", "bandcamp")
    assert len(links) >= 2 and all(l["url"].startswith("https://") for l in links), links
    return ", ".join(f"{l['label']} ({l['site']})" for l in links)


def deezer():
    r = om.search("Chris Zabriskie Divider", limit=5)
    assert r and r[0].preview_url
    return f"{len(r)} results"


def ytdlp_current():
    from core import updates, downloader
    return f"bundled yt-dlp {downloader.engine().ytdlp_version()}"


check("Deezer search", deezer)
check("Top songs in your country (Apple charts)", country_charts)
check("Genre pages: more playlists (Deezer)", genre_playlists)
check("Spotify playlist import (no account)", spotify_import)
check("Bandcamp search + stream link", bandcamp, blocked_ok=True)
check("Bandcamp download", bandcamp_download, blocked_ok=True)
check("Bandcamp app API (no Client Challenge)", bandcamp_app_api, blocked_ok=True)
check("SoundCloud search + stream link", soundcloud, blocked_ok=True)
check("SoundCloud albums (artist pages)", soundcloud_albums, blocked_ok=True)
check("YouTube full song", youtube, blocked_ok=True)
check("Podcasts (Apple directory + feed)", podcasts)
check("Lyrics (LRCLIB)", lyrics)
check("Support the artist (MusicBrainz)", support_links)
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

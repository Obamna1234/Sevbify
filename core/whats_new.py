"""What's new (Spotify's bell): new episodes of shows you follow and new releases from artists you listen to,
worked out on your device. It asks only the podcasts' own feeds and Deezer's public new-release lists (the same
requests Podcasts and Release Radar already make); nothing about you is sent.
"""
import time

MAX_AGE = 14 * 86400


def gather(net, online, shows, listens, fetch_show=None, release_radar=None, now=None):
    """[{"kind": "episode"|"release", "title", "subtitle", "when", "track"}], newest first (last two weeks)."""
    now = now or time.time()
    out = []
    if fetch_show is None:
        from core.podcasts import fetch_show
    for show in list(shows)[:30]:
        try:
            show, episodes = fetch_show(net, show)
        except Exception:
            continue
        for ep in episodes[:3]:
            if ep.published and now - ep.published <= MAX_AGE:
                out.append({"kind": "episode", "title": ep.track.title, "subtitle": show.title,
                            "when": ep.published, "track": ep.track})
    if release_radar is None:
        from core.discovery import release_radar
    try:
        for t in release_radar(online, listens) or []:
            out.append({"kind": "release", "title": t.title, "subtitle": f"New from {t.artist}",
                        "when": now - 1, "track": t})
    except Exception:
        pass
    out.sort(key=lambda x: -x["when"])
    return out


def unseen(items, seen_at):
    return sum(1 for x in items if x["when"] > (seen_at or 0))

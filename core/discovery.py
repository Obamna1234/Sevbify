"""Spotify's "Made for you" playlists, made on this computer from what you listen to:

- Discover Weekly (new every Monday): 30 songs you haven't played, by artists related to the ones you play most,
  leaving out artists you already know well.
- Daily Mix 1-4 (new every day): each around one of your favourite artists, mixing their songs and similar ones.
- Release Radar (new every Friday): the latest releases (last two weeks) from artists you listen to.

How it stays private: your listening history (artist, song, time) is kept only in Sevbify's data folder on this
computer and is never sent anywhere. To find related music, only artist names are looked up on Deezer / Last.fm
— the same lookups as a song radio — with no account and nothing that identifies you. Nothing is recorded during
a Private session. Spotify's "taste twins" (comparing you with millions of other users) isn't possible without
collecting everyone's listening, which Sevbify doesn't do; related-artist and listener data from Deezer/Last.fm
stands in for it.
"""
import datetime
import random
import re
from collections import Counter

MAX_LISTENS = 5000


def _norm(text):
    return " ".join(re.findall(r"\w+", (text or "").casefold()))


def record(listens, artist, title, when=None):
    """Add one listen (newest last), keeping at most MAX_LISTENS. Returns the list."""
    if not artist or artist == "Unknown Artist" or not title:
        return listens
    listens.append([artist, title, int(when if when is not None else datetime.datetime.now().timestamp())])
    del listens[:-MAX_LISTENS]
    return listens


def top_artists(listens, days=28, n=10, now=None):
    """Your most played artists lately (more recent plays count a little more)."""
    now = now or datetime.datetime.now().timestamp()
    score, names = Counter(), {}
    for artist, _title, ts in listens:
        age = (now - ts) / 86400
        if age > days:
            continue
        key = _norm(artist)
        score[key] += 1.0 + max(0.0, (days - age) / days)
        names.setdefault(key, artist)
    return [names[k] for k, _ in score.most_common(n)]


def week_seed(today=None):
    today = today or datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return int(monday.strftime("%Y%m%d"))


def day_seed(today=None):
    return int((today or datetime.date.today()).strftime("%Y%m%d"))


def radar_seed(today=None):
    """Release Radar changes on Fridays."""
    today = today or datetime.date.today()
    friday = today - datetime.timedelta(days=(today.weekday() - 4) % 7)
    return int(friday.strftime("%Y%m%d"))


def discover_weekly(online, listens, known_keys=(), today=None, size=30):
    """30 songs by artists related to your favourites, not ones you play already, nor songs you know."""
    seed = week_seed(today)
    rng = random.Random(seed)
    favourites = top_artists(listens, days=60, n=12)
    if not favourites:
        return []
    familiar = {_norm(a) for a in top_artists(listens, days=365, n=60)}
    known = set(known_keys) | {(_norm(a), _norm(t)) for a, t, _ts in listens}
    pool, seen_artists = [], set()
    for fav in favourites:
        a = online.deezer.find_artist(fav)
        if not a:
            continue
        related = online.deezer.related(a.get("id"), limit=15)
        rng.shuffle(related)
        for rel in related[:6]:
            name = rel.get("name") or ""
            if not name or _norm(name) in familiar or _norm(name) in seen_artists:
                continue
            seen_artists.add(_norm(name))
            try:
                tracks = online.deezer.top_tracks(rel.get("id"), limit=8)
            except Exception:
                continue
            tracks = [t for t in tracks if (_norm(t.artist), _norm(t.title)) not in known]
            rng.shuffle(tracks)
            pool.extend(tracks[:2])
        if len(pool) >= size * 2:
            break
    rng.shuffle(pool)
    out, per = [], Counter()
    for t in pool:
        if per[_norm(t.artist)] >= 2:
            continue
        per[_norm(t.artist)] += 1
        out.append(t)
        if len(out) >= size:
            break
    return out


def daily_mixes(online, listens, today=None, count=4, size=50):
    """Up to 4 mixes, each around one of your favourite artists: [{"title", "subtitle", "tracks", "artist"}]."""
    seed = day_seed(today)
    favourites = top_artists(listens, days=90, n=count * 3)
    mixes, used = [], set()
    for fav in favourites:
        if len(mixes) >= count:
            break
        if _norm(fav) in used:
            continue
        rng = random.Random(seed + len(mixes))
        try:
            tracks = online.radio(fav, "", limit=size, rng=rng)
        except Exception:
            continue
        if len(tracks) < 10:
            continue
        used.add(_norm(fav))
        others = []
        for t in tracks:
            if _norm(t.artist) != _norm(fav) and t.artist not in others:
                others.append(t.artist)
        mixes.append({"title": f"Daily Mix {len(mixes) + 1}", "artist": fav, "tracks": tracks,
                      "subtitle": ", ".join([fav] + others[:2]) + (" and more" if len(others) > 2 else "")})
    return mixes


def release_radar(online, listens, today=None, size=30, days=14):
    """New songs (released in the last two weeks) from artists you listen to."""
    today = today or datetime.date.today()
    since = (today - datetime.timedelta(days=days)).isoformat()
    out = []
    for name in top_artists(listens, days=180, n=30):
        a = online.deezer.find_artist(name)
        if not a:
            continue
        try:
            releases = online.deezer.artist_albums(a.get("id"))
        except Exception:
            continue
        for group in ("albums", "singles"):
            for album in releases.get(group) or []:
                if (album.get("release_date") or "") >= since:
                    try:
                        out.extend(online.deezer.album_tracks(album)[:5])
                    except Exception:
                        pass
        if len(out) >= size:
            break
    return out[:size]


MOODS = (("chill", "Chill"), ("happy", "Happy"), ("energetic", "Energy"), ("focus", "Focus"), ("sad", "Melancholy"))


def daylist(online, listens, now=None, size=40):
    """Spotify's daylist: a mix for this part of the day, from what you usually play around this hour (last 90
    days), topped up with songs like those. {"title", "subtitle", "tracks"} or None. Changes through the day."""
    import time as _t
    now = now or _t.time()
    lt = _t.localtime(now)
    part = ("early morning" if lt.tm_hour < 7 else "morning" if lt.tm_hour < 12 else "afternoon" if lt.tm_hour < 17
            else "evening" if lt.tm_hour < 22 else "late night")
    day = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[lt.tm_wday]
    near = []
    for row in listens:
        if not (isinstance(row, (list, tuple)) and len(row) >= 3 and isinstance(row[2], (int, float))):
            continue
        if now - row[2] > 90 * 86400:
            continue
        h = _t.localtime(row[2]).tm_hour
        if min(abs(h - lt.tm_hour), 24 - abs(h - lt.tm_hour)) <= 2:
            near.append(row)
    if len(near) < 3:
        return None
    from collections import Counter
    favs = [a for a, _n in Counter(r[0] for r in near if r[0] and r[0] != "Unknown Artist").most_common(3)]
    rng = random.Random(int(now // 3600))
    tracks, seen = [], set()
    for fav in favs:
        try:
            got = online.radio(fav, "", limit=size // max(1, len(favs)) + 5, rng=rng)
        except Exception:
            continue
        for t in got:
            k = (_norm(t.artist), _norm(t.title))
            if k not in seen:
                seen.add(k)
                tracks.append(t)
    rng.shuffle(tracks)
    if len(tracks) < 10:
        return None
    return {"title": f"daylist · {day} {part}", "subtitle": "For this time of day: " + ", ".join(favs),
            "tracks": tracks[:size]}


def mood_mix(online, mood, listens, size=40):
    """A mood mix (Chill, Happy, Energy, Focus, Melancholy) leaning towards artists you play: Deezer's mood
    playlists searched by name, mixed with songs like your favourites. {"title", "subtitle", "tracks"} or None."""
    label = dict(MOODS).get(mood, mood.title())
    try:
        found = online.deezer.search_playlists(f"{label} mix", limit=3)
    except Exception:
        found = []
    tracks = []
    for pl in found[:2]:
        try:
            tracks += online.deezer.playlist_tracks(pl.get("id"))[: size // 2]
        except Exception:
            pass
    favs = top_artists(listens, days=90, n=2)
    for fav in favs:
        try:
            tracks += online.radio(fav, "", limit=10)
        except Exception:
            pass
    seen, out = set(), []
    for t in tracks:
        k = (_norm(t.artist), _norm(t.title))
        if k not in seen:
            seen.add(k)
            out.append(t)
    random.Random(hash(mood) & 0xFFFF).shuffle(out)
    return {"title": f"{label} Mix", "subtitle": f"{label} songs, with a little of what you love",
            "tracks": out[:size]} if len(out) >= 10 else None

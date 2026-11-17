"""Your listening stats ("Wrapped"), worked out on your device from your own play history. Nothing is sent anywhere.

listens: [[artist, title, unix_time], ...] (what Sevbify records as you play; nothing during a private session and
nothing you excluded from your taste profile). durations: optional {(artist, title) key: ms} for minutes; songs
without a known length count as 3.5 minutes (the average song).
"""
import re
import time
from collections import Counter

AVERAGE_MS = 210_000
PERIODS = {"4 weeks": 28 * 86400, "6 months": 182 * 86400, "This year": None, "All time": 0}


def _key(artist, title):
    return " ".join(re.findall(r"\w+", (artist or "").casefold())) + "|" + " ".join(re.findall(r"\w+", (title or "").casefold()))


def _since(period, now):
    span = PERIODS.get(period, 0)
    if span is None:                                   # this calendar year
        t = time.localtime(now)
        return time.mktime((t.tm_year, 1, 1, 0, 0, 0, 0, 0, -1))
    return now - span if span else 0


def stats(listens, period="This year", durations=None, now=None):
    now = now or time.time()
    since = _since(period, now)
    rows = [r for r in listens if isinstance(r, (list, tuple)) and len(r) >= 3 and isinstance(r[2], (int, float))
            and since <= r[2] <= now + 60]
    durations = durations or {}
    songs, artists, names = Counter(), Counter(), {}
    ms, days, hours = 0, set(), Counter()
    for artist, title, at in ((str(r[0]), str(r[1]), r[2]) for r in rows):
        k = _key(artist, title)
        songs[k] += 1
        names.setdefault(k, (artist, title))
        if artist and artist != "Unknown Artist":
            artists[artist] += 1
        ms += int(durations.get(k) or AVERAGE_MS)
        lt = time.localtime(at)
        days.add((lt.tm_year, lt.tm_yday))
        hours[lt.tm_hour] += 1
    top_hour = hours.most_common(1)[0][0] if hours else None
    return {
        "period": period,
        "plays": len(rows),
        "minutes": ms // 60_000,
        "days": len(days),
        "songs": len(songs),
        "artists": len(artists),
        "top_artists": [{"artist": a, "plays": n} for a, n in artists.most_common(5)],
        "top_songs": [{"artist": names[k][0], "title": names[k][1], "plays": n} for k, n in songs.most_common(5)],
        "top_50": [{"artist": names[k][0], "title": names[k][1]} for k, _n in songs.most_common(50)],
        "time_of_day": (None if top_hour is None else
                        "morning" if 5 <= top_hour < 12 else "afternoon" if top_hour < 17 else
                        "evening" if top_hour < 22 else "late night"),
    }

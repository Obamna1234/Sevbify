"""Smart downloads, like Spotify's: songs you keep playing are downloaded for you, so they play offline too.

Off unless you turn it on (Settings). Worked out on your device from your own play history: a streamed song you
played at least MIN_PLAYS times in the last DAYS days is downloaded, at most PER_DAY a day, and (on phones) only
on Wi-Fi. Nothing is sent anywhere except the download itself, from the same place as any download.
"""
import re
import time

MIN_PLAYS = 3
DAYS = 30
PER_DAY = 20


def _key(artist, title):
    return " ".join(re.findall(r"\w+", (artist or "").casefold())) + "|" + " ".join(re.findall(r"\w+", (title or "").casefold()))


def pick(listens, pool, is_downloaded, done_today=0, now=None, min_plays=MIN_PLAYS, days=DAYS, per_day=PER_DAY):
    """Which of `pool` (songs you could download: objects or dicts with artist/title) to download now, most played
    first. listens: [[artist, title, unix_time], ...]; is_downloaded(song) -> bool."""
    now = now or time.time()
    room = max(0, per_day - int(done_today))
    if not room:
        return []
    counts = {}
    for row in listens or []:
        if isinstance(row, (list, tuple)) and len(row) >= 3 and isinstance(row[2], (int, float)) \
                and now - row[2] <= days * 86400:
            k = _key(str(row[0]), str(row[1]))
            counts[k] = counts.get(k, 0) + 1

    def get(s, name):
        return s.get(name, "") if isinstance(s, dict) else getattr(s, name, "")
    out, seen = [], set()
    for s in pool:
        k = _key(get(s, "artist"), get(s, "title"))
        if k in seen or counts.get(k, 0) < min_plays or not get(s, "title"):
            continue
        seen.add(k)
        try:
            if is_downloaded(s):
                continue
        except Exception:
            continue
        out.append((counts[k], s))
    out.sort(key=lambda x: -x[0])
    return [s for _n, s in out[:room]]

"""Flow: put a playlist's songs in an order that's nice to listen to, as a new playlist (the original isn't touched).

Each song gets a feel: an energy score from 0 (calm) to 1 (intense) and a family (electronic, rock, jazz...). The
energy comes from what Deezer publishes about the song (tempo in BPM and loudness, no account needed), the genre
and sub-genre (synthwave vs darkwave vs chillwave, soft rock vs metal...) and clues in the title ("acoustic",
"slowed", "remix"...). Songs Deezer doesn't know are placed by their genre and title alone, so nothing is dropped.

Orders ("modes"):
  wind_down  big energy first, then the middle, ending calm (default)
  build      calm first, building up to big energy
  waves      builds up, eases off, builds up again (hot, cold, hot, cold)
  smooth     every song leads gently into the next; genres blend instead of jumping
  mix        a bit of everything: calm, energetic and in-between songs spread through the playlist, shuffled
  genre      grouped by family, smooth inside each group, the groups in an order that flows too
Options: keep the same artist apart (never twice in a row), start calm or start energetic.

What's learned about a song is kept in flow_features.json in Sevbify's own folder, so the next Flow is instant.
Nothing about you is sent: only the song's artist and title are looked up, the same as a search.
"""
import json
import os
import re
import threading

MAX_SONGS = 2000           # Sort by energy works on playlists up to this size (bigger: the first 2000 are sorted)
MODES = ("wind_down", "build", "waves", "smooth", "mix", "genre")
VERSION = 1

# (words in a genre name, family, how intense that style usually is 0..1). The first match wins, so the more
# specific styles come first (e.g. "chillwave" before "wave", "soft rock" before "rock").
STYLES = [
    (("ambient", "drone", "new age", "meditation", "sleep"), "ambient", 0.08),
    (("lo-fi", "lofi", "chillhop", "chillout", "chill out", "downtempo", "trip hop", "trip-hop"), "chill", 0.25),
    (("chillwave", "vaporwave", "dreamwave", "retrowave chill"), "electronic", 0.3),
    (("darksynth", "darkwave", "cyberpunk", "industrial"), "electronic", 0.78),
    (("synthwave", "outrun", "retrowave", "synth-pop", "synthpop", "new wave"), "electronic", 0.55),
    (("drum and bass", "drum & bass", "dnb", "dubstep", "hardstyle", "hardcore", "trance", "techno", "edm",
      "electro house", "big room"), "electronic", 0.85),
    (("house", "dance", "disco", "electro", "electronic", "club"), "electronic", 0.7),
    (("classical", "orchestra", "opera", "baroque", "piano", "film score", "soundtrack", "films/games", "score"),
     "classical", 0.2),
    (("smooth jazz", "bossa", "lounge", "easy listening"), "jazz", 0.22),
    (("jazz", "swing", "bebop", "big band"), "jazz", 0.38),
    (("blues",), "blues", 0.42),
    (("soul", "r&b", "rnb", "neo soul", "funk", "motown"), "soul", 0.5),
    (("acoustic", "folk", "singer-songwriter", "singer & songwriter", "country", "bluegrass", "americana"), "folk", 0.3),
    (("reggae", "dub", "ska"), "reggae", 0.45),
    (("latin", "reggaeton", "salsa", "bachata", "samba", "afrobeat", "afro", "k-pop", "kpop", "j-pop", "world"),
     "world", 0.6),
    (("rap", "hip hop", "hip-hop", "trap", "drill", "grime"), "hiphop", 0.62),
    (("death metal", "black metal", "thrash", "metalcore", "deathcore", "grindcore", "doom"), "metal", 0.95),
    (("metal", "heavy"), "metal", 0.88),
    (("punk", "hardcore punk", "emo", "post-hardcore"), "rock", 0.8),
    (("soft rock", "yacht rock", "acoustic rock"), "rock", 0.42),
    (("indie", "alternative", "shoegaze", "dream pop", "post-rock"), "rock", 0.5),
    (("rock", "grunge", "garage"), "rock", 0.68),
    (("pop",), "pop", 0.55),
]

# Families next to each other in this list blend well (used to order genre groups and to soften jumps).
FAMILY_ORDER = ["ambient", "classical", "chill", "jazz", "folk", "blues", "soul", "reggae", "pop", "world",
                "electronic", "hiphop", "rock", "metal", "other"]

# Clues in a song's title or album: (words, change to energy).
CLUES = [
    (("acoustic", "unplugged", "piano version", "lullaby", "slowed", "reverb", "stripped", "orchestral",
      "instrumental", "ambient mix", "sleep", "calm", "chill"), -0.18),
    (("remix", "club mix", "extended mix", "vip", "sped up", "nightcore", "bass boosted", "hard mix", "rework"), 0.12),
    (("live",), 0.05),
]


def style_of(genre, title="", album=""):
    """(family, energy prior) for a genre name, with the title/album as a fallback when the genre is unknown."""
    text = f"{genre or ''}".lower()
    for words, family, energy in STYLES:
        if any(w in text for w in words):
            return family, energy
    extra = f"{title or ''} {album or ''}".lower()
    for words, family, energy in STYLES:
        if any(re.search(r"\b" + re.escape(w) + r"\b", extra) for w in words):
            return family, energy
    return "other", 0.5


def clue_shift(title="", album=""):
    text = f"{title or ''} {album or ''}".lower()
    shift = 0.0
    for words, change in CLUES:
        if any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words):
            shift += change
    return shift


def energy_of(prior, bpm=0.0, gain=None, shift=0.0):
    """0 (calm) .. 1 (intense) from the style's usual energy, the tempo and the loudness when known."""
    parts, weights = [prior], [0.45]
    if bpm and bpm > 0:
        b = float(bpm)
        if b < 70 and prior > 0.55:          # half-time counted (a fast song read as 60-something BPM)
            b *= 2
        parts.append(min(1.0, max(0.0, (b - 65) / (175 - 65))))
        weights.append(0.35)
    if gain is not None:
        try:
            g = float(gain)                       # Deezer's gain: about -16 (quiet) .. -3 (loud) dB
            parts.append(min(1.0, max(0.0, (g + 16) / 13)))
            weights.append(0.2)
        except (TypeError, ValueError):
            pass
    e = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
    return round(min(1.0, max(0.0, e + shift)), 3)


def key_of(t):
    a = re.sub(r"\W+", " ", str(t.get("artist", "")).casefold()).strip()
    n = re.sub(r"\W+", " ", str(t.get("title", "")).casefold()).strip()
    return f"{a}|{n}"


# --- looking songs up -----------------------------------------------------------------------------------------
def valid(f):
    """A song's details as Sevbify writes them (anything else, e.g. from a damaged file, is ignored)."""
    return (isinstance(f, dict) and isinstance(f.get("energy"), (int, float)) and 0 <= f["energy"] <= 1
            and isinstance(f.get("family"), str) and len(f["family"]) <= 40
            and isinstance(f.get("genre", ""), str) and len(f.get("genre", "")) <= 100)


class FeatureStore:
    """What's been learned about songs (energy, family, genre, bpm), kept between runs."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("songs", {}) if isinstance(data, dict) and data.get("version") == VERSION else {}
            self.items = {k: v for k, v in (items.items() if isinstance(items, dict) else [])
                          if isinstance(k, str) and valid(v)}       # a damaged entry is just looked up again
        except (OSError, ValueError, AttributeError):
            self.items = {}

    def get(self, k):
        with self.lock:
            return self.items.get(k)

    def put(self, k, v):
        with self.lock:
            self.items[k] = v
            if len(self.items) > 20000:                       # oldest first out
                for old in list(self.items)[:2000]:
                    self.items.pop(old, None)

    def save(self):
        if not self.path:
            return
        with self.lock:
            data = {"version": VERSION, "songs": dict(self.items)}
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self.path)
        except OSError:
            pass


def _deezer_track(deezer, t):
    """Deezer's full track (with bpm and gain) for a song, or None."""
    from .online.models import OnlineTrack
    from .online.providers import same_song
    sid = str(t.get("source_id", "") or "")
    if t.get("source") == "deezer" and sid.isdigit():
        return deezer._get(f"/track/{sid}", ttl=30 * 24 * 3600)
    artist, title = str(t.get("artist", "")), str(t.get("title", ""))
    if not artist or not title or artist == "Unknown Artist":
        return None
    want = OnlineTrack(title=title, artist=artist)
    for cand in deezer.search(f'artist:"{artist}" track:"{title}"', 5) or deezer.search(f"{artist} {title}", 5):
        if cand.key == want.key or same_song(want, cand):
            return deezer._get(f"/track/{cand.source_id}", ttl=30 * 24 * 3600)
    return None


def features(t, deezer=None, store=None, online=True):
    """{"energy", "family", "genre", "bpm", "known"} for one song (a dict with artist/title/album/genre...)."""
    k = key_of(t)
    if store is not None:
        hit = store.get(k)
        if hit and (hit.get("known") or not online):
            return hit
    genre, bpm, gain, known = str(t.get("genre", "") or "")[:100], 0.0, None, False
    if online and deezer is not None:
        try:
            d = _deezer_track(deezer, t)
            if d:
                known = True
                bpm = float(d.get("bpm") or 0)
                gain = d.get("gain")
                album = d.get("album") or {}
                if not genre and album.get("id"):
                    genre = str(deezer.album_genre(album["id"]) or "")[:100]
        except Exception:
            pass                                               # offline / not found: genre and title only
    family, prior = style_of(genre, t.get("title", ""), t.get("album", ""))
    out = {"energy": energy_of(prior, bpm, gain, clue_shift(t.get("title", ""), t.get("album", ""))),
           "family": family, "genre": genre, "bpm": round(bpm), "known": known}
    if store is not None:
        store.put(k, out)
    return out


# --- ordering ------------------------------------------------------------------------------------------------
def _family_gap(a, b):
    if a == b:
        return 0.0
    try:
        return abs(FAMILY_ORDER.index(a) - FAMILY_ORDER.index(b)) / len(FAMILY_ORDER)
    except ValueError:
        return 0.5


def _distance(fa, fb):
    """How big a jump it is from one song to the next."""
    return abs(fa["energy"] - fb["energy"]) + 0.6 * _family_gap(fa["family"], fb["family"]) + \
        (0.08 if (fa.get("genre") or "") != (fb.get("genre") or "") else 0.0)


def _chain(idx, feats, start_high=False):
    """Nearest-neighbour path through the songs: each next song is the closest in feel to the one before."""
    if not idx:
        return []
    left = list(idx)
    first = max(left, key=lambda i: feats[i]["energy"]) if start_high else min(left, key=lambda i: feats[i]["energy"])
    out = [first]
    left.remove(first)
    while left:
        cur = feats[out[-1]]
        nxt = min(left, key=lambda i: (_distance(cur, feats[i]), i))
        out.append(nxt)
        left.remove(nxt)
    return out


def _sorted_smooth(idx, feats, descending=False):
    """By energy, with neighbours of nearly the same energy arranged so genres don't flip back and forth."""
    ordered = sorted(idx, key=lambda i: (feats[i]["energy"], i), reverse=descending)
    out = []
    band = []
    for i in ordered:                                     # bands of similar energy (0.08 wide)
        if band and abs(feats[i]["energy"] - feats[band[0]]["energy"]) > 0.08:
            out += _band(band, feats, out[-1] if out else None)
            band = []
        band.append(i)
    out += _band(band, feats, out[-1] if out else None)
    return out


def _band(band, feats, prev):
    if len(band) < 3:
        return band
    left = list(band)
    out = []
    cur = feats[prev] if prev is not None else feats[left[0]]
    while left:
        nxt = min(left, key=lambda i: (_family_gap(cur["family"], feats[i]["family"]), i))
        out.append(nxt)
        left.remove(nxt)
        cur = feats[nxt]
    return out


def _waves(idx, feats, start_high=False, wave=8):
    """Up and down like waves: each wave covers calm to intense, rising then falling in turn."""
    ordered = sorted(idx, key=lambda i: (feats[i]["energy"], i))
    n = len(ordered)
    waves = max(1, round(n / wave))
    buckets = [ordered[k::waves] for k in range(waves)]       # each bucket spans the whole range
    out = []
    for k, b in enumerate(buckets):
        rising = (k % 2 == 0) != start_high
        out += _sorted_smooth(b, feats, descending=not rising)
    return out


def _mix(idx, feats, seed=None):
    """A bit of everything: songs split into calm / middle / energetic thirds (shuffled inside each), then dealt
    out in turn so every stretch of the playlist has some of each, never two big jumps in a row."""
    import random
    rnd = random.Random(seed)
    ordered = sorted(idx, key=lambda i: (feats[i]["energy"], i))
    n = len(ordered)
    thirds = [ordered[:n // 3], ordered[n // 3: 2 * n // 3], ordered[2 * n // 3:]]
    for t in thirds:
        rnd.shuffle(t)
    pattern = [1, 2, 1, 0]                      # middle, energetic, middle, calm, ... (gentle steps)
    out, k = [], rnd.randrange(len(pattern))
    while any(thirds):
        want = pattern[k % len(pattern)]
        k += 1
        for pick in (want, 1, 2, 0):
            if thirds[pick]:
                out.append(thirds[pick].pop())
                break
    return out


def _grouped(idx, feats, start_high=False):
    groups = {}
    for i in idx:
        groups.setdefault(feats[i]["family"], []).append(i)
    mean = {f: sum(feats[i]["energy"] for i in g) / len(g) for f, g in groups.items()}
    order = sorted(groups, key=lambda f: (mean[f], FAMILY_ORDER.index(f) if f in FAMILY_ORDER else 99),
                   reverse=start_high)
    out = []
    for k, f in enumerate(order):
        # alternate the direction inside each group, so the end of one group meets the start of the next
        out += _sorted_smooth(groups[f], feats, descending=(k % 2 == 1) != start_high)
    return out


def _artists_apart(order, tracks):
    """No artist twice in a row where it can be helped (swap with the nearest later song by someone else)."""
    out = list(order)
    who = lambda i: str(tracks[i].get("artist", "")).casefold().strip()
    for p in range(1, len(out)):
        if who(out[p]) and who(out[p]) == who(out[p - 1]):
            for q in range(p + 1, len(out)):
                if who(out[q]) != who(out[p - 1]) and (q + 1 >= len(out) or who(out[q]) != who(out[p])
                                                       or p + 1 == q):
                    out[p], out[q] = out[q], out[p]
                    break
    return out


def order(tracks, feats, mode="wind_down", artists_apart=True, start="calm", seed=None):
    """The new order as a list of indexes into tracks (every song once)."""
    if len(tracks) != len(feats) or not all(valid(f) for f in feats):
        raise ValueError("every song needs its details")
    if len(tracks) > MAX_SONGS:
        raise ValueError(f"Sort by energy works on playlists of up to {MAX_SONGS} songs")
    idx = list(range(len(tracks)))
    if len(idx) < 3:
        return idx
    high = start == "energetic"
    if mode == "waves":
        out = _waves(idx, feats, high)
    elif mode == "build":
        out = _sorted_smooth(idx, feats)
    elif mode == "wind_down":
        out = _sorted_smooth(idx, feats, descending=True)
    elif mode == "genre":
        out = _grouped(idx, feats, high)
    elif mode == "mix":
        out = _mix(idx, feats, seed)
    else:
        out = _chain(idx, feats, high)
    if artists_apart:
        out = _artists_apart(out, tracks)
    assert sorted(out) == idx
    return out


def summary(feats, order_idx):
    """A short line for the new playlist's description, e.g. "Flow · Smooth · calm → intense → calm"."""
    if not order_idx:
        return ""
    e = [feats[i]["energy"] for i in order_idx]
    third = max(1, len(e) // 3)
    word = lambda v: "calm" if v < 0.38 else "intense" if v > 0.62 else "steady"
    parts = [word(sum(e[:third]) / third), word(sum(e[third:2 * third]) / max(1, len(e[third:2 * third]))),
             word(sum(e[2 * third:]) / max(1, len(e[2 * third:])))]
    flat = [p for k, p in enumerate(parts) if k == 0 or p != parts[k - 1]]
    return " → ".join(flat)


MODE_NAMES = {"wind_down": "Energetic → Easing down → Calm", "build": "Calm → Ramping up → Energetic",
              "mix": "Mixed energies throughout", "waves": "Waves", "smooth": "Smooth", "genre": "Grouped by genre"}

# What the new playlist is called: "<playlist> · <this>".
SHORT_NAMES = {"wind_down": "Energetic to calm", "build": "Calm to energetic", "mix": "Mixed energies",
               "waves": "Waves", "smooth": "Smooth", "genre": "By genre"}

# The three shown in Sort by energy (the others stay available to the code and tests).
SHOWN = ("wind_down", "build", "mix")

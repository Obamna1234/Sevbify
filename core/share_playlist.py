"""Collaborative playlists and Blend, without any server.

A playlist (or a "taste" for Blend) is packed into a link or a small file that you send however you like
(message, email, AirDrop, USB stick, or over pairing). Nothing is uploaded anywhere: the link *is* the playlist.

    sevbify://playlist#v1.<compressed data>        a playlist (open it to add it, or merge it into yours)
    sevbify://taste#v1.<compressed data>           someone's taste, for a Blend with yours
    "<name>.sevbify"                               the same, as a file (readable JSON)

What's inside: only the playlist's name and each song's artist, title, album, length and its public page link.
No account, name, device or listening history (a taste holds just top artists and songs, no dates).

Reading one is strict, because anyone can send you a link: size limits before and after unpacking (no "zip
bombs"), only plain text fields with length limits, song links only https on the music sites Sevbify already uses,
control and invisible characters removed, at most 5000 songs. Anything else is dropped. Nothing happens on its
own: the app shows what's in it first, and nothing plays, downloads or opens a website until you choose to.
"""
import base64
import json
import re
import unicodedata
import urllib.parse
import zlib

MAX_LINK = 400_000            # characters
MAX_UNPACKED = 3_000_000      # bytes after unpacking
MAX_SONGS = 5000
MAX_TASTE = 100
SITES = ("open.spotify.com", "bandcamp.com", "soundcloud.com", "youtube.com", "music.youtube.com", "youtu.be",
         "deezer.com", "music.apple.com", "jamendo.com", "archive.org")


class ShareError(Exception):
    pass


def clean_text(s, limit):
    """Plain, visible text: NFC, no control / format (invisible, right-to-left override) characters."""
    s = unicodedata.normalize("NFC", str(s or ""))
    s = "".join(ch for ch in s if unicodedata.category(ch) not in ("Cc", "Cf", "Co", "Cs") or ch == " ")
    # Never markup: a "<b>" or "&lt;" in a friend's playlist name stays plain text wherever it's shown.
    s = re.sub(r"<(?=[A-Za-z/!?])", "\u2039", s).replace("&", "\uff06") if re.search(r"<[A-Za-z/!?]|&[#A-Za-z0-9]+;", s) else s
    return " ".join(s.split())[:limit]


def safe_page(url):
    url = str(url or "").strip()
    if len(url) > 400 or not url.startswith("https://"):
        return ""
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return ""
    host = (u.hostname or "").lower()
    if u.username or u.password or u.port not in (None, 443):
        return ""
    if not any(host == s or host.endswith("." + s) for s in SITES):
        return ""
    return url


def _song(d):
    if not isinstance(d, dict):
        return None
    title = clean_text(d.get("title"), 300)
    artist = clean_text(d.get("artist"), 200)
    if not title:
        return None
    try:
        ms = max(0, min(int(d.get("duration_ms") or 0), 6 * 3600 * 1000))
    except (TypeError, ValueError):
        ms = 0
    source = clean_text(d.get("source"), 20).lower()
    return {"title": title, "artist": artist, "album": clean_text(d.get("album"), 200), "duration_ms": ms,
            "source": source if re.fullmatch(r"[a-z]{0,20}", source) else "", "page_url": safe_page(d.get("page_url"))}


# --- packing ------------------------------------------------------------------------------------------------
def _pack(obj):
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "v1." + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")


def _unpack(data):
    data = (data or "").strip()
    if len(data) > MAX_LINK:
        raise ShareError("That link is too long to be a Sevbify playlist.")
    if not data.startswith("v1."):
        raise ShareError("That isn't a Sevbify link (or it's from a newer Sevbify).")
    body = data[3:]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", body or "-"):
        raise ShareError("That link is damaged (it may have been cut short when it was sent).")
    try:
        packed = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        z = zlib.decompressobj()
        raw = z.decompress(packed, MAX_UNPACKED + 1)
        if len(raw) > MAX_UNPACKED or z.unconsumed_tail:
            raise ShareError("That link unpacks to far more than any playlist; it was ignored.")
        obj = json.loads(raw.decode("utf-8"))
    except ShareError:
        raise
    except Exception:
        raise ShareError("That link is damaged (it may have been cut short when it was sent).")
    if not isinstance(obj, dict):
        raise ShareError("That isn't a Sevbify playlist.")
    return obj


def playlist_link(name, songs, description=""):
    """A sevbify://playlist link holding this playlist (songs: dicts or objects with artist/title/...)."""
    items = []
    for s in list(songs)[:MAX_SONGS]:
        t = getattr(s, "track", s)
        get = (lambda k, d="": s.get(k, d)) if isinstance(s, dict) else (lambda k, d="": getattr(t, k, getattr(s, k, d)))
        song = _song({"title": get("title"), "artist": get("artist"), "album": get("album"),
                      "duration_ms": get("duration_ms", 0), "source": get("source"), "page_url": get("page_url")})
        if song:
            items.append({k: v for k, v in song.items() if v})
    return "sevbify://playlist#" + _pack({"type": "playlist", "name": clean_text(name, 100) or "Shared playlist",
                                          "description": clean_text(description, 300), "songs": items})


def playlist_file_text(name, songs, description=""):
    """The same as a small readable file (.sevbify)."""
    obj = _unpack(playlist_link(name, songs, description).split("#", 1)[1])
    return json.dumps({"sevbify": 1, **obj}, ensure_ascii=False, indent=1)


def read(text):
    """Read a shared link, or a .sevbify file's text. Returns {"type": "playlist"|"taste", ...} cleaned."""
    text = (text or "").strip()
    if len(text) > MAX_UNPACKED:
        raise ShareError("That's too big to be a Sevbify playlist.")
    m = re.search(r"sevbify://(playlist|taste)#(v1\.[A-Za-z0-9_-]+)", text)
    if m:
        obj = _unpack(m.group(2))
        kind = m.group(1)
    elif text.startswith("{"):
        try:
            obj = json.loads(text)
        except (ValueError, RecursionError):
            raise ShareError("That file isn't a Sevbify playlist.")
        if not isinstance(obj, dict) or obj.get("sevbify") != 1:
            raise ShareError("That file isn't a Sevbify playlist.")
        kind = obj.get("type")
    else:
        raise ShareError("That isn't a Sevbify playlist link or file.")
    if kind != obj.get("type") or kind not in ("playlist", "taste"):
        raise ShareError("That isn't a Sevbify playlist.")
    if kind == "playlist":
        raw = obj.get("songs")
        songs = [s for s in (_song(x) for x in (raw if isinstance(raw, list) else [])[:MAX_SONGS]) if s]
        return {"type": "playlist", "name": clean_text(obj.get("name"), 100) or "Shared playlist",
                "description": clean_text(obj.get("description"), 300), "songs": songs}
    artists = [clean_text(a, 200) for a in (obj.get("artists") if isinstance(obj.get("artists"), list) else [])][:MAX_TASTE]
    songs = [s for s in (_song(x) for x in (obj.get("songs") if isinstance(obj.get("songs"), list) else [])[:MAX_TASTE]) if s]
    return {"type": "taste", "name": clean_text(obj.get("name"), 40) or "A friend",
            "artists": [a for a in artists if a], "songs": songs}


# --- merging (collaborative playlists) ----------------------------------------------------------------------
def _key(artist, title):
    return " ".join(re.findall(r"\w+", (artist or "").casefold())) + "|" + " ".join(re.findall(r"\w+", (title or "").casefold()))


def merge(mine, theirs):
    """What merging their copy into yours would do: {"add": [their songs you don't have, in their order],
    "missing": [your songs their copy doesn't have], "same": n}. Nothing of yours is removed unless you choose."""
    have = {_key(getattr(s, "artist", ""), getattr(s, "title", "")) for s in mine}
    theirs_keys, added = set(), set()
    add = []
    for s in theirs:
        k = _key(s.get("artist"), s.get("title"))
        theirs_keys.add(k)
        if k not in have and k not in added:
            added.add(k)
            add.append(s)
    missing = [s for s in mine if _key(getattr(s, "artist", ""), getattr(s, "title", "")) not in theirs_keys]
    return {"add": add, "missing": missing, "same": len(theirs) - len(add)}


# --- Blend ----------------------------------------------------------------------------------------------------
def taste_link(listens, nickname=""):
    """Your taste for a Blend: your top artists and songs from your listening (no dates, nothing else)."""
    from collections import Counter
    songs, artists = Counter(), Counter()
    first = {}
    for row in listens:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        artist, title = clean_text(row[0], 200), clean_text(row[1], 300)
        if not title:
            continue
        k = _key(artist, title)
        songs[k] += 1
        artists[artist] += 1
        first.setdefault(k, (artist, title))
    top = [{"artist": first[k][0], "title": first[k][1]} for k, _n in songs.most_common(50)]
    return "sevbify://taste#" + _pack({"type": "taste", "name": clean_text(nickname, 40) or "A friend",
                                       "artists": [a for a, _n in artists.most_common(30) if a], "songs": top})


def blend(my_listens, their_taste, size=50):
    """A Blend playlist: songs you both like first, then your favourites and theirs taken in turn."""
    import itertools
    mine = read(taste_link(my_listens))
    theirs = their_taste
    my_keys = {_key(s["artist"], s["title"]) for s in mine["songs"]}
    their_keys = {_key(s["artist"], s["title"]) for s in theirs["songs"]}
    both = [s for s in mine["songs"] if _key(s["artist"], s["title"]) in their_keys]
    shared_artists = {a.casefold() for a in mine["artists"]} & {a.casefold() for a in theirs["artists"]}
    mine_rest = [s for s in mine["songs"] if _key(s["artist"], s["title"]) not in their_keys]
    their_rest = [s for s in theirs["songs"] if _key(s["artist"], s["title"]) not in my_keys]
    mine_rest.sort(key=lambda s: s["artist"].casefold() not in shared_artists)
    their_rest.sort(key=lambda s: s["artist"].casefold() not in shared_artists)
    out, seen = [], set()
    for s in both + [x for pair in itertools.zip_longest(mine_rest, their_rest) for x in pair if x]:
        k = _key(s["artist"], s["title"])
        if k not in seen:
            seen.add(k)
            out.append(s)
        if len(out) >= size:
            break
    return {"name": f"You + {theirs['name']}", "songs": out, "together": len(both),
            "shared_artists": sorted(shared_artists)}

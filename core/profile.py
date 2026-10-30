"""Your Sevbify profile in one small file (".sevbify"), the same on Windows, macOS, Linux, Android and iPhone.

What's in it: playlists (with their folders, pins and where they came from), followed podcasts and YouTube
channels, saved audiobooks, where you stopped in episodes and chapters, recently played, recent searches and
the settings that mean the same on every device. Songs are kept as their names (title, artist, album, length,
cover link, where they stream from), never as files, so a profile made on one device works on another: songs you
have there play from your files, the rest stream while online.

It's a compressed JSON file that only ever exists where you save it. Sevbify never uploads it anywhere.
"""
import base64
import gzip
import json
import time

FORMAT = "sevbify-profile"
VERSION = 1
EXTENSION = ".sevbify"
MAX_BYTES = 20 * 1024 * 1024            # a profile is normally a few hundred KB; refuse anything silly

# Settings that mean the same everywhere (each app keeps its own name for them).
SETTINGS = ("online", "stream_full", "explicit_ok", "autoplay", "song_quality", "show_playlist_origin",
            "skip_sponsors", "lyrics", "shuffle", "repeat")

TRACK_FIELDS = ("title", "artist", "album", "duration_ms", "cover_url", "preview_url", "stream_url", "download_url",
                "source", "source_id", "page_url", "genre", "explicit", "key", "file")


class ProfileError(Exception):
    """Something the user should see, e.g. "That isn't a Sevbify profile"."""


def clean_track(d):
    """Only the song's description (never local paths or anything about the device)."""
    if not isinstance(d, dict):
        return None
    out = {k: d[k] for k in TRACK_FIELDS if k in d and d[k] not in ("", None, 0, False)}
    if not out.get("title"):
        return None
    out.setdefault("artist", "")
    return out


def normalise(data):
    """A profile dict with only known, well-formed parts (used both when saving and loading)."""
    if not isinstance(data, dict):
        raise ProfileError("That isn't a Sevbify profile.")
    out = {"format": FORMAT, "version": VERSION, "saved": data.get("saved") or int(time.time()),
           "from": str(data.get("from") or "")[:20]}
    pls = []
    for p in data.get("playlists") or []:
        if not isinstance(p, dict) or not str(p.get("name") or "").strip():
            continue
        pls.append({"name": str(p["name"]).strip()[:200], "folder": str(p.get("folder") or "")[:200],
                    "pinned": bool(p.get("pinned")), "origin": str(p.get("origin") or "")[:20],
                    "cover_url": str(p.get("cover_url") or ""), "created": p.get("created") or 0,
                    "tracks": [t for t in (clean_track(x) for x in p.get("tracks") or []) if t]})
    out["playlists"] = pls
    out["folders"] = [str(f)[:200] for f in data.get("folders") or [] if str(f).strip()]
    out["shows"] = [_with_key(s, "show") for s in data.get("shows") or []
                    if isinstance(s, dict) and (s.get("feed_url") or s.get("apple_id"))]
    out["books"] = [_with_key(b, "book") for b in data.get("books") or [] if isinstance(b, dict) and b.get("identifier")]
    out["resume"] = {str(k): int(v) for k, v in (data.get("resume") or {}).items()
                     if isinstance(v, (int, float)) and v > 0}
    out["recent"] = [t for t in (clean_track(x) for x in data.get("recent") or []) if t][:50]
    out["searches"] = [str(q)[:200] for q in data.get("searches") or [] if str(q).strip()][:30]
    out["settings"] = {k: v for k, v in (data.get("settings") or {}).items()
                       if k in SETTINGS and isinstance(v, (bool, int, str))}
    return out


def _with_key(d, kind):
    """A followed show / saved book as every app stores it (its own fields plus "key", and a book's cover)."""
    try:
        if kind == "book":
            from core.audiobooks import Book
            b = Book.from_dict(d)
            out = b.to_dict()
            out.update(key=b.key, cover_url=b.cover_url)
        else:
            from core.podcasts import Show
            s = Show.from_dict(d)
            out = s.to_dict()
            out["key"] = s.key
        return out
    except Exception:
        return dict(d)


def pack(data):
    """The file's bytes."""
    text = json.dumps(normalise(data), ensure_ascii=False, separators=(",", ":"))
    return gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0)


def unpack(raw):
    if not raw:
        raise ProfileError("The file is empty.")
    if len(raw) > MAX_BYTES:
        raise ProfileError("That file is too big to be a Sevbify profile.")
    try:
        text = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
        if len(text) > MAX_BYTES * 10:
            raise ProfileError("That file is too big to be a Sevbify profile.")
        data = json.loads(text.decode("utf-8-sig"))
    except (OSError, ValueError, EOFError):
        raise ProfileError("That isn't a Sevbify profile.")
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProfileError("That isn't a Sevbify profile.")
    if int(data.get("version") or 0) > VERSION:
        raise ProfileError("This profile was saved by a newer Sevbify: update Sevbify first.")
    return normalise(data)


def pack_b64(json_text):
    """For the phone apps (Kotlin / Swift write the bytes themselves)."""
    return base64.b64encode(pack(json.loads(json_text))).decode("ascii")


def unpack_b64(b64):
    return unpack(base64.b64decode(b64))


def save(path, data):
    with open(path, "wb") as f:
        f.write(pack(data))


def load(path):
    with open(path, "rb") as f:
        return unpack(f.read(MAX_BYTES + 1))


def merge_names(existing, wanted):
    """A playlist name that doesn't clash: "Road trip" → "Road trip (imported)", "… (imported 2)"."""
    taken = {n.casefold() for n in existing}
    if wanted.casefold() not in taken:
        return wanted
    n, name = 1, f"{wanted} (imported)"
    while name.casefold() in taken:
        n += 1
        name = f"{wanted} (imported {n})"
    return name


def same_playlist(a_tracks, b_tracks):
    """True when two playlists hold the same songs in the same order (importing twice adds nothing)."""
    def keys(ts):
        return [(str(t.get("artist", "")).casefold(), str(t.get("title", "")).casefold()) for t in ts]
    return keys(a_tracks) == keys(b_tracks)

"""Song credits (writers, producers, performers), like Spotify's "View credits", from MusicBrainz, the open music
encyclopedia. Only the song's title and artist are sent; nothing about you. Cached for a week.

Returns [{"name": str, "roles": [str, ...]}], main artist first, at most 12 people. [] when MusicBrainz doesn't
know the song (nothing is ever guessed).
"""
import re

MB = "https://musicbrainz.org/ws/2/"
WEEK = 7 * 24 * 3600
ROLE_NAMES = {"composer": "Composer", "lyricist": "Lyricist", "writer": "Writer", "producer": "Producer",
              "mix": "Mixing engineer", "mastering": "Mastering engineer", "recording": "Recording engineer",
              "engineer": "Engineer", "arranger": "Arranger", "vocal": "Vocals", "instrument": "Musician",
              "performer": "Performer", "remixer": "Remixer", "conductor": "Conductor", "orchestrator": "Orchestrator"}
_cache = {}


def _norm(s):
    return " ".join(re.findall(r"\w+", (s or "").casefold()))


def _recording(net, artist, title):
    data = net.get_json(MB + "recording", {"query": f'recording:"{title}" AND artist:"{artist}"', "fmt": "json",
                                           "limit": 10}, ttl=WEEK)
    for rec in data.get("recordings") or []:
        if _norm(rec.get("title")) != _norm(title):
            continue
        names = [_norm((c.get("artist") or {}).get("name")) for c in rec.get("artist-credit") or []]
        if _norm(artist) in names or _norm(artist) == _norm(" ".join(n for n in names)):
            return rec
    return None


def for_song(net, artist, title):
    if not artist or not title or artist == "Unknown Artist":
        return []
    key = (_norm(artist), _norm(title))
    if key in _cache:
        return _cache[key]
    people = {}

    def add(name, role):
        name = str(name or "").strip()[:120]
        if not name:
            return
        roles = people.setdefault(name, [])
        if role and role not in roles:
            roles.append(role)

    rec = _recording(net, artist, title)
    if rec is not None:
        for c in rec.get("artist-credit") or []:
            add((c.get("artist") or {}).get("name"), "Main artist")
        full = net.get_json(MB + "recording/" + rec["id"], {"inc": "artist-rels+work-rels", "fmt": "json"}, ttl=WEEK)
        for r in full.get("relations") or []:
            if r.get("target-type") == "artist":
                add((r.get("artist") or {}).get("name"), ROLE_NAMES.get(r.get("type", ""), ""))
            elif r.get("target-type") == "work" and (r.get("work") or {}).get("id"):
                work = net.get_json(MB + "work/" + r["work"]["id"], {"inc": "artist-rels", "fmt": "json"}, ttl=WEEK)
                for w in work.get("relations") or []:
                    if w.get("target-type") == "artist":
                        add((w.get("artist") or {}).get("name"), ROLE_NAMES.get(w.get("type", ""), ""))
                break                                          # one work is enough (covers have many)
    out = [{"name": n, "roles": [r for r in roles if r] or ["Credited"]} for n, roles in people.items()][:12]
    _cache[key] = out
    return out

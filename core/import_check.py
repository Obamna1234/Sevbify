"""Checking an imported playlist file before you stream or download it.

A file is just text ("Artist - Title" per line, or a CSV), so a typo there means the full song can't be found.
Each song is looked up once (Deezer, then a spelling suggestion); what's found gets its cover, album and length, and
what isn't comes back with the closest match so the app can ask "Did you mean …?" for each one.
"""
import difflib

from core.models import fold
from core.online import spelling
from core.online.models import OnlineTrack
from core.online.net import OfflineError, OnlineDisabled
from core.online.providers import _fill, same_song

OK, SUGGEST, MISSING = "ok", "suggest", "missing"


def as_text(track):
    return f"{track.artist} - {track.title}" if track.artist else track.title


def _similar(a, b):
    return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio()


def _matches(track, found):
    if track.artist:
        return found.key == track.key or same_song(track, found)
    return fold(found.title) == fold(track.title)


def check_song(music, net, track):
    """{"status": ok / suggest / missing, "track": the song (filled in when found), "suggestion": OnlineTrack or None}."""
    try:
        candidates = music.deezer.find_tracks(track.artist, track.title)
    except (OfflineError, OnlineDisabled):
        raise                                   # offline: nothing can be checked, so nothing is "missing"
    except Exception:
        candidates = []
    for found in candidates:
        if _matches(track, found):
            return {"status": OK, "track": _fill(track, found) if track.source not in ("", "deezer") else
                    _keep_name(track, found), "suggestion": None}
    text = as_text(track)
    # A typo: the closest song Deezer has for the words as written…
    best, score = None, 0.0
    try:
        pool = list(candidates) + music.deezer.search(text, 8)
    except Exception:
        pool = list(candidates)
    for c in pool:
        s = _similar(text, as_text(c) if track.artist else c.title)
        if s > score:
            best, score = c, s
    if best is not None and score >= 0.72:
        return {"status": SUGGEST, "track": track, "suggestion": best}
    # …or what a search engine thinks was meant ("fin vs hustory" → "fin vs history").
    try:
        for s in spelling.suggestions(net, text)[:2]:
            found = music.deezer.search(s, 3)
            if found and not spelling.looks_wrong(s, found):
                return {"status": SUGGEST, "track": track, "suggestion": found[0]}
    except Exception:
        pass
    if best is not None and score >= 0.5:
        return {"status": SUGGEST, "track": track, "suggestion": best}
    return {"status": MISSING, "track": track, "suggestion": None}


def _keep_name(track, found):
    """A plain imported line found on Deezer: use Deezer's details but keep the song as the file named it."""
    found.title, found.artist = found.title or track.title, found.artist or track.artist
    return found


def check_tracks(music, net, tracks, progress=None, should_stop=lambda: False):
    """check_song for each song, in order. progress(done, total) after each one."""
    out = []
    for i, t in enumerate(tracks):
        if should_stop():
            break
        out.append(check_song(music, net, t))
        if progress:
            progress(i + 1, len(tracks))
    return out


def corrected(track, text):
    """The song with the name you typed in the review ("Artist - Title")."""
    from core.importers import split_line
    artist, title = split_line(text)
    t = OnlineTrack(title=title, artist=artist)
    t.page_url = ""
    return t

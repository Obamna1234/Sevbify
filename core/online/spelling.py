""""Did you mean …?" for searches that found nothing close (a typo like "fin vs hustory").

Only when the results look wrong is the finished search (never each key press) sent to DuckDuckGo's suggestion
service, which keeps no history and sets no cookies. Nothing else goes with it: no account, no other searches.
Works in any language: words are compared with Unicode-aware matching, so Cyrillic, Arabic, CJK etc. all count.
"""
import re
import unicodedata

SUGGEST_URL = "https://duckduckgo.com/ac/"
_NOISE = ("lyrics", "song", "songs", "spotify", "youtube", "mp3", "official video", "official audio", "letra",
          "paroles", "testo", "songtext", "lyric", "chords", "karaoke", "remix")


def _norm(text):
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"\w+", text))


def _words(text):
    return set(_norm(text).split())


def _chars(text):
    """Scripts without spaces (Chinese, Japanese, Thai) are compared character by character."""
    return set(_norm(text).replace(" ", ""))


def looks_wrong(query, tracks, top=5):
    """True when none of the first results share (most of) the search's words."""
    want = _words(query)
    if not want:
        return False
    if not tracks:
        return True
    spaced = len(want) > 1 or len(_norm(query)) <= 12
    best = 0.0
    for t in tracks[:top]:
        hay = f"{getattr(t, 'title', '')} {getattr(t, 'artist', '')} {getattr(t, 'album', '')}"
        if spaced:
            got = len(want & _words(hay)) / len(want)
        else:
            q = _chars(query)
            got = len(q & _chars(hay)) / max(1, len(q))
        best = max(best, got)
    return best < 0.6


def _clean(s):
    s = (s or "").strip()
    low = s.casefold()
    for n in _NOISE:
        if low.endswith(" " + n):
            s = s[: -len(n) - 1].strip()
            low = s.casefold()
    return s


def suggestions(net, query):
    """DuckDuckGo's spelling-corrected suggestions for a finished search (cached a week)."""
    data = net.get_json(SUGGEST_URL, {"q": query.strip(), "type": "list"}, ttl=7 * 24 * 3600)
    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
        raw = data[1]
    elif isinstance(data, list):
        raw = [d.get("phrase", "") for d in data if isinstance(d, dict)]
    else:
        raw = []
    out = []
    for s in raw:
        s = _clean(str(s))
        if s and _norm(s) != _norm(query) and s not in out:
            out.append(s)
    return out[:5]


def did_you_mean(net, music, query, tracks=None):
    """A better spelling of `query` when its results look wrong, else "". `tracks` are its results if known."""
    query = (query or "").strip()
    if len(query) < 3 or len(query) > 120:
        return ""
    if tracks is None:
        tracks = music.search(query, 10)
    if not looks_wrong(query, tracks):
        return ""
    try:
        options = suggestions(net, query)
    except Exception:
        return ""
    # Prefer a suggestion that actually finds music.
    for s in options[:3]:
        try:
            found = music.search(s, 5)
        except Exception:
            continue
        if found and not looks_wrong(s, found):
            return s
    return ""

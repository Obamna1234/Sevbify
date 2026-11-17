"""The in-app "this source isn't working" note.

Sevbify reads YouTube, Spotify's public pages, Deezer, SoundCloud and Apple's podcast directory the way a browser
does. When one of them changes something, Sevbify's way of reading it can stop working until an update fixes it.
Rather than leaving you with a string of puzzling errors, after a few failures from the same source in a short
time the error says so plainly and points to Check for updates. Counted on this device only; nothing is sent.
"""
import threading
import time

WINDOW = 30 * 60          # seconds
THRESHOLD = 3             # failures from one source within WINDOW
_lock = threading.Lock()
_fails = {}               # source -> [times]

_SOURCES = (
    ("YouTube", ("youtube", "googlevideo", "yt-dlp", "ytimg", "not a bot")),
    ("Spotify", ("spotify",)),
    ("Deezer", ("deezer",)),
    ("SoundCloud", ("soundcloud", "sndcdn")),
    ("Apple Podcasts", ("itunes.apple", "podcasts.apple", "apple.com")),
    ("Bandcamp", ("bandcamp",)),
)
# Failures that are about your connection, not the source: never counted.
_NOT_THE_SOURCE = ("offline", "no internet", "network is unreachable", "timed out", "name or service not known",
                   "getaddrinfo", "temporary failure in name resolution", "connection reset", "turned off")


def source_of(text):
    t = (text or "").lower()
    if any(n in t for n in _NOT_THE_SOURCE):
        return ""
    for name, needles in _SOURCES:
        if any(n in t for n in needles):
            return name
    return ""


def note(source):
    return (f"{source} doesn't seem to be working with Sevbify right now. It may have changed something on its "
            f"side; an update usually fixes this within days (Settings → About → Check for updates).")


def failed(text, now=None):
    """Record a failure. Returns the note if this source keeps failing, else ""."""
    source = source_of(text)
    if not source:
        return ""
    now = now or time.time()
    with _lock:
        times = [t for t in _fails.get(source, []) if now - t < WINDOW] + [now]
        _fails[source] = times[-20:]
        return note(source) if len(times) >= THRESHOLD else ""


def worked(text_or_source):
    """A source worked again: forget its failures."""
    source = source_of(text_or_source) or text_or_source
    with _lock:
        _fails.pop(source, None)


def reset():
    with _lock:
        _fails.clear()

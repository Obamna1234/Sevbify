"""When YouTube or SoundCloud stop working: check for a fix straight away, and say what's happening.

Both are read through yt-dlp, which every copy of Sevbify already updates weekly (checksum-checked). When one of
them keeps failing while you use it (core/source_status.py: a few failures in a short time, not your connection),
Sevbify doesn't wait for the weekly check: it looks for a newer yt-dlp now, at most once every 6 hours, and then
tells you plainly either that a fix was downloaded (restart to use it) or that you already have the newest one
(the site probably changed something; an update to Sevbify usually follows within days).
"""
import threading
import time

SOURCES = ("YouTube", "SoundCloud")
STILL_WORKS = ("Sevbify still works: your own music files and downloaded songs play as normal, and so do songs "
               "from Bandcamp.")
EVERY = 6 * 3600

_lock = threading.Lock()
_last = float("-inf")
_thread = None
_result = None


def start_if_due(source, update=None, now=None):
    """Start checking for a newer yt-dlp in the background if `source` is YouTube or SoundCloud and it hasn't been
    checked in the last 6 hours. True if a check was started (then wait() gives what to tell you)."""
    global _last, _thread, _result
    if source not in SOURCES:
        return False
    now = now or time.time()
    with _lock:
        if (_thread is not None and _thread.is_alive()) or now - _last < EVERY:
            return False
        _last = now
        _result = None

        def run():
            global _result
            try:
                if update is None:
                    from core import updates
                    changed, message = updates.update_ytdlp()
                else:
                    changed, message = update()
            except Exception as err:                    # noqa: BLE001 (any failure: say we couldn't check)
                changed, message = False, f"Couldn't check ({err})"
            _result = explain(source, bool(changed), str(message))

        _thread = threading.Thread(target=run, name="sevbify-engine-fix", daemon=True)
        _thread.start()
        return True


def wait(timeout=120):
    """What to tell you once the check started by start_if_due has finished: {"title", "text", "fixed",
    "source"}; None if it's still going after `timeout` seconds or none was started."""
    t = _thread
    if t is not None:
        t.join(timeout)
    return _result


def explain(source, changed, message):
    if changed:
        return {"source": source, "fixed": True, "title": f"A fix for {source} is ready",
                "text": f"{source} stopped working in Sevbify, so Sevbify checked for a fix straight away. A newer "
                        f"yt-dlp (the part of Sevbify that plays {source}) has been downloaded. Restart Sevbify to "
                        "use it.\n\n" + STILL_WORKS}
    if "newest" in message:
        return {"source": source, "fixed": False, "title": f"{source} isn't working right now",
                "text": f"{source} seems to have changed something on its side. Sevbify already has the newest "
                        f"yt-dlp (the part that plays {source}), so there's no fix to download yet. An update to "
                        "Sevbify usually fixes this within days (Settings → About → Check for updates).\n\n"
                        + STILL_WORKS}
    return {"source": source, "fixed": False, "title": f"{source} isn't working right now",
            "text": f"{source} stopped working in Sevbify, and Sevbify couldn't check for a fix just now (GitHub "
                    "couldn't be reached). Try Settings → About → Update yt-dlp later.\n\n" + STILL_WORKS}


def reset():
    """For tests."""
    global _last, _thread, _result
    with _lock:
        _last, _thread, _result = float("-inf"), None, None

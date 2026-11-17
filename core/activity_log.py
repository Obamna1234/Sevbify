"""Sevbify's activity log: a plain-text diary of what the app did, so a problem can be traced afterwards.

Help → "Show activity log" opens it; Help → "Save a problem report…" makes a copy to send. It's only on this
computer (<data folder>/activity.log, at most ~3 MB: two older files are kept and the oldest dropped), nothing
is sent anywhere. Lines look like:

    2026-11-15 02:14:07  play      Jet Pack - Cassetter (playlist "I'm the Law Radio")
    2026-11-15 02:14:11  stream    found on YouTube in 3.8 s (search 2.1, link 1.7)
    2026-11-15 02:14:12  error     VLC couldn't open the stream -> trying a fresh link

Web addresses are shortened to their site (no sign-ins or long links), email addresses are replaced with
[email], and music-server passwords never appear.
"""
import os
import re
import threading
import time

MAX_BYTES = 1_000_000
KEEP = 2
_lock = threading.Lock()
_path = [""]

_URL = re.compile(r"([a-z][a-z0-9+.-]*)://[^\s\"')]+", re.I)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_private = [False]
# While Private Session is on, these say what was played/searched, so only the kind of event is kept.
PRIVATE_KINDS = {"play", "stream", "retry", "skip", "status", "player", "podcast", "download", "online", "error",
                 "radio"}


def set_private(on):
    _private[0] = bool(on)


def start(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    _path[0] = os.path.join(data_dir, "activity.log")
    import platform
    import sys
    from core.version import app_version
    log("start", f"Sevbify {app_version()} on {platform.system()} {platform.release()} "
                 f"({platform.machine()}), Python {sys.version.split()[0]}")
    return _path[0]


def path():
    return _path[0]


def _short(text):
    """Links → just their site, e.g. https://rr3---sn-x.googlevideo.com/... → [googlevideo.com link]."""
    def site(m):
        if m.group(1).lower() == "file":
            return "[file]"
        from urllib.parse import urlsplit
        try:
            host = urlsplit(m.group(0)).hostname or ""
        except ValueError:
            host = ""
        parts = host.split(".")
        return f"[{'.'.join(parts[-2:]) if len(parts) >= 2 else host} link]"
    return _EMAIL.sub("[email]", _URL.sub(site, str(text)))          # never an email address


def log(kind, text):
    if not _path[0]:
        return
    if _private[0] and kind in PRIVATE_KINDS:
        text = "(Private Session: details not kept)"
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {kind:<9} {_short(text)}".replace("\n", " | ")[:2000] + "\n"
    with _lock:
        try:
            if os.path.exists(_path[0]) and os.path.getsize(_path[0]) > MAX_BYTES:
                for i in range(KEEP, 0, -1):
                    src = _path[0] if i == 1 else f"{_path[0]}.{i - 1}"
                    if os.path.exists(src):
                        os.replace(src, f"{_path[0]}.{i}")
            fd = os.open(_path[0], os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass


def report(dest):
    """One file with the activity log (older parts first) and the error log, to send when something goes wrong."""
    base = _path[0]
    folder = os.path.dirname(base)
    parts = [f"{base}.{i}" for i in range(KEEP, 0, -1)] + [base, os.path.join(folder, "error.log")]
    home = os.path.expanduser("~")
    user = os.path.basename(home.rstrip("\\/")) if home else ""
    import re as _re
    forms = {home, home.replace("\\", "/"), home.replace("/", "\\")} if home and home not in ("/", "~") else set()

    def tidy(text):
        text = _short(text)
        for f in sorted(forms, key=len, reverse=True):            # any case, either slash
            text = _re.sub(_re.escape(f), "~", text, flags=_re.IGNORECASE)
        if user and len(user) >= 3 and user.lower() not in ("root", "user", "admin", "home", "users"):
            text = _re.sub(r"(?i)(?<![A-Za-z0-9])" + _re.escape(user) + r"(?![A-Za-z0-9])", "<user>", text)
        return text
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        for p in parts:
            if os.path.exists(p):
                out.write(f"===== {os.path.basename(p)} =====\n")
                with open(p, encoding="utf-8", errors="replace") as f:
                    out.write(tidy(f.read()))
                out.write("\n")
    return dest

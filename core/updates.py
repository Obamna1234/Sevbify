"""Checking for updates (no UI code).

- yt-dlp: YouTube changes often and an old yt-dlp is the usual reason full songs or downloads stop working. The
  newest official yt-dlp release (github.com/yt-dlp/yt-dlp) is downloaded with SEVBY's updater into
  ~/.sevby_ytdlp (shared with SEVBY) and used from the next start.
- Sevbify: the newest release on Sevbify's GitHub page. While the project is private, GitHub doesn't answer
  this for other people, and the check says so.
Only GitHub is contacted, and only when online features are on.
"""
from core import downloader
from core.version import app_version

RELEASES_API = "https://api.github.com/repos/Obamna1234/Sevbify/releases"
RELEASES_PAGE = "https://github.com/Obamna1234/Sevbify/releases"


def ytdlp_version():
    return downloader.engine().ytdlp_version()


def ytdlp_age_days():
    return downloader.engine().ytdlp_age_days()


def check_ytdlp(latest_tag=None):
    """{"current", "latest", "newer"}; latest is None when GitHub couldn't be reached."""
    e = downloader.engine()
    current = e.ytdlp_version()
    latest = latest_tag if latest_tag is not None else e.ytdlp_latest_tag()
    newer = bool(latest) and e.ver_tuple(latest) > e.ver_tuple(current)
    return {"current": current, "latest": latest, "newer": newer}


def _get(url, timeout=60):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Sevbify"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download_verified_ytdlp(tag, fetch=None, dest_dir=None):
    """Download the official yt-dlp release file and check it against the SHA-256 that yt-dlp publishes with
    the release (SHA2-256SUMS) before it's ever used. A file that doesn't match is thrown away.
    Returns (ok, message)."""
    import hashlib
    import os
    import re
    fetch = fetch or _get
    if not re.fullmatch(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?", tag or ""):
        return False, "GitHub gave an unexpected yt-dlp version name."
    base = f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/"
    try:
        sums = fetch(base + "SHA2-256SUMS").decode("utf-8", "replace")
        expected = next((line.split()[0].lower() for line in sums.splitlines()
                         if line.split()[-1:] == ["yt-dlp"]), "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            return False, "Couldn't find yt-dlp's checksum, so the update wasn't installed."
        data = fetch(base + "yt-dlp")
    except Exception as e:
        return False, f"Couldn't download the update ({e})."
    if hashlib.sha256(data).hexdigest() != expected:
        return False, "The downloaded yt-dlp didn't match its official checksum, so it was thrown away."
    e = downloader.engine()
    folder = dest_dir or str(e.YTDLP_UPDATE_DIR)
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, "yt-dlp.part")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, os.path.join(folder, "yt-dlp"))
    return True, "ok"


def update_ytdlp(download=None):
    """Download the newest yt-dlp if it's newer. Returns (changed, message)."""
    info = check_ytdlp()
    if not info["latest"]:
        return False, "Couldn't reach GitHub to check yt-dlp. Try again later."
    if not info["newer"]:
        return False, f"yt-dlp {info['current']} is the newest version."
    ok, msg = (download or download_verified_ytdlp)(info["latest"])
    if not ok:
        return False, msg
    return True, f"yt-dlp {info['latest']} downloaded. Restart Sevbify to use it."


def check_app(net, current=None):
    """{"current", "latest", "newer", "page", "checked", "message"} for Sevbify itself."""
    e = downloader.engine()
    current = current or app_version()
    result = {"current": current, "latest": None, "newer": False, "page": RELEASES_PAGE, "checked": False,
              "message": ""}
    try:
        data = net.get_json(RELEASES_API, {"per_page": 30}, ttl=6 * 3600)
    except Exception as err:
        result["message"] = ("Couldn't check: Sevbify's releases page isn't public yet, or GitHub couldn't be "
                             f"reached ({err}).")
        return result
    result["checked"] = True
    include_pre = "-" in current                      # beta testers also hear about new betas
    best = e.app_pick_release(data, include_pre)
    if not best:
        result["message"] = "No releases found."
        return result
    result.update(latest=best["version"], page=best.get("page") or RELEASES_PAGE,
                  newer=e.app_ver_cmp(best["version"], current) > 0)
    result["message"] = (f"Sevbify {best['version']} is available." if result["newer"]
                         else f"Sevbify {current} is the newest version.")
    return result

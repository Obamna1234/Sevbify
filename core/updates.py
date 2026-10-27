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


def update_ytdlp(download=None):
    """Download the newest yt-dlp if it's newer. Returns (changed, message)."""
    info = check_ytdlp()
    if not info["latest"]:
        return False, "Couldn't reach GitHub to check yt-dlp. Try again later."
    if not info["newer"]:
        return False, f"yt-dlp {info['current']} is the newest version."
    ok, msg = (download or downloader.engine().download_ytdlp_update)(info["latest"])
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

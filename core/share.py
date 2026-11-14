"""Links for sharing a song (no UI code). Sevbify has no accounts, so a shared song is a link to it on Spotify or
YouTube (or a song.link page that opens in whatever app your friend uses).

Nothing is looked up until you press Share. Then, only when online:
- song.link (Odesli) is asked for the song's exact Spotify / YouTube / Apple Music pages, from its Deezer page
  (the song's name only; no account, nothing about you);
- if that service doesn't answer, a YouTube link comes from the video Sevbify already matched for streaming,
  and Spotify gets a search link that opens the song's search results.
"""
import urllib.parse

from core.online.net import OfflineError, ServiceError, is_web_url

ODESLI = "https://api.song.link/v1-alpha.1/links"


def search_links(artist, title):
    q = f"{artist} {title}".strip()
    return {
        "spotify": f"https://open.spotify.com/search/{urllib.parse.quote(q)}",
        "youtube": f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}",
    }


def links(net, artist, title, page_url="", youtube_url=""):
    """{"spotify", "youtube", "songlink", "exact": {"spotify": bool, "youtube": bool}} for a song.
    `page_url` is the song's Deezer page when known; `youtube_url` a YouTube video already matched to it."""
    out = search_links(artist, title)
    out["songlink"] = ""
    exact = {"spotify": False, "youtube": False}
    if is_web_url(youtube_url) and "youtube.com/watch" in youtube_url:
        out["youtube"], exact["youtube"] = youtube_url, True
    if net is not None and is_web_url(page_url) and "deezer.com" in page_url:
        try:
            data = net.get_json(ODESLI, {"url": page_url, "userCountry": "US"}, ttl=30 * 86400)
            by = (data or {}).get("linksByPlatform") or {}
            sp = (by.get("spotify") or {}).get("url", "")
            yt = (by.get("youtube") or by.get("youtubeMusic") or {}).get("url", "")
            if is_web_url(sp):
                out["spotify"], exact["spotify"] = sp, True
            if is_web_url(yt) and not exact["youtube"]:
                out["youtube"], exact["youtube"] = yt, True
            if is_web_url(data.get("pageUrl", "")):
                out["songlink"] = data["pageUrl"]
        except (OfflineError, ServiceError, ValueError, AttributeError):
            pass                       # service retired / busy / offline: the search links still work
    out["exact"] = exact
    return out


def message(artist, title, url):
    """The text that's shared: "Title by Artist" and the link."""
    who = f" by {artist}" if artist and artist != "Unknown Artist" else ""
    return f"{title}{who}\n{url}"

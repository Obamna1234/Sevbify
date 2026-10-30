"""Podcasts: find shows, read their episode lists, and play or download episodes (no UI code).

Where the data comes from (nothing else is contacted):
- Apple's public podcast directory: search (itunes.apple.com/search) and the Top Podcasts chart
  (rss.applemarketingtools.com). No account, no sign-in.
- Each show's own public RSS feed: episodes, artwork, descriptions and the audio files, exactly as the show
  publishes them for every podcast app. Episodes can be streamed and downloaded.
- YouTube channels (video podcasts) through yt-dlp, only when the user adds a channel link.

Episodes become OnlineTrack objects (source "podcast" / "youtube"), so they play in the normal player and queue.
"""
import email.utils
import html
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from core.online.models import OnlineTrack
from core.online.net import is_web_url


def _web(url):
    """Links from a feed are only kept when they're web addresses (never file: or other local links)."""
    return url.strip() if is_web_url(url) else ""

ITUNES_NS = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"
MAX_EPISODES = 300
YOUTUBE_RE = re.compile(r"https?://(?:www\.|m\.)?youtube\.com/(@[\w.\-]+|channel/[\w\-]+|c/[\w\-]+|user/[\w\-]+|playlist\?list=[\w\-]+)", re.I)


@dataclass
class Show:
    title: str
    author: str = ""
    feed_url: str = ""          # RSS feed, or a YouTube channel/playlist URL for kind "youtube"
    image_url: str = ""
    description: str = ""
    apple_id: str = ""          # from the Apple chart: the feed URL is looked up when the show is opened
    genre: str = ""
    kind: str = "podcast"       # "podcast" | "youtube"
    link: str = ""
    verified: bool = False      # YouTube: the channel has YouTube's verified tick
    followers: int = 0          # YouTube: subscribers
    channel: str = ""           # YouTube: the channel that uploads the videos (for playlists too)

    @property
    def key(self):
        return (self.feed_url or f"apple:{self.apple_id}").strip().lower()

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v}

    @classmethod
    def from_dict(cls, d):
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in (d or {}).items() if k in known})


@dataclass
class Episode:
    track: OnlineTrack
    published: float = 0.0      # seconds since 1970 (0 = unknown)
    description: str = ""
    guid: str = ""
    show_key: str = ""

    @property
    def key(self):
        return self.guid or self.track.stream_url or self.track.page_url

    @property
    def date_text(self):
        if not self.published:
            return ""
        t = time.localtime(self.published)
        now = time.localtime()
        return time.strftime("%d %b" if t.tm_year == now.tm_year else "%d %b %Y", t).lstrip("0")


# --- text helpers -------------------------------------------------------------------------------------------
def clean_text(text, limit=0):
    """HTML description -> plain text."""
    text = re.sub(r"<\s*(br|/p|/div|/li)\s*/?>", "\n", text or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:limit].rstrip() + "…" if limit and len(text) > limit else text


def parse_duration(value):
    """'1:02:03', '62:03', '3723' or '3723.5' -> milliseconds."""
    value = (value or "").strip()
    if not value:
        return 0
    try:
        if ":" in value:
            secs = 0
            for part in value.split(":"):
                secs = secs * 60 + float(part or 0)
            return int(secs * 1000)
        return int(float(value) * 1000)
    except ValueError:
        return 0


def parse_date(value):
    try:
        return email.utils.parsedate_to_datetime(value).timestamp() if value else 0.0
    except (TypeError, ValueError, IndexError):
        return 0.0


def format_duration(ms):
    mins = int(ms / 60000)
    if mins >= 60:
        return f"{mins // 60} hr {mins % 60} min"
    return f"{max(1, mins)} min" if ms else ""


# --- Apple directory ----------------------------------------------------------------------------------------
def _norm(text):
    """Lower case, no accents or punctuation, "&" as "and": for comparing show names."""
    import unicodedata
    text = unicodedata.normalize("NFKD", (text or "").replace("&", " and ")).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def match_score(term, title, author=""):
    """How well a show matches what was typed: 4 exact name, 3 name starts with it, 2 every word in the name,
    1 every word in the name or host, 0 otherwise."""
    q, t, a = _norm(term), _norm(title), _norm(author)
    t_bare = re.sub(r"\b(the|podcast|show)\b", " ", t)
    q_bare = re.sub(r"\b(the|podcast|show)\b", " ", q)
    if not q:
        return 0
    if q == t or " ".join(q_bare.split()) == " ".join(t_bare.split()):
        return 4
    if t.startswith(q):
        return 3
    words = q.split()
    if all(w in t.split() for w in words):
        return 2
    if all(w in (t + " " + a).split() for w in words):
        return 1
    return 0


def rank_shows(term, shows):
    """Best matches first (an exact name match always on top); Apple's order is kept within each group."""
    return [s for _i, s in sorted(enumerate(shows), key=lambda p: (-match_score(term, p[1].title, p[1].author), p[0]))]


def search(net, term, limit=25, country="us"):
    data = net.get_json("https://itunes.apple.com/search",
                        {"media": "podcast", "entity": "podcast", "term": term, "limit": limit, "country": country},
                        ttl=6 * 3600)
    out = []
    for r in data.get("results") or []:
        if not r.get("feedUrl"):
            continue
        out.append(Show(title=r.get("collectionName") or r.get("trackName") or "", author=r.get("artistName") or "",
                        feed_url=r["feedUrl"], image_url=r.get("artworkUrl600") or r.get("artworkUrl100") or "",
                        apple_id=str(r.get("collectionId") or ""), genre=r.get("primaryGenreName") or ""))
    return rank_shows(term, out)


def find_youtube_channel(title, author="", extract=None):
    """The show's own YouTube channel (its video version), or None. Searches YouTube for the show and only
    accepts a channel whose name is the show's name (or its host's), so an unrelated channel isn't picked.
    Returns a Show of kind "youtube". `extract` replaces yt-dlp in tests."""
    if extract is None:
        from core import downloader
        e = downloader.engine()
        if e.yt_dlp is None:
            return None

        def extract(query):
            opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "extract_flat": True,
                    "skip_download": True, "socket_timeout": 20}
            with e.yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(query, download=False)
    info = extract(f"ytsearch15:{title} podcast") or {}
    wanted = {_norm(title), re.sub(r"\b(the|podcast|show)\b", " ", _norm(title)).strip()}
    if author:
        wanted.add(_norm(author))
    wanted = {" ".join(w.split()) for w in wanted if w}
    votes = {}
    for entry in info.get("entries") or []:
        name = entry.get("channel") or entry.get("uploader") or ""
        url = entry.get("channel_url") or entry.get("uploader_url") or ""
        if not url and entry.get("channel_id"):
            url = f"https://www.youtube.com/channel/{entry['channel_id']}"
        n = " ".join(re.sub(r"\b(the|podcast|show|official|tv)\b", " ", _norm(name)).split())
        if url and is_web_url(url) and (n in wanted or _norm(name) in wanted):
            v = votes.setdefault(url, [0, name, bool(entry.get("channel_is_verified"))])
            v[0] += 1
    if not votes:
        return None
    url, (_count, name, verified) = max(votes.items(), key=lambda kv: (kv[1][0], kv[1][2]))
    return Show(title=name, author=name, feed_url=url, kind="youtube", link=url, verified=verified, channel=name)


def top_shows(net, country="us", limit=25):
    data = net.get_json(f"https://rss.applemarketingtools.com/api/v2/{country}/podcasts/top/{limit}/podcasts.json",
                        ttl=12 * 3600)
    out = []
    for r in ((data.get("feed") or {}).get("results") or []):
        art = (r.get("artworkUrl100") or "").replace("100x100", "600x600")
        genres = r.get("genres") or []
        out.append(Show(title=r.get("name") or "", author=r.get("artistName") or "", apple_id=str(r.get("id") or ""),
                        image_url=art, genre=(genres[0].get("name") if genres and isinstance(genres[0], dict) else "")))
    return out


def resolve_feed(net, show):
    """Shows from the Apple chart have no feed URL yet: look it up by id."""
    if show.feed_url or not show.apple_id:
        return show
    data = net.get_json("https://itunes.apple.com/lookup", {"id": show.apple_id, "entity": "podcast"}, ttl=7 * 86400)
    for r in data.get("results") or []:
        if r.get("feedUrl"):
            show.feed_url = r["feedUrl"]
            show.image_url = show.image_url or r.get("artworkUrl600") or ""
            break
    if not show.feed_url:
        raise ValueError("This show doesn't publish a public feed.")
    return show


# --- RSS feeds ---------------------------------------------------------------------------------------------
def parse_feed(xml_text, feed_url=""):
    """(Show, [Episode]) from a podcast RSS feed, newest first."""
    raw = xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text
    if b"<!ENTITY" in raw[:200000]:
        # Real feeds never declare entities; a feed that does could expand them to gigabytes ("billion laughs").
        raise ValueError("That feed can't be read safely.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise ValueError(f"That address isn't a podcast feed ({e}).")
    channel = root.find("channel")
    if channel is None:
        raise ValueError("That address isn't a podcast feed.")

    def text(el, tag):
        node = el.find(tag)
        return (node.text or "").strip() if node is not None and node.text else ""

    image = ""
    it_img = channel.find(f"{ITUNES_NS}image")
    if it_img is not None:
        image = _web(it_img.get("href", ""))
    if not image:
        image = _web(text(channel, "image/url"))
    show = Show(title=text(channel, "title") or "Podcast", author=text(channel, f"{ITUNES_NS}author"),
                feed_url=feed_url, image_url=image,
                description=clean_text(text(channel, "description") or text(channel, f"{ITUNES_NS}summary"), 600),
                link=_web(text(channel, "link")))
    episodes = []
    for item in channel.findall("item")[:MAX_EPISODES]:
        enc = item.find("enclosure")
        url = enc.get("url", "") if enc is not None else ""
        if not url:
            media = item.find(f"{MEDIA_NS}content")
            url = media.get("url", "") if media is not None else ""
        url = _web(url)
        if not url:
            continue
        ep_img = item.find(f"{ITUNES_NS}image")
        title = text(item, "title") or "Episode"
        track = OnlineTrack(title=title, artist=show.title, album=show.title,
                            duration_ms=parse_duration(text(item, f"{ITUNES_NS}duration")),
                            cover_url=_web(ep_img.get("href", "") if ep_img is not None else "") or image,
                            stream_url=url, download_url=url, source="podcast",
                            page_url=_web(text(item, "link")), genre="Podcast",
                            explicit=text(item, f"{ITUNES_NS}explicit").lower() in ("yes", "true", "explicit"))
        guid = text(item, "guid") or url
        track.source_id = guid
        episodes.append(Episode(track=track, published=parse_date(text(item, "pubDate")),
                                description=clean_text(text(item, "description") or text(item, f"{ITUNES_NS}summary"), 400),
                                guid=guid, show_key=show.key))
    episodes.sort(key=lambda e: e.published, reverse=True)
    return show, episodes


def fetch_show(net, show):
    """Fresh episode list for a followed or found show. Returns (Show, [Episode])."""
    if show.kind == "youtube":
        return fetch_youtube_channel(show.feed_url, show)
    show = resolve_feed(net, show)
    fresh, episodes = parse_feed(net.get_text(show.feed_url, ttl=1800), show.feed_url)
    fresh.apple_id = show.apple_id
    fresh.genre = show.genre or fresh.genre
    fresh.image_url = fresh.image_url or show.image_url
    for e in episodes:
        e.show_key = fresh.key
    return fresh, episodes


# --- YouTube channels (video podcasts) ------------------------------------------------------------------
def is_youtube_link(text):
    return bool(YOUTUBE_RE.search(text or ""))


def youtube_list_url(text):
    m = YOUTUBE_RE.search(text or "")
    if not m:
        return ""
    part = m.group(1)
    if part.lower().startswith("playlist"):
        return "https://www.youtube.com/" + part
    return f"https://www.youtube.com/{part}/videos"


def fetch_youtube_channel(url, show=None, extract=None, limit=60):
    """Latest videos of a YouTube channel or playlist as episodes (titles and lengths only; the audio or video
    link is found when an episode is played). `extract` replaces yt-dlp in tests."""
    if extract is None:
        from core import downloader
        e = downloader.engine()
        if e.yt_dlp is None:
            raise ValueError("yt-dlp is missing, so YouTube channels can't be read.")

        def extract(u):
            opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "extract_flat": True,
                    "skip_download": True, "playlistend": limit, "socket_timeout": 20}
            with e.yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(u, download=False)
    info = extract(youtube_list_url(url) or url) or {}
    title = info.get("channel") or info.get("uploader") or info.get("title") or "YouTube channel"
    title = re.sub(r"\s+-\s+Videos$", "", title)
    thumbs = [t.get("url") for t in (info.get("thumbnails") or []) if t.get("url")]
    show = Show(title=title, author=info.get("uploader") or title, feed_url=url, kind="youtube",
                image_url=(thumbs[-1] if thumbs else (show.image_url if show else "")),
                description=clean_text(info.get("description") or "", 600), link=info.get("webpage_url") or url,
                verified=bool(info.get("channel_is_verified")),
                followers=int(info.get("channel_follower_count") or 0),
                channel=info.get("channel") or info.get("uploader") or "")
    episodes = []
    for i, entry in enumerate((info.get("entries") or [])[:limit]):
        vid = entry.get("id") or ""
        if not vid:
            continue
        page = entry.get("url") if str(entry.get("url", "")).startswith("http") else f"https://www.youtube.com/watch?v={vid}"
        thumbs = [t.get("url") for t in (entry.get("thumbnails") or []) if t.get("url")]
        track = OnlineTrack(title=entry.get("title") or "Video", artist=show.title, album=show.title,
                            duration_ms=int((entry.get("duration") or 0) * 1000),
                            cover_url=(thumbs[-1] if thumbs else show.image_url), source="youtube",
                            source_id=vid, page_url=page, youtube_id=vid, genre="Podcast")
        stamp = entry.get("timestamp") or 0
        episodes.append(Episode(track=track, published=float(stamp or 0) or (time.time() - i * 60),
                                description=clean_text(entry.get("description") or "", 300), guid=f"yt:{vid}",
                                show_key=show.key))
    return show, episodes


def source_note(show):
    """How sure Sevbify is that a YouTube source is the creator's own (shown on the show page). Uses what
    YouTube itself says about the channel (its verified tick and subscribers), not the name or picture."""
    if show.kind != "youtube":
        return "From the show's own podcast feed (the publisher's official feed)."
    if show.verified:
        n = show.followers
        size = f" · {n / 1_000_000:.1f}M subscribers" if n >= 1_000_000 else (f" · {n // 1000}K subscribers" if n >= 1000 else "")
        return f"✓ Verified YouTube channel{(': ' + show.channel) if show.channel else ''}{size}"
    return ("⚠ Not verified by YouTube" + (f" ({show.channel})" if show.channel else "") +
            ": check it's the creator's own channel before downloading (re-uploads are common).")


def _ydl(extra):
    from core import downloader
    e = downloader.engine()
    if e.yt_dlp is None:
        raise ValueError("yt-dlp is missing.")
    opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "noplaylist": True, "socket_timeout": 20}
    loc = e._ffmpeg_location()
    if loc:
        opts["ffmpeg_location"] = loc
    opts.update(extra)
    return e.yt_dlp.YoutubeDL(opts)


VIDEO_FORMAT = "best[ext=mp4][vcodec!=none][acodec!=none][height<=720]/best[vcodec!=none][acodec!=none]"


def video_format(max_height=720):
    """One link with picture and sound (what Windows' video player needs), at most `max_height` lines."""
    h = int(max_height or 720)
    return (f"best[vcodec!=none][acodec!=none][height<={h}][ext=mp4]/best[vcodec!=none][acodec!=none][height<={h}]/"
            "best[vcodec!=none][acodec!=none]")


def youtube_stream(page_url, video=False, extract=None, max_height=720):
    """(direct link, HTTP headers) for an episode's audio, or for its video with sound (video=True)."""
    if extract is None:
        def extract(url):
            fmt = video_format(max_height) if video else "bestaudio/best"
            with _ydl({"format": fmt, "skip_download": True}) as ydl:
                return ydl.extract_info(url, download=False)
    info = extract(page_url) or {}
    if not info.get("url"):
        raise ValueError("YouTube didn't give a playable link for this video.")
    return info["url"], dict(info.get("http_headers") or {})


def youtube_video_streams(page_url, max_height=720, extract=None):
    """Separate video and audio links (YouTube's HD needs both), for players that can join them (the Android
    app). Returns {"video", "audio", "headers", "height"}; "audio" is "" when the one link has both."""
    h = int(max_height or 720)
    if extract is None:
        def extract(url):
            fmt = (f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/"
                   f"b[height<={h}]/b")
            with _ydl({"format": fmt, "skip_download": True}) as ydl:
                return ydl.extract_info(url, download=False)
    info = extract(page_url) or {}
    parts = info.get("requested_formats") or []
    headers = dict(info.get("http_headers") or {})
    if len(parts) >= 2 and parts[0].get("url") and parts[1].get("url"):
        return {"video": parts[0]["url"], "audio": parts[1]["url"], "headers": headers,
                "height": int(parts[0].get("height") or 0)}
    if not info.get("url"):
        raise ValueError("YouTube didn't give a playable link for this video.")
    return {"video": info["url"], "audio": "", "headers": headers, "height": int(info.get("height") or 0)}


def download_youtube_audio(page_url, out_path_without_ext):
    """Save an episode's sound as an MP3 (yt-dlp + ffmpeg). Returns the file path."""
    with _ydl({"format": "bestaudio/best", "outtmpl": out_path_without_ext + ".%(ext)s",
               "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}]}) as ydl:
        ydl.download([page_url])
    path = out_path_without_ext + ".mp3"
    if not os.path.exists(path):
        raise ValueError("The download didn't produce an MP3.")
    return path


# --- files -------------------------------------------------------------------------------------------------
def episode_filename(episode):
    """'2026-10-25 - Episode title.mp3' (extension from the audio link)."""
    ext = urllib.parse.urlparse(episode.track.stream_url or "").path.rsplit(".", 1)[-1].lower()
    ext = ext if ext in ("mp3", "m4a", "aac", "ogg", "opus", "wav", "flac") else "mp3"
    date = time.strftime("%Y-%m-%d", time.localtime(episode.published)) + " - " if episode.published else ""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", episode.track.title).strip(" .")[:150] or "Episode"
    return f"{date}{name}.{ext}"


def safe_folder(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name or "").strip(" .")[:100] or "Podcast"

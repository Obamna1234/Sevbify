"""Podcasts: find shows, read their episode lists, and play or download episodes (no UI code).

Where the data comes from (nothing else is contacted):
- Apple's public podcast directory: search (itunes.apple.com/search) and the Top Podcasts chart
  (rss.applemarketingtools.com). No account, no sign-in.
- Each show's own public RSS feed: episodes, artwork, descriptions and the audio files, exactly as the show
  publishes them for every podcast app. Episodes can be streamed and downloaded.
- YouTube (video podcasts) through yt-dlp: a channel link you add, and on the Podcasts tab a search for the
  show's own channel when Apple's directory has no show by that name.

Episodes become OnlineTrack objects (source "podcast" / "youtube"), so they play in the normal player and queue.
"""
import copy
import email.utils
import html
import json
import os
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from core.online.models import OnlineTrack
from core.online.net import is_web_url, is_outside_link


def _web(url):
    """Links from a feed are only kept when they're web addresses on the internet (never file: links, and never
    a device on your own network such as your router)."""
    return url.strip() if is_outside_link(url) else ""

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
    """Lower case, no accents or punctuation, "&" as "and": for comparing show names. Any script counts
    (Cyrillic, Arabic, CJK…), so searching in any language ranks shows properly."""
    import unicodedata
    text = unicodedata.normalize("NFKD", (text or "").replace("&", " and ")).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", text))


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


def relevant(term, shows):
    """Only shows whose name or host has the words you typed (for the "All" search page, so a typo doesn't put
    an unrelated podcast on top)."""
    return [s for s in shows if match_score(term, s.title, s.author) > 0]


def search_with_youtube(net, term, limit=25, country="us", extract=None):
    """Apple's podcast directory, plus the show's own YouTube channel on top when Apple has no show by that name
    (many podcasts are only on YouTube)."""
    shows = search(net, term, limit, country)
    if any(match_score(term, s.title, s.author) >= 3 for s in shows):
        return shows
    try:
        channel = find_youtube_channel(term, extract=extract)
    except Exception:
        channel = None
    if channel is not None and all(s.feed_url != channel.feed_url for s in shows):
        shows.insert(0, channel)
    return shows


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


_STOP = {"the", "a", "an", "of", "and", "in", "to", "is", "was", "with", "for", "on", "part"}


def _channel_link(entry):
    """The https://www.youtube.com/... link of a search result's channel, or "" (only YouTube's own addresses)."""
    url = entry.get("channel_url") or entry.get("uploader_url") or ""
    if not url and entry.get("channel_id"):
        url = f"https://www.youtube.com/channel/{entry['channel_id']}"
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    ok = url.startswith("https://") and (host == "youtube.com" or host.endswith(".youtube.com"))
    return url if ok and is_web_url(url) else ""


def channel_show(url, name=""):
    """A YouTube channel Show from a link already known to be the show's channel (no search), or None."""
    host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    if not (url.startswith("https://") and (host == "youtube.com" or host.endswith(".youtube.com")) and is_web_url(url)):
        return None
    name = name or "YouTube channel"
    return Show(title=name, author=name, feed_url=url, kind="youtube", link=url, channel=name)


def find_youtube_channel(title, author="", extract=None, episode_title="", episode_titles=()):
    """The show's own YouTube channel (its video version), or None. Searches YouTube for the show and only
    accepts a channel whose name is the show's name (or its host's), so an unrelated channel isn't picked.
    When no channel is named like the show (the channel is often called something else, e.g. the host), the
    channel of the video that matches one of the show's episodes (`episode_title`) is used instead: the same
    matching as playing an episode's video. Returns a Show of kind "youtube". `extract` replaces yt-dlp in tests."""
    if extract is None:
        from core import downloader
        e = downloader.engine()
        if e.yt_dlp is None:
            return None

        def extract(query):
            opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "extract_flat": True,
                    "skip_download": True, "socket_timeout": 20, "allowed_extractors": YOUTUBE_ONLY,
                    "extractor_args": e.yt_extractor_args()}       # on the phones: the clients that work without a JS runtime
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
    # No channel is named like the show: use the channel of a video that matches one of its episodes. The newest
    # episode may not be on YouTube yet, so a few of the recent ones are tried, one search each.
    for ep_title in ([t for t in ([episode_title] + list(episode_titles)) if t][:4] if not votes else []):
        words = {w for w in _norm(ep_title).split() if w not in _STOP}
        if not words:
            continue
        info = extract(f"ytsearch10:{title} {ep_title}") or {}
        for entry in info.get("entries") or []:
            if not is_youtube_video(entry.get("url") or entry.get("webpage_url") or ""):
                continue
            got = {w for w in _norm(entry.get("title") or "").split() if w not in _STOP}
            if len(words & got) / len(words) < 0.6:
                continue
            name = entry.get("channel") or entry.get("uploader") or ""
            url = _channel_link(entry)
            if url:
                v = votes.setdefault(url, [0, name, bool(entry.get("channel_is_verified"))])
                v[0] += 1
        if votes:
            break
    if not votes:
        return None
    url, (_count, name, verified) = max(votes.items(), key=lambda kv: (kv[1][0], kv[1][2]))
    return Show(title=name, author=name, feed_url=url, kind="youtube", link=url, verified=verified, channel=name)


def find_youtube_episode(show_title, episode_title, duration_ms=0, extract=None):
    """The YouTube video of one podcast episode (the show's video version), or "". See find_youtube_episode_ex."""
    return find_youtube_episode_ex(show_title, episode_title, duration_ms, extract)[0]


def find_youtube_episode_ex(show_title, episode_title, duration_ms=0, extract=None):
    """(video link or "", a short note on what was found). See find_youtube_episode_info."""
    r = find_youtube_episode_info(show_title, episode_title, duration_ms, extract)
    return r["url"], r["note"]


_chan_cache = {}                   # channel list address -> (time, its recent videos)


def _title_matcher(episode_title):
    """(score(video_title) -> 0..1, usable) for an episode title. Episode titles are often "Headline | Series:
    Episode (Part 5)" while the video has only one of those parts: a video also counts when it has most of the
    words of one part (3 words or more)."""
    words = {w for w in _norm(episode_title).split() if w not in _STOP}
    parts = [p for p in re.split(r"\s+[|\u2013\u2014]\s+|\s+-\s+", episode_title) if p.strip()]
    part_words = [{w for w in _norm(p).split() if w not in _STOP} for p in parts] if len(parts) > 1 else []
    part_words = [pw for pw in part_words if len(pw) >= 3]

    def score(video_title):
        got = {w for w in _norm(video_title or "").split() if w not in _STOP}
        sc = len(words & got) / len(words) if words else 0.0
        for pw in part_words:
            if len(pw & got) / len(pw) >= 0.75:
                sc = max(sc, 0.6)
        return sc
    return score, bool(words)


def _find_in_channel(channel_url, episode_title, duration_ms, extract=None):
    """Look for the episode among the show's own channel's recent videos, by title and by length. The audio and
    the video of an episode often have different names (the feed says "Headline | Series (Part 2)", the video only
    "Headline"), but they are the same length give or take the ads, and being on the show's own channel already
    says it's the right show. Returns the same answer as find_youtube_episode_info, or None when nothing fits."""
    list_url = youtube_list_url(channel_url)
    if not list_url or not duration_ms:
        return None
    score, usable = _title_matcher(episode_title)
    if not usable:
        return None
    if extract is None:
        from core import downloader
        e = downloader.engine()
        if e.yt_dlp is None:
            return None

        def extract(u):
            opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "extract_flat": True,
                    "skip_download": True, "playlistend": 60, "socket_timeout": 20, "allowed_extractors": YOUTUBE_ONLY}
            with e.yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(u, download=False)
    hit = _chan_cache.get(list_url)
    if hit and time.time() - hit[0] < 600:
        info = hit[1]
    else:
        info = extract(list_url) or {}
        _chan_cache[list_url] = (time.time(), info)
    cands = []
    for entry in info.get("entries") or []:
        if not is_youtube_video(entry.get("url") or entry.get("webpage_url") or ""):
            continue
        secs = entry.get("duration") or 0
        if not secs:
            continue
        cands.append((score(entry.get("title")), abs(secs * 1000 - duration_ms) / duration_ms, entry))
    if not cands:
        return None
    name = info.get("channel") or info.get("uploader") or ""

    def answer(entry, why):
        return {"url": entry.get("url") or entry.get("webpage_url"), "channel": name, "channel_url": channel_url,
                "note": f"on the show's channel, {why}: {(entry.get('title') or '')[:60]}"}
    # 1. the title says it (as before), and the length is in the same range
    good = [c for c in cands if c[0] >= 0.6 and c[1] <= 0.35]
    if good:
        best = max(good, key=lambda c: (c[0], -c[1]))
        return answer(best[2], f"title {best[0]:.0%}")
    # 2. a video of about the same length (within 8%) that shares some words with the title, clearly the best of those
    close = sorted([c for c in cands if c[1] <= 0.08 and c[0] >= 0.2], key=lambda c: (-c[0], c[1]))
    if close and (len(close) == 1 or close[0][0] - close[1][0] >= 0.15):
        return answer(close[0][2], f"length within {close[0][1]:.0%} and title {close[0][0]:.0%}")
    return None


def find_youtube_episode_info(show_title, episode_title, duration_ms=0, extract=None, channel_url=""):
    """{"url": video link or "", "note": a short note on what was found, "channel", "channel_url"} (the channel of
    the video that was found: it's the show's own channel, which the Watch video button can use). Searches YouTube for the show and episode and accepts
    only a video whose title says the episode's words (and whose length is in the same range when both are
    known; ads in the podcast's audio make the lengths differ a little), so a different video is never picked.
    `extract` replaces yt-dlp in tests."""
    if extract is None:
        from core import downloader
        e = downloader.engine()
        if e.yt_dlp is None:
            return {"url": "", "note": "yt-dlp isn't available", "channel": "", "channel_url": ""}

        def extract(query):
            opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "extract_flat": True,
                    "skip_download": True, "socket_timeout": 20, "allowed_extractors": YOUTUBE_ONLY,
                    "extractor_args": e.yt_extractor_args()}
            with e.yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(query, download=False)
    channel_note = ""
    if channel_url and channel_show(channel_url):
        try:
            found = _find_in_channel(channel_url, episode_title, duration_ms)
        except Exception as ex:                          # fall back to the search
            found, channel_note = None, f"(channel list failed: {str(ex)[:40]}) "
        if found:
            return found
        channel_note = channel_note or "not among the show's channel's recent videos; "
    stop = _STOP
    words = {w for w in _norm(episode_title).split() if w not in stop}
    if not words:
        return {"url": "", "note": "the episode has no usable title", "channel": "", "channel_url": ""}
    # Episode titles are often "Headline | Series: Episode (Part 5)" while the video has only one of those parts:
    # a video also counts when it has most of the words of one part (3 words or more).
    parts = [p for p in re.split(r"\s+[|\u2013\u2014]\s+|\s+-\s+", episode_title) if p.strip()]
    part_words = [{w for w in _norm(p).split() if w not in stop} for p in parts] if len(parts) > 1 else []
    part_words = [pw for pw in part_words if len(pw) >= 3]
    queries = [f"{show_title} {episode_title}"]
    if len(parts) > 1:
        queries.append(f"{show_title} {max(parts, key=len)}")      # a shorter, plainer search
    best, best_score, best_title, skipped_len, seen = "", 0.0, "", 0, 0
    best_entry = {}
    for query in queries:
        info = extract(f"ytsearch10:{query}") or {}
        entries = info.get("entries") or []
        seen += len(entries)
        for entry in entries:
            url = entry.get("url") or entry.get("webpage_url") or ""
            if not is_youtube_video(url):
                continue
            got = {w for w in _norm(entry.get("title") or "").split() if w not in stop}
            score = len(words & got) / len(words)
            for pw in part_words:                       # one part of the title is enough if it matches closely
                if len(pw & got) / len(pw) >= 0.75:
                    score = max(score, 0.6)
            secs = entry.get("duration") or 0
            if duration_ms and secs and abs(secs * 1000 - duration_ms) > 0.35 * duration_ms:
                skipped_len += 1                         # a clip or a different cut of the show
                continue
            if score > best_score:
                best, best_score, best_title, best_entry = url, score, entry.get("title") or "", entry
        if best_score >= 0.6:
            break
    if best_score >= 0.6:
        return {"url": best, "note": f"matched {best_score:.0%}: {best_title[:60]}",
                "channel": best_entry.get("channel") or best_entry.get("uploader") or "",
                "channel_url": _channel_link(best_entry)}
    return {"url": "", "channel": "", "channel_url": "",
            "note": (channel_note + f"{seen} results over {len(queries)} search{'es' if len(queries) > 1 else ''}, best match {best_score:.0%}"
                     + (f", {skipped_len} the wrong length" if skipped_len else ""))}


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


# Apple's podcast categories (its public chart for each one; no account).
PODCAST_CATEGORIES = [
    (1303, "Comedy"), (1489, "News"), (1488, "True Crime"), (1324, "Society & Culture"), (1545, "Sports"),
    (1512, "Health & Fitness"), (1321, "Business"), (1487, "History"), (1318, "Technology"), (1309, "TV & Film"),
    (1533, "Science"), (1304, "Education"), (1301, "Arts"), (1310, "Music"), (1502, "Leisure"),
    (1483, "Fiction"), (1305, "Kids & Family"), (1314, "Religion & Spirituality"),
]


def top_in_category(net, genre_id, country="us", limit=25):
    """The chart of one category ("Comedy", "True Crime"...), from Apple's public chart feed."""
    url = f"https://itunes.apple.com/{country}/rss/toppodcasts/limit={int(limit)}/genre={int(genre_id)}/json"
    data = net.get_json(url, ttl=12 * 3600)
    out = []
    entries = ((data or {}).get("feed") or {}).get("entry") or []
    if isinstance(entries, dict):
        entries = [entries]
    for e in entries:
        def label(key):
            v = e.get(key) or {}
            return v.get("label", "") if isinstance(v, dict) else ""
        images = e.get("im:image") or []
        art = images[-1].get("label", "") if images and isinstance(images[-1], dict) else ""
        art = re.sub(r"/\d+x\d+bb\.", "/600x600bb.", art)
        apple_id = (((e.get("id") or {}).get("attributes") or {}).get("im:id") or "")
        cat = (((e.get("category") or {}).get("attributes") or {}).get("label") or "")
        if label("im:name"):
            out.append(Show(title=label("im:name"), author=label("im:artist"), apple_id=str(apple_id),
                            image_url=art, genre=cat))
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
    if b"<!ENTITY" in raw or b"<!DOCTYPE" in raw:
        # Real feeds never declare entities or a DOCTYPE; one that does could expand to gigabytes ("billion laughs").
        # The whole feed is checked (older phones' XML readers have no protection of their own).
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
YOUTUBE_ONLY = ["youtube", "youtube:.*"]     # yt-dlp may only use its YouTube readers for podcasts


def is_youtube_video(url):
    """https://www.youtube.com/watch?v=… / youtu.be/… / m.youtube.com / music.youtube.com only."""
    try:
        p = urllib.parse.urlparse(url or "")
    except ValueError:
        return False
    host = (p.hostname or "").lower()
    return p.scheme in ("http", "https") and (host in ("youtu.be", "youtube.com") or host.endswith(".youtube.com"))


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
                    "skip_download": True, "playlistend": limit, "socket_timeout": 20,
                    "allowed_extractors": YOUTUBE_ONLY}
            with e.yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(u, download=False)
    list_url = youtube_list_url(url)
    if not list_url:
        raise ValueError("That isn't a YouTube channel or playlist link.")   # e.g. a crafted profile file
    info = extract(list_url) or {}
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
        if not re.fullmatch(r"[\w-]{6,20}", vid):
            continue
        page = f"https://www.youtube.com/watch?v={vid}"          # always YouTube's own page, never a link from outside
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
    opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "noplaylist": True, "socket_timeout": 20,
            "allowed_extractors": YOUTUBE_ONLY}
    loc = e._ffmpeg_location()
    if loc:
        opts["ffmpeg_location"] = loc
    opts.update(extra)
    return e.yt_dlp.YoutubeDL(opts)


_RAW_TTL = 600                     # a video page's data is kept this long (seconds)
_raw = {}                          # (page, clients) -> (time, yt-dlp's data for the page before choosing a format)
_raw_lock = threading.Lock()


def _client_ladder():
    """The yt-dlp YouTube client settings to try for an episode's audio or video, quickest first. On the phones
    (no JS runtime) yt-dlp is told to ask several clients one after the other, which is slow, so the single
    clients that give plain links go first and the full list is the fallback (the same idea as for songs). On
    the desktop there's one attempt with yt-dlp's defaults."""
    from core import downloader
    base = dict(downloader.engine().yt_extractor_args() or {})
    clients = list((base.get("youtube") or {}).get("player_client") or [])
    if not clients:
        return [{}]
    fast = [{"youtube": {**base["youtube"], "player_client": [c]}} for c in ("android_vr", "tv") if c in clients]
    return fast + [base]


_pref_client = 0                   # which of the client settings worked last (tried first from then on)


def link_failed(url=""):
    """The player was refused an episode's link: forget the kept page data and start with the next client."""
    global _pref_client
    with _raw_lock:
        _raw.clear()
    _pref_client = (_pref_client + 1) % max(len(_client_ladder()), 1)
    return True


def _refused(info):
    """True when YouTube clearly refuses one of the links yt-dlp chose (the player would get an HTTP 403)."""
    from core import streamer
    for f in (info.get("requested_formats") or [info]):
        if f.get("url") and not streamer.url_works(f["url"], f.get("http_headers") or info.get("http_headers") or {}):
            return True
    return False


def _extract_page(url, opts):
    """yt-dlp's answer for a YouTube video page with `opts` (which format is wanted). The page's data is fetched
    once per client setting and kept for 10 minutes, so listening to an episode and then watching it (or back)
    doesn't fetch it twice; only the choice of format is redone."""
    global _pref_client
    last = None
    ladder = _client_ladder()
    start = _pref_client % len(ladder)
    for n, args in enumerate(ladder[start:] + ladder[:start]):
        key = (url, json.dumps(args, sort_keys=True))
        extra = {"extractor_args": args} if args else {}
        try:
            with _raw_lock:
                hit = _raw.get(key)
            if hit and time.time() - hit[0] < _RAW_TTL:
                raw = hit[1]
            else:
                with _ydl({"skip_download": True, **extra}) as ydl:
                    raw = ydl.extract_info(url, download=False, process=False)
                with _raw_lock:
                    if len(_raw) >= 30:
                        _raw.pop(min(_raw, key=lambda k: _raw[k][0]), None)
                    _raw[key] = (time.time(), raw)
            with _ydl({**opts, **extra}) as ydl:
                info = ydl.process_ie_result(copy.deepcopy(raw), download=False)
            if n < len(ladder) - 1 and _refused(info):          # this client's links don't play: the next one
                raise ValueError("YouTube refused the link")
            _pref_client = ladder.index(args)
            return info
        except Exception as ex:                      # this client didn't work: the next one
            last = ex
            with _raw_lock:
                _raw.pop(key, None)
    raise last if last else ValueError("YouTube didn't answer.")


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
            from core import quality
            fmt = video_format(max_height) if video else quality.STREAM_AUDIO_FORMAT
            return _extract_page(url, {"format": fmt, "skip_download": True})
    if not is_youtube_video(page_url):
        raise ValueError("That isn't a YouTube video link.")
    info = extract(page_url) or {}
    if not info.get("url"):
        raise ValueError("YouTube didn't give a playable link for this video.")
    return info["url"], dict(info.get("http_headers") or {})


def video_captions(info):
    """The subtitle tracks of a YouTube video as [{"lang", "name", "auto", "url"}] (WebVTT, from YouTube itself):
    the uploader's own captions, then the automatic captions in the video's own language. Newest first is not
    needed; an empty list when the video has none (or YouTube didn't hand them out)."""
    def vtt(entries):
        for f in entries or []:
            url = f.get("url") or ""
            if f.get("ext") == "vtt" and url.startswith("https://"):
                host = (urllib.parse.urlparse(url).hostname or "").lower()
                if host == "youtube.com" or host.endswith(".youtube.com"):
                    return url
        return ""
    out, seen = [], set()
    for lang, entries in (info.get("subtitles") or {}).items():
        url = vtt(entries) if lang != "live_chat" else ""
        if url:
            name = next((f.get("name") for f in entries if f.get("name")), lang)
            out.append({"lang": lang, "name": name, "auto": False, "url": url})
            seen.add(lang.split("-")[0])
    own = (info.get("language") or "").split("-")[0]
    for lang, entries in (info.get("automatic_captions") or {}).items():
        base = lang.split("-")[0]
        if base in seen or not (lang.endswith("-orig") or (own and lang == own)):
            continue
        url = vtt(entries)
        if url:
            name = next((f.get("name") for f in entries if f.get("name")), lang)
            out.append({"lang": lang, "name": f"{name} (automatic)", "auto": True, "url": url})
            seen.add(base)
    return out[:25]


def youtube_video_streams(page_url, max_height=720, extract=None):
    """Separate video and audio links (YouTube's HD needs both), for players that can join them (the Android
    app). Returns {"video", "audio", "headers", "height", "captions"}; "audio" is "" when the one link has both."""
    h = int(max_height or 720)
    if extract is None:
        def extract(url):
            fmt = (f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/"
                   f"b[height<={h}]/b")
            # writesubtitles/writeautomaticsub only make yt-dlp list the caption tracks in the answer; with
            # download=False nothing is written to disk.
            return _extract_page(url, {"format": fmt, "skip_download": True, "writesubtitles": True,
                                       "writeautomaticsub": True})
    if not is_youtube_video(page_url):
        raise ValueError("That isn't a YouTube video link.")
    info = extract(page_url) or {}
    parts = info.get("requested_formats") or []
    headers = dict(info.get("http_headers") or {})
    if len(parts) >= 2 and parts[0].get("url") and parts[1].get("url"):
        return {"video": parts[0]["url"], "audio": parts[1]["url"], "headers": headers,
                "height": int(parts[0].get("height") or 0), "captions": video_captions(info)}
    if not info.get("url"):
        raise ValueError("YouTube didn't give a playable link for this video.")
    return {"video": info["url"], "audio": "", "headers": headers, "height": int(info.get("height") or 0),
            "captions": video_captions(info)}


def download_youtube_audio(page_url, out_path_without_ext):
    """Save an episode's sound as an MP3 (yt-dlp + ffmpeg). Returns the file path."""
    if not is_youtube_video(page_url):
        raise ValueError("That isn't a YouTube video link.")
    with _ydl({"format": "bestaudio/best", "outtmpl": out_path_without_ext.replace("%", "%%") + ".%(ext)s",
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

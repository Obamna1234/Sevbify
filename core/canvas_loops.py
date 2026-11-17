"""Automatic Canvas: a short, silent loop cut from the song's official music video on YouTube (Spotify's Canvas
videos aren't available to other apps). Settings → Canvas from music videos; your own Canvas videos always win.

How it stays small and private:
- One clip per song: about 8 seconds, no sound, at most 720p, re-encoded small (usually 0.5-1.5 MB). The whole
  video is never downloaded: only those seconds are fetched.
- Clips live in a cache with a size limit (default 200 MB). The clips played longest ago are removed first, so it
  never grows past the limit. Settings shows its size and has Clear.
- A downloaded song keeps its clip next to it (in a "canvas" folder beside the song), so it loops offline too.
- The lookup is the same YouTube search Sevbify already uses for full songs: only the song's name is sent.
- Only a video that really is the song's official music video is used (title has the song and says it's the
  official/music video, or it's on the artist's own / VEVO channel). Lyric videos, live shows, covers, reactions
  and "audio" uploads are skipped. No match: no Canvas, nothing guessed.

The clip is landscape (16:9). The side panel shows its middle, tall like Spotify's Canvas; the expanded view and
full screen show it whole.
"""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

CLIP_SECONDS = 8
DEFAULT_LIMIT_MB = 200
_lock = threading.Lock()
_misses = {}                 # key -> time: songs without a music video aren't searched again for a day
SKIP_WORDS = ("lyric", "lyrics", "live", "cover", "reaction", "karaoke", "audio", "remix", "instrumental", "8d",
              "slowed", "sped up", "nightcore", "tutorial", "lesson", "behind the scenes", "teaser", "trailer",
              "interview", "fan made", "fanmade", "amv")
VIDEO_WORDS = ("official video", "official music video", "music video", "official mv", "(mv)", "[mv]", "videoclip",
               "video oficial", "clip officiel")


def _norm(s):
    return " ".join(re.findall(r"\w+", (s or "").casefold()))


def key(artist, title):
    return hashlib.sha1(f"{_norm(artist)}|{_norm(title)}".encode()).hexdigest()[:24]


def cache_dir(data_dir):
    return os.path.join(data_dir, "canvas-cache")


def cached(data_dir, artist, title):
    p = os.path.join(cache_dir(data_dir), key(artist, title) + ".mp4")
    if os.path.isfile(p):
        try:
            os.utime(p)                  # recently played: kept longest
        except OSError:
            pass
        return p
    return ""


def is_music_video(entry, artist, title):
    """True if this search result is the song's official music video."""
    name = _norm(entry.get("title"))
    channel = _norm(entry.get("channel") or entry.get("uploader"))
    want = _norm(title)
    if not want or want not in name:
        return False
    raw = (entry.get("title") or "").casefold()
    if any(w in raw for w in SKIP_WORDS) and not any(w in _norm(title) for w in ("live", "remix", "cover")):
        return False
    dur = entry.get("duration") or 0
    if dur and (dur < 60 or dur > 900):
        return False
    says_video = any(w in raw for w in VIDEO_WORDS)
    artist_n = _norm(artist).replace(" ", "")
    own_channel = bool(artist_n) and (artist_n in channel.replace(" ", "") or channel.endswith("vevo"))
    return says_video or own_channel


def find_music_video(search, artist, title):
    """The official music video's URL, or "". `search(query, n)` returns YouTube results (dicts with title,
    channel, duration, url/id), e.g. sevby_engine.search_youtube_candidates."""
    for entry in search(f"{artist} {title} official music video", 8) or []:
        if is_music_video(entry, artist, title):
            vid = entry.get("id") or ""
            url = entry.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
            if re.match(r"^https://(www\.)?youtube\.com/watch\?v=[\w-]{6,20}$", url):
                return url
    return ""


def _ffmpeg():
    try:
        from core import downloader
        return downloader.engine().ffmpeg_path()
    except Exception:
        return shutil.which("ffmpeg") or ""


def cut_clip(url, out_path, duration_s=0, ytdlp=None, ffmpeg=None):
    """Fetch about CLIP_SECONDS from a third of the way in (past intros and logos), silent, at most 720p, and
    re-encode it small. Raises on failure."""
    if ytdlp is None:
        import yt_dlp as ytdlp
    ffmpeg = ffmpeg or _ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg isn't available")
    start = max(10.0, (duration_s or 180) * 0.33)
    tmp = tempfile.mkdtemp(prefix="sevbify-canvas-")
    try:
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 30,
                "format": "bestvideo[height<=720][ext=mp4]/bestvideo[height<=720]/best[height<=720]",
                "outtmpl": os.path.join(tmp, "raw.%(ext)s"),
                "download_ranges": ytdlp.utils.download_range_func(None, [(start, start + CLIP_SECONDS + 1)]),
                "ffmpeg_location": ffmpeg, "allowed_extractors": ["youtube"]}
        with ytdlp.YoutubeDL(opts) as y:
            y.download([url])
        raw = next((os.path.join(tmp, f) for f in os.listdir(tmp) if f.startswith("raw.")), "")
        if not raw:
            raise RuntimeError("nothing was downloaded")
        part = out_path + ".part.mp4"
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", raw, "-t", str(CLIP_SECONDS), "-an",
                        "-vf", "scale=-2:'min(720,ih)',fps=30", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", part],
                       check=True, timeout=180, capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if os.path.getsize(part) < 10_000:
            raise RuntimeError("the clip came out empty")
        os.replace(part, out_path)
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def get(data_dir, artist, title, search, duration_s=0, limit_mb=DEFAULT_LIMIT_MB, cut=cut_clip):
    """The Canvas clip for this song: cached, or found and cut now (call from a background thread). "" if none."""
    if not artist or not title or artist == "Unknown Artist":
        return ""
    have = cached(data_dir, artist, title)
    if have:
        return have
    k = key(artist, title)
    with _lock:
        if time.time() - _misses.get(k, 0) < 86400:
            return ""
    try:                                   # disk almost full: no new loops (the ones kept still play)
        import shutil
        if shutil.disk_usage(data_dir).free < 500 * 1024 * 1024:
            return ""
    except OSError:
        pass
    url = find_music_video(search, artist, title)
    if not url:
        with _lock:
            _misses[k] = time.time()
        return ""
    folder = cache_dir(data_dir)
    os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, k + ".mp4")
    try:
        cut(url, out, duration_s)
    except Exception:
        with _lock:
            _misses[k] = time.time()
        return ""
    trim(data_dir, limit_mb)
    return out if os.path.isfile(out) else ""


def phone_source(artist, title, search, duration_s=0, streams=None):
    """For the phones (which cut the clip themselves with Android's / iOS's own video tools, no ffmpeg): the music
    video's video-only link, its headers, and where the loop starts. None if the song has no music video."""
    if not artist or not title or artist == "Unknown Artist":
        return None
    k = key(artist, title)
    with _lock:
        if time.time() - _misses.get(k, 0) < 86400:
            return None
    url = find_music_video(search, artist, title)
    if not url:
        with _lock:
            _misses[k] = time.time()
        return None
    if streams is None:
        from core import podcasts
        streams = podcasts.youtube_video_streams
    s = streams(url, 720)
    video = s.get("video") or ""
    if not video.startswith("https://"):
        return None
    return {"key": k, "url": video, "headers": s.get("headers") or {}, "start": max(10.0, (duration_s or 180) * 0.33),
            "seconds": CLIP_SECONDS, "has_audio": not s.get("audio")}


def size_mb(data_dir):
    folder = cache_dir(data_dir)
    if not os.path.isdir(folder):
        return 0.0
    return sum(os.path.getsize(os.path.join(folder, f)) for f in os.listdir(folder)
               if f.endswith(".mp4")) / 1_048_576


def trim(data_dir, limit_mb=DEFAULT_LIMIT_MB):
    """Remove the clips played longest ago until the cache is under its limit."""
    folder = cache_dir(data_dir)
    if not os.path.isdir(folder):
        return 0
    files = sorted((os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".mp4")),
                   key=lambda p: os.path.getmtime(p))
    total, removed = sum(os.path.getsize(p) for p in files), 0
    limit = max(0, int(limit_mb)) * 1_048_576
    for p in files:
        if total <= limit:
            break
        try:
            total -= os.path.getsize(p)
            os.remove(p)
            removed += 1
        except OSError:
            pass
    return removed


def clear(data_dir):
    shutil.rmtree(cache_dir(data_dir), ignore_errors=True)


def keep_with_download(clip, song_path):
    """Copy the clip next to a downloaded song (<folder>/canvas/<song name>.mp4) so it loops offline too."""
    if not clip or not os.path.isfile(clip) or not song_path:
        return ""
    folder = os.path.join(os.path.dirname(song_path), "canvas")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, os.path.splitext(os.path.basename(song_path))[0] + ".mp4")
    if not os.path.isfile(target):
        shutil.copy2(clip, target)
    return target


def remove_with_song(song_path):
    """A downloaded song was deleted: its clip goes too (only the one Sevbify put there)."""
    target = os.path.join(os.path.dirname(song_path), "canvas", os.path.splitext(os.path.basename(song_path))[0] + ".mp4")
    try:
        os.remove(target)
        return True
    except OSError:
        return False

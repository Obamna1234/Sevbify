"""Download and streaming quality choices (Settings), shared by the Windows and Android apps. No UI code.

A file can never be better than its source: YouTube's audio is at most ~128-160 kbps AAC/Opus and Bandcamp's
free streams are 128 kbps MP3. Keeping the original audio is therefore both the best quality and, at full quality,
the smallest file; converting it to a high-bitrate MP3 only makes the file bigger.
"""

# Songs
SONG_QUALITIES = {
    "best": ("Best quality (original audio)",
             "Keeps the audio exactly as it comes: no quality lost, usually the smallest file at full quality "
             "(.m4a; plays in Samsung Music, VLC, Windows Media Player and phones)."),
    "mp3": ("MP3 (plays everywhere)",
            "Converted to a 160 kbps MP3 for very old players and car stereos. A bit bigger, no better."),
    "small": ("Data saver (smallest files)",
              "A lower-bitrate original (about half the size). Good for phones with little space; slightly less "
              "detail with good headphones."),
}
DEFAULT_SONG_QUALITY = "best"
SONG_PHONE_QUALITIES = ("best", "small")       # the phone can't convert to MP3 (no ffmpeg)

BEST_AUDIO_FORMAT = "bestaudio[ext=m4a]/bestaudio[acodec=mp3]/bestaudio/best"
SMALL_AUDIO_FORMAT = ("bestaudio[ext=m4a][abr<=72]/worstaudio[ext=m4a]/bestaudio[abr<=72]/"
                      "bestaudio[ext=m4a]/bestaudio/best")
MP3_QUALITY = "160"

# The link used for *streaming* a song or episode. Windows (VLC) and Android (ExoPlayer) play anything; the
# iPhone's player can't play YouTube's WebM/Opus, so the iPhone app switches this to AAC (.m4a) / MP3 first.
STREAM_AUDIO_FORMAT = "bestaudio/best"
IPHONE_STREAM_AUDIO_FORMAT = ("bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio[acodec=mp3]/"
                              "best[ext=mp4][acodec!=none]/bestaudio/best")


def song_quality(value):
    return value if value in SONG_QUALITIES else DEFAULT_SONG_QUALITY


def audio_format(quality):
    """yt-dlp format for saving original audio at this quality."""
    return SMALL_AUDIO_FORMAT if song_quality(quality) == "small" else BEST_AUDIO_FORMAT


def apply_to_engine(engine, quality):
    """Set the SEVBY engine up for this quality before a download run."""
    q = song_quality(quality)
    engine.QUALITY["best"] = q in ("best", "small")       # keep the original audio (no conversion)
    engine.QUALITY["free"] = False
    engine.AUDIO_FORMAT_ORIGINAL = audio_format(q)
    engine.MP3_QUALITY = MP3_QUALITY


# Audiobooks (LibriVox publishes every chapter at 64 and 128 kbps)
AUDIOBOOK_QUALITIES = {"standard": "Standard (64 kbps, half the size: speech sounds the same)",
                       "high": "High (128 kbps)"}
DEFAULT_AUDIOBOOK_QUALITY = "standard"


def audiobook_formats(quality):
    if quality == "high":
        return ("128Kbps MP3", "VBR MP3", "64Kbps MP3", "MP3")
    return ("64Kbps MP3", "128Kbps MP3", "VBR MP3", "MP3")


# Video podcasts (streaming)
VIDEO_QUALITIES = {"auto": "Auto (720p, less on slow connections)", "360": "360p (saves data)", "480": "480p",
                   "720": "720p (HD)", "1080": "1080p (Full HD)"}
DEFAULT_VIDEO_QUALITY = "auto"


def video_height(quality):
    return {"360": 360, "480": 480, "720": 720, "1080": 1080}.get(str(quality), 720)

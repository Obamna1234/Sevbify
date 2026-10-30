"""A song that isn't on this computer (from Radio or online search).

It looks like a local Song to the rest of the app (title, artist, artwork,
duration, key) so it can sit in the queue, the queue panel and playlists.
How it plays is decided when it starts:
  1. a full-length stream the source permits (Jamendo, Internet Archive), or
  2. with Settings -> "Play full songs" on: the full song found on Bandcamp/YouTube (core/streamer.py), or
  3. the 30-second preview (Deezer).
"""
from core.paths import PLACEHOLDER_IMAGE
from .models import OnlineTrack


class RemoteSong:
    is_remote = True
    file_path = ""
    stream_full = True           # set from Settings by the main window: play full songs instead of previews

    def __init__(self, track: OnlineTrack):
        self.track = track
        self.title = track.title
        self.artist = track.artist
        self.album = track.album or ""
        self.duration = track.duration_ms
        self.album_cover_path = PLACEHOLDER_IMAGE    # replaced once the cover is downloaded
        self.key = "remote:" + track.key

    # Never treated as a missing local file; playback checks is_remote first.
    @property
    def exists(self):
        return False

    @property
    def playable_url(self):
        return self.track.stream_url or self.track.preview_url

    @property
    def is_preview(self):
        """True when this song will play as a 30-second preview."""
        return not self.track.stream_url and bool(self.track.preview_url) and not RemoteSong.stream_full

    def matches(self, query: str) -> bool:
        from core.models import fold
        haystack = fold(f"{self.title} {self.artist} {self.album}")
        return all(word in haystack for word in fold(query).split())

    def __eq__(self, other):
        return getattr(other, "key", None) == self.key

    def __hash__(self):
        return hash(self.key)

    def __repr__(self):
        return f"RemoteSong({self.artist!r} - {self.title!r})"

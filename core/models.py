"""Data models: Song and Playlist. No Qt imports here, so these can be reused
by a future mobile/other front end."""
import os
import re

from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.wave import WAVE
from mutagen.oggvorbis import OggVorbis
from PIL import Image

from . import paths as _paths
from .paths import PLACEHOLDER_IMAGE, ASSETS_FOLDER, normalise_path

SUPPORTED_EXTENSIONS = ('.mp3', '.wav', '.flac', '.ogg', '.m4a')


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:"*?<>|]', "_", name)[:200]


def format_time(ms: int) -> str:
    """Milliseconds as Spotify shows them: 3:07, or 1:02:07 for an hour or more."""
    seconds = max(0, int(ms)) // 1000
    hrs, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs}:{mins:02d}:{secs:02d}" if hrs else f"{mins}:{secs:02d}"


def format_total(ms: int) -> str:
    """Playlist totals the way Spotify's desktop app writes them: 'about 1 hr 4 min' or '23 min 5 sec'."""
    seconds = max(0, int(ms)) // 1000
    hrs, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    if hrs:
        return f"about {hrs} hr {mins} min"
    return f"{mins} min {secs} sec"


class Song:
    """A local audio file and its metadata.

    Two Song objects are equal when they refer to the same file, so the same
    track found by two scans is treated as one track.
    """

    def __init__(self, file_path: str):
        self.file_path = str(file_path)
        self.key = normalise_path(self.file_path)
        self.title = os.path.splitext(os.path.basename(self.file_path))[0]
        self.artist = "Unknown Artist"
        self.album = "Unknown Album"
        self.duration = 0
        self.album_cover_path = PLACEHOLDER_IMAGE

        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = os.path.join(ASSETS_FOLDER, f"{base_name}{ext}")
            if os.path.exists(candidate):
                self.album_cover_path = candidate
                break

        if self.exists:
            self._extract_metadata()

    def __eq__(self, other):
        return isinstance(other, Song) and other.key == self.key

    def __hash__(self):
        return hash(self.key)

    def __repr__(self):
        return f"Song({self.title!r})"

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.file_path)

    def matches(self, query: str) -> bool:
        """True if every word of the query appears in title, artist or album."""
        haystack = f"{self.title} {self.artist} {self.album}".casefold()
        return all(word in haystack for word in query.casefold().split())

    def _extract_metadata(self):
        try:
            audio = MutagenFile(self.file_path)
            # NB: "audio is not None" - a file with no tags is falsy but still valid.
            if audio is not None and hasattr(audio.info, 'length'):
                self.duration = int(audio.info.length * 1000)

            # WAV files carry ID3 tags, so they share the MP3 tag names.
            if isinstance(audio, (MP3, WAVE)) and audio.tags:
                self.title = str(audio.tags.get('TIT2', [self.title])[0])
                self.artist = str(audio.tags.get('TPE1', [self.artist])[0])
                self.album = str(audio.tags.get('TALB', [self.album])[0])
            elif isinstance(audio, (FLAC, OggVorbis)) and audio.tags:
                self.title = audio.tags.get('title', [self.title])[0]
                self.artist = audio.tags.get('artist', [self.artist])[0]
                self.album = audio.tags.get('album', [self.album])[0]
            elif isinstance(audio, MP4) and audio.tags:
                self.title = audio.tags.get('\xa9nam', [self.title])[0]
                self.artist = audio.tags.get('\xa9ART', [self.artist])[0]
                self.album = audio.tags.get('\xa9alb', [self.album])[0]

            if self.album_cover_path == PLACEHOLDER_IMAGE:
                self._extract_album_art(audio)
        except Exception as e:
            print(f"Metadata error for {self.file_path}: {e}")

    def _extract_album_art(self, audio):
        try:
            image_data = None
            if isinstance(audio, (MP3, WAVE)) and audio.tags:
                for tag in audio.tags.values():
                    if hasattr(tag, 'FrameID') and tag.FrameID == 'APIC':
                        image_data = tag.data
                        break
            elif isinstance(audio, (FLAC, OggVorbis)) and hasattr(audio, 'pictures') and audio.pictures:
                image_data = audio.pictures[0].data
            elif isinstance(audio, MP4) and audio.tags and 'covr' in audio.tags:
                image_data = audio.tags['covr'][0]

            if image_data:
                filename = sanitize_filename(f"{self.title}_{self.artist}.png")
                path = os.path.join(_paths.ALBUM_CACHE, filename)
                if not os.path.exists(path):
                    with open(path, "wb") as f:
                        f.write(image_data)
                self.album_cover_path = path
        except Exception as e:
            print(f"Album art error: {e}")


class Playlist:
    def __init__(self, name: str, folder: str = "", created: float = 0.0, last_played: float = 0.0):
        import time
        self.name = name
        self.songs = []
        self.cover_path = PLACEHOLDER_IMAGE
        self.folder = folder                    # name of the Your Library folder it's in ("" = none)
        self.custom_cover = ""                  # a picture you chose (or the imported playlist's cover)
        self.created = created or time.time()   # for "Recently added" sorting
        self.last_played = last_played          # for "Recents" sorting (played or opened)
        self.origin = ""                        # "" made in Sevbify, or imported: spotify / apple / youtube / file

    def add_song(self, song: Song):
        self.songs.append(song)

    @property
    def total_duration(self) -> int:
        return sum(s.duration for s in self.songs)

    def generate_cover(self):
        if self.custom_cover and os.path.exists(self.custom_cover):
            self.cover_path = self.custom_cover
            return self.cover_path
        # Spotify's rule: the first 4 different albums' covers; fewer than 4 → the first song's cover alone.
        from core.playlist_cover import choose
        covers = [c for c in choose(self.songs) if os.path.isfile(c)]
        if not covers:
            self.cover_path = PLACEHOLDER_IMAGE
            return self.cover_path
        if len(covers) < 4:
            self.cover_path = covers[0]
            return self.cover_path
        self.cover_path = self.create_album_collage(covers)
        return self.cover_path

    def create_album_collage(self, paths):
        tile = 320
        collage = Image.new('RGB', (tile * 2, tile * 2), '#181818')
        pos = [(0, 0), (tile, 0), (0, tile), (tile, tile)]

        for i, p in enumerate(paths[:4]):
            try:
                with Image.open(p) as img:
                    collage.paste(img.convert('RGB').resize((tile, tile), Image.Resampling.LANCZOS), pos[i])
            except Exception as e:
                print(f"Collage image error for {p}: {e}")

        fname = os.path.join(_paths.ALBUM_CACHE, sanitize_filename(f"{self.name}_cover.png"))
        try:
            collage.save(fname)
        except Exception as e:
            print(f"Could not save playlist cover {fname}: {e}")
            return PLACEHOLDER_IMAGE
        return fname

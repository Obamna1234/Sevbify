"""Which covers make a playlist's picture, like Spotify (no UI code; shared by Windows and Android).

Spotify (as observed; it isn't documented): a playlist you haven't given a picture shows the covers of the
first four *different* albums in the playlist's own order as a 2x2 grid (top-left, top-right, bottom-left,
bottom-right). With fewer than four different albums it shows the first song's cover on its own. Songs you
haven't downloaded count too (their cover comes from the web), and the picture follows when you reorder songs.
"""

PLACEHOLDERS = ("placeholder",)


def _album_key(song):
    album = (getattr(song, "album", "") or "").strip().casefold()
    artist = (getattr(song, "artist", "") or "").strip().casefold()
    if album and album != "unknown album":
        return ("album", album, artist)
    return ("cover", cover_of(song))            # no album name: different pictures count as different albums


def cover_of(song):
    """The song's cover: the local picture if there is one, else its cover on the web ("" = none yet)."""
    for attr in ("album_cover_path", "art", "local_art", "cover_url"):
        value = getattr(song, attr, "") or ""
        if value and not any(p in value.lower() for p in PLACEHOLDERS):
            return value
    track = getattr(song, "track", None)
    if track is not None and getattr(track, "cover_url", ""):
        return track.cover_url
    return ""


def choose(songs):
    """1 or 4 cover pictures (local paths or web links) for a playlist, Spotify's way; [] when none."""
    seen, picks = set(), []
    first = ""
    for s in songs:
        cover = cover_of(s)
        if not cover:
            continue
        first = first or cover
        key = _album_key(s)
        if key in seen:
            continue
        seen.add(key)
        picks.append(cover)
        if len(picks) == 4:
            return picks
    return [first] if first else []

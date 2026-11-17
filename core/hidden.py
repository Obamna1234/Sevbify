"""Hide song / Don't play this artist (like Spotify): hidden songs and artists are skipped wherever music plays on
its own (playlists, albums, radio, mixes, autoplay), and left out of made-for-you mixes. A song you pick yourself
still plays. Everything stays on this device. Settings → Hidden songs and artists lists them with an on/off switch
each, so anything hidden by accident is one tap from coming back.

Stored in the user's data as two lists of small dicts:
  hidden_songs:   [{"key": "artist|title", "artist": "...", "title": "...", "on": True}]
  hidden_artists: [{"key": "artist", "artist": "...", "on": True}]
"on": False keeps the entry in the list (so it can be switched back) without hiding anything.
"""
import re
import unicodedata

MAX_ENTRIES = 2000


def _norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).casefold()
    return " ".join(re.findall(r"\w+", s))


def song_key(artist, title):
    return _norm(artist) + "|" + _norm(title)


def artist_key(artist):
    return _norm(artist)


def _clean(entries, kind):
    """Only well-formed entries (from a profile file, or an older version) are kept."""
    out, seen = [], set()
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        artist = str(e.get("artist") or "")[:200]
        title = str(e.get("title") or "")[:300]
        key = song_key(artist, title) if kind == "song" else artist_key(artist)
        if not key.strip("|") or key in seen:
            continue
        seen.add(key)
        item = {"key": key, "artist": artist, "on": bool(e.get("on", True))}
        if kind == "song":
            item["title"] = title
        out.append(item)
    return out[-MAX_ENTRIES:]


class Hidden:
    """The hidden lists of one user (UserData has hidden_songs / hidden_artists)."""

    def __init__(self, user_data):
        self.ud = user_data
        self.ud.hidden_songs = _clean(getattr(user_data, "hidden_songs", []), "song")
        self.ud.hidden_artists = _clean(getattr(user_data, "hidden_artists", []), "artist")
        self._rebuild()

    def _rebuild(self):
        self._songs = {e["key"] for e in self.ud.hidden_songs if e["on"]}
        self._artists = {e["key"] for e in self.ud.hidden_artists if e["on"]}

    # --- asking ---------------------------------------------------------------------------------------------
    def is_hidden(self, song):
        artist, title = getattr(song, "artist", ""), getattr(song, "title", "")
        if not artist and not title:
            return False
        if artist_key(artist) in self._artists:
            return True
        # A song with several artists ("A, B" / "A feat. B") is hidden if any of them is.
        for part in re.split(r",|&| feat\.? | ft\.? | with | x ", str(artist or ""), flags=re.I):
            if artist_key(part) and artist_key(part) in self._artists:
                return True
        return song_key(artist, title) in self._songs

    def song_hidden(self, artist, title):
        return song_key(artist, title) in self._songs

    def artist_hidden(self, artist):
        return artist_key(artist) in self._artists

    def keep(self, songs):
        """The songs that aren't hidden (for mixes, radio and autoplay)."""
        return [s for s in songs if not self.is_hidden(s)]

    # --- changing -------------------------------------------------------------------------------------------
    def _set(self, entries, key, on, make):
        for e in entries:
            if e["key"] == key:
                e["on"] = on
                break
        else:
            if not on:
                return
            entries.append(make())
            del entries[:-MAX_ENTRIES]
        self._rebuild()

    def hide_song(self, artist, title, on=True):
        key = song_key(artist, title)
        if key.strip("|"):
            self._set(self.ud.hidden_songs, key, on,
                      lambda: {"key": key, "artist": str(artist)[:200], "title": str(title)[:300], "on": True})

    def hide_artist(self, artist, on=True):
        key = artist_key(artist)
        if key:
            self._set(self.ud.hidden_artists, key, on, lambda: {"key": key, "artist": str(artist)[:200], "on": True})

    def remove(self, kind, key):
        entries = self.ud.hidden_songs if kind == "song" else self.ud.hidden_artists
        entries[:] = [e for e in entries if e["key"] != key]
        self._rebuild()

    def entries(self):
        """For Settings: [("song"|"artist", entry)], newest first."""
        return ([("artist", e) for e in reversed(self.ud.hidden_artists)]
                + [("song", e) for e in reversed(self.ud.hidden_songs)])

    def count(self):
        return len(self._songs) + len(self._artists)

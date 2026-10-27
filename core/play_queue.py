"""What plays next: the play queue, shuffle, repeat and recently played.

No Qt or VLC code here, so it can be tested on its own and reused by a
future mobile app.

Terms (same as Spotify):
- context:      the list the music came from (library, a playlist, search
                results, a radio station). Shown as "Next from: <source>".
- user queue:   songs the user picked with "Add to queue". They play next,
                before the context continues. Shown as "Next in queue".
- shuffle:      plays the context in random order (current song stays).
- repeat:       "off" (stop at the end), "all" (start again), "one" (repeat
                the current song).
"""
import random
from collections import deque

REPEAT_MODES = ("off", "all", "one")
RECENT_LIMIT = 50


class PlayQueue:
    def __init__(self, rng=None):
        self.items = []          # context in play order (shuffled if shuffle is on)
        self.original = []       # context in its original order
        self.index = 0
        self.source_name = ""
        self.user_queue = []
        self.shuffle = False
        self.repeat = "off"
        self.recent = deque(maxlen=RECENT_LIMIT)
        self._rng = rng or random.Random()

    # ------------------------------------------------------------------
    @property
    def current(self):
        if 0 <= self.index < len(self.items):
            return self.items[self.index]
        return None

    def set_context(self, songs, start_song, source_name=""):
        """Start playing start_song from the given list of songs."""
        self.original = list(songs)
        self.source_name = source_name
        if start_song not in self.original:
            self.original.insert(0, start_song)
        if self.shuffle:
            self.items = self._shuffled_with_first(start_song)
            self.index = 0
        else:
            self.items = list(self.original)
            self.index = self.items.index(start_song)

    def replace_items(self, songs):
        """Replace the context without changing shuffle state (used after rescans)."""
        self.items = list(songs)
        self.original = list(songs)
        self.index = min(self.index, max(0, len(self.items) - 1))

    def _shuffled_with_first(self, first):
        rest = [s for s in self.original if s != first]
        self._rng.shuffle(rest)
        return [first] + rest

    # ------------------------------------------------------------------
    def upcoming(self, limit=100):
        """(user_queue, context_upcoming) as shown in the queue panel."""
        ctx = self.items[self.index + 1:]
        if self.repeat == "all" and len(ctx) < limit:
            ctx = ctx + self.items[: self.index + 1]
        return list(self.user_queue), ctx[: max(0, limit - len(self.user_queue))]

    def advance(self, auto=True):
        """Move to the next song and return it, or None if playback should stop.

        auto=True means the previous song finished on its own (repeat rules
        apply). auto=False means the user pressed Next (always moves on).
        """
        if not self.items and not self.user_queue:
            return None
        if auto and self.repeat == "one" and self.current is not None:
            return self.current
        if self.user_queue:
            song = self.user_queue.pop(0)
            self.items.insert(self.index + 1, song)
            self.index += 1
            return song
        if self.index + 1 < len(self.items):
            self.index += 1
        elif self.repeat == "all" or not auto:
            if self.shuffle and len(self.items) > 1:
                # New random order for the next round, like Spotify.
                self.items = self._shuffled_with_first(self.items[0])
                self._rng.shuffle(self.items)
            self.index = 0
        else:
            return None
        return self.current

    def previous(self):
        if not self.items:
            return None
        self.index = (self.index - 1) % len(self.items)
        return self.current

    def jump_to_upcoming(self, position):
        """Play the song at `position` in the combined upcoming list."""
        if position < len(self.user_queue):
            song = self.user_queue.pop(position)
            self.items.insert(self.index + 1, song)
            self.index += 1
            return song
        ctx_pos = position - len(self.user_queue)
        target = self.index + 1 + ctx_pos
        if target >= len(self.items) and self.repeat == "all" and self.items:
            target %= len(self.items)
        if 0 <= target < len(self.items):
            self.index = target
            return self.current
        return None

    # ------------------------------------------------------------------
    def add_to_queue(self, song):
        self.user_queue.append(song)

    def remove_from_user_queue(self, position):
        if 0 <= position < len(self.user_queue):
            del self.user_queue[position]

    def set_shuffle(self, on: bool):
        if on == self.shuffle:
            return
        self.shuffle = on
        current = self.current
        if current is None:
            return
        if on:
            self.items = self._shuffled_with_first(current)
            self.index = 0
        else:
            if current in self.original:
                self.items = list(self.original)
                self.index = self.items.index(current)
            else:
                self.items = [current] + list(self.original)
                self.index = 0

    def cycle_repeat(self):
        self.repeat = REPEAT_MODES[(REPEAT_MODES.index(self.repeat) + 1) % len(REPEAT_MODES)]
        return self.repeat

    # ------------------------------------------------------------------
    def record_played(self, song):
        if song in self.recent:
            self.recent.remove(song)
        self.recent.appendleft(song)

    def rebind(self, by_key):
        """After a library rescan, point everything at the fresh Song objects."""
        fix = lambda seq: [by_key.get(s.key, s) for s in seq]
        self.items = fix(self.items)
        self.original = fix(self.original)
        self.user_queue = fix(self.user_queue)
        self.recent = deque(fix(self.recent), maxlen=RECENT_LIMIT)

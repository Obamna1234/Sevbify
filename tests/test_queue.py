"""Queue, shuffle, repeat and recently played. Run: python -m pytest tests -v"""
import random

from conftest import wait_until, make_wav


class S:
    """Minimal stand-in for Song (PlayQueue only needs equality and .key)."""
    def __init__(self, n):
        self.key = n
        self.title = n

    def __eq__(self, o):
        return isinstance(o, S) and o.key == self.key

    def __hash__(self):
        return hash(self.key)

    def __repr__(self):
        return self.key


def songs(n=5):
    return [S(f"s{i}") for i in range(n)]


# ------------------------------------------------------------ PlayQueue logic
def test_repeat_off_stops_at_end_but_next_button_wraps():
    from core.play_queue import PlayQueue
    q = PlayQueue(); L = songs(3)
    q.set_context(L, L[2], "Lib")
    assert q.advance(auto=True) is None           # song finished, nothing after it
    assert q.advance(auto=False) == L[0]          # pressing Next wraps around


def test_repeat_all_and_one():
    from core.play_queue import PlayQueue
    q = PlayQueue(); L = songs(3)
    q.set_context(L, L[2], "Lib")
    q.repeat = "all"
    assert q.advance(auto=True) == L[0]
    q.repeat = "one"
    assert q.advance(auto=True) == L[0]           # same song again
    assert q.advance(auto=False) == L[1]          # Next still moves on
    assert q.cycle_repeat() == "off"


def test_user_queue_plays_before_context_then_context_continues():
    from core.play_queue import PlayQueue
    q = PlayQueue(); L = songs(4); extra = S("extra")
    q.set_context(L, L[0], "Lib")
    q.add_to_queue(extra)
    user, ctx = q.upcoming()
    assert user == [extra] and ctx[0] == L[1]
    assert q.advance() == extra
    assert q.advance() == L[1]


def test_shuffle_keeps_current_and_all_songs_and_unshuffle_restores_order():
    from core.play_queue import PlayQueue
    q = PlayQueue(rng=random.Random(1)); L = songs(10)
    q.set_context(L, L[4], "Lib")
    q.set_shuffle(True)
    assert q.current == L[4] and q.index == 0
    assert sorted(x.key for x in q.items) == sorted(x.key for x in L)
    assert q.items != L
    q.advance(auto=False); now = q.current
    q.set_shuffle(False)
    assert q.items == L and q.current == now


def test_shuffle_on_before_choosing_a_song():
    from core.play_queue import PlayQueue
    q = PlayQueue(rng=random.Random(2)); L = songs(6)
    q.shuffle = True
    q.set_context(L, L[3], "Lib")
    assert q.current == L[3] and len(q.items) == 6


def test_jump_to_upcoming_and_recent_history():
    from core.play_queue import PlayQueue
    q = PlayQueue(); L = songs(6)
    q.set_context(L, L[0], "Lib")
    q.add_to_queue(S("x"))
    assert q.jump_to_upcoming(2) == L[2]          # pos 0 = x, pos 1 = L1, pos 2 = L2
    for s in (L[0], L[1], L[0]):
        q.record_played(s)
    assert list(q.recent) == [L[0], L[1]]         # no duplicates, newest first


# ------------------------------------------------------------- in the window
def test_queue_panel_shows_now_playing_and_next_from(window, qapp):
    window.set_right_panel("queue")
    window.play_song(window.songs[0], queue=window.songs, source="Your Songs")
    texts = [lbl.text() for lbl in window.queue_panel.scroll.widget().findChildren(type(window.song_info))]
    assert "Now playing" in texts
    assert "Next from: Your Songs" in texts
    assert "02 - second" in texts
    assert window.queue_btn.toolTip() == "Queue"


def test_add_to_queue_from_menu_plays_next(window, qapp):
    window.play_song(window.songs[0], queue=window.songs, source="Your Songs")
    menu = window.build_song_menu(window.songs[2], queue=window.songs)
    next(a for a in menu.actions() if "Add to queue" in a.text()).trigger()
    window.next_song()
    assert window.current_song is window.songs[2]
    window.next_song()
    assert window.current_song is window.songs[1]   # back to the context


def test_shuffle_repeat_and_panel_saved_across_restart(open_window, audio_dir, data_dir):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    w.toggle_shuffle()
    w.cycle_repeat(); w.cycle_repeat()              # off -> all -> one
    w.set_right_panel("queue")
    w.play_song(w.songs[1])
    w.close()
    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    assert w2.pq.shuffle and w2.pq.repeat == "one"
    assert not w2.right_panel.isHidden()
    assert [s.title for s in w2.pq.recent][:1] == ["02 - second"]


def test_end_of_queue_stops_with_repeat_off(window, qapp):
    window.play_song(window.songs[2], queue=window.songs)
    assert wait_until(qapp, lambda: window._reached_playing)
    assert wait_until(qapp, lambda: window.play_btn.text() == "▶️", timeout=8)
    assert window.current_song is window.songs[2]

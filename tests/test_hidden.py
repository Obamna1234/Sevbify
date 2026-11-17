"""Hide song / Don't play this artist: skipped when music plays by itself, listed in Settings to undo."""
from core.hidden import Hidden
from core.play_queue import PlayQueue
from core.storage import UserData


class S:
    def __init__(self, artist, title):
        self.artist, self.title = artist, title

    def __repr__(self):
        return self.title


def test_hidden_songs_and_artists_are_skipped_but_a_queued_pick_plays():
    ud = UserData()
    h = Hidden(ud)
    songs = [S("Chris Zabriskie", "Candlepower"), S("Kevin MacLeod", "Sneaky Snitch"), S("Kai Engel", "Downfall"),
             S("Kevin MacLeod feat. Someone", "Monkeys"), S("Jahzzar", "Siesta")]
    h.hide_song("Kai Engel", "DOWNFALL")                      # case and spacing don't matter
    h.hide_artist("kevin macleod")
    q = PlayQueue()
    q.is_hidden = h.is_hidden
    q.set_context(songs, songs[0])
    assert q.advance() is songs[4]                            # both Kevin MacLeod songs and Downfall skipped
    q.add_to_queue(songs[1])
    assert q.advance() is songs[1]                            # you queued it yourself: it plays
    h.hide_artist("Kevin MacLeod", on=False)                  # switched off in Settings
    assert not h.is_hidden(songs[1]) and h.is_hidden(songs[2])
    assert [k for k, _ in h.entries()] == ["artist", "song"] and h.count() == 1


def test_everything_hidden_stops_instead_of_looping():
    ud = UserData()
    h = Hidden(ud)
    songs = [S("A", "1"), S("B", "2"), S("B", "3")]
    h.hide_artist("B")
    q = PlayQueue()
    q.is_hidden = h.is_hidden
    q.set_context(songs, songs[0])
    assert q.advance(auto=True) is None


def test_hidden_lists_survive_saving_and_bad_data_is_dropped(tmp_path):
    from core.storage import Storage
    st = Storage(str(tmp_path))
    ud = st.load()
    h = Hidden(ud)
    h.hide_song("Chris Zabriskie", "Candlepower")
    ud.hidden_artists.append({"artist": 123})                 # junk (from a hand-edited profile)
    ud.hidden_artists.append("not a dict")
    st.save(ud)
    back = st.load()
    assert [e["title"] for e in back.hidden_songs] == ["Candlepower"]
    assert all(isinstance(e, dict) and e["key"] for e in back.hidden_artists)


def test_menu_hide_note_and_settings_switch(window):
    from core.models import Song  # noqa: F401
    window._auto_answer_dialogs = True
    song = window.songs[0]
    window.hide_song(song)
    assert window.hidden.is_hidden(song) and window.user_data.hide_note_seen
    window.open_settings()
    key = f"hidden:song:{window.user_data.hidden_songs[0]['key']}"
    assert key in window.settings_page.controls
    window.settings_page.controls[key].setChecked(False)
    assert not window.hidden.is_hidden(song)
    window.hide_artist(song.artist)
    assert window.hidden.is_hidden(song)
    assert window._allowed([song]) == []

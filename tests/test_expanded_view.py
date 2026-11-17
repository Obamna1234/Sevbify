"""Spotify's expanded Now playing view, song credits and Exclude from your taste profile."""
from core import credits
from core.storage import UserData


class FakeNet:
    def get_json(self, url, params=None, ttl=0):
        if url.endswith("/recording"):
            return {"recordings": [{"id": "r1", "title": "Candlepower",
                                    "artist-credit": [{"artist": {"name": "Chris Zabriskie"}}]}]}
        if "/recording/r1" in url:
            return {"relations": [{"target-type": "artist", "type": "producer", "artist": {"name": "Chris Zabriskie"}},
                                  {"target-type": "work", "work": {"id": "w1"}}]}
        if "/work/w1" in url:
            return {"relations": [{"target-type": "artist", "type": "composer", "artist": {"name": "Chris Zabriskie"}}]}
        return {}


def test_credits_come_from_musicbrainz_and_are_never_guessed():
    people = credits.for_song(FakeNet(), "Chris Zabriskie", "Candlepower")
    assert people == [{"name": "Chris Zabriskie", "roles": ["Main artist", "Producer", "Composer"]}]
    assert credits.for_song(FakeNet(), "Someone Else", "Candlepower") == []


def test_expanded_view_opens_collapses_and_tilts(window, qapp):
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    window.show()
    window.play_song(window.songs[0], queue=window.songs)
    window.set_right_panel("nowplaying")
    window.now_playing_panel.expand_button.click()
    ev = window.expanded_view
    assert ev.isVisible() and not window.center_panel.isVisible() and not window.library_panel.isVisible()
    assert ev.song_title.text() == window.songs[0].title and ev.b_art.isChecked()
    assert not ev.b_canvas.isEnabled()                       # no Canvas video for this song
    c = ev.cover
    c.resize(400, 400)
    e = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(390, 200), QPointF(390, 200), Qt.MouseButton.NoButton,
                    Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    c.mouseMoveEvent(e)
    for _ in range(40):
        c._step()
    assert c.tilt()[1] > 5                                   # tilts towards the mouse
    ev.b_collapse.click()
    assert not ev.isVisible() and window.center_panel.isVisible()


def test_excluded_songs_dont_shape_mixes(window):
    song = window.songs[0]
    window.user_data.listens = [[song.artist, song.title, 1], ["Other", "Song", 2]]
    window.set_taste_excluded(song, True)
    assert window.is_taste_excluded(song)
    assert window.taste_listens() == [["Other", "Song", 2]]
    window.set_taste_excluded(song, False)
    assert len(window.taste_listens()) == 2
    assert UserData().taste_excluded == []

"""Made for you (Discover Weekly, Daily Mixes, Release Radar), made on this computer from your own listening."""
import datetime

from core import discovery
from core.online.models import OnlineTrack


class FakeDeezer:
    def find_artist(self, name):
        return {"id": name, "name": name}

    def related(self, aid, limit=10):
        return [{"id": f"{aid}-rel{i}", "name": f"{aid} Friend {i}"} for i in range(8)]

    def top_tracks(self, aid, limit=5):
        return [OnlineTrack(f"{aid} song {i}", str(aid).replace("-rel", " Friend ")) for i in range(limit)]

    def artist_albums(self, aid):
        return {"albums": [{"id": 1, "release_date": "2026-11-10", "title": "New"},
                           {"id": 2, "release_date": "2020-01-01", "title": "Old"}], "singles": []}

    def album_tracks(self, album):
        return [OnlineTrack(f"{album['title']} track", "x")]


class FakeOnline:
    deezer = FakeDeezer()

    def radio(self, artist, title="", limit=50, rng=None):
        return [OnlineTrack(f"r{i}", f"{artist} similar {i % 5}") for i in range(limit)]


def _listens(now):
    out = []
    for i in range(30):
        discovery.record(out, "Perturbator", f"Song {i}", now - i * 3600)
    for i in range(10):
        discovery.record(out, "Carpenter Brut", f"Track {i}", now - i * 7200)
    discovery.record(out, "Unknown Artist", "x", now)            # not counted
    return out


def test_history_counts_favourites_and_is_capped():
    now = datetime.datetime(2026, 11, 16).timestamp()
    listens = _listens(now)
    assert len(listens) == 40
    assert discovery.top_artists(listens, now=now)[:2] == ["Perturbator", "Carpenter Brut"]
    big = []
    for i in range(discovery.MAX_LISTENS + 10):
        discovery.record(big, "A", str(i), i)
    assert len(big) == discovery.MAX_LISTENS and big[-1][1] == str(discovery.MAX_LISTENS + 9)


def test_discover_weekly_is_new_music_stable_for_the_week():
    listens = _listens(datetime.datetime.now().timestamp())
    monday = datetime.date(2026, 11, 16)
    a = discovery.discover_weekly(FakeOnline(), listens, today=monday)
    b = discovery.discover_weekly(FakeOnline(), listens, today=monday + datetime.timedelta(days=3))
    assert a and [t.key for t in a] == [t.key for t in b]                  # same all week
    assert all("Friend" in t.artist for t in a)                            # not the artists you already play
    per = {}
    for t in a:
        per[t.artist] = per.get(t.artist, 0) + 1
    assert max(per.values()) <= 2 and len(a) <= 30


def test_daily_mixes_and_release_radar():
    listens = _listens(datetime.datetime.now().timestamp())
    mixes = discovery.daily_mixes(FakeOnline(), listens)
    assert [m["title"] for m in mixes] == ["Daily Mix 1", "Daily Mix 2"] and mixes[0]["artist"] == "Perturbator"
    rr = discovery.release_radar(FakeOnline(), listens, today=datetime.date(2026, 11, 16))
    assert rr and all(t.title == "New track" for t in rr)                  # only the recent release


def test_nothing_is_recorded_in_a_private_session(window):
    for s in window.songs:
        s.artist = "Perturbator"
    window.apply_settings({"private_session": True})
    before = len(window.user_data.listens)
    window.play_song(window.songs[0])
    assert len(window.user_data.listens) == before
    window.apply_settings({"private_session": False})
    window.play_song(window.songs[1])
    assert window.user_data.listens[-1][:2] == ["Perturbator", window.songs[1].title]


def test_daylist_follows_the_time_of_day_and_mood_mixes():
    import time
    from core import discovery
    from core.online.models import OnlineTrack

    class Online:
        class deezer:
            @staticmethod
            def search_playlists(q, limit=5):
                return [{"id": 1}]

            @staticmethod
            def playlist_tracks(pid, limit=100):
                return [OnlineTrack(f"Calm {i}", f"Band {i}") for i in range(15)]

        @staticmethod
        def radio(artist, title="", limit=60, rng=None):
            return [OnlineTrack(f"{artist} like {i}", f"Other {i}") for i in range(limit)]
    now = time.mktime((2026, 11, 17, 20, 0, 0, 0, 0, -1))           # a Tuesday evening
    evening = [["Kevin MacLeod", "Sneaky Snitch", now - 86400 + 60 * i] for i in range(5)]
    morning = [["Jahzzar", "Siesta", now - 86400 - 12 * 3600]] * 5
    dl = discovery.daylist(Online, evening + morning, now=now)
    assert dl["title"] == "daylist · Tuesday evening" and "Kevin MacLeod" in dl["subtitle"]
    assert all("Jahzzar" not in t.title for t in dl["tracks"])          # what you play at this hour
    assert discovery.daylist(Online, morning, now=now) is None
    mm = discovery.mood_mix(Online, "chill", evening)
    assert mm["title"] == "Chill Mix" and len(mm["tracks"]) >= 10

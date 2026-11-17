"""Smart downloads: songs you keep playing are downloaded for you."""
from core import smart_downloads as sd


def test_pick_most_played_not_downloaded_with_a_daily_limit():
    now = 2_000_000_000
    listens = [["A", "One", now - 100]] * 5 + [["B", "Two", now - 100]] * 3 + [["C", "Three", now - 100]] * 2 \
        + [["D", "Old", now - 40 * 86400]] * 9
    pool = [{"artist": a, "title": t} for a, t in (("A", "One"), ("B", "Two"), ("C", "Three"), ("D", "Old"), ("a", "one"))]
    got = sd.pick(listens, pool, lambda s: False, now=now)
    assert [s["title"] for s in got] == ["One", "Two"]                     # 3+ plays this month, most played first
    assert [s["title"] for s in sd.pick(listens, pool, lambda s: s["title"] == "One", now=now)] == ["Two"]
    assert sd.pick(listens, pool, lambda s: False, done_today=sd.PER_DAY, now=now) == []
    assert len(sd.pick(listens, pool, lambda s: False, done_today=sd.PER_DAY - 1, now=now)) == 1


def test_window_smart_downloads_only_when_turned_on(window, monkeypatch):
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    import time
    s = RemoteSong(OnlineTrack("Siesta", "Jahzzar", source="deezer", source_id="1"))
    window.create_playlist("Mine", [s])
    window.user_data.listens = [["Jahzzar", "Siesta", int(time.time())]] * 4
    window.user_data.download_notice_accepted = True
    asked = []
    monkeypatch.setattr(window.downloads, "request", lambda tracks, folder, source: asked.append(tracks) or len(tracks))
    assert window.smart_downloads_check(force=True) == []                  # off by default
    window.user_data.smart_downloads = True
    window.user_data.online_enabled = True
    got = window.smart_downloads_check(force=True)
    assert [x.title for x in got] == ["Siesta"] and asked and window.user_data.smart_dl_day.endswith(":1")

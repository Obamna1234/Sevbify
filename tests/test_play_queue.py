

def test_podcast_episodes_never_shuffle():
    from core.play_queue import PlayQueue
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    eps = [RemoteSong(OnlineTrack(f"Ep {i}", "Show", source="podcast", stream_url=f"https://e/{i}.mp3")) for i in range(8)]
    q = PlayQueue()
    q.set_shuffle(True) if hasattr(q, "set_shuffle") else None
    q.shuffle = True
    q.set_context(eps, eps[2], "Show")
    assert q.items == eps and q.current is eps[2]
    q.set_shuffle(False); q.set_shuffle(True)
    assert q.items == eps


def test_smart_shuffle_cycles_and_its_songs_leave_the_queue(window, qapp):
    from core.online.models import OnlineTrack
    window.online.radio = lambda artist, title="", limit=60, **k: [OnlineTrack(f"Rec {i}", "Other", preview_url=f"https://p/{i}.mp3") for i in range(6)]
    window.user_data.online_enabled = True
    for s in window.songs:
        s.artist = "Kevin MacLeod"
    window.play_song(window.songs[0], queue=window.songs * 3, source="Mix")
    window.pq.shuffle = False
    window._smart_shuffle = False
    window.toggle_shuffle()
    assert window.pq.shuffle and not window._smart_shuffle
    window.toggle_shuffle()                                   # → Smart Shuffle
    from conftest import wait_until
    assert wait_until(qapp, lambda: any(getattr(s, "_smart", False) for s in window.pq.items), 5)
    window.toggle_shuffle()                                   # → off: the recommended songs leave the queue
    assert not window.pq.shuffle and not any(getattr(s, "_smart", False) for s in window.pq.items[window.pq.index + 1:])

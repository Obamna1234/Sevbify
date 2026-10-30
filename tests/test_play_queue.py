

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

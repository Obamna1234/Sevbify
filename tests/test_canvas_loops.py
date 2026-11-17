"""Canvas from music videos: only the official video, a small silent clip, a cache that never grows past its limit."""
import os
import time

from core import canvas_loops as C

RESULTS = [
    {"title": "Monkeys Spinning Monkeys (Lyrics)", "channel": "Lyric Land", "duration": 125, "id": "aaaaaaaaaaa"},
    {"title": "Monkeys Spinning Monkeys - Kevin MacLeod (Live)", "channel": "x", "duration": 125, "id": "bbbbbbbbbbb"},
    {"title": "Kevin MacLeod - Monkeys Spinning Monkeys (Official Music Video)", "channel": "Some Channel",
     "duration": 126, "id": "ccccccccccc"},
]


def test_only_the_official_music_video_is_used():
    url = C.find_music_video(lambda q, n: RESULTS, "Kevin MacLeod", "Monkeys Spinning Monkeys")
    assert url == "https://www.youtube.com/watch?v=ccccccccccc"
    assert C.find_music_video(lambda q, n: RESULTS[:2], "Kevin MacLeod", "Monkeys Spinning Monkeys") == ""
    own = [{"title": "Candlepower", "channel": "Chris Zabriskie", "duration": 200, "id": "ddddddddddd"}]
    assert C.find_music_video(lambda q, n: own, "Chris Zabriskie", "Candlepower")          # the artist's own channel
    bad = [{"title": "Candlepower (Official Video)", "channel": "x", "duration": 200,
            "url": "https://evil.example/watch?v=ddddddddddd"}]
    assert C.find_music_video(lambda q, n: bad, "Chris Zabriskie", "Candlepower") == ""     # YouTube links only


def test_get_caches_and_misses_are_not_searched_again(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_misses", {})
    searched, cut = [], []

    def search(q, n):
        searched.append(q)
        return RESULTS

    def fake_cut(url, out, dur):
        cut.append(url)
        open(out, "wb").write(b"x" * 20_000)
        return out
    p = C.get(str(tmp_path), "Kevin MacLeod", "Monkeys Spinning Monkeys", search, 126, cut=fake_cut)
    assert p and os.path.isfile(p) and cut == ["https://www.youtube.com/watch?v=ccccccccccc"]
    assert C.get(str(tmp_path), "Kevin MacLeod", "Monkeys Spinning Monkeys", search, cut=fake_cut) == p
    assert len(searched) == 1                                  # second time: from the cache
    assert C.get(str(tmp_path), "Nobody", "Nothing", lambda q, n: [], cut=fake_cut) == ""
    assert C.get(str(tmp_path), "Nobody", "Nothing", search, cut=fake_cut) == ""   # a miss isn't retried today
    assert len(searched) == 1


def test_cache_never_grows_past_its_limit(tmp_path):
    folder = C.cache_dir(str(tmp_path))
    os.makedirs(folder)
    for i in range(5):
        p = os.path.join(folder, f"{i}.mp4")
        open(p, "wb").write(b"x" * 600_000)
        os.utime(p, (time.time() - 100 + i, time.time() - 100 + i))
    assert C.trim(str(tmp_path), 2) == 2                       # 3 MB -> under 2 MB: the two oldest go
    assert sorted(os.listdir(folder)) == ["2.mp4", "3.mp4", "4.mp4"]
    assert C.size_mb(str(tmp_path)) <= 2
    C.clear(str(tmp_path))
    assert C.size_mb(str(tmp_path)) == 0


def test_downloaded_songs_keep_their_clip_and_lose_it_with_the_song(tmp_path):
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x" * 20_000)
    song = tmp_path / "music" / "Kevin MacLeod - Monkeys.mp3"
    song.parent.mkdir()
    song.write_bytes(b"x")
    kept = C.keep_with_download(str(clip), str(song))
    assert kept.endswith(os.path.join("music", "canvas", "Kevin MacLeod - Monkeys.mp4")) and os.path.isfile(kept)
    from core.canvas import find_canvas

    class S:
        file_path, artist, title, is_remote = str(song), "Kevin MacLeod", "Monkeys", False
    assert find_canvas(S()) == kept                            # the app's Canvas finder sees it, offline too
    assert C.remove_with_song(str(song)) and not os.path.isfile(kept)


def test_settings_have_canvas_storage(window):
    window.open_settings()
    c = window.settings_page.controls
    assert "canvas_auto" in c and "canvas_cache_mb" in c and "canvas_keep_downloads" in c
    window.apply_settings({"canvas_cache_mb": 50})
    assert window.user_data.canvas_cache_mb == 50


def test_health_list_has_a_canvas_check():
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "health_check.py"),
               encoding="utf-8").read()
    assert "canvas_from_music_video" in src

"""Podcasts, audiobooks, video podcasts, Browse and the Home chips inside the window. No internet: fake answers;
audio links are handed to a stand-in for VLC, downloads write small local files."""
import os

import pytest

from conftest import make_wav, wait_until
from online_fixtures import FakeWeb, ROUTES as BASE_ROUTES, deezer_track
from test_podcasts import ROUTES as SHOW_ROUTES


@pytest.fixture
def win(window, tmp_path, monkeypatch):
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    routes = dict(BASE_ROUTES)
    routes.update(SHOW_ROUTES)
    routes["api.deezer.com/genre"] = {"data": [{"id": 0, "name": "All"},
                                               {"id": 152, "name": "Rock", "picture_xl": "https://img/rock.jpg"},
                                               {"id": 113, "name": "Dance", "picture_xl": "https://img/dance.jpg"}]}
    routes["api.deezer.com/chart/152/tracks"] = {"data": [deezer_track(30, "Song 2", "Blur", 70),
                                                          deezer_track(31, "Plug In Baby", "Muse", 71)]}
    window.net = NetClient(str(tmp_path / "c"), enabled=lambda: True, opener=FakeWeb(routes))
    window.online = OnlineMusic(window.net)
    window.user_data.download_notice_accepted = True
    played = []
    monkeypatch.setattr(window, "_play_media", lambda location, headers=None: played.append(location) or True)
    window.played = played
    return window


def test_podcasts_page_search_open_follow_and_play(win, qapp):
    from core import podcasts
    win.show_podcasts()
    assert win.stack.currentWidget() is win.podcasts_page
    assert wait_until(qapp, lambda: win._top_shows and win._top_shows[0].title == "Top Show")
    win.search_podcasts("fin vs history")
    assert wait_until(qapp, lambda: win._podcast_results and win._podcast_results[0].title == "Fin vs History")
    win.open_show(win._podcast_results[0])
    assert win.stack.currentWidget() is win.show_page
    assert wait_until(qapp, lambda: len(win.show_page.rows) == 2)
    assert win.show_page.follow_btn.text() == "Follow"
    win.show_page.follow_btn.click()
    assert [d["title"] for d in win.user_data.shows] == ["Fin vs History"]
    assert any(e["kind"] == "podcast" and e["title"] == "Fin vs History"
               for e in win.library_panel.entries())                       # in Your Library
    win.show_page.rows[0].play_btn.click()                                  # newest episode
    assert win.played[-1] == "https://cdn.example.com/ep2.m4a?x=1"
    assert win.pq.source_name == "Fin vs History" and len(win.pq.items) == 2


def test_episodes_continue_where_you_left_off(win, qapp):
    from core import podcasts
    win.open_show(podcasts.Show("Fin vs History", feed_url="https://feeds.example.com/fvh"))
    assert wait_until(qapp, lambda: len(win._show_ctx["items"]) == 2)
    ep = win._show_ctx["items"][1]
    win._remember_position(ep, 600_000)
    assert win.user_data.resume["podcast:ep-1"]["ms"] == 600_000
    win.play_item(ep)
    assert win._pending_resume == ("podcast:ep-1", 600_000)
    win._render_show()
    assert "35 min left" in [l.text() for l in win.show_page.rows[1].findChildren(type(win.song_info))][-1] \
        or any("35 min left" in l.text() for l in win.show_page.rows[1].findChildren(type(win.song_info)))
    win.item_finished(ep)                                                  # played to the end
    assert "podcast:ep-1" in win.user_data.finished and "podcast:ep-1" not in win.user_data.resume


def test_download_an_episode_and_play_it_offline(win, qapp, monkeypatch, audio_dir):
    from core import podcasts
    from pathlib import Path

    def fake_download(url, dest, progress=None, cancelled=lambda: False, chunk=0):
        make_wav(Path(dest), 0.3)
        return dest
    monkeypatch.setattr(win.net, "download", fake_download)
    win.open_show(podcasts.Show("Fin vs History", feed_url="https://feeds.example.com/fvh"))
    assert wait_until(qapp, lambda: len(win._show_ctx["items"]) == 2)
    newest = win._show_ctx["items"][0]
    assert win.download_items([newest]) == 1
    assert wait_until(qapp, lambda: "podcast:ep-2" in win.user_data.offline, 10)
    path = win.user_data.offline["podcast:ep-2"]
    assert os.path.basename(path) == "2026-10-25 - Newest episode Vikings.m4a"
    pods = os.path.dirname(os.path.dirname(path))
    assert not os.path.exists(os.path.join(pods, ".sevbify-noscan"))       # no hidden marker file any more
    assert os.path.normcase(os.path.abspath(pods)) in {os.path.normcase(os.path.abspath(f))
                                                       for f in win.not_music_folders()}
    win.rescan_library()
    assert wait_until(qapp, lambda: not win._rescan_pending)
    assert not any("Vikings" in s.file_path for s in win.songs)
    win.user_data.online_enabled = False                                    # offline: plays the file
    win.play_item(newest)
    assert win.played[-1] == path
    win.remove_item_download(newest)
    assert not os.path.exists(path) and "podcast:ep-2" not in win.user_data.offline


def test_audiobooks_page_book_and_chapters(win, qapp):
    win.show_audiobooks()
    assert wait_until(qapp, lambda: win._popular_books and win._popular_books[0].title == "Pride and Prejudice")
    win.open_book(win._popular_books[0])
    assert wait_until(qapp, lambda: len(win.show_page.rows) == 2)
    win.show_page.follow_btn.click()                                        # Add to Your Library
    assert win.user_data.books[0]["identifier"] == "pride_prejudice_librivox"
    assert any(e["kind"] == "audiobook" for e in win.library_panel.entries())
    first = win._show_ctx["items"][0]
    win._mark_finished(first, True)
    win._play_show()                                                        # carries on at chapter 2
    assert win.current_song is win._show_ctx["items"][1]
    assert win.played[-1].endswith("prideandprejudice_02_austen_64kb.mp3")


def test_youtube_video_podcast_watch_and_switch_to_audio(win, qapp, monkeypatch):
    from core import podcasts
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    song = RemoteSong(OnlineTrack("The Vikings", "Fin vs History", album="Fin vs History", source="youtube",
                                  source_id="abc123", page_url="https://www.youtube.com/watch?v=abc123",
                                  youtube_id="abc123", duration_ms=3_600_000))
    asked = []
    monkeypatch.setattr(podcasts, "youtube_stream",
                        lambda page, video=False, extract=None: asked.append(video) or
                        ("https://video.example/v.mp4" if video else "https://audio.example/a.webm", {"User-Agent": "UA"}))
    shown = []
    monkeypatch.setattr(win.video_page, "play", lambda url, title, start_ms=0, volume=80: shown.append((url, start_ms)))
    monkeypatch.setattr(win.video_page, "position", lambda: 90_000)
    win.show_home()
    win.watch_item(song)
    assert wait_until(qapp, lambda: win.stack.currentWidget() is win.video_page)
    assert shown == [("https://video.example/v.mp4", 0)] and asked == [True]
    win._video_to_audio(90_000)                                             # "Listen as audio only"
    assert win.user_data.resume["youtube:abc123"]["ms"] == 90_000
    assert wait_until(qapp, lambda: win.played and win.played[-1] == "https://audio.example/a.webm")
    assert win._pending_resume == ("youtube:abc123", 90_000)


def test_browse_tiles_and_a_genre_page(win, qapp):
    from ui.shows_page import BrowseTile
    win.show_browse()
    assert win.stack.currentWidget() is win.search_page and win.browse_scroll.isVisibleTo(win.search_page)
    ok = wait_until(qapp, lambda: [t.title for t in win.browse_scroll.widget().findChildren(BrowseTile)]
                    == ["Podcasts", "Audiobooks", "Rock", "Dance"])
    assert ok, ([t.title for t in win.browse_scroll.widget().findChildren(BrowseTile)], win._genres)
    rock = next(t for t in win.browse_scroll.widget().findChildren(BrowseTile) if t.title == "Rock")
    rock.clicked.emit()
    assert wait_until(qapp, lambda: win.stack.currentWidget() is win.collection_page)
    assert [s.title for s in win.collection_table.songs_in_view()] == ["Song 2", "Plug In Baby"]
    win.search_input.setText("narc")
    assert not win.browse_scroll.isVisibleTo(win.search_page)               # typing hides Browse


def test_home_chips(win, qapp):
    win.user_data.shows = [{"title": "Fin vs History", "feed_url": "https://feeds.example.com/fvh"}]
    for chip in ("podcasts", "audiobooks", "music", "all"):
        win.set_home_chip(chip)
        qapp.processEvents()
    win.set_home_chip("podcasts")
    labels = [l.text() for l in win.home_scroll.widget().findChildren(type(win.song_info))]
    assert "Your shows" in labels
    assert wait_until(qapp, lambda: win._top_shows)

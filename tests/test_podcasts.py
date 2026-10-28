"""Podcasts (Apple directory + RSS feeds + YouTube channels) and free audiobooks (LibriVox via archive.org).
No internet: answers are fake ones shaped like each service's real replies."""
import time

import pytest

from online_fixtures import FakeWeb

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel>
  <title>Fin vs History</title>
  <link>https://example.com/fvh</link>
  <description><![CDATA[<p>History, <b>badly</b> told.</p>]]></description>
  <itunes:author>Fin Taylor</itunes:author>
  <itunes:image href="https://img.example.com/show.jpg"/>
  <item>
    <title>Older episode</title>
    <guid>ep-1</guid>
    <pubDate>Mon, 01 Sep 2025 10:00:00 +0000</pubDate>
    <enclosure url="https://cdn.example.com/ep1.mp3" type="audio/mpeg" length="1"/>
    <itunes:duration>45:30</itunes:duration>
    <description>First &amp; oldest</description>
  </item>
  <item>
    <title>Newest episode: Vikings</title>
    <guid>ep-2</guid>
    <pubDate>Sat, 25 Oct 2026 10:00:00 +0000</pubDate>
    <enclosure url="https://cdn.example.com/ep2.m4a?x=1" type="audio/mp4" length="1"/>
    <itunes:duration>3723</itunes:duration>
    <itunes:image href="https://img.example.com/ep2.jpg"/>
    <itunes:explicit>yes</itunes:explicit>
  </item>
  <item><title>No audio, skipped</title></item>
</channel>
</rss>"""

ROUTES = {
    "itunes.apple.com/search": {"results": [
        {"collectionName": "Fin vs History", "artistName": "Fin Taylor", "feedUrl": "https://feeds.example.com/fvh",
         "artworkUrl600": "https://img.example.com/show600.jpg", "collectionId": 111, "primaryGenreName": "History"},
        {"collectionName": "No feed", "artistName": "X"}]},
    "rss.applemarketingtools.com/api/v2/us/podcasts/top": {"feed": {"results": [
        {"id": "222", "name": "Top Show", "artistName": "Someone",
         "artworkUrl100": "https://img.example.com/top/100x100bb.png", "genres": [{"name": "Comedy"}]}]}},
    "itunes.apple.com/lookup": {"results": [{"collectionId": 222, "feedUrl": "https://feeds.example.com/fvh"}]},
    "feeds.example.com/fvh": FEED,
    "archive.org/advancedsearch.php": {"response": {"docs": [
        {"identifier": "pride_prejudice_librivox", "title": "Pride and Prejudice (LibriVox)", "creator": "Jane Austen",
         "downloads": 500000, "description": "<p>A classic.</p>"},
        {"title": "no id"}]}},
    "archive.org/metadata/pride_prejudice_librivox": {
        "metadata": {"title": "Pride and Prejudice", "creator": "Jane Austen", "description": "Read by volunteers."},
        "files": [
            {"name": "prideandprejudice_02_austen_64kb.mp3", "format": "64Kbps MP3", "title": "Chapter 2",
             "track": "2", "length": "10:05"},
            {"name": "prideandprejudice_01_austen_64kb.mp3", "format": "64Kbps MP3", "title": "Chapter 1",
             "track": "1", "length": "612.5"},
            {"name": "prideandprejudice_01_austen_128kb.mp3", "format": "128Kbps MP3", "title": "Chapter 1",
             "track": "1"},
            {"name": "cover.jpg", "format": "JPEG"}]},
}


@pytest.fixture
def net(tmp_path):
    from core.online.net import NetClient
    return NetClient(str(tmp_path / "cache"), enabled=lambda: True, opener=FakeWeb(ROUTES))


def test_search_and_top_shows(net):
    from core import podcasts
    found = podcasts.search(net, "fin vs history")
    assert [s.title for s in found] == ["Fin vs History"]           # shows without a public feed are left out
    assert found[0].feed_url == "https://feeds.example.com/fvh" and found[0].genre == "History"
    top = podcasts.top_shows(net)
    assert top[0].title == "Top Show" and top[0].image_url.endswith("600x600bb.png") and not top[0].feed_url
    assert podcasts.resolve_feed(net, top[0]).feed_url == "https://feeds.example.com/fvh"


def test_feed_is_read_newest_first(net):
    from core import podcasts
    show, eps = podcasts.fetch_show(net, podcasts.Show("Fin vs History", feed_url="https://feeds.example.com/fvh"))
    assert show.title == "Fin vs History" and show.author == "Fin Taylor"
    assert show.image_url == "https://img.example.com/show.jpg" and show.description == "History, badly told."
    assert [e.track.title for e in eps] == ["Newest episode: Vikings", "Older episode"]
    newest, older = eps
    assert newest.track.duration_ms == 3723000 and older.track.duration_ms == 2730000
    assert newest.track.cover_url == "https://img.example.com/ep2.jpg" and older.track.cover_url.endswith("show.jpg")
    assert newest.track.stream_url == newest.track.download_url == "https://cdn.example.com/ep2.m4a?x=1"
    assert newest.track.source == "podcast" and newest.track.explicit and newest.guid == "ep-2"
    assert older.description == "First & oldest"
    assert podcasts.episode_filename(newest) == "2026-10-25 - Newest episode Vikings.m4a"


def test_not_a_feed():
    from core import podcasts
    with pytest.raises(ValueError):
        podcasts.parse_feed("<html><body>hello</body></html>")
    with pytest.raises(ValueError):
        podcasts.parse_feed("not xml at all <")


def test_youtube_channels_as_video_podcasts():
    from core import podcasts
    assert podcasts.is_youtube_link("https://www.youtube.com/@FinvsHistory")
    assert podcasts.youtube_list_url("https://youtube.com/@FinvsHistory/featured") == \
        "https://www.youtube.com/@FinvsHistory/videos"
    assert not podcasts.is_youtube_link("https://example.com/feed.xml")
    seen = []
    info = {"channel": "Fin vs History", "uploader": "Fin vs History",
            "thumbnails": [{"url": "https://yt.example/small.jpg"}, {"url": "https://yt.example/big.jpg"}],
            "entries": [{"id": "abc123", "title": "The Vikings", "duration": 3600, "timestamp": 1761400000},
                        {"id": "def456", "title": "The Romans", "duration": 1800}]}
    show, eps = podcasts.fetch_youtube_channel("https://www.youtube.com/@FinvsHistory",
                                               extract=lambda u: seen.append(u) or info)
    assert seen == ["https://www.youtube.com/@FinvsHistory/videos"]
    assert show.kind == "youtube" and show.title == "Fin vs History" and show.image_url.endswith("big.jpg")
    assert eps[0].track.youtube_id == "abc123" and eps[0].track.page_url == "https://www.youtube.com/watch?v=abc123"
    assert eps[0].track.source == "youtube" and eps[0].track.duration_ms == 3600000


def test_audiobooks_search_and_chapters_in_order(net):
    from core import audiobooks
    books = audiobooks.popular(net)
    assert [b.title for b in books] == ["Pride and Prejudice"] and books[0].author == "Jane Austen"
    assert books[0].cover_url == "https://archive.org/services/img/pride_prejudice_librivox"
    assert audiobooks.search(net, "austen; DROP") and audiobooks.search(net, "!!!") == []
    book, chaps = audiobooks.chapters(net, books[0])
    assert [c.title for c in chaps] == ["Chapter 1", "Chapter 2"]          # in order, 64 kbps copies only
    assert chaps[0].duration_ms == 612500 and chaps[1].duration_ms == 605000
    assert chaps[0].stream_url == ("https://archive.org/download/pride_prejudice_librivox/"
                                   "prideandprejudice_01_austen_64kb.mp3")
    assert chaps[0].album == "Pride and Prejudice" and chaps[0].source == "audiobook"
    assert audiobooks.chapter_filename(1, chaps[0]) == "01 - Chapter 1.mp3"
    assert audiobooks.book_folder(book) == "Jane Austen - Pride and Prejudice"


def test_podcast_folders_are_not_scanned_as_music(tmp_path):
    from conftest import make_wav
    from core.library import scan_folders, remove_old_marker, OLD_NO_SCAN_MARKER
    music = tmp_path / "Music"
    (music / "Artist").mkdir(parents=True)
    make_wav(music / "Artist" / "song.wav", 0.2)
    (music / "Podcasts" / "Show").mkdir(parents=True)
    make_wav(music / "Podcasts" / "Show" / "episode.wav", 0.2)
    songs, problems = scan_folders([str(music)], skip=[str(music / "Podcasts")])
    assert [s.title for s in songs] == ["song"] and not problems
    # beta.6's hidden marker file is cleaned up; no new one is made
    (music / "Podcasts" / OLD_NO_SCAN_MARKER).write_text("Podcasts and audiobooks downloaded by Sevbify\n")
    remove_old_marker(str(music / "Podcasts"))
    assert not (music / "Podcasts" / OLD_NO_SCAN_MARKER).exists()


def test_youtube_source_note_uses_youtube_facts_not_names():
    from core.podcasts import Show, source_note, fetch_youtube_channel
    info = {"channel": "Fin vs History", "uploader": "Fin vs History", "channel_is_verified": True,
            "channel_follower_count": 812000, "entries": [{"id": "abc", "title": "Ep 1", "duration": 60}]}
    show, eps = fetch_youtube_channel("https://www.youtube.com/@FinvsHistory", extract=lambda u: info)
    assert show.verified and source_note(show).startswith("✓ Verified YouTube channel: Fin vs History · 812K")
    copy = dict(info, channel="Fin vs History Clips", channel_is_verified=False)
    show2, _ = fetch_youtube_channel("https://www.youtube.com/@fvhclips", extract=lambda u: copy)
    assert source_note(show2).startswith("⚠ Not verified by YouTube")
    assert "official feed" in source_note(Show("A Podcast", feed_url="https://feed"))

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


def test_search_puts_the_exact_show_first():
    from core.podcasts import Show, rank_shows
    shows = [Show("Friends Like Us"), Show("Bad Friends Reacts"), Show("Bad Friends"), Show("Good Friends, Bad Times")]
    assert [s.title for s in rank_shows("bad friends", shows)][:2] == ["Bad Friends", "Bad Friends Reacts"]
    shows = [Show("History Hit"), Show("Fin vs History", "Fin Taylor")]
    assert rank_shows("fin vs history", shows)[0].title == "Fin vs History"


def test_find_youtube_channel_only_accepts_the_shows_own_channel():
    from core.podcasts import find_youtube_channel
    entries = [{"channel": "Clips Daily", "channel_url": "https://www.youtube.com/@clips"},
               {"channel": "Bad Friends", "channel_url": "https://www.youtube.com/@BadFriends", "channel_is_verified": True},
               {"channel": "Bad Friends", "channel_url": "https://www.youtube.com/@BadFriends"}]
    show = find_youtube_channel("Bad Friends", "Bobby Lee", extract=lambda q: {"entries": entries})
    assert show.kind == "youtube" and show.feed_url == "https://www.youtube.com/@BadFriends" and show.verified
    assert find_youtube_channel("Some Quiet Show", extract=lambda q: {"entries": entries[:1]}) is None
    bad = [{"channel": "Bad Friends", "channel_url": "file:///C:/x.exe"}]
    assert find_youtube_channel("Bad Friends", extract=lambda q: {"entries": bad}) is None


def test_find_youtube_channel_falls_back_to_the_channel_of_a_matching_episode():
    from core.podcasts import find_youtube_channel
    calls = []

    def extract(q):
        calls.append(q)
        if q.startswith("ytsearch15"):          # nothing named like the show
            return {"entries": [{"channel": "Someone Else", "channel_url": "https://www.youtube.com/@else"}]}
        return {"entries": [
            {"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "Totally different video",
             "channel": "Wrong", "channel_url": "https://www.youtube.com/@wrong"},
            {"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "Episode 12: The Big Heist (Full Show)",
             "channel": "PowerfulHost", "channel_url": "https://www.youtube.com/@host", "channel_is_verified": True}]}
    show = find_youtube_channel("Heist Show", episode_title="The Big Heist", extract=extract)
    assert show and show.feed_url == "https://www.youtube.com/@host" and show.verified
    assert find_youtube_channel("Heist Show", extract=extract) is None                  # no episode given: as before
    assert find_youtube_channel("Heist Show", episode_title="Unrelated words here", extract=extract) is None


def test_find_youtube_episode_matches_title_and_length():
    from core import podcasts
    entries = {"entries": [
        {"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "Totally different video", "duration": 3200},
        {"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "The War of The Noses | Agincourt", "duration": 600},
        {"url": "https://www.youtube.com/watch?v=ccccccccccc", "title": "The War of The Noses | Agincourt (Fin vs History)", "duration": 3360},
    ]}
    got = podcasts.find_youtube_episode("Fin vs History", "The War of The Noses | Agincourt", 3365000,
                                        extract=lambda q: entries)
    assert got.endswith("ccccccccccc")
    assert podcasts.find_youtube_episode("Fin vs History", "Something nobody uploaded", 1000,
                                         extract=lambda q: entries) == ""


def test_find_youtube_episode_says_why_not():
    from core import podcasts
    url, note = podcasts.find_youtube_episode_ex(
        "Show", "Some Long Episode Title Here", 1000, extract=lambda q: {"entries": []})
    assert url == "" and "0 results" in note


def test_video_captions_lists_own_captions_then_the_automatic_one_in_the_videos_language():
    from core import podcasts
    yt = "https://www.youtube.com/api/timedtext?v=abc&lang={}&fmt=vtt"
    info = {"language": "en",
            "subtitles": {"es": [{"ext": "srv1", "url": yt.format("es")}, {"ext": "vtt", "url": yt.format("es"), "name": "Spanish"}],
                          "live_chat": [{"ext": "json", "url": "https://www.youtube.com/x"}]},
            "automatic_captions": {"en-orig": [{"ext": "vtt", "url": yt.format("en"), "name": "English (Original)"}],
                                   "fr": [{"ext": "vtt", "url": yt.format("fr")}],
                                   "es-orig": [{"ext": "vtt", "url": yt.format("es")}]}}
    caps = podcasts.video_captions(info)
    assert [(c["lang"], c["auto"]) for c in caps] == [("es", False), ("en-orig", True)]   # Spanish isn't doubled by an automatic one
    assert caps[0]["name"] == "Spanish" and caps[1]["name"].endswith("(automatic)")
    # only https links on YouTube itself are accepted
    bad = {"subtitles": {"en": [{"ext": "vtt", "url": "https://evil.example/x.vtt"}, {"ext": "vtt", "url": "http://www.youtube.com/x"}]}}
    assert podcasts.video_captions(bad) == [] and podcasts.video_captions({}) == []


def test_youtube_video_streams_carries_the_captions():
    from core import podcasts
    cap = [{"ext": "vtt", "url": "https://www.youtube.com/api/timedtext?x=1", "name": "English"}]
    info = {"requested_formats": [{"url": "https://v/1", "height": 720}, {"url": "https://a/1"}],
            "http_headers": {}, "subtitles": {"en": cap}}
    out = podcasts.youtube_video_streams("https://www.youtube.com/watch?v=aaaaaaaaaaa", extract=lambda u: info)
    assert out["video"] == "https://v/1" and [c["lang"] for c in out["captions"]] == ["en"]


def test_find_youtube_episode_second_search_and_one_part_of_the_title_is_enough():
    from core import podcasts
    asked = []

    def extract(q):
        asked.append(q)
        if q.count("|"):                                   # the long title finds nothing useful
            return {"entries": [{"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "Unrelated", "duration": 3000}]}
        return {"entries": [{"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb",
                             "title": "Stalin: Yalta & Last Days", "duration": 2800}]}
    url, note = podcasts.find_youtube_episode_ex(
        "Fin vs History", "Russian Humour Is Pushing People Into Canals | Stalin: Yalta & Last Days (Part 5)", 2820000, extract)
    assert url.endswith("bbbbbbbbbbb") and len(asked) == 2 and "|" not in asked[1]
    # nothing close in either search: no video, and the note counts both searches
    url, note = podcasts.find_youtube_episode_ex("Fin vs History", "A | B C D E", 0,
                                                 lambda q: {"entries": [{"url": "https://www.youtube.com/watch?v=ccccccccccc", "title": "Cats"}]})
    assert url == "" and "2 searches" in note


def test_find_youtube_channel_tries_a_few_recent_episodes_not_only_the_newest():
    from core.podcasts import find_youtube_channel
    asked = []

    def extract(q):
        asked.append(q)
        if q.startswith("ytsearch15"):
            return {"entries": []}
        if "Brand New Episode" in q:                       # the newest isn't on YouTube yet
            return {"entries": [{"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "Cats"}]}
        return {"entries": [{"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "Stalin Yalta Last Days",
                             "channel": "Fin vs History", "channel_url": "https://www.youtube.com/@finvshistory"}]}
    show = find_youtube_channel("Show", episode_title="Brand New Episode",
                                episode_titles=["Stalin Yalta Last Days", "Older one"], extract=extract)
    assert show and show.feed_url == "https://www.youtube.com/@finvshistory"
    assert len(asked) == 3                                  # the channel search, the newest, the next one (then stop)


def test_episode_match_reports_its_channel_and_channel_show_only_takes_youtube_links():
    from core import podcasts
    r = podcasts.find_youtube_episode_info("Show", "The Big Heist", 0, lambda q: {"entries": [
        {"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "The Big Heist", "channel": "Host",
         "channel_url": "https://www.youtube.com/@host"}]})
    assert r["url"].endswith("bbbbbbbbbbb") and r["channel_url"] == "https://www.youtube.com/@host" and r["channel"] == "Host"
    bad = podcasts.find_youtube_episode_info("Show", "The Big Heist", 0, lambda q: {"entries": [
        {"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "The Big Heist", "channel_url": "http://evil.example/x"}]})
    assert bad["url"] and bad["channel_url"] == ""
    assert podcasts.channel_show("https://www.youtube.com/@host", "Host").kind == "youtube"
    assert podcasts.channel_show("https://evil.example/@host") is None
    assert podcasts.channel_show("http://www.youtube.com/@host") is None


def test_page_data_is_fetched_once_for_listening_and_watching(monkeypatch):
    from core import podcasts
    from core import streamer
    monkeypatch.setenv("SEVBIFY_PHONE", "1")
    monkeypatch.setattr(streamer, "url_works", lambda url, headers=None, timeout=8: True)
    monkeypatch.setattr(podcasts, "_pref_client", 0)
    podcasts._raw.clear()
    log = []

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False, process=True):
            clients = self.opts["extractor_args"]["youtube"]["player_client"]
            log.append(("fetch", clients))
            if clients == ["android_vr"] and url.endswith("failing1111"):
                raise ValueError("this client has nothing")
            return {"formats": ["raw"], "url": ""}

        def process_ie_result(self, info, download=False):
            log.append(("choose", self.opts["format"]))
            info["url"] = "https://a/" + self.opts["format"]
            return info
    monkeypatch.setattr(podcasts, "_ydl", lambda extra: FakeYDL(extra))
    page = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
    a = podcasts._extract_page(page, {"format": "audio"})
    b = podcasts._extract_page(page, {"format": "video"})
    assert a["url"] == "https://a/audio" and b["url"] == "https://a/video"
    assert [x for x in log if x[0] == "fetch"] == [("fetch", ["android_vr"])]        # one fetch, two format choices
    # a client that fails: the next one is asked
    log.clear()
    out = podcasts._extract_page("https://www.youtube.com/watch?v=failing1111", {"format": "audio"})
    assert out["url"] == "https://a/audio" and [x[1] for x in log if x[0] == "fetch"] == [["android_vr"], ["tv"]]


def test_a_refused_link_moves_on_to_the_next_client_and_is_remembered(monkeypatch):
    from core import podcasts, streamer
    monkeypatch.setenv("SEVBIFY_PHONE", "1")
    monkeypatch.setattr(podcasts, "_pref_client", 0)
    podcasts._raw.clear()
    asked = []

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False, process=True):
            return {"formats": []}

        def process_ie_result(self, info, download=False):
            c = self.opts["extractor_args"]["youtube"]["player_client"]
            asked.append(c)
            return {"url": "https://" + "-".join(c) + "/a", "http_headers": {}}
    monkeypatch.setattr(podcasts, "_ydl", lambda extra: FakeYDL(extra))
    monkeypatch.setattr(streamer, "url_works", lambda url, headers=None, timeout=8: "android_vr" not in url)
    out = podcasts._extract_page("https://www.youtube.com/watch?v=aaaaaaaaaaa", {"format": "audio"})
    assert out["url"] == "https://tv/a" and asked == [["android_vr"], ["tv"]]
    asked.clear()
    podcasts._extract_page("https://www.youtube.com/watch?v=bbbbbbbbbbb", {"format": "audio"})
    assert asked == [["tv"]]                                    # tv worked, so it goes first now
    podcasts.link_failed()                                     # the player was refused anyway: the next one after tv
    asked.clear()
    podcasts._extract_page("https://www.youtube.com/watch?v=ccccccccccc", {"format": "audio"})
    assert asked and asked[0] != ["tv"]


def test_episode_is_found_on_the_shows_channel_by_length_when_the_names_differ():
    from core import podcasts
    podcasts._chan_cache.clear()
    chan = "https://www.youtube.com/@finvshistory"

    def vid(i, title, secs):
        return {"url": f"https://www.youtube.com/watch?v={i * 11}", "title": title, "duration": secs}
    listing = {"channel": "Fin vs History", "entries": [
        vid("a", "Genghis Khan: The Mongol Horde", 3100),
        vid("b", "Was Chairman Mao the greatest dictator ever?", 3010),          # the feed calls it something else
        vid("c", "The Cuban Missile Crisis", 2400),
        vid("d", "Why Mao still divides China", 3060)]}
    feed_title = "Is Chairman Mao The G.O.A.T of Dictators? | The Life of Chairman Mao (Part 1)"
    r = podcasts._find_in_channel(chan, feed_title, 3050000, extract=lambda q: listing)
    assert r and r["url"].endswith("bbbbbbbbbbb") and r["channel_url"] == chan
    # a length with no title in common: no guess
    assert podcasts._find_in_channel(chan, "Something Else Entirely About Cats", 2400000, extract=lambda q: listing) is None
    # two equally plausible videos: no guess
    twin = {"entries": [vid("e", "Mao legacy one", 3000), vid("f", "Mao legacy two", 3010)]}
    podcasts._chan_cache.clear()
    assert podcasts._find_in_channel(chan, "Mao rise fall legacy chairman", 3005000, extract=lambda q: twin) is None
    # a title that matches is taken as before
    podcasts._chan_cache.clear()
    r = podcasts._find_in_channel(chan, "The Cuban Missile Crisis", 2450000, extract=lambda q: listing)
    assert r and r["url"].endswith("cccccccccc" + "c")

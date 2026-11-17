"""'Support the artist': only the artist's own links, https, matched through the song; podcasts' own funding link."""
from core import support
from core.podcasts import parse_feed


class FakeNet:
    def __init__(self, recordings=None, artists=None, rels=None):
        self.recordings, self.artists, self.rels = recordings or [], artists or [], rels or []
        self.asked = []

    def get_json(self, url, params=None, ttl=0):
        self.asked.append((url, params))
        if url.endswith("/recording"):
            return {"recordings": self.recordings}
        if url.endswith("/artist"):
            return {"artists": self.artists}
        return {"relations": self.rels}


def rel(kind, url, ended=False):
    return {"type": kind, "url": {"resource": url}, "ended": ended}


def test_bandcamp_page_of_the_song_comes_first_then_the_artists_own_links():
    net = FakeNet(recordings=[{"title": "Candlepower", "artist-credit": [{"artist": {"id": "zab", "name": "Chris Zabriskie"}}]}],
                  rels=[rel("official homepage", "https://chriszabriskie.com/"),
                        rel("bandcamp", "https://chriszabriskie.bandcamp.com/"),
                        rel("purchase for mail-order", "http://store.example.org/zab"),
                        rel("purchase for download", "https://bit.ly/fake"),               # shortener: never
                        rel("bandcamp", "https://bandcamp-music-free.com/zab"),          # not bandcamp.com: never
                        rel("official homepage", "https://old.example.net/", ended=True)])
    links = support.for_song(net, "Chris Zabriskie", "Candlepower",
                             "https://chriszabriskie.bandcamp.com/track/candlepower", "bandcamp")
    urls = [l["url"] for l in links]
    assert urls[0] == "https://chriszabriskie.bandcamp.com/track/candlepower"
    assert "https://chriszabriskie.bandcamp.com/" in urls and "https://chriszabriskie.com/" in urls
    assert "https://store.example.org/zab" in urls                                        # upgraded to https
    assert not any("bit.ly" in u or "bandcamp-music-free" in u or "old.example" in u for u in urls)
    assert links[0]["site"] == "chriszabriskie.bandcamp.com"


def test_same_named_artist_without_this_song_isnt_used():
    support._cache.clear()
    net = FakeNet(recordings=[{"title": "Other Song", "artist-credit": [{"artist": {"id": "x", "name": "Tours"}}]}],
                  artists=[{"id": "a", "name": "Tours", "score": 100}, {"id": "b", "name": "Tours", "score": 100}])
    assert support.for_song(net, "Tours", "Enthusiast") == []                        # two "Tours": no guess


def test_unsafe_links_are_refused():
    for bad in ("http://x.com", "javascript:alert(1)", "https://user:pw@x.com/", "https://x.com:8443/", "https://lnk.to/a",
                "file:///etc/passwd", "https://localhost/"):
        assert not support.safe_link(bad), bad
    assert support.safe_link("https://artist.bandcamp.com/album/x")
    assert support.bandcamp_page("https://daily.bandcamp.com/features/x") == ""
    assert support.bandcamp_page("https://evil.com/?x=artist.bandcamp.com/track/a") == ""


def test_podcast_funding_from_its_own_feed():
    xml = """<rss xmlns:podcast="https://podcastindex.org/namespace/1.0"><channel><title>Show</title>
    <link>https://show.example.com</link>
    <podcast:funding url="https://www.patreon.com/show">Back us on Patreon</podcast:funding>
    <item><title>Ep</title><enclosure url="https://cdn.example.com/1.mp3"/></item></channel></rss>"""
    show, _eps = parse_feed(xml)
    links = support.for_show(show)
    assert links[0] == {"label": "Back us on Patreon", "url": "https://www.patreon.com/show", "site": "patreon.com"}
    assert links[1]["url"] == "https://show.example.com"


def test_support_card_on_the_desktop(window, qapp):
    w = window
    w._auto_answer_dialogs = True
    w.user_data.online_enabled = False
    d = w.support_artist("Chris Zabriskie")
    assert "Go online" in d.status.text()
    d.show_links([{"label": "Buy on Bandcamp", "url": "https://a.bandcamp.com/", "site": "a.bandcamp.com"}], "none")
    assert d.links and d.status.isHidden()
    d.close()

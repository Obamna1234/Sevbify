"""'Did you mean …?' (typo correction through DuckDuckGo, only for finished searches whose results look wrong)."""
from core.online.models import OnlineTrack
from core.online.net import NetClient
from core.online.providers import OnlineMusic
from core.online import spelling
from online_fixtures import FakeWeb, deezer_track


def T(title, artist):
    return OnlineTrack(title, artist)


def test_results_that_match_are_left_alone():
    assert not spelling.looks_wrong("narc mega drive", [T("NARC", "Mega Drive")])
    assert not spelling.looks_wrong("Beyoncé halo", [T("Halo", "Beyonce")])           # accents don't matter
    assert not spelling.looks_wrong("кино группа крови", [T("Группа крови", "Кино")])  # any language
    assert not spelling.looks_wrong("米津玄師", [T("Lemon", "米津玄師")])


def test_unrelated_results_look_wrong():
    assert spelling.looks_wrong("fin vs hustory", [T("History of Finance", "Money Podcast")])
    assert spelling.looks_wrong("anything", [])


def test_did_you_mean_asks_duckduckgo_once_and_checks_the_suggestion_finds_music(tmp_path):
    web = FakeWeb({
        "duckduckgo.com/ac/": ["fin vs hustory", ["fin vs history lyrics", "fin vs hustory"]],
        "api.deezer.com/search?q=fin+vs+history": {"data": [deezer_track(1, "Fin vs History", "Fin", 7)]},
        "api.deezer.com/search?q=fin+vs+hustory": {"data": [deezer_track(2, "History of Finance", "Money Podcast", 8)]},
    })
    net = NetClient(str(tmp_path / "c"), opener=web)
    music = OnlineMusic(net)
    assert spelling.did_you_mean(net, music, "fin vs hustory") == "fin vs history"
    ddg = [u for u in web.calls if "duckduckgo" in u]
    assert len(ddg) == 1 and "q=fin+vs+hustory" in ddg[0]          # only the finished search is sent


def test_good_results_never_contact_duckduckgo(tmp_path):
    web = FakeWeb()
    net = NetClient(str(tmp_path / "c"), opener=web)
    assert spelling.did_you_mean(net, OnlineMusic(net), "narc") == ""
    assert not any("duckduckgo" in u for u in web.calls)


def test_your_own_songs_are_found_whatever_the_accents_or_language():
    from core.models import fold
    assert fold("beyonce") in fold("Beyoncé – Halo")
    assert fold("ＡＢＣ") == "abc"
    assert fold("Группа крови") == "группа крови"


def test_podcast_search_works_in_any_language_and_adds_youtube_only_shows(tmp_path):
    from core import podcasts
    assert podcasts.match_score("арзамас", "Арзамас Подкаст") > 0
    shows = [podcasts.Show(title="History of Finance", author="Money", feed_url="https://a/feed")]
    assert podcasts.relevant("fin vs hustory", shows) == []
    web = FakeWeb({"itunes.apple.com/search": {"results": [
        {"collectionName": "History of Finance", "artistName": "Money", "feedUrl": "https://a/feed"}]}})
    net = NetClient(str(tmp_path / "c"), opener=web)

    def fake_extract(q):
        return {"entries": [{"channel": "Fin vs History", "channel_url": "https://www.youtube.com/@finvshistory"}]}
    found = podcasts.search_with_youtube(net, "Fin vs History", extract=fake_extract)
    assert found[0].kind == "youtube" and found[0].title == "Fin vs History"

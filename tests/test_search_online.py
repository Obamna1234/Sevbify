"""Search page: library results + 'More from the web'."""
from conftest import wait_until
from online_fixtures import FakeWeb


def use_web(window, tmp_path, offline=False):
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    window.net = NetClient(str(tmp_path / "c"), enabled=lambda: window.user_data.online_enabled,
                           opener=FakeWeb(offline=offline))
    window.online = OnlineMusic(window.net)


def test_web_results_shown_and_owned_song_plays_full(window, qapp, tmp_path):
    use_web(window, tmp_path)
    owned = window.songs[0]
    owned.artist, owned.title, owned.duration = "Mega Drive", "NARC", 284_000
    window.show_search()
    window.search_input.setText("narc")
    assert window.search_lib_header.isVisibleTo(window.search_page)
    assert wait_until(qapp, lambda: window.web_table.rowCount() == 1)
    # Your own copy is listed on top under "In your library" and not repeated in the web results.
    assert owned in window.search_table.songs_in_view()
    items = window.web_table.songs_in_view()
    assert getattr(items[0], "is_remote", False) and items[0].title == "Gamechanger"
    assert window.web_table.item(0, 1).text().endswith("⬇")   # clearly not downloaded
    assert "30-second previews" in window.search_web_status.text()
    window.web_table.play_requested.emit(items[0], items)
    assert window.current_song is items[0]
    assert window.pq.source_name == "Search: narc"


def test_web_search_offline_message(window, qapp, tmp_path):
    use_web(window, tmp_path, offline=True)
    window.search_input.setText("anything")
    assert wait_until(qapp, lambda: "offline" in window.search_web_status.text())
    assert not window.web_table.isVisibleTo(window.search_page)


def test_web_search_hidden_when_switched_off(window, qapp, tmp_path):
    use_web(window, tmp_path)
    window.apply_settings({"online_enabled": False, "lastfm_api_key": "", "jamendo_client_id": ""})
    window.search_input.setText("narc")
    assert not window.search_web_header.isVisibleTo(window.search_page)
    assert "Turn on Online features" in window.search_summary.text()


def test_typing_fast_only_searches_once(window, qapp, tmp_path):
    use_web(window, tmp_path)
    web = window.net._opener
    for text in ("n", "na", "nar", "narc"):
        window.search_input.setText(text)
    assert wait_until(qapp, lambda: window.web_table.rowCount() > 0)
    searches = [u for u in web.calls if "/search?" in u]
    assert len(searches) == 1 and "q=narc" in searches[0]

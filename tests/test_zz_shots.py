import os
from conftest import wait_until
S = "/tmp/claude-0/-home-claude/ab8e0ca9-f76e-5df1-9e5d-018865a9803c/scratchpad/shots"


def test_shots(window, qapp):
    os.makedirs(S, exist_ok=True)
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    window.resize(1500, 900)
    window.show()
    pl = window.create_playlist("Alternative/Indie Chill", list(window.songs) + [
        RemoteSong(OnlineTrack("Let Me Down Easy", "Gang of Youths", album="Go Farther In Lightness", duration_ms=319000)),
        RemoteSong(OnlineTrack("Get Off", "The Dandy Warhols", duration_ms=191000))])
    window.show_playlist(pl)
    wait_until(qapp, lambda: False, 0.5)
    window.pl_table.selectRow(1)
    window.pl_table._set_hover(3)
    wait_until(qapp, lambda: False, 0.3)
    window.grab().save(f"{S}/playlist.png")


def test_shots2(window, qapp):
    window.resize(1500, 900)
    window.show()
    window.open_settings()
    wait_until(qapp, lambda: False, 0.4)
    sp = window.settings_page
    sp.scroll.ensureWidgetVisible(sp.eq_curve)
    wait_until(qapp, lambda: False, 0.3)
    window.grab().save(f"{S}/settings_eq.png")
    sp.scroll.verticalScrollBar().setValue(sp.scroll.verticalScrollBar().maximum())
    wait_until(qapp, lambda: False, 0.3)
    window.grab().save(f"{S}/settings_bottom.png")
    window.play_song(window.songs[0], queue=window.songs)
    window.open_full_screen()
    window.full_screen_view.resize(1400, 850)
    wait_until(qapp, lambda: False, 0.4)
    window.full_screen_view.grab().save(f"{S}/fullscreen.png")
    window.full_screen_view.close()
    window.open_mini_player()
    from PyQt6.QtGui import QEnterEvent
    window.mini_player.overlay.show()
    wait_until(qapp, lambda: False, 0.3)
    window.mini_player.grab().save(f"{S}/mini.png")

"""The Settings page: every switch changes and saves the setting, and the playback options work."""
import os

from conftest import wait_until


def control(window, key):
    window.open_settings()
    return window.settings_page.controls[key]


def test_settings_is_a_page_and_switches_save(open_window, audio_dir, data_dir):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    w.open_settings()
    assert w.stack.currentWidget() is w.settings_page
    for key in ("autoplay", "explicit_ok", "canvas_enabled", "np_on_play"):
        sw = w.settings_page.controls[key]
        assert sw.isChecked()
        sw.click()
        assert getattr(w.user_data, key) is False
    w.settings_page.controls["fade_seconds"].setCurrentText("5 seconds")
    w.settings_page.controls["startup"].setEnabled(True)
    w.settings_page.controls["proxy_mode"].setCurrentText("HTTP proxy")
    assert w.user_data.fade_seconds == 5 and w.user_data.proxy_mode == "http"
    assert w.settings_page.restart_bar.isVisibleTo(w.settings_page)        # proxy needs a restart
    w.settings_page.controls["zoom"].button(120).click()
    assert w.user_data.zoom == 120
    w.close()
    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    u = w2.user_data
    assert (u.autoplay, u.explicit_ok, u.canvas_enabled, u.fade_seconds, u.zoom) == (False, False, False, 5, 120)


def test_equalizer_presets_and_sliders(window):
    page_eq = control(window, "eq_panel")
    page = window.settings_page
    assert "Flat" in page.eq_presets and len(page.eq_presets) > 5         # VLC's presets (Rock, Pop, ...)
    name = next(n for n in page.eq_presets if n != "Flat")
    page.eq_combo.setCurrentText(name)
    assert window.user_data.eq_enabled and window.user_data.eq_preset == name
    assert window.user_data.eq_bands == [float(b) for b in page.eq_presets[name]]
    assert window._eq is not None
    page.eq_sliders[0].setValue(55)
    page._eq_slider_moved()
    assert window.user_data.eq_preset == "Custom" and window.user_data.eq_bands[0] == 5.5
    page.controls["eq_enabled"].click()
    assert not window.user_data.eq_enabled and window._eq is None
    assert page_eq is not None


def test_music_folders_can_be_switched_off(window, qapp, tmp_path):
    from conftest import make_wav
    extra = tmp_path / "Extra"
    extra.mkdir()
    make_wav(extra / "x.wav", 0.2)
    window.user_data.music_folders.append(str(extra))
    window.rescan_library()
    assert wait_until(qapp, lambda: len(window.songs) == 4)
    control(window, f"folder:{extra}").click()                              # switch it off
    assert window.user_data.disabled_folders == [str(extra)]
    assert wait_until(qapp, lambda: len(window.songs) == 3)
    assert str(extra) in window.user_data.music_folders                      # still listed, just off


def test_private_session_keeps_recently_played_clean(window, qapp):
    window.apply_settings({"private_session": True})
    window.play_song(window.songs[1])
    assert window.songs[1] not in window.pq.recent
    tree_file = [a for a in window.build_app_menu().actions() if a.text() == "File"][0].menu()
    assert any(a.text() == "Private Session" and a.isChecked() for a in tree_file.actions())
    window.apply_settings({"private_session": False})
    window.play_song(window.songs[2])
    assert window.songs[2] in window.pq.recent


def test_explicit_songs_left_out_when_not_allowed(window):
    from core.online.models import OnlineTrack
    tracks = [OnlineTrack("Clean", "A"), OnlineTrack("Rude", "B", explicit=True)]
    assert len(window._allowed(tracks)) == 2
    window.apply_settings({"explicit_ok": False})
    assert [t.title for t in window._allowed(tracks)] == ["Clean"]


def test_autoplay_continues_with_radio_when_the_queue_ends(window, qapp, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "start_radio", lambda seed, autoplay=False: calls.append((seed, autoplay)))
    window.songs[2].artist = "Mega Drive"
    window.play_song(window.songs[2], queue=[window.songs[2]])
    assert wait_until(qapp, lambda: calls, 10)
    assert calls[0] == (window.songs[2], True)
    window.apply_settings({"autoplay": False})
    calls.clear()
    window.play_song(window.songs[2], queue=[window.songs[2]])
    assert wait_until(qapp, lambda: not window.is_playing, 10)
    assert not calls


def test_fade_and_start_up_helpers():
    from core.audio_settings import fade_factor, BAND_LABELS
    from core.startup_settings import apply_env, set_start_at_login, run_command
    from core.storage import UserData
    assert fade_factor(0, 200_000, 5000) == 0 and fade_factor(2500, 200_000, 5000) == 0.5
    assert fade_factor(100_000, 200_000, 5000) == 1 and fade_factor(197_500, 200_000, 5000) == 0.5
    assert fade_factor(1000, 8000, 5000) == 1                         # very short songs don't fade
    assert len(BAND_LABELS) == 10
    u = UserData(zoom=120, hw_accel=False, proxy_mode="http", proxy_url="127.0.0.1:8080")
    env = {}
    apply_env(u, env)
    assert env["QT_SCALE_FACTOR"] == "1.20" and env["QT_OPENGL"] == "software"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:8080"
    env = {"HTTPS_PROXY": "x"}
    apply_env(UserData(proxy_mode="none"), env)
    assert "HTTPS_PROXY" not in env and env["NO_PROXY"] == "*"

    class FakeReg:
        HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ = 1, 2, 3
        values = {}
        def OpenKey(self, *a): return "key"
        def CloseKey(self, k): pass
        def SetValueEx(self, k, name, _r, _t, value): self.values[name] = value
        def DeleteValue(self, k, name): self.values.pop(name)

    reg = FakeReg()
    assert set_start_at_login("minimized", r"C:\Apps\Sevbify.exe", reg)
    assert reg.values["Sevbify"] == r'"C:\Apps\Sevbify.exe" --minimized'
    assert set_start_at_login("no", r"C:\Apps\Sevbify.exe", reg) and "Sevbify" not in reg.values
    assert run_command("yes", "x.exe") == '"x.exe"'


def test_close_to_tray_hides_instead_of_quitting(window, qapp, monkeypatch):
    from PyQt6.QtWidgets import QSystemTrayIcon
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    window.show()
    window.apply_settings({"close_to_tray": True})
    window.close()
    assert not window.isVisible() and not getattr(window, "_shut_down", False)   # still running
    window.quit_app()
    assert window._shut_down

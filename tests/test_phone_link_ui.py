"""The computer's pairing windows: Settings → Your phone, the QR card, receiving with a yes/no, Send to phone."""
import os
import time

import pytest

pytest.importorskip("Cryptodome")
pytest.importorskip("segno")

from core import pairing as pr  # noqa: E402


def _wait(qapp, cond, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_pair_a_phone_and_receive_a_song(window, qapp, tmp_path):
    w = window
    w._auto_answer_dialogs = True
    w.open_settings()
    assert w.settings_page.controls["pair_phone"].isEnabled()
    d = w.phone_link.open_pairing()
    assert d is not None and not d.qr.pixmap().isNull()
    info = pr.parse_pair_link(d.link)
    sess, saved = pr.connect("127.0.0.1", info["port"], code=info["code"], name="Pixel", platform="android",
                             receive_folder=str(tmp_path / "phone"))
    assert _wait(qapp, lambda: w.phone_link.phones())
    assert w.phone_link.phones()[0]["name"] == "Pixel"
    import threading
    threading.Thread(target=sess.run, daemon=True).start()
    song = tmp_path / "Song.mp3"
    song.write_bytes(os.urandom(50_000))
    sess.send_paths([str(song)])
    folder = os.path.join(w.phone_link._receive_folder(), "From Pixel")
    assert _wait(qapp, lambda: os.path.exists(os.path.join(folder, "Song.mp3")), 20)
    # the song menu offers "Send to Pixel" for songs on this computer
    assert _wait(qapp, lambda: w.phone_link.connected())
    assert _wait(qapp, lambda: any(x.title == "Song" for x in w.songs), 20)       # it shows up in Your Songs
    s = next(x for x in w.songs if x.title == "Song")
    texts = [a.text() for a in w.build_song_menu(s).actions()]
    assert any("Send to Pixel" in t for t in texts)
    # remove the phone: its key stops working
    w.phone_link.forget(saved["dev"])
    assert not w.phone_link.phones()
    sess.link.close()


def test_declining_saves_nothing(window, qapp, tmp_path):
    w = window
    w._auto_answer_dialogs = True
    d = w.phone_link.open_pairing()
    info = pr.parse_pair_link(d.link)
    sess, _ = pr.connect("127.0.0.1", info["port"], code=info["code"], name="Nope", receive_folder=str(tmp_path / "phone"))
    import threading
    threading.Thread(target=sess.run, daemon=True).start()
    w._auto_answer_dialogs = False
    song = tmp_path / "x.mp3"
    song.write_bytes(b"abc")
    sess.send_paths([str(song)])
    _wait(qapp, lambda: False, 1.5)
    assert not os.path.exists(os.path.join(w.phone_link._receive_folder(), "From Nope", "x.mp3"))
    sess.link.close()
    w.phone_link.stop()


def test_a_paired_phone_controls_the_music_and_adds_to_the_queue(window, qapp, tmp_path):
    """Remote control and Jam over the pairing link: the phone sends commands, the computer sends what's playing."""
    import threading
    w = window
    w._auto_answer_dialogs = True
    d = w.phone_link.open_pairing()
    info = pr.parse_pair_link(d.link)
    states = []

    class Ev:
        pass
    sess, _ = pr.connect("127.0.0.1", info["port"], code=info["code"], name="Pixel", receive_folder=str(tmp_path / "p"))
    real_handle = sess.handle

    def handle(msg):
        if isinstance(msg, dict) and msg.get("t") == "state":
            states.append(msg)
            return
        real_handle(msg)
    sess.handle = handle
    threading.Thread(target=sess.run, daemon=True).start()
    assert _wait(qapp, lambda: w.phone_link.connected())
    w.play_song(w.songs[0], queue=w.songs)
    titles = {x.title for x in w.songs}
    assert _wait(qapp, lambda: any(s.get("title") in titles for s in states), 10)   # the phone sees what's playing
    cur = w.current_song
    sess.link.send_json({"t": "remote", "cmd": "next"})
    assert _wait(qapp, lambda: w.current_song is not cur, 10)
    sess.link.send_json({"t": "remote", "cmd": "volume", "v": 37})
    assert _wait(qapp, lambda: w.volume_slider.value() == 37, 10)
    sess.link.send_json({"t": "remote", "cmd": "queue_add", "song": {"title": "Siesta", "artist": "Jahzzar"}})
    # (The test songs are 1 second long, so the added song may already be playing by the time we look.)
    assert _wait(qapp, lambda: any(s.title == "Siesta" for s in w.pq.user_queue)
                 or getattr(w.current_song, "title", "") == "Siesta", 10)
    sess.link.send_json({"t": "remote", "cmd": "format_disk"})             # not a command: ignored
    w.apply_settings({"phone_remote": False})                                # switched off in Settings
    sess.link.send_json({"t": "remote", "cmd": "volume", "v": 80})
    qapp.processEvents()
    time.sleep(0.5)
    qapp.processEvents()
    assert w.volume_slider.value() == 37
    sess.link.close()

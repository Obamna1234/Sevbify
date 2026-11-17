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
    sess, saved = pr.connect("127.0.0.1", info["port"], code=info["code"], name="Pixel", platform="android")
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
    sess, _ = pr.connect("127.0.0.1", info["port"], code=info["code"], name="Nope")
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

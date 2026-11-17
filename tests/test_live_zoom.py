"""Ctrl + / Ctrl - change the size straight away (like Spotify), keeping the window's place and size on screen."""
from PyQt6.QtWidgets import QWidget

from ui import live_zoom


def test_live_zoom_redraws_bigger_and_keeps_the_window_size(qapp):
    assert live_zoom.available(), live_zoom.why        # found in Qt on Windows, macOS and Linux
    w = QWidget()
    w.setGeometry(100, 100, 800, 600)
    w.show()
    qapp.processEvents()
    try:
        assert live_zoom.apply(100, 150, [w])
        qapp.processEvents()
        assert w.isVisible() and abs(w.devicePixelRatio() - 1.5) < 0.01
        g = w.geometry()
        assert abs(g.width() * 1.5 - 800) <= 2 and abs(g.height() * 1.5 - 600) <= 2   # same size on screen
    finally:
        live_zoom.apply(150, 100, [w])
        qapp.processEvents()
    assert abs(w.devicePixelRatio() - 1.0) < 0.01 and w.geometry().width() == 800
    w.close()


def test_same_zoom_is_nothing_to_do(qapp):
    assert live_zoom.apply(100, 100, []) == live_zoom.available()

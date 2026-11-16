"""The taskbar preview buttons (Windows only; elsewhere they quietly do nothing)."""
import sys

import pytest


def test_button_clicks_reach_the_player():
    from ui import win_taskbar
    clicked = []
    tb = win_taskbar.ThumbBar(0, {k: (lambda k=k: clicked.append(k)) for k in win_taskbar.IDS})
    for key, i in win_taskbar.IDS.items():
        assert tb.handle(win_taskbar.WM_COMMAND, (win_taskbar.THBN_CLICKED << 16) | i) == "clicked"
    assert clicked == list(win_taskbar.IDS)
    assert tb.handle(win_taskbar.WM_COMMAND, 5) is None            # an ordinary menu command isn't ours


@pytest.mark.skipif(sys.platform != "win32", reason="Windows taskbar")
def test_windows_accepts_the_buttons(window, qapp):
    window.show()
    qapp.processEvents()
    tb = window._thumbbar()
    assert tb is not None and tb._tb is not None
    tb.add(False, False)                         # may already have been added when Windows sent its note
    window._update_thumbbar()

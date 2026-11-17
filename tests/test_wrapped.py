"""Your listening stats (Wrapped), worked out on the device."""
import time

from core import wrapped


def test_stats_count_minutes_tops_and_periods():
    now = time.time()
    old = now - 400 * 86400
    listens = ([["Kevin MacLeod", "Monkeys Spinning Monkeys", now - 3600]] * 4 + [["Jahzzar", "Siesta", now - 7200]]
               + [["Chris Zabriskie", "Candlepower", old]] + ["junk", [1, 2], ["a", "b", "not a time"]])
    st = wrapped.stats(listens, "4 weeks", {wrapped._key("Jahzzar", "Siesta"): 60_000}, now=now)
    assert st["plays"] == 5 and st["minutes"] == (4 * wrapped.AVERAGE_MS + 60_000) // 60_000
    assert st["top_artists"][0] == {"artist": "Kevin MacLeod", "plays": 4}
    assert st["top_songs"][0]["title"] == "Monkeys Spinning Monkeys" and len(st["top_50"]) == 2
    assert wrapped.stats(listens, "All time", now=now)["plays"] == 6       # the old one counts in All time only


def test_window_shows_wrapped_and_makes_top_songs(window):
    window._auto_answer_dialogs = True
    window.user_data.listens = [["Kevin MacLeod", "Sneaky Snitch", int(time.time())]] * 3
    d, state = window.show_wrapped("4 weeks")
    assert state["st"]["plays"] == 3
    window.user_data.listens = []
    d, state = window.show_wrapped("4 weeks")
    assert state["st"]["plays"] == 0

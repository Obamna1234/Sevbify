"""What's new: new episodes of followed shows and new releases, and the bell's dot."""
import time

from core import whats_new
from core.online.models import OnlineTrack


def test_gather_recent_episodes_and_releases():
    now = time.time()

    class Ep:
        def __init__(self, title, ago):
            self.track, self.published = OnlineTrack(title, "Show"), now - ago

    class Show:
        title = "The Show"

    def fetch(net, show):
        return show, [Ep("New one", 3600), Ep("Older", 20 * 86400)]
    items = whats_new.gather(None, None, [Show()], [], fetch_show=fetch,
                             release_radar=lambda online, listens: [OnlineTrack("Fresh", "Kevin MacLeod")], now=now)
    assert [x["title"] for x in items] == ["Fresh", "New one"]                # newest first; old ones left out
    assert whats_new.unseen(items, now - 7200) == 2 and whats_new.unseen(items, now) == 0


def test_bell_dot_clears_when_opened(window):
    window._whats_new = [{"kind": "release", "title": "Fresh", "subtitle": "", "when": time.time(),
                          "track": OnlineTrack("Fresh", "Kevin MacLeod", preview_url="https://p/x.mp3")}]
    window.top_bar.set_new(1)
    assert "1" in window.top_bar.bell_btn.toolTip()
    window.show_whats_new()
    assert window.top_bar.bell_btn.toolTip() == "What's new" and window.user_data.whats_new_seen > 0

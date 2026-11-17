"""The in-app note when one source keeps failing (it probably changed something; an update fixes it)."""
from core import source_status as ss


def test_note_after_three_failures_from_one_source_only():
    ss.reset()
    assert ss.failed("ERROR: [youtube] abc: Sign in to confirm you're not a bot", now=1000) == ""
    assert ss.failed("youtube: HTTP Error 403", now=1100) == ""
    assert ss.failed("deezer: HTTP 500", now=1150) == ""                    # another source: counted apart
    note = ss.failed("googlevideo.com refused", now=1200)
    assert note.startswith("YouTube doesn't seem to be working") and "Check for updates" in note
    ss.worked("youtube")
    assert ss.failed("youtube 403", now=1300) == ""


def test_old_failures_and_connection_problems_dont_count():
    ss.reset()
    ss.failed("spotify 404", now=0)
    ss.failed("spotify 404", now=10)
    assert ss.failed("spotify 404", now=10 + ss.WINDOW + 1) == ""
    for i in range(5):
        assert ss.failed("youtube: Network is unreachable", now=5000 + i) == ""
    assert ss.source_of("something odd") == ""

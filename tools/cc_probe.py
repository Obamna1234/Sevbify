"""Which Creative Commons songs can the automated checks use? (Only openly licensed music is used in tests and
demos.) Prints, for each candidate, whether Deezer, Bandcamp, SoundCloud and YouTube have it. Information only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CANDIDATES = [
    ("Kevin MacLeod", "Monkeys Spinning Monkeys"), ("Kevin MacLeod", "Sneaky Snitch"),
    ("Chris Zabriskie", "Candlepower"), ("Chris Zabriskie", "Divider"), ("Chris Zabriskie", "Cylinder Five"),
    ("Broke For Free", "Night Owl"), ("Josh Woodward", "Let It In"), ("Kai Engel", "Downfall"),
    ("Tours", "Enthusiast"), ("Komiku", "Bicycle"), ("Scott Holmes Music", "Hopeful Journey"),
    ("Jahzzar", "Siesta"), ("Lee Rosevere", "Let's Start at the Beginning"),
]


def run(label, fn):
    try:
        out = fn()
        print(f"  {label}: {out}", flush=True)
    except Exception as e:
        print(f"  {label}: no ({type(e).__name__}: {str(e)[:120]})", flush=True)


def main():
    import tempfile
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    from core import downloader, streamer
    net = NetClient(tempfile.mkdtemp())
    om = OnlineMusic(net)
    e = downloader.engine()
    for artist, title in CANDIDATES:
        print(f"{artist} - {title}", flush=True)
        run("Deezer", lambda: [f"{t.artist} - {t.title}" for t in om.search(f"{artist} {title}", limit=3)][:2])
        run("Bandcamp", lambda: (lambda r: r.get("url") if r.get("found") else "no")(e.search_bandcamp(f"{artist} - {title}")))
        run("SoundCloud", lambda: [f"{t.artist} - {t.title}" for t in streamer.search_soundcloud(f"{artist} {title}", 3)][:2])
        run("SoundCloud albums", lambda: [a.get("title") for a in streamer.soundcloud_albums(artist, 3)])


LYRICS = [("Josh Woodward", "Let It In"), ("Josh Woodward", "Words Fail"), ("Josh Woodward", "Afterglow"),
          ("Jason Shaw", "Back To The Woods"), ("Brad Sucks", "Making Me Nervous"), ("Brad Sucks", "Total Breakdown"),
          ("Jonathan Coulton", "Code Monkey"), ("Jonathan Coulton", "Re: Your Brains")]


def lyrics_probe():
    import tempfile
    from core.online.net import NetClient
    from core import lyrics as L
    net = NetClient(tempfile.mkdtemp())
    for artist, title in LYRICS:
        try:
            data = net.get_json("https://lrclib.net/api/search", {"artist_name": artist, "track_name": title})
            hits = [(d.get("duration"), bool(d.get("plainLyrics"))) for d in (data or [])][:3]
            print(f"LRCLIB {artist} - {title}: {hits}", flush=True)
        except Exception as e:
            print(f"LRCLIB {artist} - {title}: no ({e})", flush=True)


if __name__ == "__main__":
    lyrics_probe()
    main()

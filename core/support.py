"""Support the artist: where to buy a song or album straight from the artist (or the closest thing), with links
that can be trusted.

Where the links come from, most direct first; nothing is ever guessed from a web search or an ad:
1. The Bandcamp page the song itself was found on (the artist's or label's own Bandcamp store: digital, and often
   vinyl / CD / merch; most of the money goes to the artist).
2. MusicBrainz, the open music encyclopedia, for the artist's links of the kinds it marks as the artist's own:
   "official homepage", "bandcamp", "purchase for download", "purchase for mail-order". The artist is matched through
   the song (a recording with this title by this artist), so a different artist with the same name isn't used.
3. Podcasts: the show's own "support us" link from its feed (<podcast:funding>), and the show's website.

Every link must be https and is shown with its website's name before it opens. Only names (artist, song) are sent
to MusicBrainz; nothing about you. Results are kept for a week.
"""
import re
import time
import urllib.parse

MB = "https://musicbrainz.org/ws/2/"
KINDS = {"bandcamp": "Buy on Bandcamp", "purchase for download": "Buy downloads",
         "purchase for mail-order": "Buy CDs, vinyl or merch", "official homepage": "Official website"}
ORDER = ["bandcamp", "purchase for download", "purchase for mail-order", "official homepage"]
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "linktr.ee", "lnk.to", "smarturl.it", "found.ee"}
_cache = {}


def _norm(s):
    return " ".join(re.findall(r"\w+", (s or "").casefold()))


def domain(url):
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def safe_link(url):
    """Only plain https links to a real host (no shorteners, no logins in the link, no odd ports)."""
    try:
        u = urllib.parse.urlparse(str(url or ""))
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return (u.scheme == "https" and bool(host) and "." in host and u.username is None and u.password is None
            and u.port in (None, 443) and domain(url) not in SHORTENERS and len(url) < 500)


def bandcamp_page(page_url):
    """The song's own Bandcamp page (artist.bandcamp.com/track|album/...), or ""."""
    m = re.match(r"^https://([a-z0-9-]+)\.bandcamp\.com/(track|album)/[A-Za-z0-9_.-]+/?$", str(page_url or ""))
    return m.group(0) if m and m.group(1) not in ("www", "daily", "bandcamp") else ""


def _mb_artist(net, artist, title):
    """The MusicBrainz id of this artist, confirmed through one of their songs (or the only exact name match)."""
    q = f'recording:"{title}" AND artist:"{artist}"' if title else f'artist:"{artist}"'
    want = _norm(artist)
    if title:
        data = net.get_json(MB + "recording", {"query": q, "fmt": "json", "limit": 10}, ttl=7 * 24 * 3600)
        for rec in data.get("recordings") or []:
            if _norm(rec.get("title")) != _norm(title):
                continue
            for credit in rec.get("artist-credit") or []:
                a = credit.get("artist") or {}
                if _norm(a.get("name")) == want and a.get("id"):
                    return a["id"]
    data = net.get_json(MB + "artist", {"query": f'artist:"{artist}"', "fmt": "json", "limit": 5},
                        ttl=7 * 24 * 3600)
    exact = [a for a in data.get("artists") or [] if _norm(a.get("name")) == want and int(a.get("score", 0)) >= 95]
    return exact[0]["id"] if len(exact) == 1 else ""


def artist_links(net, artist, title=""):
    """[{"label", "url", "site"}] from MusicBrainz, most direct first."""
    if not artist or artist == "Unknown Artist":
        return []
    key = (_norm(artist), _norm(title))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 7 * 24 * 3600:
        return hit[1]
    mbid = _mb_artist(net, artist, title)
    out = []
    if mbid:
        data = net.get_json(MB + "artist/" + mbid, {"inc": "url-rels", "fmt": "json"}, ttl=7 * 24 * 3600)
        rels = [r for r in data.get("relations") or [] if r.get("type") in KINDS and not r.get("ended")]
        rels.sort(key=lambda r: ORDER.index(r["type"]))
        seen = set()
        for r in rels:
            url = ((r.get("url") or {}).get("resource") or "").strip()
            if url.startswith("http://"):
                url = "https://" + url[len("http://"):]
            if not safe_link(url) or url in seen:
                continue
            if r["type"] == "bandcamp" and not re.match(r"^https://[a-z0-9-]+\.bandcamp\.com/?", url):
                continue                                  # a "Bandcamp" link must really be on bandcamp.com
            seen.add(url)
            out.append({"label": KINDS[r["type"]], "url": url, "site": domain(url)})
    _cache[key] = (time.time(), out)
    return out


def for_song(net, artist, title, page_url="", source=""):
    """Where to support this song's artist: its own Bandcamp page first, then the artist's own links."""
    out = []
    bc = bandcamp_page(page_url) if source in ("bandcamp", "Bandcamp", "") or "bandcamp.com" in str(page_url) else ""
    if bc:
        out.append({"label": "Buy this on Bandcamp", "url": bc, "site": domain(bc)})
    try:
        for link in artist_links(net, artist, title):
            same_store = bc and link["site"] == domain(bc) and link["label"] == KINDS["bandcamp"]
            if not same_store and link["url"].rstrip("/") not in {o["url"].rstrip("/") for o in out}:
                out.append(link)
    except Exception:
        pass                                              # offline / MusicBrainz busy: what we have
    return out[:5]


def for_show(show):
    """A podcast's own support links: <podcast:funding> and its website."""
    out = []
    fund = getattr(show, "funding", "") or ""
    if safe_link(fund):
        label = getattr(show, "funding_label", "") or "Support this show"
        out.append({"label": label[:60], "url": fund, "site": domain(fund)})
    link = getattr(show, "link", "") or ""
    if safe_link(link) and link != fund:
        out.append({"label": "The show's website", "url": link, "site": domain(link)})
    return out


NOTE = ("Enjoying this? Support the artists and podcasters you love: buy their music, go to their shows, or back "
        "their show directly.")

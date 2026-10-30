"""Free audiobooks: LibriVox recordings of public-domain books, through the Internet Archive (no UI code).

LibriVox volunteers record books whose copyright has expired and release them into the public domain; the
Internet Archive hosts them for anyone to stream or download. Only this collection is used (no commercial
audiobooks from unofficial sites).

- search / popular / new: archive.org's public search (collection "librivoxaudio")
- a book's chapters: archive.org's public metadata for that item (MP3 files, in order)
- cover: archive.org's item picture
Chapters become OnlineTrack objects (source "audiobook") so they play in the normal player and queue.
"""
import re
import urllib.parse
from dataclasses import dataclass

from core.online.models import OnlineTrack
from core.podcasts import clean_text, parse_duration, safe_folder

COLLECTION = "librivoxaudio"
SEARCH_URL = "https://archive.org/advancedsearch.php"


@dataclass
class Book:
    identifier: str
    title: str
    author: str = ""
    description: str = ""
    downloads: int = 0

    @property
    def key(self):
        return f"archive:{self.identifier}"

    @property
    def cover_url(self):
        return f"https://archive.org/services/img/{self.identifier}"

    @property
    def page_url(self):
        return f"https://archive.org/details/{self.identifier}"

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v}

    @classmethod
    def from_dict(cls, d):
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in (d or {}).items() if k in known})


def _first(value):
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _quote_query(text):
    """Words for archive.org's search (special characters removed)."""
    words = re.findall(r"[\w']+", text or "")
    return " ".join(words)


def _search(net, query, sort, rows):
    params = [("q", query), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "creator"), ("fl[]", "downloads"),
              ("fl[]", "description"), ("sort[]", sort), ("rows", str(rows)), ("page", "1"), ("output", "json")]
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    data = net.get_json(url, ttl=12 * 3600)
    out = []
    for d in ((data.get("response") or {}).get("docs") or []):
        if not d.get("identifier"):
            continue
        title = _first(d.get("title"))
        title = re.sub(r"\s*\(?LibriVox\)?\s*$", "", title, flags=re.I) or title
        out.append(Book(identifier=d["identifier"], title=title, author=_first(d.get("creator")),
                        description=clean_text(_first(d.get("description")), 400),
                        downloads=int(d.get("downloads") or 0)))
    return out


def search(net, text, rows=30):
    words = _quote_query(text)
    if not words:
        return []
    return _search(net, f"collection:{COLLECTION} AND (title:({words}) OR creator:({words}))", "downloads desc", rows)


def popular(net, rows=30):
    return _search(net, f"collection:{COLLECTION}", "downloads desc", rows)


# LibriVox subjects for the Audiobooks page (free, public-domain books read by volunteers).
BOOK_CATEGORIES = [
    ("Fiction", "fiction"), ("Mystery", "mystery"), ("Science fiction", "science fiction"), ("Adventure", "adventure"),
    ("Romance", "romance"), ("Horror", "horror"), ("Fantasy", "fantasy"), ("Children", "children"),
    ("History", "history"), ("Poetry", "poetry"), ("Philosophy", "philosophy"), ("Biography", "biography"),
]


def in_category(net, subject, rows=30):
    """Most-listened books with this subject."""
    words = _quote_query(subject)
    if not words:
        return []
    return _search(net, f"collection:{COLLECTION} AND subject:({words})", "downloads desc", rows)


def newest(net, rows=30):
    return _search(net, f"collection:{COLLECTION}", "addeddate desc", rows)


def chapters(net, book, quality="standard"):
    """(Book with details, [OnlineTrack chapters in order])."""
    meta = net.get_json(f"https://archive.org/metadata/{book.identifier}", ttl=7 * 86400)
    md = meta.get("metadata") or {}
    book = Book(identifier=book.identifier, title=_first(md.get("title")) or book.title,
                author=_first(md.get("creator")) or book.author,
                description=clean_text(_first(md.get("description")), 800) or book.description,
                downloads=book.downloads)
    files = [f for f in (meta.get("files") or []) if str(f.get("name", "")).lower().endswith(".mp3")]
    # LibriVox items have each chapter in several qualities: Settings -> Audiobook quality picks 64 or 128 kbps.
    from core.quality import audiobook_formats
    for preferred in audiobook_formats(quality):
        chosen = [f for f in files if f.get("format") == preferred]
        if chosen:
            files = chosen
            break

    def order(f):
        try:
            return (int(str(f.get("track", "")).split("/")[0]), f.get("name", ""))
        except ValueError:
            return (10 ** 6, f.get("name", ""))
    out = []
    for i, f in enumerate(sorted(files, key=order), 1):
        name = f["name"]
        url = f"https://archive.org/download/{book.identifier}/{urllib.parse.quote(name)}"
        title = (f.get("title") or re.sub(r"_\d+kb$", "", name.rsplit(".", 1)[0]).replace("_", " ")).strip()
        out.append(OnlineTrack(title=title, artist=book.author or "LibriVox", album=book.title,
                               duration_ms=parse_duration(str(f.get("length") or "")), cover_url=book.cover_url,
                               stream_url=url, download_url=url, source="audiobook",
                               source_id=f"{book.identifier}/{name}", page_url=book.page_url,
                               license="https://librivox.org/pages/public-domain/", genre="Audiobook"))
    return book, out


def chapter_filename(index, track):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", track.title).strip(" .")[:120] or "Chapter"
    return f"{index:02d} - {name}.mp3"


def book_folder(book):
    return safe_folder(f"{book.author} - {book.title}" if book.author else book.title)

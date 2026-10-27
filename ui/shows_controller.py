"""Podcasts, audiobooks, video podcasts and Browse, for the main window (mixed into MainWindow).

Kept apart from main_window.py so that file doesn't keep growing. Everything here runs on the UI thread and
does its online work through MainWindow.online_call (in the background)."""
import os
import time

from PyQt6.QtCore import Qt, QLocale
from PyQt6.QtGui import QPixmap

from core import podcasts, audiobooks
from core.library import mark_no_scan
from core.online.models import OnlineTrack
from core.online.remote_song import RemoteSong
from core.paths import PLACEHOLDER_IMAGE
from .cards import Card
from .shows_page import ShowsHome, ShowPage, EpisodeRow, BrowseTile, TileGrid, TILE_COLOURS
from .video_page import VideoPage
from . import theme

ITEM_SOURCES = ("podcast", "audiobook", "youtube")
RESUME_SAVE_MS = 5000


def item_key(song_or_track):
    t = getattr(song_or_track, "track", song_or_track)
    return f"{t.source}:{t.source_id}" if getattr(t, "source", "") in ITEM_SOURCES and t.source_id else ""


def country_code():
    name = QLocale().name()                       # e.g. "en_AU"
    cc = name.split("_")[-1].lower() if "_" in name else "us"
    return cc if len(cc) == 2 else "us"


class ShowsMixin:
    # defaults, so anything that runs before setup_shows() is safe
    _genres = None
    _show_ctx = None
    _pending_resume = None
    _item_queue = ()
    _item_active = None
    _covers_asked = set()
    # ==================================================================================================
    # Setup
    # ==================================================================================================
    def setup_shows(self):
        self._top_shows, self._podcast_results, self._podcast_query = None, None, ""
        self._popular_books, self._new_books, self._book_results, self._book_query = None, None, None, ""
        self._genres = None
        self._show_ctx = None            # what the show page shows: dict(kind, obj, items)
        self._item_queue, self._item_active = [], None
        self._covers_asked = set()
        self._resume_saved_at = 0.0
        self._pending_resume = None
        self.podcasts_page = ShowsHome(
            "Podcasts", "Search Apple's podcast directory, follow shows, and stream or download episodes. Episodes "
            "come straight from each show's public feed. Video podcasts: paste a YouTube channel link.",
            "What do you want to listen to?", "Paste a YouTube channel or podcast feed (RSS) link")
        self.podcasts_page.search_requested.connect(self.search_podcasts)
        self.podcasts_page.link_added.connect(self.follow_link)
        self.audiobooks_page = ShowsHome(
            "Audiobooks", "Free audiobooks of public-domain books, read by LibriVox volunteers and hosted by the "
            "Internet Archive. Stream them or download whole books.", "Search by title or author")
        self.audiobooks_page.search_requested.connect(self.search_books)
        self.show_page = ShowPage()
        self.show_page.play_clicked.connect(self._play_show)
        self.show_page.follow_clicked.connect(self._toggle_follow)
        self.show_page.download_all_clicked.connect(self._download_whole_show)
        self.video_page = VideoPage()
        self.video_page.audio_only_requested.connect(self._video_to_audio)
        self.video_page.error.connect(lambda msg: self.show_status(f"⚠ Video: {msg}", 10000))
        self._video_song = None
        for page in (self.podcasts_page, self.audiobooks_page, self.show_page, self.video_page):
            page.setObjectName("page")
            page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            page.setStyleSheet("#page { background: transparent; }")
            self.stack.addWidget(page)
        self.stack.currentChanged.connect(self._page_changed)

    def _page_changed(self, _index):
        # Leaving the video: stop it, remember where it was.
        if self.stack.currentWidget() is not self.video_page and self._video_song is not None:
            self._remember_position(self._video_song, self.video_page.position())
            self.video_page.stop()
            self._video_song = None

    # ==================================================================================================
    # Images
    # ==================================================================================================
    def _with_image(self, url, callback):
        """callback(QPixmap) now if the picture is cached, otherwise when it has downloaded."""
        path = self.net.cached_image(url)
        if path:
            callback(QPixmap(path))
            return
        if url and self.online_enabled:
            self.online_call(self.net.get_image, url, on_done=lambda p: p and callback(QPixmap(p)))

    def _card(self, title, subtitle, image_url, on_open, on_play=None, round_art=False):
        from .main_window import load_pixmap
        c = Card(load_pixmap(PLACEHOLDER_IMAGE), title, subtitle, round_art=round_art)
        c.clicked.connect(on_open)
        c.play_clicked.connect(on_play or on_open)
        self._with_image(image_url, lambda pm, card=c: self._set_card_art(card, pm, round_art))
        return c

    @staticmethod
    def _set_card_art(card, pm, round_art):
        from .library_panel import rounded
        try:
            card.art.setPixmap(rounded(pm, 160, 80 if round_art else 6))
        except RuntimeError:          # the card was replaced meanwhile
            pass

    # ==================================================================================================
    # Podcasts page
    # ==================================================================================================
    def followed_shows(self):
        return [podcasts.Show.from_dict(d) for d in self.user_data.shows]

    def show_podcasts(self):
        self.stack.setCurrentWidget(self.podcasts_page)
        self._set_nav("podcasts")
        self.refresh_podcasts_page()
        if self._top_shows is None and self.online_enabled:
            self._top_shows = []
            self.online_call(podcasts.top_shows, self.net, country_code(),
                             on_done=lambda shows: (setattr(self, "_top_shows", shows), self.refresh_podcasts_page()),
                             on_error=lambda e: setattr(self, "_top_shows", None))

    def _show_cards(self, shows):
        return [self._card(s.title, s.author or ("YouTube" if s.kind == "youtube" else "Podcast"), s.image_url,
                           lambda s=s: self.open_show(s)) for s in shows]

    def refresh_podcasts_page(self):
        sections = []
        if self._podcast_results is not None:
            sections.append((f"Results for “{self._podcast_query}”", self._show_cards(self._podcast_results), 0))
        sections.append(("Your shows", self._show_cards(self.followed_shows()), 0))
        cont = self._continue_cards(("podcast", "youtube"))
        sections.append(("Continue listening", cont, 1))
        if self._top_shows:
            sections.append(("Top podcasts", self._show_cards(self._top_shows), 0))
        msg = "" if self.online_enabled else "You're offline or online features are off: downloaded episodes still play."
        if not self.user_data.shows and self._podcast_results is None:
            msg = msg or "Follow a show and its new episodes show up here and in Your Library."
        self.podcasts_page.set_sections(sections, msg)

    def search_podcasts(self, term):
        if not term:
            self._podcast_results = None
            self.refresh_podcasts_page()
            return
        self._podcast_query = term
        self.online_call(podcasts.search, self.net, term, 30, country_code(),
                         on_done=lambda shows: (setattr(self, "_podcast_results", shows), self.refresh_podcasts_page()),
                         on_error=lambda e: self.show_status(f"⚠ Podcast search failed: {e}", 8000))

    def follow_link(self, text):
        text = (text or "").strip()
        if not text:
            return
        if podcasts.is_youtube_link(text):
            show = podcasts.Show(title="YouTube channel", feed_url=text, kind="youtube")
        elif text.startswith(("http://", "https://")):
            show = podcasts.Show(title="Podcast", feed_url=text)
        else:
            self.show_status("⚠ Paste a YouTube channel link or a podcast feed (RSS) address.", 8000)
            return
        self.open_show(show, follow=True)

    # ==================================================================================================
    # A show (podcast / YouTube channel) or a book
    # ==================================================================================================
    def is_followed(self, key):
        return any(podcasts.Show.from_dict(d).key == key for d in self.user_data.shows) or \
            any(audiobooks.Book.from_dict(d).key == key for d in self.user_data.books)

    def open_show(self, show, follow=False):
        self._show_ctx = dict(kind="show", obj=show, items=[], episodes=[])
        self._render_show(loading=True)
        self.stack.setCurrentWidget(self.show_page)
        self._set_nav("show", show.key)

        def done(result):
            fresh, episodes = result
            if follow and not self.is_followed(fresh.key):
                self.user_data.shows.append(fresh.to_dict())
                self.save_now()
                self._refresh_library_panel()
                self.show_status(f"Following {fresh.title}", kind="info", timeout_ms=4000)
            elif self.is_followed(fresh.key):              # keep the saved copy up to date (title, picture)
                self.user_data.shows = [fresh.to_dict() if podcasts.Show.from_dict(d).key == fresh.key else d
                                        for d in self.user_data.shows]
            if self._show_ctx and self._show_ctx["obj"].key in (show.key, fresh.key):
                self._show_ctx.update(obj=fresh, episodes=episodes, items=[RemoteSong(e.track) for e in episodes])
                self._render_show()

        def failed(err):
            if self._show_ctx and self._show_ctx["obj"] is show:
                self._render_show(message=f"Couldn't load this show: {err}")
        if self.online_enabled:
            self.online_call(podcasts.fetch_show, self.net, show, on_done=done, on_error=failed)
        else:
            self._render_show(message="You're offline or online features are off. Downloaded episodes are in "
                                      "Your Library under Downloaded.")

    def open_book(self, book):
        self._show_ctx = dict(kind="book", obj=book, items=[], episodes=[])
        self._render_show(loading=True)
        self.stack.setCurrentWidget(self.show_page)
        self._set_nav("show", book.key)

        def done(result):
            fresh, tracks = result
            if self._show_ctx and self._show_ctx["obj"].key == fresh.key:
                self._show_ctx.update(obj=fresh, items=[RemoteSong(t) for t in tracks])
                self._render_show()
        if self.online_enabled:
            self.online_call(audiobooks.chapters, self.net, book, on_done=done,
                             on_error=lambda e: self._render_show(message=f"Couldn't load this book: {e}"))
        else:
            self._render_show(message="You're offline or online features are off.")

    def _render_show(self, loading=False, message=""):
        ctx = self._show_ctx
        if ctx is None:
            return
        obj, kind = ctx["obj"], ctx["kind"]
        followed = self.is_followed(obj.key)
        rows = []
        playing_key = item_key(self.current_song) if self.current_song is not None else ""
        if kind == "book":
            image = obj.cover_url
            for i, song in enumerate(ctx["items"], 1):
                rows.append(self._episode_row(song, f"{i}. {song.title}", "", show_cover=False, playing_key=playing_key))
            label = "Audiobook"
            author = obj.author
            follow_text = ("Add to Your Library", "In Your Library")
            description = obj.description
        else:
            image = obj.image_url
            episodes = ctx["episodes"]
            for song, ep in zip(ctx["items"], episodes):
                meta = ep.date_text
                rows.append(self._episode_row(song, song.title, ep.description, meta_prefix=meta,
                                              playing_key=playing_key))
            label = "YouTube channel · video podcast" if obj.kind == "youtube" else "Podcast"
            author = obj.author
            follow_text = ("Follow", "Following")
            description = obj.description
        if loading:
            message = "Loading…"
        elif not rows and not message:
            message = "No episodes found." if kind != "book" else "No chapters found."
        self.show_page.build(label, obj.title, author, description, followed, rows,
                             top_colour="#2d4a5a" if kind != "book" else "#5a3d2d",
                             can_download_all=kind == "book" and bool(rows), follow_text=follow_text, message=message)
        self._with_image(image, self.show_page.set_cover)
        cover_cache = {}
        for row, song in zip(rows, ctx["items"]):
            url = song.track.cover_url or image
            if kind == "book":
                continue
            if url in cover_cache:
                row.set_cover(cover_cache[url])
                continue
            self._with_image(url, lambda pm, r=row, u=url: (cover_cache.__setitem__(u, pm), self._safe(r.set_cover, pm)))

    @staticmethod
    def _safe(fn, *args):
        try:
            fn(*args)
        except RuntimeError:          # the row was replaced meanwhile
            pass

    def _episode_row(self, song, title, description, meta_prefix="", show_cover=True, playing_key=""):
        key = item_key(song)
        saved = self.user_data.resume.get(key)
        length = song.track.duration_ms
        bits = [meta_prefix] if meta_prefix else []
        if saved and length:
            left = max(0, length - saved["ms"])
            bits.append(f"{podcasts.format_duration(left)} left")
        elif length:
            bits.append(podcasts.format_duration(length))
        offline = self.user_data.offline.get(key)
        downloaded = bool(offline and os.path.exists(offline))
        downloading = key in self._item_keys_waiting()
        row = EpisodeRow(title, "  •  ".join(b for b in bits if b), description, playing=key == playing_key,
                         downloaded=downloaded, downloading=downloading, can_watch=song.track.source == "youtube",
                         finished=key in self.user_data.finished, show_cover=show_cover)
        row.play_clicked.connect(lambda s=song: self.play_item(s))
        row.download_clicked.connect(lambda s=song: self.download_items([s]))
        row.watch_clicked.connect(lambda s=song: self.watch_item(s))
        row.context_requested.connect(lambda pos, s=song: self._item_menu(s, pos))
        return row

    def _item_menu(self, song, pos):
        menu = self._new_menu()
        menu.addAction("▶  Play").triggered.connect(lambda: self.play_item(song))
        menu.addAction("≡  Add to queue").triggered.connect(lambda: self.add_to_queue(song))
        key = item_key(song)
        path = self.user_data.offline.get(key)
        if path and os.path.exists(path):
            menu.addAction("📂  Show in folder").triggered.connect(
                lambda: __import__("core.platform_fixes", fromlist=["x"]).reveal_in_file_manager(path))
            menu.addAction("✕  Remove download").triggered.connect(lambda: self.remove_item_download(song))
        else:
            menu.addAction("⬇  Download").triggered.connect(lambda: self.download_items([song]))
        if key in self.user_data.finished:
            menu.addAction("Mark as not played").triggered.connect(lambda: self._mark_finished(song, False))
        else:
            menu.addAction("✓  Mark as played").triggered.connect(lambda: self._mark_finished(song, True))
        if song.track.page_url:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            menu.addAction("↗  Open web page").triggered.connect(
                lambda: QDesktopServices.openUrl(QUrl(song.track.page_url)))
        menu.exec(pos)

    def _toggle_follow(self):
        ctx = self._show_ctx
        if ctx is None:
            return
        obj = ctx["obj"]
        if ctx["kind"] == "book":
            if self.is_followed(obj.key):
                self.user_data.books = [d for d in self.user_data.books if audiobooks.Book.from_dict(d).key != obj.key]
            else:
                self.user_data.books.append(obj.to_dict())
        else:
            if self.is_followed(obj.key):
                self.user_data.shows = [d for d in self.user_data.shows if podcasts.Show.from_dict(d).key != obj.key]
            else:
                self.user_data.shows.append(obj.to_dict())
        self.save_now()
        self._refresh_library_panel()
        self._render_show()

    def _play_show(self):
        ctx = self._show_ctx
        if not ctx or not ctx["items"]:
            return
        items = ctx["items"]
        if ctx["kind"] == "book":
            # Carry on where you left off: the first chapter not finished.
            start = next((s for s in items if item_key(s) not in self.user_data.finished), items[0])
            self.play_item(start)
        else:
            self.play_item(items[0])                         # the newest episode

    def play_item(self, song):
        ctx = self._show_ctx
        queue = ctx["items"] if ctx and song in ctx["items"] else [song]
        if ctx and ctx["kind"] == "show" and song in ctx["items"]:
            queue = ctx["items"][ctx["items"].index(song):]   # podcasts: this episode, then older ones
        title = ctx["obj"].title if ctx else song.album
        self.play_song(song, queue=queue, source=title)

    def _mark_finished(self, song, done):
        key = item_key(song)
        if done:
            if key not in self.user_data.finished:
                self.user_data.finished.append(key)
            self.user_data.resume.pop(key, None)
        else:
            self.user_data.finished = [k for k in self.user_data.finished if k != key]
        self.schedule_save()
        if self.stack.currentWidget() is self.show_page:
            self._render_show()

    # ==================================================================================================
    # Playing episodes and chapters (called from MainWindow._start_current)
    # ==================================================================================================
    def start_item(self, song):
        """Play a podcast episode / chapter / YouTube episode: the downloaded file if there is one, else stream.
        Continues where you left off."""
        key = item_key(song)
        saved = self.user_data.resume.get(key)
        self._pending_resume = (key, saved["ms"]) if saved and saved.get("ms", 0) > 5000 else None
        path = self.user_data.offline.get(key)
        kind = {"podcast": "Podcast", "audiobook": "Audiobook", "youtube": "Video podcast"}[song.track.source]
        if path and os.path.exists(path):
            self._set_now_playing_text(song.title, song.artist, f"{kind} · downloaded")
            self._play_media(path)
            return
        if not self.online_enabled:
            self.player.stop()
            self._track_handled = True
            self._handle_failed_track("needs the internet (or download it first)")
            return
        if song.track.source == "youtube":
            self._set_now_playing_text(song.title, song.artist, "Finding the audio…")
            self.player.stop()
            self._track_handled = True

            def done(res, s=song):
                if self.current_song is s:
                    self._set_now_playing_text(s.title, s.artist, kind)
                    self._play_media(res[0], res[1])

            def failed(err, s=song):
                if self.current_song is s:
                    self._track_handled = True
                    self._handle_failed_track(f"YouTube didn't give the audio ({err})")
            self.online_call(podcasts.youtube_stream, song.track.page_url, on_done=done, on_error=failed)
            return
        self._set_now_playing_text(song.title, song.artist, kind)
        self._play_media(song.track.stream_url)

    def apply_pending_resume(self):
        """Called by update_progress once playback has started: jump to where you left off."""
        pr = self._pending_resume
        if pr is None or self.current_song is None or item_key(self.current_song) != pr[0]:
            return
        self._pending_resume = None
        length = self.player.get_length()
        if not length or pr[1] < length - 15000:
            self.player.set_time(int(pr[1]))
            self.show_status(f"Continuing from {pr[1] // 60000}:{(pr[1] // 1000) % 60:02d}", kind="info",
                             timeout_ms=3000)

    def track_item_progress(self, position_ms):
        """Called while an episode / chapter plays: remember the position every few seconds."""
        song = self.current_song
        if song is None or not item_key(song) or getattr(self, "private_session", False):
            return
        now = time.time()
        if (now - self._resume_saved_at) * 1000 < RESUME_SAVE_MS:
            return
        self._resume_saved_at = now
        self._remember_position(song, position_ms)

    def _remember_position(self, song, position_ms):
        key = item_key(song)
        if not key or position_ms < 5000:
            return
        self.user_data.resume[key] = {"ms": int(position_ms), "t": time.time(), "track": song.track.to_dict()}
        # keep the 200 most recent
        if len(self.user_data.resume) > 200:
            for k, _v in sorted(self.user_data.resume.items(), key=lambda kv: kv[1].get("t", 0))[:-200]:
                self.user_data.resume.pop(k, None)
        self.schedule_save(3000)

    def item_finished(self, song):
        """The episode / chapter played to the end."""
        key = item_key(song)
        if key:
            self.user_data.resume.pop(key, None)
            if key not in self.user_data.finished:
                self.user_data.finished.append(key)
            self.schedule_save()

    def _continue_cards(self, sources):
        items = sorted(((k, v) for k, v in self.user_data.resume.items() if v.get("track", {}).get("source") in sources),
                       key=lambda kv: kv[1].get("t", 0), reverse=True)[:12]
        cards = []
        for _k, v in items:
            song = RemoteSong(OnlineTrack.from_dict(v["track"]))
            left = max(0, song.track.duration_ms - v["ms"])
            sub = f"{podcasts.format_duration(left)} left" if song.track.duration_ms else song.artist
            cards.append(self._card(song.title, sub, song.track.cover_url,
                                    lambda s=song: self.play_song(s, queue=[s], source=s.album or s.artist)))
        return cards

    # ==================================================================================================
    # Watching a video podcast
    # ==================================================================================================
    def watch_item(self, song):
        if not self.online_enabled:
            self.show_status("⚠ Watching needs the internet.", 6000)
            return
        if self.player.is_playing():
            self.play_pause_song()
        self.show_status("Loading the video…", kind="info", timeout_ms=8000)
        saved = self.user_data.resume.get(item_key(song))

        def done(res):
            self._video_song = song
            self.stack.setCurrentWidget(self.video_page)
            self._set_nav("video", item_key(song))
            self.video_page.play(res[0], song.title, saved["ms"] if saved else 0, self.user_data.volume)
        self.online_call(podcasts.youtube_stream, song.track.page_url, True, on_done=done,
                         on_error=lambda e: self.show_status(f"⚠ Couldn't load the video: {e}", 10000))

    def _video_to_audio(self, position_ms):
        song = self._video_song
        self._video_song = None
        if song is None:
            return
        self._remember_position(song, position_ms)
        self._resume_saved_at = 0
        self.go_back()
        self.play_item(song)

    # ==================================================================================================
    # Downloading episodes and chapters (direct files; YouTube through yt-dlp)
    # ==================================================================================================
    def _item_keys_waiting(self):
        keys = {item_key(s) for s, _p in self._item_queue}
        if self._item_active is not None:
            keys.add(item_key(self._item_active[0]))
        return keys

    def _item_path(self, song):
        """Where an episode or chapter is saved. These folders are marked so they never show up as music."""
        root = self.download_folder()
        t = song.track
        if t.source == "audiobook":
            folder = mark_no_scan(os.path.join(root, "Audiobooks"))
            book_dir = os.path.join(folder, podcasts.safe_folder(f"{t.artist} - {t.album}"))
            index = 1
            ctx = self._show_ctx
            if ctx and song in ctx["items"]:
                index = ctx["items"].index(song) + 1
            return os.path.join(book_dir, audiobooks.chapter_filename(index, t))
        folder = mark_no_scan(os.path.join(root, "Podcasts"))
        ep = podcasts.Episode(track=t, published=self._episode_date(song))
        return os.path.join(folder, podcasts.safe_folder(t.album or t.artist), podcasts.episode_filename(ep))

    def _episode_date(self, song):
        ctx = self._show_ctx
        if ctx and ctx.get("episodes") and song in ctx["items"]:
            return ctx["episodes"][ctx["items"].index(song)].published
        return 0.0

    def download_items(self, songs):
        if not self.online_enabled:
            self.show_status("⚠ Downloading needs the internet.", 6000)
            return 0
        waiting = self._item_keys_waiting()
        added = 0
        for s in songs:
            key = item_key(s)
            path = self.user_data.offline.get(key)
            if not key or key in waiting or (path and os.path.exists(path)):
                continue
            self._item_queue.append((s, self._item_path(s)))
            added += 1
        if added:
            self.show_status(f"⬇ Downloading {added} {'chapter' if songs[0].track.source == 'audiobook' else 'episode'}"
                             f"{'s' if added != 1 else ''}…", kind="info", timeout_ms=4000)
            self._next_item_download()
            if self.stack.currentWidget() is self.show_page:
                self._render_show()
        return added

    def _download_whole_show(self):
        if self._show_ctx:
            self.download_items(self._show_ctx["items"])

    def _next_item_download(self):
        if self._item_active is not None or not self._item_queue:
            return
        song, path = self._item_queue.pop(0)
        self._item_active = (song, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        def work():
            if song.track.source == "youtube":
                return podcasts.download_youtube_audio(song.track.page_url, os.path.splitext(path)[0])
            return self.net.download(song.track.download_url or song.track.stream_url, path)

        def done(result):
            self._item_active = None
            self.user_data.offline[item_key(song)] = result
            self.schedule_save()
            if not self._item_queue:
                self.show_status("⬇ Downloads finished", kind="info", timeout_ms=5000)
            self._after_item_download()

        def failed(err):
            self._item_active = None
            self.show_status(f"⚠ Couldn't download “{song.title}”: {err}", 10000)
            self._after_item_download()
        from .async_tasks import run_async
        run_async(self, work, on_done=done, on_error=failed)

    def _after_item_download(self):
        if self.stack.currentWidget() is self.show_page:
            self._render_show()
        self._refresh_library_panel()
        self._next_item_download()

    def remove_item_download(self, song):
        key = item_key(song)
        path = self.user_data.offline.pop(key, None)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                self.show_status(f"⚠ Couldn't delete the file: {e}", 8000)
        self.schedule_save()
        if self.stack.currentWidget() is self.show_page:
            self._render_show()

    # ==================================================================================================
    # Audiobooks page
    # ==================================================================================================
    def saved_books(self):
        return [audiobooks.Book.from_dict(d) for d in self.user_data.books]

    def _book_cards(self, books):
        return [self._card(b.title, b.author, b.cover_url, lambda b=b: self.open_book(b)) for b in books]

    def show_audiobooks(self):
        self.stack.setCurrentWidget(self.audiobooks_page)
        self._set_nav("audiobooks")
        self.refresh_audiobooks_page()
        if self._popular_books is None and self.online_enabled:
            self._popular_books = []
            self.online_call(audiobooks.popular, self.net,
                             on_done=lambda b: (setattr(self, "_popular_books", b), self.refresh_audiobooks_page()),
                             on_error=lambda e: setattr(self, "_popular_books", None))
            self.online_call(audiobooks.newest, self.net,
                             on_done=lambda b: (setattr(self, "_new_books", b), self.refresh_audiobooks_page()))

    def refresh_audiobooks_page(self):
        sections = []
        if self._book_results is not None:
            sections.append((f"Results for “{self._book_query}”", self._book_cards(self._book_results), 0))
        sections.append(("Your audiobooks", self._book_cards(self.saved_books()), 0))
        sections.append(("Continue listening", self._continue_cards(("audiobook",)), 1))
        if self._popular_books:
            sections.append(("Popular free audiobooks", self._book_cards(self._popular_books), 0))
        if self._new_books:
            sections.append(("Newly added", self._book_cards(self._new_books), 1))
        msg = "" if self.online_enabled else "You're offline or online features are off: downloaded books still play."
        self.audiobooks_page.set_sections(sections, msg)

    def search_books(self, term):
        if not term:
            self._book_results = None
            self.refresh_audiobooks_page()
            return
        self._book_query = term
        self.online_call(audiobooks.search, self.net, term,
                         on_done=lambda b: (setattr(self, "_book_results", b), self.refresh_audiobooks_page()),
                         on_error=lambda e: self.show_status(f"⚠ Audiobook search failed: {e}", 8000))

    # ==================================================================================================
    # Browse (genre tiles) and genre pages
    # ==================================================================================================
    def browse_tiles(self):
        tiles = []
        for name, colour, slot in (("Podcasts", "#006450", self.show_podcasts),
                                   ("Audiobooks", "#1e3264", self.show_audiobooks)):
            t = BrowseTile(name, colour)
            t.clicked.connect(slot)
            tiles.append(t)
        for i, g in enumerate(self._genres or []):
            t = BrowseTile(g["name"], TILE_COLOURS[(i + 2) % len(TILE_COLOURS)])
            t.clicked.connect(lambda g=g: self.show_genre(g))
            self._with_image(g["picture"], lambda pm, tile=t: self._safe(tile.set_pixmap, pm))
            tiles.append(t)
        return tiles

    def load_genres(self, then=None):
        if self._genres is not None or not self.online_enabled:
            return
        self._genres = []

        def done(genres):
            self._genres = genres
            if then:
                then()
        def failed(err):
            self._genres = None
            print(f"Browse: couldn't load genres: {err!r}")
        self.online_call(self.online.deezer.genres, on_done=done, on_error=failed)

    def show_genre(self, genre):
        self.show_status(f"Loading {genre['name']}…", kind="info", timeout_ms=8000)

        def done(tracks):
            songs = self.radio_items(tracks)
            cover = self.net.cached_image(genre["picture"]) or PLACEHOLDER_IMAGE
            self.collection_table.mark_pending = True
            self.collection_table.download_state = self.downloads.state
            self._show_collection("Genre", genre["name"], songs, cover,
                                  f"Popular right now  •  {len(songs)} songs  •  double-click to play",
                                  ("genre", genre["id"]))
            self.fetch_covers(songs)
            self.clear_status()
        self.online_call(self.online.deezer.genre_chart, genre["id"], on_done=done,
                         on_error=lambda e: self.show_status(f"⚠ Couldn't load {genre['name']}: {e}", 8000))

    # ==================================================================================================
    # Your Library entries
    # ==================================================================================================
    def _refresh_library_when_cover_arrives(self, url):
        if url and not self.net.cached_image(url):
            self._with_image(url, lambda _pm: self._refresh_library_panel())

    def library_show_entries(self):
        """Followed shows and saved books for Your Library: dicts with kind, title, subtitle, cover path, open."""
        out = []
        if not self.online_enabled:
            pass
        else:
            for url in [s.image_url for s in self.followed_shows()] + [b.cover_url for b in self.saved_books()]:
                if url and not self.net.cached_image(url) and url not in self._covers_asked:
                    self._covers_asked.add(url)
                    self._refresh_library_when_cover_arrives(url)
        for s in self.followed_shows():
            out.append(dict(kind="podcast", key=s.key, title=s.title,
                            subtitle=("YouTube" if s.kind == "youtube" else "Podcast") + (f" • {s.author}" if s.author else ""),
                            cover_path=self.net.cached_image(s.image_url) or PLACEHOLDER_IMAGE, obj=s))
        for b in self.saved_books():
            out.append(dict(kind="audiobook", key=b.key, title=b.title, subtitle=f"Audiobook • {b.author}",
                            cover_path=self.net.cached_image(b.cover_url) or PLACEHOLDER_IMAGE, obj=b))
        return out

    def open_library_show(self, entry):
        if entry["kind"] == "audiobook":
            self.open_book(entry["obj"])
        else:
            self.open_show(entry["obj"])

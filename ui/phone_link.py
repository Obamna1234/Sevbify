"""Sevbify on your phone and this computer: pair with a QR code, then send songs and folders either way.

The network side is core/pairing.py (same Wi-Fi only, encrypted, nothing via the internet). This file is the
computer's windows: the "Pair a phone" card with the QR code, the "<phone> wants to send you…" question, progress in
the status line, and "Send to <phone>" for songs and playlists.

The listener only runs while there is a paired phone (or the pairing card is open) and Settings → Your phone →
"Let paired phones connect" is on.
"""
import os
import platform as _platform
import socket

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton

from . import theme
from .dialogs import _Card


def _human(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024


def qr_pixmap(text, size=280):
    import segno
    import io
    buf = io.BytesIO()
    segno.make(text, error="m", micro=False).save(buf, kind="png", scale=10, border=2, dark="#000000",
                                                   light="#ffffff")
    pm = QPixmap()
    pm.loadFromData(buf.getvalue(), "PNG")
    return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)


class _Bridge(QObject):
    """Network threads -> the window (Qt signals cross threads safely)."""
    paired = pyqtSignal(str, str)
    connected = pyqtSignal(object)
    closed = pyqtSignal(object)
    offer = pyqtSignal(object, str, str, object)
    progress = pyqtSignal(object, str, object, object)
    received = pyqtSignal(object, str, object)
    sent = pyqtSignal(object, str, bool)

    # the core's callbacks (called on network threads)
    def on_paired(self, dev, name):
        self.paired.emit(dev, name)

    def on_connected(self, sess):
        self.connected.emit(sess)

    def on_closed(self, sess):
        self.closed.emit(sess)

    def on_offer(self, sess, oid, title, items):
        self.offer.emit(sess, oid, title, items)

    def on_progress(self, sess, oid, done, total):
        self.progress.emit(sess, oid, done, total)

    def on_received(self, sess, oid, paths):
        self.received.emit(sess, oid, paths)

    def on_sent(self, sess, oid, ok):
        self.sent.emit(sess, oid, ok)


class PhoneLink(QObject):
    phones_changed = pyqtSignal()

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.server = None
        self.bridge = _Bridge()
        self.bridge.paired.connect(self._paired)
        self.bridge.connected.connect(lambda s: self._changed(f"{s.name} connected"))
        self.bridge.closed.connect(lambda s: self._changed(""))
        self.bridge.offer.connect(self._offer)
        self.bridge.progress.connect(self._progress)
        self.bridge.received.connect(self._received)
        self.bridge.sent.connect(self._sent)
        self._dialog = None
        self._last_pct = {}

    # --- running ---------------------------------------------------------------------------------------------
    def _receive_folder(self):
        folders = self.win.active_music_folders() if hasattr(self.win, "active_music_folders") else []
        return str(folders[0]) if folders else os.path.join(self.win.storage.data_dir, "Received music")

    def _ensure_server(self):
        if self.server is not None:
            return self.server
        from core import pairing
        from core.version import app_version
        name = socket.gethostname() or _platform.node() or "Computer"
        self.server = pairing.PairServer(self.win.storage.data_dir, self._receive_folder(), name, app_version(),
                                         self.bridge)
        self.server.start()
        return self.server

    def available(self):
        try:
            import Cryptodome  # noqa: F401
            import segno  # noqa: F401
            return True
        except Exception:
            return False

    def start_if_paired(self):
        """At start-up: listen only if a phone is paired and the setting is on."""
        if not getattr(self.win.user_data, "phone_link", True) or not self.available():
            return
        from core.pairing import DeviceStore
        if DeviceStore(self.win.storage.data_dir).devices:
            try:
                self._ensure_server()
            except OSError as e:
                self.win.show_status(f"Couldn't listen for your phone: {e}")

    def stop(self):
        if self.server is not None:
            self.server.stop()
            self.server = None

    def phones(self):
        from core.pairing import DeviceStore
        store = self.server.store if self.server is not None else DeviceStore(self.win.storage.data_dir)
        live = {s.dev for s in (self.server.connected() if self.server else [])}
        return [dict(p, connected=p["id"] in live) for p in store.listing()]

    def connected(self):
        return self.server.connected() if self.server is not None else []

    def forget(self, dev):
        from core.pairing import DeviceStore
        if self.server is not None:
            self.server.forget(dev)
            if not self.server.store.devices:
                self.stop()
        else:
            DeviceStore(self.win.storage.data_dir).remove(dev)
        self.phones_changed.emit()

    def _changed(self, note):
        if note:
            self.win.show_status(note, kind="info", timeout_ms=4000)
        self.phones_changed.emit()

    # --- pairing card -------------------------------------------------------------------------------------------
    def open_pairing(self):
        if not self.available():
            self.win.show_status("Pairing needs the 'pycryptodomex' and 'segno' packages (included in the ready-made "
                                 "app).")
            return
        try:
            srv = self._ensure_server()
        except OSError as e:
            self.win.show_status(f"Couldn't start pairing: {e}")
            return
        d = PairDialog(self.win, srv)
        self._dialog = d
        d.finished.connect(lambda _r: (srv.close_pairing(), setattr(self, "_dialog", None),
                                       (not srv.store.devices or not getattr(self.win.user_data, "phone_link", True))
                                       and self.stop()))
        if getattr(self.win, "_auto_answer_dialogs", None) is not None:      # tests
            d.show()
            return d
        d.exec()
        return d

    def _paired(self, dev, name):
        if self._dialog is not None:
            self._dialog.done_pairing(name)
        self.win.show_status(f"Paired with {name}", kind="info", timeout_ms=5000)
        self.phones_changed.emit()

    # --- receiving -------------------------------------------------------------------------------------------------
    def _offer(self, sess, oid, title, items):
        from .dialogs import confirm
        total = sum(s for _p, s in items)
        what = f"{len(items)} file{'s' if len(items) != 1 else ''} ({_human(total)})"
        names = ", ".join(os.path.basename(p) for p, _s in items[:3]) + ("…" if len(items) > 3 else "")
        text = (f"<b>{_esc(sess.name)}</b> wants to send you {what}{' — ' + _esc(title) if title else ''}.<br><br>"
                f"{_esc(names)}<br><br>They'll be saved in your music folder, in “From {_esc(sess.name)}”.")
        ok = confirm(self.win, "Receive music?", text, ok_text="Accept", cancel_text="Decline", safe_default=True)
        sess.answer(oid, ok)

    def _progress(self, sess, oid, done, total):
        pct = int(100 * done / max(1, total))
        if self._last_pct.get(oid) == pct:
            return
        self._last_pct[oid] = pct
        self.win.show_status(f"{sess.name}: {pct}%", kind="info", timeout_ms=3000)

    def _received(self, sess, oid, paths):
        self._last_pct.pop(oid, None)
        n = len(paths)
        self.win.show_status(f"Received {n} file{'s' if n != 1 else ''} from {sess.name}", kind="info",
                             timeout_ms=6000)
        if n and hasattr(self.win, "rescan_library"):
            self.win.rescan_library()

    def _sent(self, sess, oid, ok):
        self._last_pct.pop(oid, None)
        self.win.show_status(f"Sent to {sess.name}" if ok else f"{sess.name} didn't take the music",
                             kind="info", timeout_ms=5000)

    # --- sending -------------------------------------------------------------------------------------------------
    def send(self, sess, paths, title=""):
        paths = [p for p in paths if p and os.path.exists(p)]
        if not paths:
            self.win.show_status("Only songs on this computer can be sent (download them first).")
            return
        try:
            sess.send_paths(paths, title)
            self.win.show_status(f"Waiting for {sess.name} to accept…", kind="info", timeout_ms=8000)
        except ValueError as e:
            self.win.show_status(str(e))


def _esc(text):
    import html
    return html.escape(str(text))


class PairDialog(_Card):
    """Spotify-style card: a QR code to scan with Sevbify on the phone (Your Library → ⋯ → Pair with computer)."""

    def __init__(self, win, server):
        super().__init__(win, light=False)
        self.server = server
        self.setMinimumWidth(420)
        h = QLabel("Pair your phone")
        h.setStyleSheet("font-size: 22px; font-weight: 800;")
        self.body.addWidget(h)
        t = QLabel("In Sevbify on your phone, open Settings → Your computer → Pair with a computer, and scan this "
                   "code. Your phone needs to be on the same Wi-Fi. If your computer asks whether Sevbify may use "
                   "the network (Windows firewall, Mac), choose Allow – on private networks only is enough.")
        t.setWordWrap(True)
        t.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
        self.body.addWidget(t)
        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setStyleSheet("background: white; border-radius: 12px; padding: 12px;")
        self.body.addWidget(self.qr, 0, Qt.AlignmentFlag.AlignHCenter)
        self.status = QLabel()
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 13px;")
        self.body.addWidget(self.status)
        row = QHBoxLayout()
        self.new_btn = QPushButton("New code")
        self.new_btn.clicked.connect(self.new_code)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        for b in (self.new_btn, close):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("QPushButton { color: white; background: transparent; border: 1px solid #7c7c7c;"
                            " border-radius: 16px; padding: 6px 16px; font-weight: 700; }"
                            " QPushButton:hover { border-color: white; }")
        row.addStretch()
        row.addWidget(self.new_btn)
        row.addWidget(close)
        self.body.addLayout(row)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self.link = ""
        self._paired = False
        self.new_code()

    def new_code(self):
        from core import pairing
        self.link = self.server.open_pairing()
        self.qr.setPixmap(qr_pixmap(self.link))
        self.qr.setVisible(True)
        self.new_btn.setVisible(False)
        self._left = pairing.PAIR_WINDOW_SECONDS
        self._tick()

    def _tick(self):
        if self._paired:
            return
        self._left -= 1
        if self._left <= 0 or not self.server.pairing_open():
            self.server.close_pairing()
            self.qr.setVisible(False)
            self.status.setText("This code can't be used any more. Make a new one.")
            self.new_btn.setVisible(True)
            return
        m, s = divmod(self._left, 60)
        self.status.setText(f"Waiting for your phone… (code works for {m}:{s:02d})")

    def done_pairing(self, name):
        self._paired = True
        self.timer.stop()
        self.qr.setVisible(False)
        self.status.setText(f"✓  Paired with {name}")
        self.status.setStyleSheet(f"color: {theme.GREEN}; font-size: 16px; font-weight: 700;")
        QTimer.singleShot(1500, self.accept)

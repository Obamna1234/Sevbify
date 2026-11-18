"""Song menu → Preview (30 s): a small Spotify-style player over Sevbify for a song's 30-second clip.

Plainly a preview (a green "30-SECOND PREVIEW" badge, a 0:30 tag on the cover and 0:30 at the end of the slider).
The clip plays on its own VLC player, so the main song is only paused. The slider can be clicked or dragged
anywhere in the 30 seconds; Restart goes back to 0:00, Add to queue keeps the song for later, ⊕ saves it.
"Play full song" plays the whole song now; Close (✕ or Esc) carries on with your song where it paused.

Everything else (playlists, imports, search results, radio) plays the full song; a clip is never used in their place.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, QTimer, QSize

from . import icons, theme
from .click_slider import ClickSlider


def _clock(ms):
    s = max(0, int(round((ms or 0) / 1000)))
    return f"{s // 60}:{s % 60:02d}"


SLIDER = ("QSlider::groove:horizontal { background: #5a5a5a; height: 4px; border-radius: 2px; }"
          "QSlider::sub-page:horizontal { background: #ffffff; border-radius: 2px; }"
          "QSlider::sub-page:horizontal:hover { background: #1ed760; }"
          "QSlider::handle:horizontal { background: #ffffff; width: 12px; height: 12px; margin: -4px 0;"
          " border-radius: 6px; }")

COVER = 328


def _side_button(icon, text):
    b = QPushButton(text)
    b.setIcon(icon)
    b.setIconSize(QSize(20, 20))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFixedWidth(110)
    b.setStyleSheet(f"QPushButton {{ border: none; background: transparent; color: {theme.SUBDUED}; font-size: 12px;"
                    " padding: 6px; border-radius: 6px; } QPushButton:hover { background: rgba(255,255,255,0.08);"
                    " color: #ffffff; }")
    return b


class PreviewDialog(QDialog):
    def __init__(self, parent, vlc_instance, url, title, artist, cover=None, on_full=None, on_queue=None,
                 on_save=None, saved=False, resume_note=False):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Preview")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(COVER + 40)
        self.player = vlc_instance.media_player_new()
        self.player.set_media(vlc_instance.media_new(url))
        self._dragging = False
        self._drag_from = None
        self.full_chosen = False
        self._on_full = on_full

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("previewCard")
        card.setStyleSheet("#previewCard { border-radius: 14px; background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                           " stop:0 #3b4f6b, stop:0.55 #1f2733, stop:1 #181818); }"
                           " QLabel { color: #ffffff; background: transparent; }")
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        top = QHBoxLayout()
        badge = QLabel("30-SECOND PREVIEW")
        badge.setStyleSheet("background: #1ed760; color: #000000; font-size: 11px; font-weight: 800;"
                            " letter-spacing: 1px; padding: 4px 10px; border-radius: 11px;")
        top.addWidget(badge)
        top.addStretch(1)
        close = QPushButton()
        close.setIcon(icons.close("#ffffff", 16))
        close.setFixedSize(32, 32)
        close.setToolTip("Close (Esc)")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet("QPushButton { border: none; background: rgba(255,255,255,0.14); border-radius: 16px; }"
                            " QPushButton:hover { background: rgba(255,255,255,0.24); }")
        close.clicked.connect(self.close)
        top.addWidget(close)
        lay.addLayout(top)

        art = QLabel()
        art.setFixedSize(COVER, COVER)
        if cover is not None and not cover.isNull():
            from .library_panel import rounded
            art.setPixmap(rounded(cover, COVER, 8))
        else:
            art.setStyleSheet("background: #3e3e3e; border-radius: 8px;")
        tag = QLabel("0:30", art)
        tag.setStyleSheet("background: rgba(0,0,0,0.8); color: #ffffff; font-size: 11px; font-weight: 700;"
                          " padding: 2px 6px; border-radius: 4px;")
        tag.adjustSize()
        tag.move(COVER - tag.width() - 8, COVER - tag.height() - 8)
        lay.addWidget(art, 0, Qt.AlignmentFlag.AlignHCenter)

        names = QHBoxLayout()
        texts = QVBoxLayout()
        texts.setSpacing(2)
        name = QLabel(title or "Unknown song")
        name.setStyleSheet("font-size: 20px; font-weight: 700;")
        who = QLabel(artist or "")
        who.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 14px;")
        texts.addWidget(name)
        texts.addWidget(who)
        names.addLayout(texts, 1)
        self.save_btn = QPushButton()
        self.save_btn.setFixedSize(36, 36)
        self.save_btn.setIconSize(QSize(26, 26))
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
        self._set_saved(saved)
        if on_save is not None:
            self.save_btn.clicked.connect(lambda: self._set_saved(bool(on_save(self.save_btn))))
        names.addWidget(self.save_btn)
        lay.addLayout(names)

        self.slider = ClickSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 30000)
        self.slider.setStyleSheet(SLIDER)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.slider.sliderMoved.connect(lambda v: self.pos_label.setText(_clock(v)))
        self.slider.sliderReleased.connect(self._seek)
        lay.addWidget(self.slider)
        times = QHBoxLayout()
        self.pos_label = QLabel("0:00")
        self.len_label = QLabel("0:30")
        for lbl in (self.pos_label, self.len_label):
            lbl.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 11px;")
        times.addWidget(self.pos_label)
        times.addStretch(1)
        times.addWidget(self.len_label)
        lay.addLayout(times)

        controls = QHBoxLayout()
        restart = _side_button(icons.repeat("#ffffff", 20),
                               "Restart")
        restart.setToolTip("Back to 0:00")
        restart.clicked.connect(self.restart)
        self.button = QPushButton()
        self.button.setFixedSize(60, 60)
        self.button.setIconSize(QSize(24, 24))
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setStyleSheet("QPushButton { background: #ffffff; border: none; border-radius: 30px; }"
                                  " QPushButton:hover { background: #f0f0f0; }")
        self.button.clicked.connect(self.toggle)
        queue = _side_button(icons.queue("#ffffff", 20),
                             "Add to queue")
        if on_queue is not None:
            queue.clicked.connect(on_queue)
        controls.addWidget(restart)
        controls.addStretch(1)
        controls.addWidget(self.button)
        controls.addStretch(1)
        controls.addWidget(queue)
        lay.addLayout(controls)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        full = QPushButton("  Play full song")
        full.setIcon(icons.play("#000000", 14))
        full.setCursor(Qt.CursorShape.PointingHandCursor)
        full.setStyleSheet("QPushButton { background: #1ed760; color: #000000; font-weight: 700; font-size: 14px;"
                           " border: none; border-radius: 22px; padding: 12px; } QPushButton:hover { background: #3be477; }")
        full.clicked.connect(self.play_full)
        shut = QPushButton("Close")
        shut.setCursor(Qt.CursorShape.PointingHandCursor)
        shut.setStyleSheet("QPushButton { background: transparent; color: #ffffff; font-size: 14px;"
                           " border: 1px solid #777777; border-radius: 22px; padding: 12px; }"
                           " QPushButton:hover { border-color: #ffffff; }")
        shut.clicked.connect(self.close)
        buttons.addWidget(full, 1)
        buttons.addWidget(shut, 1)
        lay.addLayout(buttons)
        if resume_note:
            note = QLabel("Close and your song carries on where it was")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            note.setStyleSheet(f"color: {theme.SUBDUED}; font-size: 11px;")
            lay.addWidget(note)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.player.play()
        self._tick()
        if parent is not None:                    # centred over Sevbify, like Spotify's cards
            g = parent.geometry()
            self.adjustSize()
            self.move(g.center().x() - self.width() // 2, g.center().y() - self.height() // 2)

    def _set_saved(self, saved):
        self.save_btn.setIcon(icons.check("#1ed760", 26) if saved else icons.plus(theme.SUBDUED, 26))
        self.save_btn.setToolTip("Saved in…" if saved else "Add to Liked Songs")

    def restart(self):
        self.player.stop()
        self.player.play()

    def play_full(self):
        self.full_chosen = True
        self.close()
        if self._on_full is not None:
            self._on_full()

    # The card has no title bar: drag it by its background.
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_from = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_from is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, e):
        self._drag_from = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        elif e.key() == Qt.Key.Key_Space:
            self.toggle()
        else:
            super().keyPressEvent(e)

    def toggle(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            if self.player.get_state() is not None and str(self.player.get_state()).endswith("Ended"):
                self.player.stop()
            self.player.play()

    def _seek(self):
        self._dragging = False
        if not self.player.is_playing():
            self.player.play()
        self.player.set_time(int(self.slider.value()))

    def _tick(self):
        length = self.player.get_length()
        if length and length > 0 and self.slider.maximum() != length:
            self.slider.setRange(0, int(length))
        pos = max(0, self.player.get_time())
        if not self._dragging:
            self.slider.setValue(int(pos))
        if not self._dragging:
            self.pos_label.setText(_clock(pos))
        self.len_label.setText(_clock(self.slider.maximum()))
        playing = self.player.is_playing()
        self.button.setIcon(icons.pause("#000000", 16) if playing else icons.play("#000000", 16))
        self.button.setToolTip("Pause" if playing else "Play")

    def closeEvent(self, e):
        self.timer.stop()
        try:
            self.player.stop()
            self.player.release()
        except Exception:
            pass
        super().closeEvent(e)

# app.py
import os
import sys
import time
import traceback
from pathlib import Path

# Make sure the project folder is importable even when the app is launched
# from a different working directory (e.g. "python C:\path\to\app.py").
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The ready-made app carries its own copy of VLC's playback engine; use it before anything loads VLC.
from core.vlc_setup import use_bundled_vlc
BUNDLED_VLC = use_bundled_vlc()

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer

# "--smoke-test": start, wait for the library to load, then exit with code 0
# (or non-zero on any error) without showing pop-ups. Used by the automatic
# Windows build to check the packaged .exe really works.
SMOKE_TEST = "--smoke-test" in sys.argv


VLC_HELP = (
    "The music player needs the VLC media player to be installed.\n\n"
    "1. Download VLC from https://www.videolan.org/vlc/\n"
    "2. Install the 64-bit version (it must match your 64-bit Python).\n"
    "3. Start this app again.\n\n"
    "Technical details:\n{details}"
)


def _log_stderr(text: str):
    # A windowed .exe has no console: sys.stderr is None there.
    if sys.stderr is not None:
        try:
            sys.stderr.write(text)
        except Exception:
            pass


def _smoke_log(text: str):
    from core.storage import default_data_dir
    try:
        os.makedirs(default_data_dir(), exist_ok=True)
        with open(os.path.join(default_data_dir(), "smoke-test.log"), "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass


def _smoke_playback():
    """Play a generated one-second tone through libVLC's silent output: WAV, plus MP3, FLAC, OGG, Opus and
    M4A made with the bundled ffmpeg, and the MP3 again as a web stream from a local server (like previews).
    A file VLC can't read ends with length 0. Returns (ok, details)."""
    import functools, http.server, math, struct, subprocess, tempfile, threading, wave
    try:
        import vlc
        lib = getattr(getattr(vlc, "dll", None), "_name", "?")
        if getattr(sys, "frozen", False) and os.name == "nt" and not BUNDLED_VLC:
            return False, f"the app has no bundled VLC (loaded {lib})"
        folder = tempfile.mkdtemp()
        files = [os.path.join(folder, "smoke.wav")]
        with wave.open(files[0], "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 10))) for i in range(22050)))
        from core import downloader
        ff = downloader.engine().ffmpeg_path()
        for name, extra in (("smoke.mp3", []), ("smoke.flac", []), ("smoke.ogg", ["-c:a", "libvorbis"]),
                            ("smoke.opus", ["-c:a", "libopus"]), ("smoke.m4a", ["-c:a", "aac"])):
            out = os.path.join(folder, name)
            subprocess.run([ff, "-y", "-loglevel", "error", "-i", files[0], *extra, out], timeout=60,
                           creationflags=0x08000000 if os.name == "nt" else 0)
            if not os.path.isfile(out):
                return False, f"ffmpeg could not make {name} for the check"
            files.append(out)
        # Serve the folder over http so web-stream playback is checked too (no internet needed).
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):       # the windowed app has no console to log to
                pass

        handler = functools.partial(QuietHandler, directory=folder)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        files.append(f"http://127.0.0.1:{server.server_address[1]}/smoke.mp3")
        inst = vlc.Instance("--aout=adummy", "--no-video", "--quiet")
        results = []
        for path in files:
            player = inst.media_player_new()
            media = inst.media_new(path)
            player.set_media(media)
            player.play()
            end = time.time() + 10
            while time.time() < end and player.get_state() not in (vlc.State.Ended, vlc.State.Error):
                time.sleep(0.05)
            state, length = player.get_state(), media.get_duration()
            player.stop(); player.release()
            label = "web stream" if path.startswith("http") else os.path.splitext(path)[1][1:].upper()
            if state != vlc.State.Ended or length <= 0:
                inst.release()
                why = _vlc_log_for(vlc, path)
                server.shutdown()
                return False, f"{label} did not play ({state}, length {length} ms, libVLC: {lib}). VLC said: {why}"
            results.append(f"{label} {length} ms")
        inst.release()
        server.shutdown()
        return True, f"played {', '.join(results)} with libVLC {vlc.libvlc_get_version().decode()} from {lib}"
    except Exception:
        return False, traceback.format_exc()


def _vlc_log_for(vlc, path):
    """Try `path` again with VLC's own log switched on and return the important lines (for diagnosis)."""
    import tempfile
    log = os.path.join(tempfile.mkdtemp(), "vlc.log")
    try:
        inst = vlc.Instance("--aout=adummy", "--no-video", "--verbose=2", "--file-logging", f"--logfile={log}",
                            "--logmode=text")
        player = inst.media_player_new()
        player.set_media(inst.media_new(path))
        player.play()
        end = time.time() + 10
        while time.time() < end and player.get_state() not in (vlc.State.Ended, vlc.State.Error):
            time.sleep(0.05)
        player.stop(); player.release(); inst.release()
        lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
        lines = [l for l in lines if "does not exist" not in l]          # options of removed video parts
        start = next((i for i, l in enumerate(lines) if "creating access" in l), 0)
        return " | ".join(l.strip() for l in lines[start:start + 60] if l.strip())[:6000]
    except Exception as e:
        return f"(no VLC log: {e})"


def _smoke_canvas(window):
    """Play a generated 2-second looping video in the Now playing panel (the Canvas feature), with Qt's
    video player as packaged in the app. Returns (ok, details)."""
    import subprocess, tempfile
    from PyQt6.QtCore import QEventLoop, QTimer, QUrl
    try:
        from ui.now_playing_panel import HAVE_VIDEO
        player = window.now_playing_panel.video_player
        if not HAVE_VIDEO or player is None:
            return False, "Qt's video player (QtMultimedia) is missing from the app"
        from core import downloader
        ff = downloader.engine().ffmpeg_path()
        path = os.path.join(tempfile.mkdtemp(), "canvas.mp4")
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x400:rate=24:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", path], timeout=60,
                       creationflags=0x08000000 if os.name == "nt" else 0)
        if not os.path.isfile(path):
            return False, "ffmpeg could not make the test video"
        errors = []
        player.errorOccurred.connect(lambda *a: errors.append(player.errorString()))
        player.setSource(QUrl.fromLocalFile(path))
        player.play()
        loop = QEventLoop()
        deadline = time.time() + 15
        poll = QTimer()
        poll.timeout.connect(lambda: loop.quit() if (errors or player.position() > 300 or time.time() > deadline) else None)
        poll.start(50)
        loop.exec()
        poll.stop()
        pos = player.position()
        player.stop()
        if errors or pos <= 300:
            return False, f"the test video did not play (position {pos} ms, errors: {errors})"
        return True, f"looping video played to {pos} ms (H.264 MP4, Qt video player)"
    except Exception:
        return False, traceback.format_exc()


def install_error_guard():
    """Log unexpected errors instead of letting them close the app.

    By default PyQt6 terminates the whole program if any button/timer handler
    raises an error. With this hook the error is written to error.log (next to
    library.json) and shown once, and the music keeps playing.
    """
    from core.storage import default_data_dir
    log_path = os.path.join(default_data_dir(), "error.log")
    last_shown = [0.0]

    def hook(exc_type, exc, tb):
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        _log_stderr(details)
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n{details}")
        except OSError:
            pass
        if SMOKE_TEST:
            _smoke_log("UNEXPECTED ERROR:\n" + details)
            os._exit(3)
        if time.time() - last_shown[0] > 10:  # don't flood the user with pop-ups
            last_shown[0] = time.time()
            QMessageBox.warning(
                None, "Something went wrong",
                f"An unexpected error occurred, but the app is still running.\n\n"
                f"{exc_type.__name__}: {exc}\n\nDetails were saved to:\n{log_path}")

    sys.excepthook = hook


APP_ID = "Obamna1234.Sevbify"
ICON_FILE = os.path.join("assets", "branding", "sevbify_icon_512.png")


def set_app_identity(app):
    """Show Sevbify's own logo in the window, taskbar and Alt+Tab (not Python's)."""
    from PyQt6.QtGui import QIcon
    from core.paths import RESOURCE_ROOT
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass
    app.setApplicationName("Sevbify")
    icon_path = os.path.join(str(RESOURCE_ROOT), ICON_FILE)
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    return icon_path


def main():
    # 1. Create the QApplication first
    app = QApplication(sys.argv)
    icon_path = set_app_identity(app)
    install_error_guard()

    # 2. Import and create the main window. Importing loads libVLC, which
    #    fails if VLC is not installed, so show a helpful message instead of
    #    crashing with a traceback.
    try:
        from ui.main_window import MainWindow
        window = MainWindow()
    except Exception as e:
        _log_stderr(traceback.format_exc())
        text = str(e) or e.__class__.__name__
        if SMOKE_TEST:
            _smoke_log("STARTUP FAILED:\n" + traceback.format_exc())
            sys.exit(1)
        if "vlc" in text.lower() or "libvlc" in text.lower() or isinstance(e, (OSError, NameError)):
            QMessageBox.critical(None, "VLC not found", VLC_HELP.format(details=text))
        else:
            QMessageBox.critical(None, "Startup error", f"The app could not start:\n\n{text}")
        sys.exit(1)

    window.show()

    if SMOKE_TEST:
        def loaded():
            _smoke_log(f"OK: window opened, library loaded with {len(window.songs)} songs "
                       f"from {window.user_data.music_folders}")
            if app.windowIcon().isNull():
                _smoke_log(f"FAILED: Sevbify's icon is missing ({icon_path})")
                window.close()
                app.exit(7)
                return
            _smoke_log("OK: Sevbify icon loaded")
            # Downloading needs yt-dlp and ffmpeg inside the packaged app.
            try:
                from core import downloader
                problems = downloader.check_tools()
                e = downloader.engine()
                details = f"yt-dlp {e.ytdlp_version()}, ffmpeg at {e.ffmpeg_path()}"
            except Exception:
                problems, details = ["download engine failed to load:\n" + traceback.format_exc()], ""
            # Playback must work with the VLC engine inside the app (no separately installed VLC).
            ok_play, play_details = _smoke_playback()
            ok_video, video_details = _smoke_canvas(window)
            window.close()
            if not ok_video:
                _smoke_log("FAILED: canvas video check: " + video_details)
                app.exit(6)
                return
            _smoke_log("OK: canvas video check: " + video_details)
            if not ok_play:
                _smoke_log("FAILED: playback check: " + play_details)
                app.exit(5)
                return
            _smoke_log("OK: playback check: " + play_details)
            if problems:
                _smoke_log("FAILED: downloads would not work: " + " | ".join(problems))
                app.exit(4)
                return
            _smoke_log("OK: download tools found: " + details)
            app.exit(0)

        def timed_out():
            _smoke_log("FAILED: library did not load within 60 seconds")
            app.exit(2)

        window.library_loaded.connect(loaded)
        QTimer.singleShot(60000, timed_out)

    # 3. Run the application event loop
    code = app.exec()
    # Let any online request still in flight finish before Python exits.
    from ui.async_tasks import wait_for_all
    wait_for_all(5000)
    sys.exit(code)


if __name__ == "__main__":
    main()

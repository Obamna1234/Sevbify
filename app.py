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


def main():
    # 1. Create the QApplication first
    app = QApplication(sys.argv)
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
            window.close()
            app.exit(0)

        def timed_out():
            _smoke_log("FAILED: library did not load within 60 seconds")
            app.exit(2)

        window.library_loaded.connect(loaded)
        QTimer.singleShot(60000, timed_out)

    # 3. Run the application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

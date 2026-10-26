# app.py
import sys
import traceback
from pathlib import Path

# Make sure the project folder is importable even when the app is launched
# from a different working directory (e.g. "python C:\path\to\app.py").
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication, QMessageBox


VLC_HELP = (
    "The music player needs the VLC media player to be installed.\n\n"
    "1. Download VLC from https://www.videolan.org/vlc/\n"
    "2. Install the 64-bit version (it must match your 64-bit Python).\n"
    "3. Start this app again.\n\n"
    "Technical details:\n{details}"
)


def main():
    # 1. Create the QApplication first
    app = QApplication(sys.argv)

    # 2. Import and create the main window. Importing loads libVLC, which
    #    fails if VLC is not installed, so show a helpful message instead of
    #    crashing with a traceback.
    try:
        from ui.main_window import MainWindow
        window = MainWindow()
    except Exception as e:
        traceback.print_exc()
        text = str(e) or e.__class__.__name__
        if "vlc" in text.lower() or "libvlc" in text.lower() or isinstance(e, (OSError, NameError)):
            QMessageBox.critical(None, "VLC not found", VLC_HELP.format(details=text))
        else:
            QMessageBox.critical(None, "Startup error", f"The app could not start:\n\n{text}")
        sys.exit(1)

    window.show()

    # 3. Run the application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

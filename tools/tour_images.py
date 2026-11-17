"""Make the feature tour's pictures from screenshots of Sevbify (all playing openly licensed music).

    python tools/tour_images.py desktop <showcase folder>        -> ui/tour/*.jpg
    python tools/tour_images.py android <android screens folder> -> android/app/src/main/assets/tour/*.jpg
    python tools/tour_images.py iphone  <iphone screens folder>  -> ios/Sevbify/Tour/*.jpg

Window screenshots are scaled to fit; a dialog is shown centred over a dimmed Home page, as it looks in the app.
A picture whose screenshot is missing is left as it was. Small JPEGs, so the app barely grows.
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# picture -> (screenshot name, is a dialog)
DESKTOP = {"search.jpg": ("search", False), "save.jpg": ("save-picker-popup", True), "expanded.jpg": ("expanded", False), "import.jpg": ("import", True),
           "radio.jpg": ("preview-feed", False), "podcast.jpg": ("podcast", False), "pair.jpg": ("pair", True),
           "support.jpg": ("support", True), "mini.jpg": ("mini-player", True),
           "private.jpg": ("private-session", False), "settings.jpg": ("settings", False)}
ANDROID = {"search.jpg": "search_results", "save.jpg": "your_songs_menu", "import.jpg": "import_result",
           "radio.jpg": "now_playing", "podcast.jpg": "audiobook_page", "pair.jpg": "settings_computer",
           "support.jpg": "support_sheet", "lyrics.jpg": "lyrics_card", "downloads.jpg": "download_choice",
           "settings.jpg": "settings_privacy"}
IPHONE = {"search.jpg": "search", "library.jpg": "library", "now_playing.jpg": "now_playing",
          "home.jpg": "home", "pair.jpg": "settings_computer"}


def find(folder, name):
    """<number>-<name>.png or <number>_<name>.png (the newest number if there are several)."""
    import re
    hits = sorted(f for f in glob.glob(os.path.join(folder, "*.png"))
                  if re.fullmatch(r"\d+[-_]" + re.escape(name) + r"\.png", os.path.basename(f)))
    return hits[-1] if hits else None


def main(kind, folder):
    from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter
    from PyQt6.QtCore import Qt
    _app = QGuiApplication.instance() or QGuiApplication(["x", "-platform", "offscreen"])  # noqa: F841
    if kind == "desktop":
        out, size, table = os.path.join(HERE, "ui", "tour"), (1328, 800), DESKTOP
    elif kind == "android":
        out, size, table = os.path.join(HERE, "android", "app", "src", "main", "assets", "tour"), (540, 1100), \
            {k: (v, False) for k, v in ANDROID.items()}
    else:
        out, size, table = os.path.join(HERE, "ios", "Sevbify", "Tour"), (540, 1100), \
            {k: (v, False) for k, v in IPHONE.items()}
    os.makedirs(out, exist_ok=True)
    backdrop = find(folder, "liked-songs") if kind == "desktop" else None      # CC songs only (Home shows live charts)
    made = 0
    for pic, (name, dialog) in table.items():
        src = find(folder, name)
        if not src:
            print(f"missing {name}")
            continue
        img = QImage(src)
        canvas = QImage(size[0], size[1], QImage.Format.Format_RGB32)
        canvas.fill(QColor("#121212"))
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if dialog and backdrop:
            bg = QImage(backdrop).scaled(size[0], size[1], Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation)
            p.drawImage(0, 0, bg)
            p.fillRect(0, 0, size[0], size[1], QColor(0, 0, 0, 150))
            fit = img
            if img.width() > size[0] * 0.9 or img.height() > size[1] * 0.9:
                fit = img.scaled(int(size[0] * 0.9), int(size[1] * 0.9), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            p.drawImage((size[0] - fit.width()) // 2, (size[1] - fit.height()) // 2, fit)
        else:
            fit = img.scaled(size[0], size[1], Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            p.drawImage((size[0] - fit.width()) // 2, (size[1] - fit.height()) // 2, fit)
        p.end()
        canvas.save(os.path.join(out, pic), "JPG", 78)
        made += 1
        print(f"{pic} <- {os.path.basename(src)}")
    print(f"{made} pictures in {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

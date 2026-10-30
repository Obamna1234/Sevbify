"""Build core/sevby_engine.py (the window-free SEVBY download engine) from the SEVBY desktop app source.

Usage:  python tools/make_engine.py path/to/sevby/sevby_app.py core/sevby_engine.py
Source: https://github.com/Obamna1234/sevby (MIT). Re-run this after SEVBY changes; do not edit the output by hand."""
import re, sys
if len(sys.argv) != 3:
    sys.exit(__doc__)
src = open(sys.argv[1], encoding="utf-8").read()

# 1. keep only the engine part (before the GUI helpers)
cut = src.index("def _icon_png_b64")
body = src[:cut]

# 2. drop GUI-only pieces
body = body.replace("import customtkinter as ctk\nimport tkinter as tk\nfrom tkinter import filedialog, messagebox\n", "")
body = re.sub(r"# Optional: drag-and-drop.*?_HAS_DND = False\n", "_HAS_DND = False  # no drag-and-drop in the engine\n", body, flags=re.S)
body = body.replace('ctk.set_appearance_mode("Dark")\nctk.set_default_color_theme("green")\n', "")
body = re.sub(r"def resource_path.*?\n\n\nICON_PATH = resource_path\(\"sevbyicon.ico\"\)\n.*?\nVERSION", "def resource_path(name: str) -> str:\n    base = getattr(sys, \"_MEIPASS\", os.path.dirname(os.path.abspath(__file__)))\n    return os.path.join(base, name)\n\n\nVERSION", body, flags=re.S)
body = re.sub(r"# [^\n]*GUI base[^\n]*\n\nif _HAS_DND:.*?(?=# -- Colours)", "", body, flags=re.S)
body = body.replace('VERSION = "1.0.1"\nAPP_NAME = "SEVBY"', 'VERSION = "1.0.1"  # version of the SEVBY engine this file was taken from\nAPP_NAME = "SEVBY"')

# 3. download quality is chosen by Sevbify (Settings -> Download quality), not fixed
old_fmt = '"format": "bestaudio[ext=m4a]/bestaudio/best" if original else "bestaudio/best",'
assert old_fmt in body, "SEVBY's format line changed: update tools/make_engine.py"
body = body.replace(old_fmt, '"format": AUDIO_FORMAT_ORIGINAL if original else "bestaudio/best",')
assert body.count('"preferredcodec": "mp3", "preferredquality": "0"}') == 2, "SEVBY's MP3 settings changed"
body = body.replace('"preferredcodec": "mp3", "preferredquality": "0"}', '"preferredcodec": "mp3", "preferredquality": MP3_QUALITY}')
body = body.replace('def _run_ytdlp_module(', '''# Set by Sevbify: which audio to keep when saving the original (smaller files: a lower-bitrate original), and
# the MP3 quality when converting (yt-dlp/ffmpeg: a bitrate like "160" or a VBR level "0"-"9").
AUDIO_FORMAT_ORIGINAL = "bestaudio[ext=m4a]/bestaudio/best"
MP3_QUALITY = "0"


def _run_ytdlp_module(''', 1)

header = '''"""
SEVBY download engine, used by Sevbify's "Get music" page.

This file is generated from the SEVBY desktop app (MIT licence, https://github.com/Obamna1234/sevby)
with all the window code removed, so it can run inside Sevbify without customtkinter.
Do not edit it by hand: change SEVBY and regenerate it instead.

What it does for each "Artist - Title" line: look on Bandcamp first, fall back to YouTube (via yt-dlp),
and save a 128 kbps MP3 with title, artist, album, year, track number and cover art (via ffmpeg).
Only download music you have the right to download.
"""
'''
# replace the original module docstring with ours
body = re.sub(r'^#!/usr/bin/env python3\n""".*?"""\n', header, body, count=1, flags=re.S)
open(sys.argv[2], "w", encoding="utf-8").write(body)
print("written", sys.argv[2], len(body.splitlines()), "lines")

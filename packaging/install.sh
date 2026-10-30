#!/bin/sh
# Adds Sevbify to your app menu (only for you; no admin password needed).
# Run it from the extracted Sevbify folder:  ./install.sh      Undo:  ./install.sh --remove
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"
if [ "$1" = "--remove" ]; then
  rm -f "$APPS/sevbify.desktop" "$ICONS/sevbify.png"
  echo "Removed Sevbify from the app menu (this folder and your playlists are untouched)."
  exit 0
fi
mkdir -p "$APPS" "$ICONS"
cp "$HERE/sevbify.png" "$ICONS/sevbify.png"
sed "s|^Exec=.*|Exec=\"$HERE/Sevbify\"|; s|^Icon=.*|Icon=sevbify|" "$HERE/sevbify.desktop" > "$APPS/sevbify.desktop"
chmod +x "$HERE/Sevbify"
update-desktop-database "$APPS" 2>/dev/null || true
echo "Sevbify is now in your app menu."
if ! ldconfig -p 2>/dev/null | grep -q libvlc.so; then
  echo "Sevbify plays music with VLC. Install it first, e.g.:  sudo apt install vlc"
fi

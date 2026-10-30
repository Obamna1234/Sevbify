#!/bin/bash
# Gets everything the iPhone app needs before Xcode builds it (run on a Mac, from the repository root):
#  1. Python for iOS (BeeWare's support package, checksum-checked),
#  2. the shared Python code (core/ and the Android app's bridge) into ios/app,
#  3. the pure-Python packages it uses (yt-dlp, mutagen, certifi) into ios/app_packages,
#  4. the Xcode project (XcodeGen).
set -euo pipefail
cd "$(dirname "$0")"
PY_TAG="3.13-b18"
PY_FILE="Python-3.13-iOS-support.b18.tar.gz"
PY_SHA="d06acf2a9c7964a8689566353a0e707402eff822037de5e29ba0e16040f7047d"

if [ ! -d Python.xcframework ]; then
  curl -sSL -o "$PY_FILE" "https://github.com/beeware/Python-Apple-support/releases/download/$PY_TAG/$PY_FILE"
  echo "$PY_SHA  $PY_FILE" | shasum -a 256 -c -
  tar xzf "$PY_FILE" Python.xcframework
  rm -f "$PY_FILE"
fi

rm -rf app app_packages
mkdir -p app app_packages
cp -R ../core app/core
find app -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -rf app/core/album_covers
cp ../android/app/src/main/python/sevbify_bridge.py app/
cp python/ios_entry.py app/
cp ../VERSION app/VERSION

# Pure-Python packages only (no compiled parts), so they run on the iPhone as they are.
python3 -m pip install --quiet --no-compile --no-deps --only-binary=:all: --target app_packages \
  yt-dlp mutagen certifi
# yt-dlp-ejs is for Deno, which can't run on an iPhone.
find app_packages -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -rf app_packages/bin
ls app_packages

V=$(tr -d '[:space:]' < ../VERSION)
sed -i '' "s/MARKETING_VERSION: .*/MARKETING_VERSION: \"${V%%-*}\"/; s/SEVBIFY_VERSION: .*/SEVBIFY_VERSION: \"$V\"/" project.yml
xcodegen generate

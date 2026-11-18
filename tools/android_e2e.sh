#!/usr/bin/env bash
# Run on the emulator by .github/workflows/e2e.yml (the emulator step runs each line on its own, so the steps live here).
# 1. If the last release's app was downloaded (previous.apk): install it, make a playlist, install this build over it
#    and check the playlist is still there (tools/android_upgrade.py). 2. A fresh install of this build, then the
#    journey (tools/android_journey.py).
set -u
APK="$(ls Sevbify-Android*.apk | head -1)"
PKG=com.obamna1234.sevbify
adb wait-for-device; sleep 30
mkdir -p android-journey
if [ -f previous.apk ]; then
  if adb install -g previous.apk; then
    python3 tools/android_upgrade.py before android-journey || true
    if adb install -r -g "$APK"; then
      python3 tools/android_upgrade.py after android-journey || true
    else
      python3 - <<'PY'
import json
json.dump({"step": "Update from the last release keeps your library", "status": "fail",
           "detail": "this build couldn't be installed over the last release (a different signing key?)"},
          open("android-journey/upgrade.json", "w"))
PY
    fi
  fi
  adb uninstall "$PKG" || true          # the journey below starts from a fresh install
fi
adb install -r -g "$APK" || { sleep 20; adb install -r -g "$APK"; }
adb shell pm grant "$PKG" android.permission.POST_NOTIFICATIONS || true
adb logcat -G 16M || true
python3 tools/android_journey.py android-journey || true

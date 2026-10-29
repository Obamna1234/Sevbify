#!/bin/bash
# Runs inside the emulator job of .github/workflows/android-screens.yml.
set -x
APK=Sevbify-Android.apk; PKG=com.obamna1234.sevbify; OUT=screens
mkdir -p $OUT music
adb wait-for-device
# A few test songs (tones with real tags) in the phone's Music folder, like a user's own music.
i=0
for t in "Morning Light:Sevbify Test Band" "City Rain:Sevbify Test Band" "Slow Orbit:Night Signals" "Paper Planes:Night Signals"; do
  i=$((i+1)); title=${t%%:*}; artist=${t##*:}
  ffmpeg -loglevel error -y -f lavfi -i "sine=frequency=$((220*i)):duration=40" -metadata title="$title" \
    -metadata artist="$artist" -metadata album="Test Album $artist" -b:a 128k "music/$i.mp3"
done
adb shell mkdir -p "/sdcard/Music/Test"
adb push music/. /sdcard/Music/Test/
adb shell content call --uri content://media/ --method scan_volume --arg external_primary || true
for f in 1 2 3 4; do adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Music/Test/$f.mp3 >/dev/null || true; done
# Wait until Android's music index has the test songs (the app reads songs from that index).
for k in $(seq 1 20); do
  N=$(adb shell content query --uri content://media/external/audio/media --projection _display_name:relative_path:is_music 2>/dev/null | grep -c "Music/Test")
  echo "indexed test songs: $N"; [ "$N" -ge 4 ] && break; sleep 3
done
adb shell content query --uri content://media/external/audio/media --projection _display_name:relative_path:is_music:title > $OUT/media_index.txt 2>&1
sleep 20   # let the freshly booted emulator settle (avoids "System UI isn't responding")
adb install -r -g $APK
adb shell pm grant $PKG android.permission.READ_MEDIA_AUDIO || true
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS || true
adb shell settings put global window_animation_scale 1
# Screen recordings of the whole walk-through (Android limits one recording to 3 minutes).
( adb shell screenrecord --size 540x1200 --bit-rate 2000000 --time-limit 175 /sdcard/walk1.mp4
  adb shell screenrecord --size 540x1200 --bit-rate 2000000 --time-limit 175 /sdcard/walk2.mp4 ) &
REC=$!
python3 tools/android_screens.py $OUT
sleep 3
adb shell pkill -INT screenrecord || true
sleep 4
kill $REC 2>/dev/null || true
adb pull /sdcard/walk1.mp4 $OUT/ || true
adb pull /sdcard/walk2.mp4 $OUT/ || true
adb logcat -d -t 3000 > $OUT/logcat.txt 2>/dev/null || true
grep -E "AndroidRuntime|python|Sevbify|FATAL" $OUT/logcat.txt | tail -200 > $OUT/app_log.txt || true
ls -la $OUT
exit 0

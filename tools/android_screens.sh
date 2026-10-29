#!/bin/bash
# Runs inside the emulator job of .github/workflows/android-screens.yml.
set -x
APK=Sevbify-Android.apk; PKG=com.obamna1234.sevbify; OUT=screens
mkdir -p $OUT music
adb wait-for-device
# A few test songs (short tones) in the phone's Music folder, like a user's own music. mp3 with tags when
# ffmpeg is there, otherwise plain WAV files.
python3 - <<'PY'
import math, os, shutil, struct, subprocess, wave
songs = [("Morning Light", "Sevbify Test Band"), ("City Rain", "Sevbify Test Band"),
         ("Slow Orbit", "Night Signals"), ("Paper Planes", "Night Signals")]
for i, (title, artist) in enumerate(songs, 1):
    wav = f"music/{artist} - {title}.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 220 * i * n / 22050)))
                               for n in range(22050 * 40)))
    if shutil.which("ffmpeg"):
        mp3 = wav[:-4] + ".mp3"
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-metadata", f"title={title}",
                            "-metadata", f"artist={artist}", "-metadata", f"album=Test Album {artist}", mp3])
        if r.returncode == 0:
            os.remove(wav)
print(os.listdir("music"))
PY
adb shell mkdir -p "/sdcard/Music/Test"
adb push music/. /sdcard/Music/Test/
adb shell content call --uri content://media/ --method scan_volume --arg external_primary 2>&1 | head -3
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Music/Test 2>&1 | head -2
adb shell ls -la /sdcard/Music/Test > $OUT/pushed_songs.txt 2>&1
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
adb logcat -G 16M || true
adb logcat -c
python3 tools/android_screens.py $OUT
# Stress: 1,500 random taps, swipes and key presses inside Sevbify (no system keys), looking for crashes.
adb shell monkey -p $PKG --throttle 250 --pct-syskeys 0 --pct-appswitch 0 --ignore-crashes --ignore-timeouts -s 42 -v 1500 > $OUT/monkey.txt 2>&1 || true
sleep 3
adb shell pkill -INT screenrecord || true
sleep 4
kill $REC 2>/dev/null || true
adb pull /sdcard/walk1.mp4 $OUT/ || true
adb pull /sdcard/walk2.mp4 $OUT/ || true
adb logcat -d > $OUT/logcat.txt 2>/dev/null || true
grep -E -A25 "FATAL EXCEPTION|ANR in|Fatal signal|python.stderr|chaquopy" $OUT/logcat.txt | head -800 > $OUT/crashes.txt || true
grep -c "FATAL EXCEPTION" $OUT/logcat.txt > $OUT/crash_count.txt || true
grep -E "AndroidRuntime|python|Sevbify|FATAL|$PKG" $OUT/logcat.txt | grep -v uiautomator | tail -400 > $OUT/app_log.txt || true
ls -la $OUT
exit 0

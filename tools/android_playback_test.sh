#!/bin/bash
# Runs inside the emulator job of the "Android playback" check (.github/workflows/build.yml).
# Plays real audio files through the installed app ("Open with Sevbify", the same code path as tapping a
# song) and fails unless the player is really PLAYING and its position moves on - the thing that broke for
# several betas ("songs just skip, nothing plays") while every compile check was green.
set -x
APK=${1:-Sevbify-Android.apk}; PKG=com.obamna1234.sevbify; OUT=playback-test
mkdir -p $OUT music
adb wait-for-device
python3 - <<'PY'
import math, struct, wave
for i in (1, 2, 3):
    with wave.open(f"music/Playback Test {i}.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 220 * i * n / 22050)))
                               for n in range(22050 * 90)))
PY
adb shell mkdir -p /sdcard/Music/PlaybackTest
adb push music/. /sdcard/Music/PlaybackTest/
adb shell content call --uri content://media/ --method scan_volume --arg external_primary 2>&1 | head -3
for k in $(seq 1 20); do
  N=$(adb shell content query --uri content://media/external/audio/media --projection _id:_display_name 2>/dev/null | grep -c "Playback Test")
  echo "indexed: $N"; [ "$N" -ge 3 ] && break; sleep 3
done
sleep 15
adb install -r -g $APK
adb shell pm grant $PKG android.permission.READ_MEDIA_AUDIO || true
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS || true
adb logcat -G 16M || true
adb logcat -c
# Start the app once so Python and the player service are up, then hand it songs.
adb shell am start -W -n $PKG/com.sevbify.app.MainActivity
sleep 20

uri_of() {   # content:// link of "Playback Test N"
  adb shell content query --uri content://media/external/audio/media --projection _id:_display_name \
    --where "_display_name='Playback Test $1.wav'" | grep -o "_id=[0-9]*" | head -1 | cut -d= -f2
}

# "state position" of Sevbify's media session, from dumpsys (state 3 = PLAYING).
session_state() {
  adb shell dumpsys media_session | PKG=$PKG python3 -c '
import os, re, sys
ours = False
for line in sys.stdin:
    if "package=" in line: ours = ("package=" + os.environ["PKG"]) in line
    m = re.search(r"PlaybackState \{state=(\d+), position=(-?\d+)", line)
    if m and ours: print(m.group(1), m.group(2)); sys.exit()
print("none 0")'
}

FAILED=0
play_and_check() {   # $1 = song number
  local id; id=$(uri_of $1)
  echo "== song $1 (media id $id)" | tee -a $OUT/result.txt
  adb shell am start -W -a android.intent.action.VIEW -d "content://media/external/audio/media/$id" -t audio/x-wav \
      -n $PKG/com.sevbify.app.MainActivity
  local ok=0 s p
  for k in $(seq 1 25); do
    read s p < <(session_state)
    echo "t+${k}s state=$s position=$p"
    if [ "$s" = "3" ]; then ok=1; break; fi
    sleep 1
  done
  if [ $ok = 1 ]; then
    local p1=$p; sleep 4; read s p < <(session_state)
    echo "after 4s: state=$s position=$p (was $p1)"
    if [ "$s" = "3" ] && [ "$p" -gt "$p1" ]; then echo "PASS song $1" | tee -a $OUT/result.txt; return; fi
  fi
  echo "FAIL song $1: the player never kept playing (state=$s)" | tee -a $OUT/result.txt
  FAILED=1
}
play_and_check 1
play_and_check 2
play_and_check 3
play_and_check 1       # back to the first one: this is what failed for the user

adb exec-out screencap -p > $OUT/final.png || true
adb shell dumpsys media_session > $OUT/media_session.txt 2>&1 || true
adb logcat -d > $OUT/logcat.txt 2>/dev/null || true
grep -E -A25 "FATAL EXCEPTION|ANR in|python.stderr" $OUT/logcat.txt | head -300 > $OUT/crashes.txt || true
echo $FAILED > $OUT/failed.txt
exit 0

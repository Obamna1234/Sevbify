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
import math, os, shutil, struct, subprocess, wave
for i in (1, 2, 3):
    wav = f"music/PlaybackTest{i}.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 220 * i * n / 22050)))
                               for n in range(22050 * 90)))
    if shutil.which("ffmpeg"):       # tagged mp3 like a real song; Android indexes these reliably
        mp3 = wav[:-4] + ".mp3"
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-metadata", f"title=PlaybackTest{i}",
                            "-metadata", "artist=Sevbify CI", mp3])
        if r.returncode == 0:
            os.remove(wav)
print(os.listdir("music"))
PY
adb shell mkdir -p /sdcard/Music/Test
adb push music/. /sdcard/Music/Test/
adb shell content call --uri content://media/ --method scan_volume --arg external_primary 2>&1 | head -3
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Music/Test 2>&1 | head -2
for k in $(seq 1 20); do
  N=$(adb shell content query --uri content://media/external/audio/media --projection _id:_display_name:relative_path 2>/dev/null | grep -c "PlaybackTest")
  echo "indexed: $N"; [ "$N" -ge 3 ] && break; sleep 3
done
adb shell content query --uri content://media/external/audio/media --projection _id:_display_name:relative_path | tee $OUT/media_index.txt | tail -8
sleep 15
adb install -r -g $APK
adb shell pm grant $PKG android.permission.READ_MEDIA_AUDIO || true
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS || true
adb logcat -G 16M || true
adb logcat -c
# Start the app once so Python and the player service are up, then hand it songs.
adb shell am start -W -n $PKG/com.sevbify.app.MainActivity
sleep 20

uri_of() {   # media id of "PlaybackTestN.*" from the index (no quoting tricks)
  adb shell content query --uri content://media/external/audio/media --projection _id:_display_name \
    | grep "PlaybackTest$1" | grep -o "_id=[0-9]*" | head -1 | cut -d= -f2
}

# "state position title" of Sevbify's media session, from dumpsys (state 3 = PLAYING).
session_state() {
  adb shell dumpsys media_session | PKG=$PKG python3 -c '
import os, re, sys
mine = "package=" + os.environ["PKG"]
blocks, cur = [], None
for line in sys.stdin:
    if "package=" in line:
        cur = {"ours": mine in line, "state": None, "desc": ""}; blocks.append(cur)
    if cur is None or not cur["ours"]: continue
    m = re.search(r"PlaybackState \{state=\w+\((\d+)\), position=(-?\d+)", line)
    if m and cur["state"] is None: cur["state"] = (m.group(1), m.group(2))
    d = re.search(r"description=(.*)", line)
    if d and not cur["desc"]: cur["desc"] = d.group(1).strip()
for b in blocks:
    if b["ours"] and b["state"]:
        print(b["state"][0], b["state"][1], b["desc"] or "-"); sys.exit()
print("none 0 -")'
}

FAILED=0
play_and_check() {   # $1 = song number
  local id; id=$(uri_of $1)
  echo "== song $1 (media id $id)" | tee -a $OUT/result.txt
  adb shell am start -W -a android.intent.action.VIEW -d "content://media/external/audio/media/$id" -t audio/mpeg \
      -n $PKG/com.sevbify.app.MainActivity
  local ok=0 s p t
  for k in $(seq 1 25); do
    read s p t < <(session_state)
    echo "t+${k}s state=$s position=$p title=$t"
    # PLAYING and it's *this* song (not the previous one still finishing its last second).
    if [ "$s" = "3" ] && { [ "$t" = "-" ] || [[ "$t" == *"PlaybackTest$1"* ]]; }; then ok=1; break; fi
    sleep 1
  done
  [ -f $OUT/session_debug.txt ] || adb shell dumpsys media_session | grep -n "package=\|PlaybackState\|description=" | head -30 > $OUT/session_debug.txt
  if [ $ok = 1 ]; then
    local p1=$p; sleep 4; read s p t < <(session_state)
    echo "after 4s: state=$s position=$p title=$t (was $p1)"
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

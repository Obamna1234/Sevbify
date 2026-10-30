#!/bin/bash
# Runs the iPhone app on GitHub's iPhone simulator: checks that Python starts and the online features answer
# (Documents/smoke.json), and takes screenshots of the main screens. Everything goes into ./screens.
set -uo pipefail
APP=ios/build/Build/Products/Debug-iphonesimulator/Sevbify.app
BID=com.obamna1234.sevbify
mkdir -p screens
DEV=$(xcrun simctl list devices available -j | python3 -c "
import json, sys
d = json.load(sys.stdin)['devices']
phones = [x for k, v in d.items() if 'iOS' in k for x in v if x['name'].startswith('iPhone')]
pro = [x for x in phones if 'Pro' in x['name'] and 'Max' not in x['name']]
print((pro or phones)[-1]['udid'])")
echo "Simulator: $DEV"
xcrun simctl boot "$DEV" 2>/dev/null || true
xcrun simctl bootstatus "$DEV" -b >/dev/null
xcrun simctl install "$DEV" "$APP"

run() {        # run <name> <seconds> <launch arguments...>
  local name=$1 wait=$2; shift 2
  xcrun simctl terminate "$DEV" "$BID" 2>/dev/null || true
  xcrun simctl launch --stdout="$PWD/screens/$name.out.txt" --stderr="$PWD/screens/$name.err.txt" "$DEV" "$BID" "$@" \
    >> screens/launch.txt 2>&1 || echo "launch $name failed" >> screens/launch.txt
  sleep "$wait"
  xcrun simctl io "$DEV" screenshot "screens/$name.png" >/dev/null 2>&1
  echo "screenshot $name"
}

# 1. Start-up check (first start unpacks nothing, but Python imports take a moment).
run 01_home_first_start 20 -SEVSmoke -SEVTab home
DATA=$(xcrun simctl get_app_container "$DEV" "$BID" data)
for i in $(seq 1 30); do [ -f "$DATA/Documents/smoke.json" ] && break; sleep 5; done
cp "$DATA/Documents/smoke.json" screens/smoke.json 2>/dev/null || echo '{"error": "no smoke.json (the app may not have started Python)"}' > screens/smoke.json
xcrun simctl io "$DEV" screenshot screens/02_home.png >/dev/null 2>&1

run 03_search 25 -SEVTab search -SEVQuery "daft punk"
run 04_library 8 -SEVTab library
run 05_now_playing 30 -SEVTab home -SEVQuery "daft punk" -SEVPlay open
run 06_first_run_notice 10

# What's inside the app, and any crash reports.
{ echo "== Frameworks"; ls "$APP/Frameworks" | head -50; echo "== top"; ls "$APP" | head -50
  echo "== python"; ls "$APP/python/lib" 2>&1 | head; otool -L "$APP/Sevbify" 2>&1 | head -20
  otool -l "$APP/Sevbify" | grep -A2 LC_RPATH; } > screens/bundle.txt 2>&1
mkdir -p screens/crashes
cp ~/Library/Logs/DiagnosticReports/*Sevbify* screens/crashes/ 2>/dev/null || true
find ~/Library/Logs/DiagnosticReports -name "*Sevbify*" -newer "$APP" 2>/dev/null | head >> screens/launch.txt
xcrun simctl spawn "$DEV" log show --last 10m --style compact --predicate 'process == "Sevbify" OR eventMessage CONTAINS "Sevbify"' > screens/system_log.txt 2>/dev/null || true
cat screens/smoke.json

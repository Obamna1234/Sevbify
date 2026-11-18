#!/usr/bin/env bash
# CI check of android/sign-rotated.sh with two THROWAWAY keys made here (never the real ones): takes an APK, signs
# it with throwaway key A (standing in for the original), rotates to throwaway key B, then checks that
#   - apksigner verify shows key A for Android 8 (SDK 26-27) and key B for Android 9+ (SDK 28+), and
#   - apksigner lineage lists both keys, with key A's "installed data" = false.
set -euo pipefail
apk_in=${1:?usage: test-key-rotation.sh <some.apk>}
work=$(mktemp -d)
bt=$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)
signer="$bt/apksigner"
export OLD_KEYSTORE_PASSWORD=throwaway-old-$RANDOM$RANDOM NEW_KEYSTORE_PASSWORD=throwaway-new-$RANDOM$RANDOM
keytool -genkeypair -keystore "$work/old.jks" -alias old -keyalg RSA -keysize 2048 -validity 2 -dname "CN=Throwaway Old" \
  -storepass "$OLD_KEYSTORE_PASSWORD" -keypass "$OLD_KEYSTORE_PASSWORD" -noprompt >/dev/null 2>&1
keytool -genkeypair -keystore "$work/new.jks" -alias new -keyalg RSA -keysize 2048 -validity 2 -dname "CN=Throwaway New" \
  -storepass "$NEW_KEYSTORE_PASSWORD" -keypass "$NEW_KEYSTORE_PASSWORD" -noprompt >/dev/null 2>&1
fp() { keytool -list -v -keystore "$1" -storepass "$2" | awk -F': ' '/SHA256:/{gsub(":","",$2); print tolower($2); exit}'; }
OLD_FP=$(fp "$work/old.jks" "$OLD_KEYSTORE_PASSWORD"); NEW_FP=$(fp "$work/new.jks" "$NEW_KEYSTORE_PASSWORD")
mkdir -p "$work/apks"
"$signer" sign --ks "$work/old.jks" --ks-key-alias old --ks-pass env:OLD_KEYSTORE_PASSWORD --out "$work/apks/app.apk" "$apk_in"
OLD_KEYSTORE="$work/old.jks" OLD_KEY_ALIAS=old NEW_KEYSTORE="$work/new.jks" NEW_KEY_ALIAS=new LINEAGE_OUT="$work/lineage" \
  bash "$(dirname "$0")/sign-rotated.sh" "$work/apks"
certs() { "$signer" verify --print-certs "$@" "$work/apks/app.apk" | awk -F': ' '/certificate SHA-256 digest/{print $2}' | sort -u; }
android8=$(certs --min-sdk-version 26 --max-sdk-version 27)
android9=$(certs --min-sdk-version 28)
lineage=$("$signer" lineage --in "$work/lineage" --print-certs -v)
echo "Android 8 sees: $android8"; echo "Android 9+ sees: $android9"; echo "$lineage"
fail=0
[ "$android8" = "$OLD_FP" ] || { echo "::error title=Key rotation test::Android 8 doesn't see only the original key"; fail=1; }
echo "$android9" | grep -qx "$NEW_FP" && ! echo "$android9" | grep -qx "$OLD_FP" \
  || { echo "::error title=Key rotation test::Android 9+ doesn't see only the new key"; fail=1; }
echo "$lineage" | grep -qi "$OLD_FP" && echo "$lineage" | grep -qi "$NEW_FP" \
  || { echo "::error title=Key rotation test::the lineage doesn't list both keys"; fail=1; }
# The original key's entry must say installed data: false (the first signer listed in the lineage).
echo "$lineage" | awk '/Signer #1/{f=1} f&&/[Ii]nstalled data/{print; exit}' | grep -qi "false" \
  || { echo "::error title=Key rotation test::the original key's \"installed data\" isn't false"; fail=1; }
rm -rf "$work"
[ $fail -eq 0 ] && echo "Key rotation test passed: Android 8 = original key, Android 9+ = new key, lineage has both (original: installed data false)."
exit $fail

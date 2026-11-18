#!/usr/bin/env bash
# Android signing-key rotation (Nov 2026: the original key was exposed in a since-deleted backup workflow).
#
# Re-signs the release APKs in <dir> with APK Signature Scheme v3 key rotation, so that:
#   - Android 8 / 8.1 (API 26-27, v2 signatures) still see the ORIGINAL key: they can't do rotation, and
#   - Android 9+ (API 28+, v3) see the NEW key plus a proof-of-rotation signed by the original key, so the update
#     installs over the existing app (no uninstall, nothing lost). Once a phone has it, an APK signed only with the
#     original key can no longer update the app there (--set-installed-data false on the original key).
#
# Needs: OLD_KEYSTORE / OLD_KEY_ALIAS / OLD_KEYSTORE_PASSWORD / OLD_KEY_PASSWORD
#        NEW_KEYSTORE / NEW_KEY_ALIAS / NEW_KEYSTORE_PASSWORD (NEW_KEY_PASSWORD defaults to it)
# With no new key set, the APKs are left exactly as Gradle signed them (so builds keep working until it's added).
# Based on the tested android/sign-rotated.sh in the SEVBY repository.
set -euo pipefail
dir=${1:?usage: sign-rotated.sh <apk folder>}
if [ -z "${NEW_KEYSTORE:-}" ] || [ ! -s "${NEW_KEYSTORE}" ] || [ -z "${OLD_KEYSTORE:-}" ] || [ ! -s "${OLD_KEYSTORE}" ]; then
  echo "Key rotation: no new key set - the APKs keep the original key only."
  exit 0
fi
export NEW_KEY_PASSWORD="${NEW_KEY_PASSWORD:-$NEW_KEYSTORE_PASSWORD}"
export OLD_KEY_PASSWORD="${OLD_KEY_PASSWORD:-$OLD_KEYSTORE_PASSWORD}"
bt=$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)
signer="$bt/apksigner"
lineage="${LINEAGE_OUT:-${RUNNER_TEMP:-/tmp}/signing.lineage}"
old=(--ks "$OLD_KEYSTORE" --ks-key-alias "$OLD_KEY_ALIAS" --ks-pass env:OLD_KEYSTORE_PASSWORD --key-pass env:OLD_KEY_PASSWORD)
new=(--ks "$NEW_KEYSTORE" --ks-key-alias "$NEW_KEY_ALIAS" --ks-pass env:NEW_KEYSTORE_PASSWORD --key-pass env:NEW_KEY_PASSWORD)
"$signer" rotate --out "$lineage" --old-signer "${old[@]}" --set-installed-data false --new-signer "${new[@]}"
shopt -s nullglob
apks=("$dir"/*.apk)
[ ${#apks[@]} -gt 0 ] || { echo "::error::Key rotation: no APKs in $dir"; exit 1; }
for apk in "${apks[@]}"; do
  out="${apk%.apk}.rotated.apk"
  "$signer" sign "${old[@]}" --next-signer "${new[@]}" --lineage "$lineage" \
    --rotation-min-sdk-version 28 --out "$out" "$apk"
  "$signer" verify --min-sdk-version 26 "$out"
  mv "$out" "$apk"
  rm -f "$out.idsig" "$apk.idsig"
done
echo "Key rotation: ${#apks[@]} APK(s) signed with the original key (Android 8) and the new key (Android 9+)."

"""The AltStore / SideStore source for Sevbify's iPhone app (so they offer each new version as an update).

  python3 tools/altstore_source.py --build 5.0.0-beta.21        -> 21 (the iPhone build number)
  python3 tools/altstore_source.py VERSION IPA NOTES OUT.json   -> writes the source

The release job publishes OUT.json to the "altstore" branch; people add
https://raw.githubusercontent.com/Obamna1234/Sevbify/altstore/source.json to AltStore or SideStore once.
"""
import datetime
import json
import os
import re
import sys

REPO = "Obamna1234/Sevbify"
BUNDLE_ID = "com.obamna1234.sevbify"


def build_number(version):
    m = re.search(r"-(?:beta|alpha|rc)\.?(\d+)$", version)
    return str(int(m.group(1))) if m else "1000"


def source(version, ipa_path, notes):
    marketing = version.split("-", 1)[0]
    tag = f"v{version}"
    return {
        "name": "Sevbify",
        "identifier": f"{BUNDLE_ID}.source",
        "subtitle": "A private, ad-free music player.",
        "website": f"https://github.com/{REPO}",
        "iconURL": f"https://raw.githubusercontent.com/{REPO}/main/assets/branding/sevbify_icon_512.png",
        "tintColor": "1ed760",
        "apps": [{
            "name": "Sevbify",
            "bundleIdentifier": BUNDLE_ID,
            "developerName": "Obamna1234",
            "subtitle": "Your music, podcasts and audiobooks. No account, no ads, no tracking.",
            "localizedDescription": ("Sevbify plays your own music and streams songs you don't have yet, with "
                                     "podcasts, audiobooks, radios and lyrics. Nothing you do is sold or tracked."),
            "iconURL": f"https://raw.githubusercontent.com/{REPO}/main/assets/branding/sevbify_icon_512.png",
            "tintColor": "1ed760",
            "category": "entertainment",
            "versions": [{
                "version": marketing,
                "buildVersion": build_number(version),
                "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "localizedDescription": f"Sevbify {version}\n\n{notes.strip()[:4000]}",
                "downloadURL": f"https://github.com/{REPO}/releases/download/{tag}/Sevbify-iOS.ipa",
                "size": os.path.getsize(ipa_path),
                "minOSVersion": "16.0",
            }],
            "appPermissions": {"entitlements": [], "privacy": {}},
        }],
        "news": [],
    }


if __name__ == "__main__":
    if sys.argv[1:2] == ["--build"]:
        print(build_number(sys.argv[2]))
        sys.exit(0)
    version, ipa, notes, out = sys.argv[1:5]
    with open(notes, encoding="utf-8") as f:
        text = f.read()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(source(version, ipa, text), f, indent=2, ensure_ascii=False)
    print(f"wrote {out}")

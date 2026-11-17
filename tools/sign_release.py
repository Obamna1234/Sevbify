"""Sign a release's downloads for the in-app updater (run by the release build).

    UPDATE_SIGNING_KEY=<hex seed> python tools/sign_release.py <tag> <folder with the release files>

Writes <folder>/Sevbify-update-signatures.json. Refuses to run if the key is missing or isn't Sevbify's key (its
public half must match core/update_sign.py), so a release can never go out with wrong or missing signatures.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import update_sign  # noqa: E402


def main(tag, folder):
    seed = os.environ.get("UPDATE_SIGNING_KEY", "").strip()
    if len(seed) != 64:
        sys.exit("UPDATE_SIGNING_KEY isn't set (a GitHub secret): the release can't be signed, so it isn't published.")
    if update_sign.public_from_seed(seed) != update_sign.PUBLIC_KEY_HEX:
        sys.exit("UPDATE_SIGNING_KEY isn't Sevbify's update key (its public half doesn't match the app's).")
    files = {}
    for name in sorted(os.listdir(folder)):
        if not name.startswith("Sevbify-") or name == update_sign.SIGNATURES_NAME:
            continue
        h = hashlib.sha256()
        with open(os.path.join(folder, name), "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        sha = h.hexdigest()
        files[name] = {"sha256": sha, "signature": update_sign.sign(seed, tag, name, sha)}
        update_sign.check(json.dumps({"tag": tag, "files": {name: files[name]}}), tag, name, sha)   # self-check
    if not files:
        sys.exit("No release files to sign.")
    with open(os.path.join(folder, update_sign.SIGNATURES_NAME), "w", encoding="utf-8") as f:
        json.dump({"tag": tag, "files": files}, f, indent=1)
    print(f"Signed {len(files)} files for {tag}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

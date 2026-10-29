"""Sevbify's version number, read from the VERSION file (bundled into the packaged app)."""
import os

from core.paths import PROJECT_ROOT, RESOURCE_ROOT


def app_version():
    # The Android app passes its own version in (its VERSION copy sits inside the APK, not on disk).
    if os.environ.get("SEVBIFY_VERSION", "").strip():
        return os.environ["SEVBIFY_VERSION"].strip()
    for base in (RESOURCE_ROOT, PROJECT_ROOT):
        try:
            with open(os.path.join(str(base), "VERSION"), encoding="utf-8-sig") as f:
                v = f.read().strip()
                if v:
                    return v
        except OSError:
            continue
    return "dev"

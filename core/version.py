"""Sevbify's version number, read from the VERSION file (bundled into the packaged app)."""
import os

from core.paths import PROJECT_ROOT, RESOURCE_ROOT


def app_version():
    for base in (RESOURCE_ROOT, PROJECT_ROOT):
        try:
            with open(os.path.join(str(base), "VERSION"), encoding="utf-8-sig") as f:
                v = f.read().strip()
                if v:
                    return v
        except OSError:
            continue
    return "dev"

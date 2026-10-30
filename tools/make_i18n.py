"""Make the per-app translation files from core/i18n/translations.txt.

  python3 tools/make_i18n.py json OUT_DIR      -> OUT_DIR/<lang>.json (the Android app's assets)
  python3 tools/make_i18n.py ios OUT_DIR       -> OUT_DIR/<lang>.lproj/Localizable.strings (the iPhone app)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from core import i18n  # noqa: E402

IOS_CODES = {"zh": "zh-Hans"}


def _esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main(kind, out):
    table = i18n.load_table()
    os.makedirs(out, exist_ok=True)
    for code in i18n.CODES:
        strings = table.get(code, {})
        if kind == "json":
            with open(os.path.join(out, f"{code}.json"), "w", encoding="utf-8") as f:
                json.dump(strings, f, ensure_ascii=False)
        else:
            d = os.path.join(out, f"{IOS_CODES.get(code, code)}.lproj")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "Localizable.strings"), "w", encoding="utf-8") as f:
                for en, t in strings.items():
                    f.write(f'"{_esc(en)}" = "{_esc(t)}";\n')
    print(f"wrote {kind} translations to {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

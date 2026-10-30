"""Sevbify in 20 languages. One table (translations.txt: English, then each language) is shared by every app:
the computer apps use tr() below, the Android app reads the same file from its assets, and the iPhone app gets
Localizable.strings made from it (tools/make_i18n.py).

Only the words on screen change. Search always works in every language, whatever language Sevbify is shown in.
Anything not in the table stays in English.
"""
import locale
import os

# (code, name in its own language), in the order the language menu shows them.
LANGUAGES = [
    ("en", "English"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"), ("pt", "Português"),
    ("it", "Italiano"), ("ru", "Русский"), ("zh", "简体中文"), ("ja", "日本語"), ("ko", "한국어"),
    ("ar", "العربية"), ("hi", "हिन्दी"), ("tr", "Türkçe"), ("nl", "Nederlands"), ("pl", "Polski"),
    ("id", "Bahasa Indonesia"), ("vi", "Tiếng Việt"), ("th", "ไทย"), ("uk", "Українська"), ("sv", "Svenska"),
]
CODES = [c for c, _ in LANGUAGES]
RTL = {"ar"}
TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations.txt")

_current = "en"
_strings = {}


def load_table(path=TABLE):
    """{lang: {english: translation}} from translations.txt."""
    out = {c: {} for c in CODES if c != "en"}
    order = [c for c in CODES if c != "en"]
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#") or "\t" not in line:
                continue
            english, rest = line.split("\t", 1)
            parts = [p.strip() for p in rest.split("|")]
            if len(parts) != len(order):
                continue
            for code, text in zip(order, parts):
                if text:
                    out[code][english] = text
    return out


def normalise(code):
    """'pt_BR' / 'zh-Hans' / 'in' (old Indonesian code) -> one of CODES, or 'en'."""
    code = (code or "").replace("-", "_").split("_")[0].lower()
    code = {"in": "id", "iw": "he", "nb": "no"}.get(code, code)
    return code if code in CODES else "en"


def system_language():
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(name)
        if v and v not in ("C", "POSIX"):
            return normalise(v.split(":")[0])
    try:
        import sys
        if sys.platform.startswith("win"):
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return normalise(locale.windows_locale.get(lcid, "en"))
        return normalise((locale.getlocale()[0] or "en"))
    except Exception:
        return "en"


def set_language(code=""):
    """'' = the computer's language. Returns the language used."""
    global _current, _strings
    _current = normalise(code) if code else system_language()
    _strings = {} if _current == "en" else load_table().get(_current, {})
    return _current


def current():
    return _current


def is_rtl():
    return _current in RTL


def tr(text):
    """The text in the chosen language (English when there's no translation)."""
    return _strings.get(text, text)

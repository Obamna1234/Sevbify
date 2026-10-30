"""Sevbify in 20 languages: one shared table, English when a phrase isn't translated, search never affected."""
import json
import subprocess
import sys

from core import i18n


def test_every_language_has_every_phrase():
    table = i18n.load_table()
    assert len(i18n.CODES) == 20 and set(table) == set(i18n.CODES) - {"en"}
    english = set(table["es"])
    for code, strings in table.items():
        assert set(strings) == english, code
        assert all(t.strip() for t in strings.values()), code


def test_language_codes_from_systems_and_fallback():
    assert i18n.normalise("pt_BR.UTF-8") == "pt"
    assert i18n.normalise("zh-Hans") == "zh"
    assert i18n.normalise("in") == "id"                       # Android's old code for Indonesian
    assert i18n.normalise("xx") == "en"
    try:
        assert i18n.set_language("de") == "de"
        assert i18n.tr("Add to queue") == "Zur Warteschlange hinzufügen"
        assert i18n.tr("A song called Lyrics?") == "A song called Lyrics?"
        assert i18n.set_language("ar") == "ar" and i18n.is_rtl()
    finally:
        i18n.set_language("en")


def test_menu_items_are_translated_but_names_never(qapp):
    from PyQt6.QtWidgets import QMenu
    import ui  # noqa: F401  (installs the menu translation)
    try:
        i18n.set_language("fr")
        m = QMenu()
        a = m.addAction("≡  Add to queue")
        b = m.addAction("Lyrics")                                # e.g. a playlist with that name
        assert a.text() == "≡  Ajouter à la file d'attente" and b.text() == "Lyrics"
    finally:
        i18n.set_language("en")


def test_phone_files_are_made_from_the_same_table(tmp_path):
    subprocess.run([sys.executable, "tools/make_i18n.py", "json", str(tmp_path / "j")], check=True)
    subprocess.run([sys.executable, "tools/make_i18n.py", "ios", str(tmp_path / "i")], check=True)
    assert json.loads((tmp_path / "j" / "ja.json").read_text("utf-8"))["Home"] == "ホーム"
    text = (tmp_path / "i" / "zh-Hans.lproj" / "Localizable.strings").read_text("utf-8")
    assert '"Home" = "首页";' in text


def test_language_setting_is_saved(tmp_path):
    from core.storage import Storage
    st = Storage(str(tmp_path))
    d = st.load()
    d.language = "ko"
    st.save(d)
    assert Storage(str(tmp_path)).load().language == "ko"

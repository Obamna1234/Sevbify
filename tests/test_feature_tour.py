"""The feature tour: opens once, 'Don't show this again' keeps it closed, Settings / Help always open it."""
import os

from ui import feature_tour


def test_every_page_has_its_picture_and_text():
    for pic, title, text in feature_tour.PAGES:
        assert os.path.isfile(os.path.join(feature_tour.HERE, pic)), pic
        assert title and len(text) > 40
        assert os.path.getsize(os.path.join(feature_tour.HERE, pic)) < 250_000      # small pictures: the app stays small


def test_tour_pages_and_never_again(window, qapp):
    window._auto_answer_dialogs = True
    d = window.show_feature_tour()
    assert d is not None and d.title.text() == feature_tour.PAGES[0][1]
    assert not d.back.isEnabled() and d.next.text() == "Next" and d.again.isChecked()
    for _ in range(len(d.pages) - 1):
        d.next.click()
    assert d.next.text() == "Done" and not d.skip.isVisible()
    assert d.done_with_tour()
    d.reject()
    window.user_data.tour_seen = True
    assert window.show_feature_tour() is None                      # closed for good on start-up...
    again = window.show_feature_tour(again=True)                   # ...but Settings / Help still open it
    assert again is not None and not again.again.isVisible()
    again.reject()


def test_tour_seen_is_saved(window):
    window.user_data.tour_seen = True
    window.storage.save(window.user_data)
    assert window.storage.load().tour_seen is True


def test_app_startup_code_has_no_local_name_clash():
    """Regression: a `from ... import QTimer` inside app.main() made QTimer local there and crashed the packaged app
    at start ("cannot access local variable 'QTimer'"). pyflakes finds such clashes."""
    import ast
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"), encoding="utf-8").read()
    main = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "main")
    module_names = {a.asname or a.name for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))
                    for a in n.names}
    local = {a.asname or a.name for n in ast.walk(main) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    assert not (module_names & local), module_names & local

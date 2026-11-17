"""Static checks that catch crashes before they ship: a name used but never imported or defined (e.g. QApplication
in the main window, which broke 'Paste copied songs', 'Open Chosic' and installing updates), or a variable used
before it's assigned (QTimer in app.main)."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_no_undefined_names():
    pytest.importorskip("pyflakes")
    out = subprocess.run([sys.executable, "-m", "pyflakes", "app.py", "core", "ui", "tools",
                          os.path.join("android", "app", "src", "main", "python")],
                         cwd=ROOT, capture_output=True, text=True).stdout
    bad = [line for line in out.splitlines()
           if "undefined name" in line or "referenced before assignment" in line or "undefined local" in line]
    assert not bad, "\n".join(bad)

"""After importing a playlist file: the songs that couldn't be found, each with "Did you mean …?" to fix the
spelling before streaming or downloading. Nothing is changed unless you press Fix."""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget,
                             QLineEdit, QCheckBox, QGridLayout)
from PyQt6.QtCore import Qt

from . import theme


class ImportReview(QDialog):
    def __init__(self, parent, playlist_name, problems):
        """problems: [(number, "as written", "suggested" or "")]."""
        super().__init__(parent)
        from core.i18n import tr
        self.setWindowTitle(tr("Check the spelling"))
        self.resize(720, 520)
        self.setStyleSheet(f"QDialog {{ background: {theme.ELEVATED}; }} QLabel {{ color: {theme.TEXT}; }}"
                           f" QLineEdit {{ background: #3e3e3e; color: white; border: none; border-radius: 4px;"
                           f" padding: 6px; }} QCheckBox {{ color: {theme.TEXT}; }}")
        v = QVBoxLayout(self)
        head = QLabel(f"{len(problems)} song{'s' if len(problems) != 1 else ''} in “{playlist_name}” couldn't be "
                      "found as written, so they can't be streamed or downloaded yet. Check the spelling: Sevbify "
                      "filled in the closest song it found. Untick a song to leave it as it is.")
        head.setWordWrap(True)
        v.addWidget(head)
        tip = QLabel("Or fix these lines in your file (search the file for the text on the left) and import it again.")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {theme.SUBDUED};")
        v.addWidget(tip)
        area = QScrollArea()
        area.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        self.rows = []
        for r, (number, written, suggestion) in enumerate(problems):
            box = QCheckBox(f"#{number}")
            box.setChecked(bool(suggestion))
            orig = QLabel(written)
            orig.setWordWrap(True)
            edit = QLineEdit(suggestion or written)
            edit.setPlaceholderText("Artist - Title")
            edit.textEdited.connect(lambda _t, b=box: b.setChecked(True))
            grid.addWidget(box, r, 0)
            grid.addWidget(orig, r, 1)
            grid.addWidget(edit, r, 2)
            self.rows.append((box, edit, written))
        grid.setRowStretch(len(problems), 1)
        area.setWidget(body)
        v.addWidget(area, 1)
        row = QHBoxLayout()
        row.addStretch()
        keep = QPushButton(tr("Keep as written"))
        fix = QPushButton(tr("Fix the ticked songs"))
        fix.setStyleSheet(f"QPushButton {{ background: {theme.GREEN}; color: black; border-radius: 16px;"
                          f" padding: 8px 18px; font-weight: bold; }}")
        keep.clicked.connect(self.reject)
        fix.clicked.connect(self.accept)
        fix.setDefault(True)
        row.addWidget(keep)
        row.addWidget(fix)
        v.addLayout(row)

    def fixes(self):
        """{row index: "Artist - Title"} for the ticked songs whose text changed."""
        return {i: e.text().strip() for i, (b, e, w) in enumerate(self.rows)
                if b.isChecked() and e.text().strip() and e.text().strip() != w}

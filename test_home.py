from PyQt5.QtWidgets import QApplication
from ui.Home_View import HomeView  # adjust if your ui folder is named differently
import sys

app = QApplication(sys.argv)
window = HomeView()
window.show()
sys.exit(app.exec_())

import sys
from PyQt6.QtWidgets import QApplication
from ui_main import MainWindow
from database import initialize_db

if __name__ == "__main__":
    initialize_db()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

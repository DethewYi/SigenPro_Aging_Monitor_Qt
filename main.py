import sys
from PyQt6.QtWidgets import QApplication
from src.app.application import Application


def main():
    app = Application(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

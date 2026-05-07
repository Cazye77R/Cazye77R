import sys

from PySide6.QtWidgets import QApplication

from app import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("WiFi Heatmap")
    app.setOrganizationName("wifi_heatmap")

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QSplitter
)
from PyQt6.QtCore import QTimer, Qt

# your modules
from WLM_DDS import ArduinoControl, WLMControl, TinySAControl


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DDS + WLM + TinySA Control")
        self.resize(1500, 900)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.arduino = ArduinoControl()
        self.wlm = WLMControl()

        left_layout.addWidget(self.arduino)
        left_layout.addWidget(self.wlm, 1)

        self.tinysa = TinySAControl()

        splitter.addWidget(left_panel)
        splitter.addWidget(self.tinysa)
        splitter.setSizes([500, 1000])

        QTimer.singleShot(500, self.start_tinysa)

    # ---------------------------------------------------
    # Launch TinySA
    # ---------------------------------------------------
    def start_tinysa(self):
        self.tinysa.open_tinysa()
        self.raise_()
        self.activateWindow()

    # ---------------------------------------------------
    # Clean exit
    # ---------------------------------------------------
    def closeEvent(self, event):
        self.arduino.stop_scan(wait=True)
        self.wlm.stop_acquisition()
        self.tinysa.close()
        event.accept()


# ============================================================
# Run
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())

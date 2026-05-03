import sys
import time
import subprocess

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import QTimer

# your modules
from WLM_DDS import ArduinoControl, WLMControl, TinySAControl

# Windows API (for snapping windows)
import win32gui
import win32api

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DDS + WLM + TinySA Control")
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)

        # ===== Layout: left/right split =====
        main_layout = QHBoxLayout(central)

        # LEFT side (Arduino + WLM)
        left_layout = QVBoxLayout()
        self.arduino = ArduinoControl()
        self.wlm = WLMControl()

        left_layout.addWidget(self.arduino)
        left_layout.addWidget(self.wlm)

        # RIGHT side (TinySA control panel only)
        right_layout = QVBoxLayout()
        self.tinysa = TinySAControl()

        right_layout.addWidget(self.tinysa)

        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        # Equal split
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)

        # ===== Start TinySA automatically =====
        QTimer.singleShot(500, self.start_tinysa)

        # ===== Arrange windows after launch =====
        QTimer.singleShot(1500, self.arrange_windows)

    # ---------------------------------------------------
    # Launch TinySA
    # ---------------------------------------------------
    def start_tinysa(self):
        self.tinysa.open_tinysa()

        # bring main window to front
        self.raise_()
        self.activateWindow()

    # ---------------------------------------------------
    # Arrange windows side-by-side
    # ---------------------------------------------------
    def arrange_windows(self):
        time.sleep(1)

        tinysa_windows = []

        def enum_handler(hwnd, ctx):
            title = win32gui.GetWindowText(hwnd)
            if "QtTinySA" in title:
                ctx.append(hwnd)

        win32gui.EnumWindows(enum_handler, tinysa_windows)

        if tinysa_windows:
            tinysa_hwnd = tinysa_windows[0]
            main_hwnd = self.winId().__int__()

            screen_width = win32api.GetSystemMetrics(0)
            screen_height = win32api.GetSystemMetrics(1)

            # LEFT = your app
            win32gui.MoveWindow(
                main_hwnd,
                0, 0,
                screen_width // 2,
                screen_height,
                True
            )

            # RIGHT = TinySA
            win32gui.MoveWindow(
                tinysa_hwnd,
                screen_width // 2,
                0,
                screen_width // 2,
                screen_height,
                True
            )

    # ---------------------------------------------------
    # Clean exit
    # ---------------------------------------------------
    def closeEvent(self, event):
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
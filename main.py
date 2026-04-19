import sys
import serial.tools.list_ports

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QDoubleSpinBox
)
from PyQt6.QtCore import QThread, pyqtSignal

from arduino_init import dds_initial_1_new_2015, reset_arduino
from arduino_set_freq import profile0
from wlm_client import WLMClient


# =========================
# WLM Worker (background)
# =========================
class WLMWorker(QThread):
    data_ready = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.wlm = WLMClient()
        self.running = True

    def run(self):
        while self.running:
            wl = self.wlm.get_channel(6)

            if wl is not None:
                self.data_ready.emit(wl)

            self.msleep(500)  # 0.5 sec (smooth + safe)

    def stop(self):
        self.running = False
        self.wait()


# =========================
# Arduino Init Worker
# =========================
class InitWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, port):
        super().__init__()
        self.port = port

    def run(self):
        try:
            reset_arduino(self.port)
            dds_initial_1_new_2015(0, 0, 0, 0, 0, 0, port=self.port)
            self.done.emit(f"Initialized on {self.port}")
        except Exception as e:
            self.done.emit(str(e))


# =========================
# Frequency Worker
# =========================
class FreqWorker(QThread):
    def __init__(self, port, freq):
        super().__init__()
        self.port = port
        self.freq = freq

    def run(self):
        try:
            profile0(self.freq, 0, 0, port=self.port)
        except Exception as e:
            print("Freq error:", e)


# =========================
# Main UI
# =========================
class ControlUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DDS + WLM Control")
        self.resize(500, 200)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # -------- COM selection --------
        com_layout = QHBoxLayout()
        com_layout.addWidget(QLabel("COM:"))

        self.com_box = QComboBox()
        self.refresh_ports()
        com_layout.addWidget(self.com_box)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        com_layout.addWidget(refresh_btn)

        layout.addLayout(com_layout)

        # -------- Init --------
        init_layout = QHBoxLayout()

        self.init_btn = QPushButton("Initialize Arduino")
        self.init_btn.clicked.connect(self.init_arduino)
        init_layout.addWidget(self.init_btn)

        self.status_label = QLabel("Idle")
        init_layout.addWidget(self.status_label)

        layout.addLayout(init_layout)

        # -------- Frequency --------
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("Frequency (MHz):"))

        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0, 1000)
        self.freq_spin.setValue(35.0)
        self.freq_spin.setDecimals(3)
        freq_layout.addWidget(self.freq_spin)

        self.set_freq_btn = QPushButton("Set Frequency")
        self.set_freq_btn.clicked.connect(self.set_frequency)
        freq_layout.addWidget(self.set_freq_btn)

        layout.addLayout(freq_layout)

        # -------- WLM --------
        wlm_layout = QHBoxLayout()
        wlm_layout.addWidget(QLabel("WLM Signal (Ch 6):"))

        self.wlm_label = QLabel("---")
        wlm_layout.addWidget(self.wlm_label)

        layout.addLayout(wlm_layout)

        # -------- Start WLM thread --------
        self.wlm_thread = WLMWorker()
        self.wlm_thread.data_ready.connect(self.update_wlm)
        self.wlm_thread.start()

    # ---------------- UI logic ----------------

    def refresh_ports(self):
        self.com_box.clear()
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            self.com_box.addItem(p.device)

    def get_port(self):
        return self.com_box.currentText()

    def init_arduino(self):
        port = self.get_port()

        self.init_worker = InitWorker(port)
        self.init_worker.done.connect(self.status_label.setText)
        self.init_worker.start()

    def set_frequency(self):
        port = self.get_port()
        freq = self.freq_spin.value()

        self.freq_worker = FreqWorker(port, freq)
        self.freq_worker.start()

    def update_wlm(self, wl):
        self.wlm_label.setText(f"{wl:.6f}")

    # clean exit
    def closeEvent(self, event):
        self.wlm_thread.stop()
        event.accept()


# =========================
# Run
# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ControlUI()
    win.show()
    sys.exit(app.exec())
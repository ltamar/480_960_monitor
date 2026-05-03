import sys
import time
from collections import deque

import requests as req
import serial.tools.list_ports
import pyqtgraph as pg

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox, QGroupBox
)
from PyQt6.QtCore import QThread, pyqtSignal

from arduino_init import dds_initial_1_new_2015, reset_arduino
from arduino_set_freq import profile0


# ============================================================
# Classes
# ============================================================

import subprocess
import os
import sys

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox



class TinySAControl(QWidget):
    def __init__(self):
        super().__init__()

        self.process = None

        layout = QVBoxLayout(self)

        box = QGroupBox("TinySA Control")
        box_layout = QHBoxLayout(box)
        layout.addWidget(box)

        self.status_label = QLabel("TinySA closed")
        box_layout.addWidget(self.status_label)

        self.open_btn = QPushButton("Open TinySA GUI")
        self.open_btn.clicked.connect(self.open_tinysa)
        box_layout.addWidget(self.open_btn)

        self.close_btn = QPushButton("Close TinySA GUI")
        self.close_btn.clicked.connect(self.close_tinysa)
        self.close_btn.setEnabled(False)
        box_layout.addWidget(self.close_btn)

    def open_tinysa(self):
        if self.process is not None and self.process.poll() is None:
            self.status_label.setText("TinySA already running")
            return

        script_path = os.path.join(
            os.path.dirname(__file__),
            "QtTinySA-main",
            "src",
            "QtTinySA.py"
        )

        self.process = subprocess.Popen(
            [sys.executable, script_path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        self.status_label.setText("TinySA running")
        self.open_btn.setEnabled(False)
        self.close_btn.setEnabled(True)

    def close_tinysa(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self.process = None

        self.status_label.setText("TinySA closed")
        self.open_btn.setEnabled(True)
        self.close_btn.setEnabled(False)

    def close(self):
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
        self.process = None

def Get_Freq_WLM_web(chan=None, debug=False):
    url = "http://132.77.40.255:5000/_getWLMData/"

    try:
        resp = req.get(url, timeout=2)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            wavelengths = [float(v) for v in data.values()]
        elif isinstance(data, list):
            wavelengths = [float(v) for v in data]
        else:
            raise ValueError(f"Unexpected JSON structure: {type(data)}")

    except Exception as e:
        print("Get_Freq_WLM_web ERROR:", repr(e))
        wavelengths = [0.0] * 8

    if chan is not None:
        wavelengths = wavelengths[chan - 1]

    return wavelengths


# ============================================================
# Arduino workers
# ============================================================

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
            self.done.emit(f"Init error: {e}")


class FreqWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, port, freq):
        super().__init__()
        self.port = port
        self.freq = freq

    def run(self):
        try:
            profile0(self.freq, 0, 0, port=self.port)
            self.done.emit(f"Frequency set to {self.freq:.3f} MHz")
        except Exception as e:
            self.done.emit(f"Freq error: {e}")


# ============================================================
# Arduino class
# ============================================================

class ArduinoControl(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        box = QGroupBox("Arduino / DDS Control")
        box_layout = QVBoxLayout(box)
        layout.addWidget(box)

        # COM selection
        com_layout = QHBoxLayout()
        com_layout.addWidget(QLabel("COM:"))

        self.com_box = QComboBox()
        com_layout.addWidget(self.com_box)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        com_layout.addWidget(refresh_btn)

        box_layout.addLayout(com_layout)

        # Initialize
        init_layout = QHBoxLayout()

        self.init_btn = QPushButton("Initialize Arduino")
        self.init_btn.clicked.connect(self.init_arduino)
        init_layout.addWidget(self.init_btn)

        self.status_label = QLabel("Idle")
        init_layout.addWidget(self.status_label)

        box_layout.addLayout(init_layout)

        # Frequency
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("Frequency (MHz):"))

        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0, 1000)
        self.freq_spin.setDecimals(3)
        self.freq_spin.setValue(35.0)
        freq_layout.addWidget(self.freq_spin)

        self.set_freq_btn = QPushButton("Set Frequency")
        self.set_freq_btn.clicked.connect(self.set_frequency)
        freq_layout.addWidget(self.set_freq_btn)

        box_layout.addLayout(freq_layout)

        self.refresh_ports()

    def refresh_ports(self):
        self.com_box.clear()
        ports = list(serial.tools.list_ports.comports())

        for p in ports:
            self.com_box.addItem(p.device)

    def get_port(self):
        return self.com_box.currentText()

    def init_arduino(self):
        port = self.get_port()

        if not port:
            self.status_label.setText("No COM port selected")
            return

        self.status_label.setText("Initializing...")
        self.init_worker = InitWorker(port)
        self.init_worker.done.connect(self.status_label.setText)
        self.init_worker.start()

    def set_frequency(self):
        port = self.get_port()

        if not port:
            self.status_label.setText("No COM port selected")
            return

        freq = self.freq_spin.value()

        self.status_label.setText("Setting frequency...")
        self.freq_worker = FreqWorker(port, freq)
        self.freq_worker.done.connect(self.status_label.setText)
        self.freq_worker.start()


# ============================================================
# WLM worker
# ============================================================

class WLMWorker(QThread):
    data_ready = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.running = False
        self.channel = 1
        self.interval_ms = 200

    def set_channel(self, channel):
        self.channel = int(channel)

    def run(self):
        self.running = True

        while self.running:
            wl = Get_Freq_WLM_web(chan=self.channel)

            try:
                self.data_ready.emit(float(wl))
            except Exception as e:
                print("WLM emit error:", e)

            self.msleep(self.interval_ms)

    def stop(self):
        self.running = False
        self.wait()


# ============================================================
# Plot axis
# ============================================================

class DecimalAxis(pg.AxisItem):
    def __init__(self, get_decimals, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._get_decimals = get_decimals

    def tickStrings(self, values, scale, spacing):
        d = self._get_decimals()
        fmt = f"{{:.{d}f}}"
        return [fmt.format(v) for v in values]


# ============================================================
# WLM class
# ============================================================

class WLMControl(QWidget):
    def __init__(self):
        super().__init__()

        self.max_points = 300
        self.time_data = deque(maxlen=self.max_points)
        self.wl_data = deque(maxlen=self.max_points)

        self.t0 = time.time()
        self.decimals = 7

        layout = QVBoxLayout(self)

        box = QGroupBox("WLM Live Monitor")
        box_layout = QVBoxLayout(box)
        layout.addWidget(box)

        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Channel:"))
        self.chan_spin = QSpinBox()
        self.chan_spin.setMinimum(1)
        self.chan_spin.setMaximum(8)
        self.chan_spin.setValue(6)
        controls_layout.addWidget(self.chan_spin)

        controls_layout.addWidget(QLabel("Decimals:"))
        self.decimals_spin = QSpinBox()
        self.decimals_spin.setMinimum(0)
        self.decimals_spin.setMaximum(10)
        self.decimals_spin.setValue(self.decimals)
        self.decimals_spin.valueChanged.connect(self.set_decimals)
        controls_layout.addWidget(self.decimals_spin)

        self.start_button = QPushButton("Start WLM")
        self.stop_button = QPushButton("Stop WLM")
        self.stop_button.setEnabled(False)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)

        self.read_label = QLabel("WL: ---")
        self.read_label.setStyleSheet("""
            font-size: 70px;
            font-weight: bold;
            color: rgb(139, 0, 0);
            font-family: Consolas, monospace;
        """)
        controls_layout.addStretch()
        controls_layout.addWidget(self.read_label)
        controls_layout.addStretch()

        controls_layout.addStretch()

        self.status_label = QLabel("Stopped")
        controls_layout.addWidget(self.status_label)

        box_layout.addLayout(controls_layout)

        left_axis = DecimalAxis(lambda: self.decimals, orientation="left")

        self.plot_widget = pg.PlotWidget(axisItems={"left": left_axis})
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.setLabel("left", "Wavelength")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.5)

        self.curve = self.plot_widget.plot(
            [],
            [],
            pen=pg.mkPen(width=2),
            symbol="o",
            symbolSize=6,
            symbolBrush="w"
        )

        box_layout.addWidget(self.plot_widget)

        self.worker = WLMWorker()
        self.worker.data_ready.connect(self.update_data)

        self.start_button.clicked.connect(self.start_acquisition)
        self.stop_button.clicked.connect(self.stop_acquisition)
        self.chan_spin.valueChanged.connect(self.worker.set_channel)
        self.chan_spin.setValue(6)  # ensure channel 6
        self.start_acquisition()

    def set_decimals(self, value):
        self.decimals = int(value)

    def start_acquisition(self):
        if self.worker.isRunning():
            return

        self.t0 = time.time()
        self.time_data.clear()
        self.wl_data.clear()

        self.worker.set_channel(6)
        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Running")

    def stop_acquisition(self):
        if self.worker.isRunning():
            self.worker.stop()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def update_data(self, wl_value):
        wl_value = round(float(wl_value), self.decimals)
        t = time.time() - self.t0

        self.time_data.append(t)
        self.wl_data.append(wl_value)

        self.curve.setData(list(self.time_data), list(self.wl_data))
        self.plot_widget.enableAutoRange()

        fmt = f"{{:.{self.decimals}f}}"
        self.read_label.setText(f"WL: {fmt.format(wl_value)}")

    def close(self):
        self.stop_acquisition()


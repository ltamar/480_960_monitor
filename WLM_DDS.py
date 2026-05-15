import os
import subprocess
import sys
import time
from collections import deque

import requests as req
import serial.tools.list_ports
import pyqtgraph as pg

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox, QGroupBox,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

from arduino_init import dds_initial_1_new_2015, reset_arduino
from arduino_set_freq import profile0


try:
    import win32con
    import win32gui
    import win32process

except ImportError:
    win32con = None
    win32gui = None
    win32process = None

from datetime import datetime


class TinySAControl(QWidget):
    def __init__(self):
        super().__init__()

        self.process = None
        self.tinysa_hwnd = None
        self._embed_timer = QTimer(self)
        self._embed_timer.timeout.connect(self._try_embed_tinysa)

        layout = QVBoxLayout(self)

        box = QGroupBox("TinySA Control")
        box_layout = QVBoxLayout(box)
        layout.addWidget(box)

        controls_layout = QHBoxLayout()

        self.status_label = QLabel("TinySA closed")
        controls_layout.addWidget(self.status_label)

        self.open_btn = QPushButton("Open TinySA GUI")
        self.open_btn.clicked.connect(self.open_tinysa)
        controls_layout.addWidget(self.open_btn)

        self.close_btn = QPushButton("Close TinySA GUI")
        self.close_btn.clicked.connect(self.close_tinysa)
        self.close_btn.setEnabled(False)
        controls_layout.addWidget(self.close_btn)

        box_layout.addLayout(controls_layout)

        self.embed_frame = QFrame()
        self.embed_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.embed_frame.setMinimumSize(700, 500)
        self.embed_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        box_layout.addWidget(self.embed_frame, 1)

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

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=os.path.dirname(script_path),
            creationflags=creationflags
        )

        self.tinysa_hwnd = None
        self.status_label.setText("TinySA starting...")
        self.open_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self._embed_timer.start(250)

    def close_tinysa(self):
        self._embed_timer.stop()

        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
                try:
                    self.process.wait(timeout=2)
                except Exception:
                    pass

        self.process = None
        self.tinysa_hwnd = None

        self.status_label.setText("TinySA closed")
        self.open_btn.setEnabled(True)
        self.close_btn.setEnabled(False)

    def _try_embed_tinysa(self):
        if self.process is None:
            self._embed_timer.stop()
            return

        if self.process.poll() is not None:
            self.process = None
            self.tinysa_hwnd = None
            self._embed_timer.stop()
            self.status_label.setText("TinySA closed")
            self.open_btn.setEnabled(True)
            self.close_btn.setEnabled(False)
            return

        if win32con is None or win32gui is None or win32process is None:
            self._embed_timer.stop()
            self.status_label.setText("TinySA running in separate window")
            return

        hwnd = self._find_tinysa_window()
        if hwnd is None:
            return

        parent_hwnd = int(self.embed_frame.winId())

        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style &= ~win32con.WS_POPUP
        style &= ~win32con.WS_CAPTION
        style &= ~win32con.WS_THICKFRAME
        style |= win32con.WS_CHILD
        style |= win32con.WS_VISIBLE
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        win32gui.SetParent(hwnd, parent_hwnd)
        win32gui.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_FRAMECHANGED
        )
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        self.tinysa_hwnd = hwnd
        self._resize_embedded_tinysa()
        self._embed_timer.stop()
        self.status_label.setText("TinySA embedded")

    def _find_tinysa_window(self):
        matches = []

        def enum_handler(hwnd, ctx):
            if not win32gui.IsWindowVisible(hwnd):
                return

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid != self.process.pid:
                return

            title = win32gui.GetWindowText(hwnd)
            if "QtTinySA" in title:
                ctx.append(hwnd)

        win32gui.EnumWindows(enum_handler, matches)
        return matches[0] if matches else None

    def _resize_embedded_tinysa(self):
        if self.tinysa_hwnd is None or win32gui is None:
            return

        size = self.embed_frame.size()
        win32gui.MoveWindow(
            self.tinysa_hwnd,
            0,
            0,
            size.width(),
            size.height(),
            True
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_embedded_tinysa()

    def closeEvent(self, event):
        self.close_tinysa()
        super().closeEvent(event)


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


class FreqScanWorker(QThread):
    progress = pyqtSignal(float)
    done = pyqtSignal(str)

    def __init__(self, port, min_freq, max_freq, step_size):
        super().__init__()
        self.port = port
        self.min_freq = min_freq
        self.max_freq = max_freq
        self.step_size = step_size
        self.running = True

    def run(self):
        current = self.min_freq
        scanned_max = False

        try:
            while self.running and current <= self.max_freq:
                profile0(current, 0, 0, port=self.port)
                self.progress.emit(current)

                if abs(current - self.max_freq) < 1e-9:
                    scanned_max = True
                    break

                if not self._wait_between_steps():
                    break

                next_freq = current + self.step_size
                if next_freq > self.max_freq and not scanned_max:
                    current = self.max_freq
                else:
                    current = next_freq

            if self.running:
                self.done.emit("Frequency scan complete")
            else:
                self.done.emit("Frequency scan stopped")
        except Exception as e:
            self.done.emit(f"Scan error: {e}")

    def _wait_between_steps(self):
        for _ in range(10):
            if not self.running:
                return False
            self.msleep(100)
        return True

    def stop(self, wait=True):
        self.running = False
        if wait:
            self.wait()


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

        # Frequency scan
        scan_layout = QHBoxLayout()
        scan_layout.addWidget(QLabel("Scan min/max/step (MHz):"))

        self.scan_min_spin = QDoubleSpinBox()
        self.scan_min_spin.setRange(0, 1000)
        self.scan_min_spin.setDecimals(3)
        self.scan_min_spin.setValue(30.0)
        scan_layout.addWidget(self.scan_min_spin)

        self.scan_max_spin = QDoubleSpinBox()
        self.scan_max_spin.setRange(0, 1000)
        self.scan_max_spin.setDecimals(3)
        self.scan_max_spin.setValue(40.0)
        scan_layout.addWidget(self.scan_max_spin)

        self.scan_step_spin = QDoubleSpinBox()
        self.scan_step_spin.setRange(0.001, 1000)
        self.scan_step_spin.setDecimals(3)
        self.scan_step_spin.setValue(1.0)
        scan_layout.addWidget(self.scan_step_spin)

        self.start_scan_btn = QPushButton("Start Scan")
        self.start_scan_btn.clicked.connect(self.start_scan)
        scan_layout.addWidget(self.start_scan_btn)

        self.stop_scan_btn = QPushButton("Stop Scan")
        self.stop_scan_btn.clicked.connect(self.stop_scan)
        self.stop_scan_btn.setEnabled(False)
        scan_layout.addWidget(self.stop_scan_btn)

        box_layout.addLayout(scan_layout)

        self.scan_worker = None
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

    def start_scan(self):
        port = self.get_port()

        if not port:
            self.status_label.setText("No COM port selected")
            return

        if self.scan_worker is not None and self.scan_worker.isRunning():
            self.status_label.setText("Scan already running")
            return

        min_freq = self.scan_min_spin.value()
        max_freq = self.scan_max_spin.value()
        step_size = self.scan_step_spin.value()

        if min_freq > max_freq:
            self.status_label.setText("Scan min must be <= max")
            return

        self.status_label.setText("Starting frequency scan...")
        self.start_scan_btn.setEnabled(False)
        self.stop_scan_btn.setEnabled(True)
        self.set_freq_btn.setEnabled(False)
        self.init_btn.setEnabled(False)

        self.scan_worker = FreqScanWorker(port, min_freq, max_freq, step_size)
        self.scan_worker.progress.connect(self.update_scan_progress)
        self.scan_worker.done.connect(self.finish_scan)
        self.scan_worker.start()

    def stop_scan(self, wait=False):
        if self.scan_worker is not None and self.scan_worker.isRunning():
            self.status_label.setText("Stopping frequency scan...")
            self.scan_worker.stop(wait=wait)

    def update_scan_progress(self, freq):
        self.freq_spin.setValue(freq)
        self.status_label.setText(f"Scanning: {freq:.3f} MHz")

    def finish_scan(self, message):
        self.status_label.setText(message)
        self.start_scan_btn.setEnabled(True)
        self.stop_scan_btn.setEnabled(False)
        self.set_freq_btn.setEnabled(True)
        self.init_btn.setEnabled(True)

    def closeEvent(self, event):
        self.stop_scan(wait=True)
        super().closeEvent(event)


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
        self.latest_wl = None
        self.log_file_path = None

        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.log_wavelength)

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

        # Create log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = f"wlm_log_{timestamp}.csv"

        with open(self.log_file_path, "w") as f:
            f.write("timestamp,wavelength_nm\n")

        # Start periodic logger (1 minute)
        self.log_timer.start(60000)

        self.worker.set_channel(6)
        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText(f"Running | Logging -> {self.log_file_path}")

    def stop_acquisition(self):
        self.log_timer.stop()

        if self.worker.isRunning():
            self.worker.stop()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def update_data(self, wl_value):
        wl_value = round(float(wl_value), self.decimals)

        # Store latest value for logger
        self.latest_wl = wl_value

        t = time.time() - self.t0

        self.time_data.append(t)
        self.wl_data.append(wl_value)

        self.curve.setData(list(self.time_data), list(self.wl_data))
        self.plot_widget.enableAutoRange()

        fmt = f"{{:.{self.decimals}f}}"
        self.read_label.setText(f"WL: {fmt.format(wl_value)}")

    def log_wavelength(self):
        if self.latest_wl is None:
            return

        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(self.log_file_path, "a") as f:
                f.write(f"{ts},{self.latest_wl:.{self.decimals}f}\n")

        except Exception as e:
            print("Logging error:", e)

    def close(self):
        self.stop_acquisition()


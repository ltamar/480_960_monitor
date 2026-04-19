import sys
import time
from collections import deque

import requests as req
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSpinBox
)
from PyQt6.QtCore import QTimer
import pyqtgraph as pg


def Get_Freq_WLM_web(chan=None, debug=False):
    """
    Fetch wavelength data (in nm or whatever the server returns) from the HighFinesse WLM web server.
    Adapted from your function.
    """
    url = "http://132.77.40.255:5000/_getWLMData/"

    try:
        resp = req.get(url, timeout=2)
        if debug:
            print("Status code:", resp.status_code)
            print("Raw text:", resp.text[:500])
        resp.raise_for_status()
        data = resp.json()
        if debug:
            print("Parsed JSON:", data, "type:", type(data))

        # Handle dict or list
        if isinstance(data, dict):
            wavelengths = [float(v) for v in data.values()]
        elif isinstance(data, list):
            wavelengths = [float(v) for v in data]
        else:
            raise ValueError(f"Unexpected JSON structure: {type(data)}")

    except Exception as e:
        print("Get_Freq_WLM_web ERROR:", repr(e))
        # fall back to zeros (8 channels assumed)
        wavelengths = [0.0] * 8

    if chan is not None:
        # MATLAB-style 1-based indexing
        if isinstance(chan, int):
            wavelengths = wavelengths[chan - 1]
        else:
            wavelengths = [wavelengths[c - 1] for c in chan]

    return wavelengths


class DecimalAxis(pg.AxisItem):
    """
    AxisItem that formats tick labels with a configurable number of decimals.
    """
    def __init__(self, get_decimals, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._get_decimals = get_decimals

    def tickStrings(self, values, scale, spacing):
        d = self._get_decimals()
        fmt = f"{{:.{d}f}}"
        return [fmt.format(v) for v in values]


class WLMMonitor(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("WLM Live Monitor")
        self.resize(800, 500)

        # Data buffers
        self.max_points = 300  # keep last N points in the plot
        self.time_data = deque(maxlen=self.max_points)
        self.wl_data = deque(maxlen=self.max_points)
        self.t0 = time.time()

        # Polling interval (ms)
        self.update_interval_ms = 200

        # Number of decimal places for display/rounding
        self.decimals = 7

        # --- Central widget and layout ---
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Top controls: channel selector, decimals, start/stop, status ---
        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Channel:"))

        self.chan_spin = QSpinBox()
        self.chan_spin.setMinimum(1)
        self.chan_spin.setMaximum(8)  # adjust if you have more channels
        self.chan_spin.setValue(1)
        controls_layout.addWidget(self.chan_spin)

        # Decimals selector
        controls_layout.addWidget(QLabel("Decimals:"))
        self.decimals_spin = QSpinBox()
        self.decimals_spin.setMinimum(0)
        self.decimals_spin.setMaximum(6)
        self.decimals_spin.setValue(self.decimals)
        self.decimals_spin.valueChanged.connect(self.set_decimals)
        controls_layout.addWidget(self.decimals_spin)

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)

        # Current wavelength readout
        self.read_label = QLabel("WL: ---")
        controls_layout.addWidget(self.read_label)

        controls_layout.addStretch()

        self.status_label = QLabel("Stopped")
        controls_layout.addWidget(self.status_label)

        layout.addLayout(controls_layout)

        # --- Plot widget (pyqtgraph) with custom Y axis ---
        left_axis = DecimalAxis(lambda: self.decimals, orientation="left")
        self.plot_widget = pg.PlotWidget(axisItems={"left": left_axis})
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.setLabel("left", "Wavelength")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.5)
        self.curve = self.plot_widget.plot(
            [],
            [],
            pen=pg.mkPen(width=2),  # visible connecting line
            symbol="o",
            symbolSize=6,
            symbolBrush="w"
        )
        layout.addWidget(self.plot_widget)

        # --- Timer for polling the WLM ---
        self.timer = QTimer()
        self.timer.setInterval(self.update_interval_ms)
        self.timer.timeout.connect(self.update_data)

        # --- Connect buttons ---
        self.start_button.clicked.connect(self.start_acquisition)
        self.stop_button.clicked.connect(self.stop_acquisition)

    def set_decimals(self, value: int):
        self.decimals = max(0, int(value))

    def start_acquisition(self):
        self.t0 = time.time()
        self.time_data.clear()
        self.wl_data.clear()

        self.timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Running")

    def stop_acquisition(self):
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def update_data(self):
        chan = self.chan_spin.value()

        # Call your web function
        wl = Get_Freq_WLM_web(chan=chan)
        # If chan is int, your function returns a float, else list
        if isinstance(wl, list):
            wl_value = wl[0]
        else:
            wl_value = wl

        # Round to the chosen number of decimals before plotting
        wl_value = round(float(wl_value), self.decimals)

        t = time.time() - self.t0

        self.time_data.append(t)
        self.wl_data.append(wl_value)

        # Update plot
        self.curve.setData(list(self.time_data), list(self.wl_data))
        self.plot_widget.enableAutoRange()

        # Update numeric readout with same precision
        fmt = f"{{:.{self.decimals}f}}"
        self.read_label.setText(f"WL: {fmt.format(wl_value)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = WLMMonitor()
    win.show()
    sys.exit(app.exec())

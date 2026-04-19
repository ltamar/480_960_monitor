import requests as req


class WLMClient:
    """
    Client for HighFinesse WLM web interface.

    Features:
    - Fetch all channels or a single channel
    - Handles dict or list JSON formats
    - Safe fallback on errors
    - Optional debug output
    """

    def __init__(self,
                 url: str = "http://132.77.40.255:5000/_getWLMData/",
                 timeout: float = 1.0,
                 num_channels: int = 8):
        self.url = url
        self.timeout = timeout
        self.num_channels = num_channels

    # -----------------------------
    # Core request
    # -----------------------------
    def _fetch_raw(self, debug=False):
        try:
            resp = req.get(self.url, timeout=self.timeout)

            if debug:
                print("Status:", resp.status_code)
                print("Raw:", resp.text[:200])

            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            if debug:
                print("WLM fetch error:", repr(e))
            return None

    # -----------------------------
    # Parse response into float list
    # -----------------------------
    def get_all(self, debug=False):
        data = self._fetch_raw(debug=debug)

        if data is None:
            return [0.0] * self.num_channels

        try:
            if isinstance(data, dict):
                values = list(data.values())
            elif isinstance(data, list):
                values = data
            else:
                raise ValueError(f"Unexpected type: {type(data)}")

            return [float(v) for v in values]

        except Exception as e:
            if debug:
                print("Parsing error:", repr(e))
            return [0.0] * self.num_channels

    # -----------------------------
    # Single channel (1-based index)
    # -----------------------------
    def get_channel(self, chan: int, debug=False) -> float:
        if chan < 1 or chan > self.num_channels:
            raise ValueError(f"Channel must be 1–{self.num_channels}")

        data = self.get_all(debug=debug)
        return float(data[chan - 1])

    # -----------------------------
    # Multiple channels
    # -----------------------------
    def get_channels(self, channels, debug=False):
        data = self.get_all(debug=debug)
        return [float(data[c - 1]) for c in channels]

    # -----------------------------
    # Optional: frequency conversion (THz)
    # -----------------------------
    @staticmethod
    def wavelength_to_frequency_nm(wavelength_nm: float) -> float:
        """
        Convert wavelength (nm) → frequency (THz)
        f = c / λ
        """
        c = 299792458  # m/s
        wl_m = wavelength_nm * 1e-9
        return (c / wl_m) / 1e12  # THz


# -----------------------------
# Optional standalone test
# -----------------------------
if __name__ == "__main__":
    wlm = WLMClient()

    print("All channels:", wlm.get_all())
    print("Channel 6:", wlm.get_channel(6))

    wl = wlm.get_channel(6)
    print("Freq (THz):", WLMClient.wavelength_to_frequency_nm(wl))
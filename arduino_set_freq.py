import serial
import time


def profile0(fout, offset_phase, Adb,
             port="COM1", baud=9600, fsys=1000.0):
    """
    Set DDS frequency
    """

    FTW = int(round((2**32) * (fout / fsys))) & 0xFFFFFFFF
    POW = int((offset_phase * (2**16)) / 360.0) & 0xFFFF
    ASF = int(round(((2**14) - 1) * (10 ** (Adb / 20.0)))) & 0xFFFF

    bytes_to_send = [
        0x0E,
        (ASF >> 8) & 0xFF, ASF & 0xFF,
        (POW >> 8) & 0xFF, POW & 0xFF,
        (FTW >> 24) & 0xFF,
        (FTW >> 16) & 0xFF,
        (FTW >> 8) & 0xFF,
        FTW & 0xFF,
    ]

    with serial.Serial(port, baudrate=baud, timeout=1) as ser:

        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(2.0)  # Arduino reset delay

        # Start byte
        ser.write(b's')
        ser.flush()
        time.sleep(0.01)

        for b in bytes_to_send:
            ser.write(bytes([b]))
            ser.flush()
            time.sleep(0.002)
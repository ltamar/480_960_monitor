import serial
import time


def reset_arduino(port: str, baud: int = 9600):
    """
    Reset Arduino by opening the port and sending 's'
    """
    with serial.Serial(port, baudrate=baud, timeout=1) as ser:
        time.sleep(2.0)  # allow Arduino reset
        ser.write(b's')
        ser.flush()


def dds_initial_1_new_2015(parallel, DRG, Singlemode, OSK, REF1, TCXO1,
                          port="COM1", baud=9600):
    """
    Initialize DDS registers (same behavior as MATLAB version)
    """

    with serial.Serial(port=port, baudrate=baud, timeout=1) as ser:
        time.sleep(1.0)

        # Start command
        ser.write(b"a")

        # CFR1
        ser.write(bytes([0x00, 0x00, 0x00, 0x00, 0x00]))

        # CFR2
        ser.write(bytes([0x01, 0x01, 0x40, 0x08, 0x00]))

        # CFR3
        ser.write(bytes([0x02, 0x2D, 0x3F, 0xC1, 0xC8]))

        # IO_UPDATE
        ser.write(bytes([0x04, 0x00, 0x00, 0x00, 0x02]))

        # DAC
        ser.write(bytes([0x03, 0x00, 0x00, 0x00, 0xFF]))

        # ASF
        ser.write(bytes([0x09, 0xFF, 0xFF, 0xFF, 0xFF]))

        # REF + CONTROL
        if REF1 == 1:
            ser.write(bytes([0x00, 0x00]))
        else:
            ser.write(bytes([0xFF, 0xFF]))

        ser.flush()
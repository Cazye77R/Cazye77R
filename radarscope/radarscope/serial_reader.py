import serial

FRAME_HEADER = bytes([0xAA, 0xFF, 0x03, 0x00])
FRAME_FOOTER = bytes([0x55, 0xCC])

MAX_FRAME_SIZE = 256


class SerialReader:
    def __init__(self, port: str, baudrate: int = 256000):
        self.port = port
        self.baudrate = baudrate
        self._serial: serial.Serial | None = None
        self._open()

    def _open(self) -> None:
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
        )

    def read_raw_frame(self) -> bytes | None:
        """Read bytes until a complete LD2450 frame is found and return it."""
        buf = bytearray()

        while True:
            byte = self._serial.read(1)
            if not byte:
                continue

            buf += byte

            # Keep buffer bounded; discard leading bytes when too large
            if len(buf) > MAX_FRAME_SIZE:
                buf = buf[1:]

            # Check for header at the start of buffer
            if len(buf) >= len(FRAME_HEADER):
                if buf[: len(FRAME_HEADER)] != FRAME_HEADER:
                    buf = buf[1:]
                    continue

            # Once header is confirmed, look for footer
            if len(buf) >= len(FRAME_HEADER) + len(FRAME_FOOTER):
                footer_pos = buf.find(FRAME_FOOTER, len(FRAME_HEADER))
                if footer_pos != -1:
                    end = footer_pos + len(FRAME_FOOTER)
                    frame = bytes(buf[:end])
                    buf = buf[end:]
                    return frame

    def close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()

    def __enter__(self) -> "SerialReader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

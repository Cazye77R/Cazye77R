from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from services.wifi_scanner import WifiError, WifiResult, WifiScanner


class ScanWorker(QThread):
    """Runs WifiScanner.scan_averaged() in a background thread."""

    result_ready   = Signal(WifiResult)
    error_occurred = Signal(str)

    def __init__(
        self,
        scanner: WifiScanner,
        count: int = 5,
        interval: float = 0.4,
    ) -> None:
        super().__init__()
        self._scanner  = scanner
        self._count    = count
        self._interval = interval

    def run(self) -> None:
        try:
            result = self._scanner.scan_averaged(self._count, self._interval)
            self.result_ready.emit(result)
        except WifiError as exc:
            self.error_occurred.emit(str(exc))
        except Exception as exc:
            self.error_occurred.emit(f"Unerwarteter Fehler: {exc}")


class NetworkListWorker(QThread):
    """Fetches visible networks via WifiScanner.get_available_networks()."""

    result_ready = Signal(list)   # list[dict]

    def __init__(self, scanner: WifiScanner) -> None:
        super().__init__()
        self._scanner = scanner

    def run(self) -> None:
        try:
            nets = self._scanner.get_available_networks()
            self.result_ready.emit(nets)
        except WifiError:
            self.result_ready.emit([])
        except Exception:
            self.result_ready.emit([])

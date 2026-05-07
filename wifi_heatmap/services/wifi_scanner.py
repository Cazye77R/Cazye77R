from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class WifiNetwork:
    ssid: str
    bssid: str
    dbm: float
    channel: int
    band: str  # "2.4GHz" | "5GHz"


class WifiScanner:
    def scan(self) -> list[WifiNetwork]:
        """Return available wifi networks. Platform-specific implementation goes here."""
        return []

    def get_signal(self, ssid: str) -> Optional[WifiNetwork]:
        return next((n for n in self.scan() if n.ssid == ssid), None)

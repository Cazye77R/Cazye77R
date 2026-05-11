from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Measurement:
    x: float
    y: float
    dbm: float
    signal_percent: int
    ssid: str
    channel: int
    band: str             # "2.4 GHz" | "5 GHz"
    timestamp: datetime = field(default_factory=datetime.now)
    std_deviation: float = 0.0
    bssid: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "dbm": self.dbm,
            "signal_percent": self.signal_percent,
            "ssid": self.ssid,
            "channel": self.channel,
            "band": self.band,
            "timestamp": self.timestamp.isoformat(),
            "std_deviation": self.std_deviation,
            "bssid": self.bssid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Measurement":
        return cls(
            x=data["x"],
            y=data["y"],
            dbm=data["dbm"],
            signal_percent=data["signal_percent"],
            ssid=data["ssid"],
            channel=data["channel"],
            band=data["band"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            std_deviation=data.get("std_deviation", 0.0),
            bssid=data.get("bssid", ""),
        )

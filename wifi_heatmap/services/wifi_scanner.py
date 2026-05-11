from __future__ import annotations

import math
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

_AIRPORT = (
    "/System/Library/PrivateFrameworks/Apple80211.framework"
    "/Versions/Current/Resources/airport"
)
_TIMEOUT = 5
_MAC_RE  = re.compile(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}")


# ── Exceptions ────────────────────────────────────────────────────────────────

class WifiError(Exception):
    """Raised for any wifi scanning failure (not connected, no adapter, …)."""


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class WifiResult:
    ssid:           str
    dbm:            float
    signal_percent: int
    channel:        int
    band:           str        # "2.4 GHz" | "5 GHz" | "?"
    bssid:          str
    std_deviation:  float = field(default=0.0)


# Backward-compat alias for code that still imports WifiNetwork
WifiNetwork = WifiResult


# ── Internal helpers ──────────────────────────────────────────────────────────

def _run(args: list[str]) -> str:
    try:
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
        return r.stdout
    except subprocess.TimeoutExpired:
        raise WifiError(
            f"Zeitüberschreitung nach {_TIMEOUT} s beim Ausführen von: {args[0]}"
        )
    except FileNotFoundError:
        raise WifiError(f"Befehl nicht gefunden: {args[0]}")


def _channel_to_band(channel: int) -> str:
    if 1 <= channel <= 14:
        return "2.4 GHz"
    if channel >= 36:
        return "5 GHz"
    return "?"


def _radio_type_to_band(radio: str) -> str:
    r = radio.lower()
    if "802.11ac" in r or ("802.11a" in r and "802.11n" not in r):
        return "5 GHz"
    return "2.4 GHz"


def _pct_to_dbm(pct: int) -> float:
    return (pct / 2.0) - 100.0


def _dbm_to_pct(dbm: float) -> int:
    return min(max(int(2.0 * (dbm + 100.0)), 0), 100)


# ── Platform parsers ──────────────────────────────────────────────────────────

def _parse_netsh_interfaces(output: str) -> WifiResult:
    """Parse stdout of 'netsh wlan show interfaces'."""

    def field(pattern: str, default: str = "") -> str:
        m = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else default

    state = field(r"^\s+State\s*:\s*(.+)$")
    if state and "connected" not in state.lower():
        raise WifiError(
            f"WLAN-Adapter nicht verbunden (State: {state}). "
            "Bitte zuerst mit einem Netzwerk verbinden."
        )

    ssid   = field(r"^\s+SSID\s*:\s*(.+)$")
    bssid  = field(r"^\s+BSSID\s*:\s*(.+)$")
    radio  = field(r"^\s+Radio type\s*:\s*(.+)$")
    chan_s = field(r"^\s+Channel\s*:\s*(\d+)")
    sig_s  = field(r"^\s+Signal\s*:\s*(\d+)\s*%")

    if not ssid:
        if not output.strip():
            raise WifiError(
                "Kein WLAN-Adapter gefunden. "
                "Bitte prüfen Sie, ob ein WLAN-Adapter installiert ist."
            )
        raise WifiError("Keine WLAN-Verbindung aktiv")

    channel    = int(chan_s) if chan_s.isdigit() else 0
    signal_pct = int(sig_s)  if sig_s.isdigit()  else 0
    dbm        = _pct_to_dbm(signal_pct)
    band       = _channel_to_band(channel) if channel else _radio_type_to_band(radio)

    return WifiResult(
        ssid=ssid, dbm=dbm, signal_percent=signal_pct,
        channel=channel, band=band, bssid=bssid,
    )


def _parse_airport_info(output: str) -> WifiResult:
    """Parse stdout of 'airport -I'."""

    def field(pattern: str, default: str = "") -> str:
        m = re.search(pattern, output, re.MULTILINE)
        return m.group(1).strip() if m else default

    ssid   = field(r"^\s+SSID\s*:\s*(.+)$")
    bssid  = field(r"^\s+BSSID\s*:\s*(\S+)")
    dbm_s  = field(r"^\s+agrCtlRSSI\s*:\s*(-?\d+)")
    chan_s = field(r"^\s+channel\s*:\s*(\d+)")

    if not ssid:
        state = field(r"^\s+state\s*:\s*(.+)$")
        if state and "running" not in state.lower():
            raise WifiError(
                f"WLAN nicht aktiv (state: {state}). "
                "Bitte WLAN einschalten und mit einem Netzwerk verbinden."
            )
        raise WifiError("Keine WLAN-Verbindung aktiv")

    dbm        = float(dbm_s) if dbm_s else -100.0
    channel    = int(chan_s)   if chan_s.isdigit() else 0
    signal_pct = _dbm_to_pct(dbm)
    band       = _channel_to_band(channel)

    return WifiResult(
        ssid=ssid, dbm=dbm, signal_percent=signal_pct,
        channel=channel, band=band, bssid=bssid,
    )


# ── Scanner ───────────────────────────────────────────────────────────────────

class WifiScanner:
    """
    Platform-aware WiFi scanner.

    Usage
    -----
    scanner = WifiScanner()
    result  = scanner.scan()                      # single measurement
    result  = scanner.scan_averaged(count=5)      # averaged over N scans
    nets    = scanner.get_available_networks()    # all visible SSIDs
    """

    # ── Single scan ───────────────────────────────────────────────

    def scan(self) -> WifiResult:
        """Return current connection info as a WifiResult.

        Raises WifiError if no adapter is found, the adapter is not
        connected, or the command times out.
        """
        if sys.platform == "win32":
            return self._scan_windows()
        if sys.platform == "darwin":
            return self._scan_macos()
        raise WifiError(
            f"Nicht unterstütztes Betriebssystem: {sys.platform}. "
            "Nur Windows und macOS werden unterstützt."
        )

    def _scan_windows(self) -> WifiResult:
        output = _run(["netsh", "wlan", "show", "interfaces"])
        return _parse_netsh_interfaces(output)

    def _scan_macos(self) -> WifiResult:
        output = _run([_AIRPORT, "-I"])
        return _parse_airport_info(output)

    # ── Averaged scan ─────────────────────────────────────────────

    def scan_averaged(self, count: int = 5, interval: float = 0.4) -> WifiResult:
        """Perform *count* scans spaced *interval* seconds apart.

        Returns a WifiResult whose dbm is the arithmetic mean and
        std_deviation is the population standard deviation.
        Raises WifiError if *every* individual scan fails.
        """
        results: list[WifiResult] = []
        last_exc: Optional[WifiError] = None

        for i in range(max(1, count)):
            if i > 0:
                time.sleep(interval)
            try:
                results.append(self.scan())
            except WifiError as exc:
                last_exc = exc

        if not results:
            raise last_exc or WifiError("Keine einzige Messung war erfolgreich")

        dbm_values = [r.dbm for r in results]
        mean_dbm   = sum(dbm_values) / len(dbm_values)
        variance   = sum((d - mean_dbm) ** 2 for d in dbm_values) / len(dbm_values)
        std_dev    = math.sqrt(variance)

        base = results[-1]
        return WifiResult(
            ssid=base.ssid,
            dbm=round(mean_dbm, 1),
            signal_percent=_dbm_to_pct(mean_dbm),
            channel=base.channel,
            band=base.band,
            bssid=base.bssid,
            std_deviation=round(std_dev, 2),
        )

    # ── Network list ──────────────────────────────────────────────

    def get_available_networks(self) -> list[dict]:
        """Return all visible SSIDs as a list of dicts.

        Keys: ssid, bssid, dbm, signal_percent, channel, band
        Raises WifiError if scanning is not supported or fails.
        """
        if sys.platform == "win32":
            return self._networks_windows()
        if sys.platform == "darwin":
            return self._networks_macos()
        raise WifiError(
            f"Nicht unterstütztes Betriebssystem: {sys.platform}"
        )

    def _networks_windows(self) -> list[dict]:
        output = _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
        if not output:
            raise WifiError(
                "Kein WLAN-Adapter gefunden oder keine Netzwerke in Reichweite"
            )

        networks: list[dict] = []
        # Split into per-SSID blocks; each starts with "SSID N :"
        blocks = re.split(r"\nSSID \d+\s*:", "\n" + output)
        for block in blocks[1:]:
            ssid_m = re.match(r"[ \t]*(.+)", block)
            ssid   = ssid_m.group(1).strip() if ssid_m else ""

            bssid_m  = re.search(r"BSSID \d+\s*:\s*(\S+)", block)
            bssid    = bssid_m.group(1) if bssid_m else ""
            sig_m    = re.search(r"Signal\s*:\s*(\d+)\s*%", block, re.IGNORECASE)
            sig_pct  = int(sig_m.group(1)) if sig_m else 0
            chan_m   = re.search(r"Channel\s*:\s*(\d+)", block, re.IGNORECASE)
            channel  = int(chan_m.group(1)) if chan_m else 0
            radio_m  = re.search(r"Radio type\s*:\s*(.+)", block, re.IGNORECASE)
            radio    = radio_m.group(1).strip() if radio_m else ""

            dbm  = _pct_to_dbm(sig_pct)
            band = _channel_to_band(channel) if channel else _radio_type_to_band(radio)
            networks.append({
                "ssid": ssid, "bssid": bssid, "dbm": dbm,
                "signal_percent": sig_pct, "channel": channel, "band": band,
            })
        return networks

    def _networks_macos(self) -> list[dict]:
        output = _run([_AIRPORT, "-s"])
        if not output:
            return []

        networks: list[dict] = []
        for line in output.splitlines():
            m = _MAC_RE.search(line)
            if not m:
                continue
            bssid = m.group(0)
            ssid  = line[:m.start()].strip()
            rest  = line[m.end():].split()
            if len(rest) < 2:
                continue
            try:
                dbm     = float(rest[0])
                channel = int(rest[1].split(",")[0])
            except (ValueError, IndexError):
                continue

            networks.append({
                "ssid": ssid, "bssid": bssid, "dbm": dbm,
                "signal_percent": _dbm_to_pct(dbm),
                "channel": channel, "band": _channel_to_band(channel),
            })
        return networks

    # ── Convenience (old API) ─────────────────────────────────────

    def get_signal(self, ssid: str) -> Optional[WifiResult]:
        """Return WifiResult for a given SSID from the network list, or None."""
        try:
            return next(
                (WifiResult(**{k: n[k] for k in WifiResult.__dataclass_fields__
                               if k != "std_deviation"}, std_deviation=0.0)
                 for n in self.get_available_networks() if n["ssid"] == ssid),
                None,
            )
        except WifiError:
            return None

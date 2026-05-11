"""
tests/test_scanner.py — WifiScanner smoke tests.

Run from the repo root:
    python -m pytest tests/test_scanner.py -v
or directly:
    python tests/test_scanner.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Make the wifi_heatmap package importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent / "wifi_heatmap"))

from services.wifi_scanner import (
    WifiError,
    WifiResult,
    WifiScanner,
    _parse_airport_info,
    _parse_netsh_interfaces,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_NETSH_CONNECTED = """\

There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX201
    GUID                   : 11111111-2222-3333-4444-555555555555
    Physical address       : aa:bb:cc:dd:ee:ff
    Interface Type         : Primary
    State                  : connected
    SSID                   : TestNetz
    BSSID                  : 11:22:33:44:55:66
    Network type           : Infrastructure
    Radio type             : 802.11ac
    Authentication         : WPA2-Personal
    Cipher                 : CCMP
    Connection mode        : Auto Connect
    Channel                : 36
    Receive rate (Mbps)    : 866
    Transmit rate (Mbps)   : 866
    Signal                 : 76%
    Profile                : TestNetz
"""

_NETSH_DISCONNECTED = """\

There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX201
    GUID                   : 11111111-2222-3333-4444-555555555555
    Physical address       : aa:bb:cc:dd:ee:ff
    Interface Type         : Primary
    State                  : disconnected
"""

_AIRPORT_CONNECTED = """\
     agrCtlRSSI: -57
     agrExtRSSI: 0
    agrCtlNoise: -95
    agrExtNoise: 0
          state: running
        op mode: station
     lastTxRate: 433
        maxRate: 433
lastAssocStatus: 0
    802.11 auth: open
      link auth: wpa2-psk
          BSSID: aa:bb:cc:dd:ee:ff
           SSID: HeimnetzApfel
            MCS: 9
        channel: 36,80
"""

_AIRPORT_NOT_CONNECTED = """\
          state: init
        op mode: station
     lastTxRate: 0
        maxRate: 0
lastAssocStatus: 0
    802.11 auth: open
      link auth: none
          BSSID: 0:0:0:0:0:0
           SSID:
"""

_NETSH_NETWORKS = """\
Interface name : Wi-Fi
There are 2 networks currently visible.

SSID 1 : AlphaNet
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP
 BSSID 1                 : aa:bb:cc:dd:ee:01
      Signal             : 80%
      Radio type         : 802.11ac
      Channel            : 36

SSID 2 : BetaNet
    Network type            : Infrastructure
    Authentication          : Open
    Encryption              : None
 BSSID 1                 : aa:bb:cc:dd:ee:02
      Signal             : 50%
      Radio type         : 802.11n
      Channel            : 6
"""

_AIRPORT_SCAN = """\
                            SSID BSSID             RSSI CHANNEL HT CC
                         AlphaNet aa:bb:cc:dd:ee:01  -60  36,80   Y  DE
                          BetaNet aa:bb:cc:dd:ee:02  -82   6      Y  DE
"""


# ── Parser unit tests ─────────────────────────────────────────────────────────

class TestWindowsParser(unittest.TestCase):
    def test_connected(self):
        r = _parse_netsh_interfaces(_NETSH_CONNECTED)
        self.assertEqual(r.ssid,           "TestNetz")
        self.assertEqual(r.bssid,          "11:22:33:44:55:66")
        self.assertEqual(r.signal_percent, 76)
        self.assertAlmostEqual(r.dbm,      -62.0)
        self.assertEqual(r.channel,        36)
        self.assertEqual(r.band,           "5 GHz")
        self.assertEqual(r.std_deviation,  0.0)

    def test_disconnected_raises(self):
        with self.assertRaises(WifiError):
            _parse_netsh_interfaces(_NETSH_DISCONNECTED)

    def test_empty_raises(self):
        with self.assertRaises(WifiError):
            _parse_netsh_interfaces("")


class TestMacOSParser(unittest.TestCase):
    def test_connected(self):
        r = _parse_airport_info(_AIRPORT_CONNECTED)
        self.assertEqual(r.ssid,           "HeimnetzApfel")
        self.assertEqual(r.bssid,          "aa:bb:cc:dd:ee:ff")
        self.assertAlmostEqual(r.dbm,      -57.0)
        self.assertEqual(r.signal_percent, 86)
        self.assertEqual(r.channel,        36)
        self.assertEqual(r.band,           "5 GHz")

    def test_not_connected_raises(self):
        with self.assertRaises(WifiError):
            _parse_airport_info(_AIRPORT_NOT_CONNECTED)


# ── WifiScanner mocked tests ──────────────────────────────────────────────────

class TestWifiScannerWindows(unittest.TestCase):
    def setUp(self):
        self.scanner = WifiScanner()

    @patch("services.wifi_scanner.sys")
    @patch("services.wifi_scanner._run", return_value=_NETSH_CONNECTED)
    def test_scan(self, _mock_run, mock_sys):
        mock_sys.platform = "win32"
        r = self.scanner._scan_windows()
        self.assertIsInstance(r, WifiResult)
        self.assertEqual(r.ssid, "TestNetz")

    @patch("services.wifi_scanner._run", return_value=_NETSH_NETWORKS)
    def test_get_available_networks(self, _mock_run):
        nets = self.scanner._networks_windows()
        self.assertEqual(len(nets), 2)
        self.assertEqual(nets[0]["ssid"],    "AlphaNet")
        self.assertEqual(nets[0]["band"],    "5 GHz")
        self.assertEqual(nets[0]["channel"], 36)
        self.assertEqual(nets[1]["ssid"],    "BetaNet")
        self.assertEqual(nets[1]["band"],    "2.4 GHz")


class TestWifiScannerMacOS(unittest.TestCase):
    def setUp(self):
        self.scanner = WifiScanner()

    @patch("services.wifi_scanner._run", return_value=_AIRPORT_CONNECTED)
    def test_scan(self, _mock_run):
        r = self.scanner._scan_macos()
        self.assertIsInstance(r, WifiResult)
        self.assertEqual(r.ssid,  "HeimnetzApfel")
        self.assertEqual(r.band,  "5 GHz")

    @patch("services.wifi_scanner._run", return_value=_AIRPORT_SCAN)
    def test_get_available_networks(self, _mock_run):
        nets = self.scanner._networks_macos()
        self.assertEqual(len(nets), 2)
        self.assertEqual(nets[0]["ssid"],    "AlphaNet")
        self.assertEqual(nets[0]["band"],    "5 GHz")
        self.assertEqual(nets[0]["channel"], 36)
        self.assertEqual(nets[1]["ssid"],    "BetaNet")
        self.assertEqual(nets[1]["band"],    "2.4 GHz")


class TestScanAveraged(unittest.TestCase):
    def setUp(self):
        self.scanner = WifiScanner()

    def _make_result(self, dbm: float) -> WifiResult:
        return WifiResult(
            ssid="TestNetz", dbm=dbm,
            signal_percent=_dbm_to_pct(dbm),
            channel=36, band="5 GHz", bssid="aa:bb:cc:dd:ee:ff",
        )

    @patch("services.wifi_scanner.time.sleep")
    def test_averages_dbm(self, _mock_sleep):
        values = [-60.0, -62.0, -64.0]
        self.scanner.scan = lambda: self._make_result(values.pop(0))
        r = self.scanner.scan_averaged(count=3, interval=0.0)
        self.assertAlmostEqual(r.dbm,           -62.0)
        self.assertAlmostEqual(r.std_deviation,   1.63, places=1)
        self.assertEqual(r.ssid, "TestNetz")

    @patch("services.wifi_scanner.time.sleep")
    def test_all_failures_raise(self, _mock_sleep):
        self.scanner.scan = lambda: (_ for _ in ()).throw(WifiError("fail"))
        with self.assertRaises(WifiError):
            self.scanner.scan_averaged(count=3)


# ── Live scan (informational, always passes) ──────────────────────────────────

def _live_scan() -> None:
    """Run a real scan and print the result. Skipped if not on Windows/macOS."""
    print("\n" + "=" * 60)
    print("Live scan (aktuelles System)")
    print("=" * 60)

    scanner = WifiScanner()
    try:
        result = scanner.scan()
        print(f"  SSID:           {result.ssid}")
        print(f"  BSSID:          {result.bssid}")
        print(f"  Signal:         {result.signal_percent} %  ({result.dbm:.1f} dBm)")
        print(f"  Kanal:          {result.channel}  ({result.band})")
    except WifiError as exc:
        print(f"  WifiError: {exc}")

    print()
    try:
        print("Verfügbare Netzwerke:")
        for net in scanner.get_available_networks():
            print(f"  {net['ssid']:<30} {net['dbm']:>6.0f} dBm  "
                  f"CH {net['channel']:>3}  {net['band']}")
    except WifiError as exc:
        print(f"  WifiError: {exc}")


# ── Helper used in TestScanAveraged ──────────────────────────────────────────

def _dbm_to_pct(dbm: float) -> int:
    return min(max(int(2.0 * (dbm + 100.0)), 0), 100)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _live_scan()
    print("Running unit tests …\n")
    unittest.main(argv=[__file__], verbosity=2, exit=True)

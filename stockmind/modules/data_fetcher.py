"""
StockMind – Marktdaten-Modul
Ticker-Suche (Name/WKN/Freitext), WKN-Auflösung, OHLCV-Download mit
technischen Indikatoren (ta-Bibliothek) und lokalem 24h-Cache.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    CACHE_DIR,
    CACHE_TTL_HOURS,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
)
from modules.logger import logger

logger.debug(f"Module loaded: {__name__}")

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

_YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (StockMind/0.1; +https://github.com/stockmind)",
    "Accept": "application/json",
    "Accept-Language": "de-DE,de;q=0.9",
}
_CACHE_TTL_S: int = CACHE_TTL_HOURS * 3600

# WKN: genau 6 alphanumerische Zeichen (deutsche Wertpapierkennnummer)
_WKN_RE = re.compile(r'^[A-Za-z0-9]{6}$')

# ISIN: 2 Buchstaben + 10 Zeichen
_ISIN_RE = re.compile(r'^[A-Z]{2}[A-Z0-9]{10}$')

# Lesbarer Typ je Yahoo quoteType
_TYPE_MAP: dict[str, str] = {
    "EQUITY":         "Aktie",
    "ETF":            "ETF",
    "MUTUALFUND":     "Fonds",
    "INDEX":          "Index",
    "FUTURE":         "Future",
    "CURRENCY":       "Währung",
    "CRYPTOCURRENCY": "Krypto",
    "OPTION":         "Option",
}

# Bekannte deutsche Xetra-Suffixe für WKN-Mapping-Fallback
_DE_SUFFIX = ".DE"

# Deutsche Regionalbörsen-Suffixe (niedrigere Priorität als XETRA)
_DE_SFXS = frozenset({"F", "MU", "BE", "HM", "DU", "HA"})

# Binance REST API für Crypto-OHLCV
_BINANCE_URL = "https://api.binance.com/api/v3/klines"
_BINANCE_PERIOD_LIMIT: dict[str, int] = {
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825,
}
_BINANCE_INTERVAL_MAP: dict[str, str] = {
    "1d": "1d", "1h": "1h", "1wk": "1w", "1mo": "1M",
}

# Statische Liste der wichtigsten Kryptowährungen (Fallback wenn Yahoo-Suche nichts liefert)
_CRYPTO_STATIC: list[dict] = [
    {"symbol": "BTC-USD",  "name": "Bitcoin",       "exchange": "Binance/Coinbase", "type": "Krypto", "wkn": ""},
    {"symbol": "ETH-USD",  "name": "Ethereum",      "exchange": "Binance/Coinbase", "type": "Krypto", "wkn": ""},
    {"symbol": "BNB-USD",  "name": "BNB",           "exchange": "Binance",          "type": "Krypto", "wkn": ""},
    {"symbol": "XRP-USD",  "name": "XRP",           "exchange": "Binance/Coinbase", "type": "Krypto", "wkn": ""},
    {"symbol": "SOL-USD",  "name": "Solana",        "exchange": "Binance/Coinbase", "type": "Krypto", "wkn": ""},
    {"symbol": "ADA-USD",  "name": "Cardano",       "exchange": "Binance/Coinbase", "type": "Krypto", "wkn": ""},
    {"symbol": "DOGE-USD", "name": "Dogecoin",      "exchange": "Binance/Coinbase", "type": "Krypto", "wkn": ""},
    {"symbol": "AVAX-USD", "name": "Avalanche",     "exchange": "Binance",          "type": "Krypto", "wkn": ""},
    {"symbol": "DOT-USD",  "name": "Polkadot",      "exchange": "Binance",          "type": "Krypto", "wkn": ""},
    {"symbol": "LINK-USD", "name": "Chainlink",     "exchange": "Binance",          "type": "Krypto", "wkn": ""},
    {"symbol": "LTC-USD",  "name": "Litecoin",      "exchange": "Binance/Coinbase", "type": "Krypto", "wkn": ""},
    {"symbol": "MATIC-USD","name": "Polygon (MATIC)","exchange": "Binance",         "type": "Krypto", "wkn": ""},
    {"symbol": "UNI-USD",  "name": "Uniswap",       "exchange": "Binance",          "type": "Krypto", "wkn": ""},
    {"symbol": "ATOM-USD", "name": "Cosmos",        "exchange": "Binance",          "type": "Krypto", "wkn": ""},
    {"symbol": "XLM-USD",  "name": "Stellar",       "exchange": "Binance/Coinbase", "type": "Krypto", "wkn": ""},
    {"symbol": "TRX-USD",  "name": "TRON",          "exchange": "Binance",          "type": "Krypto", "wkn": ""},
    {"symbol": "TON-USD",  "name": "Toncoin",       "exchange": "Binance",          "type": "Krypto", "wkn": ""},
    {"symbol": "SHIB-USD", "name": "Shiba Inu",     "exchange": "Binance",          "type": "Krypto", "wkn": ""},
]

# Schlüsselwörter die ALLE Kryptowährungen zurückgeben (generische Suchanfragen)
_CRYPTO_KEYWORDS = frozenset({"krypto", "crypto", "cryptocurrency", "coin", "token", "defi"})


# ---------------------------------------------------------------------------
# 1. Ticker-Suche
# ---------------------------------------------------------------------------

def search_stocks(query: str) -> list[dict]:
    """
    Sucht Wertpapiere per Freitext, WKN oder ISIN.

    Strategie:
    - Bei WKN-Muster (6 alphanumerisch): erst `get_wkn_symbol`, dann Yahoo-Suche
    - Sonst: direkte Yahoo Finance Search API
    - Beide Quellen werden dedupliziert und nach Relevanz sortiert

    Returns:
        Liste von Dicts:
        [{"symbol": "SAP.DE", "name": "SAP SE", "exchange": "XETRA",
          "wkn": "716460", "type": "Aktie"}]
    """
    query = query.strip()
    if not query:
        return []

    results: list[dict] = []

    # WKN-Sonderbehandlung: versuche direkte Auflösung
    if _WKN_RE.match(query):
        symbol = get_wkn_symbol(query)
        if symbol:
            results = _yahoo_search(symbol)
            # WKN in alle Treffer eintragen
            for r in results:
                r.setdefault("wkn", query.upper())
            if results:
                return results

    # Standard-Yahoo-Suche (Freitext, ISIN, Ticker)
    results = _yahoo_search(query)

    # Krypto-Suche: statische Liste ergänzen wenn Yahoo-Suche nichts liefert
    # oder Suchanfrage eindeutig auf Krypto hinweist
    crypto_hits = _search_crypto_static(query)
    if crypto_hits:
        seen = {r.get("symbol") for r in results if "error" not in r}
        for c in crypto_hits:
            if c["symbol"] not in seen:
                results.append(c)

    return [r for r in results if "error" not in r] or results


def _yahoo_search(query: str) -> list[dict]:
    """Interne Yahoo-Finance-Such-Anfrage."""
    params = {
        "q": query,
        "lang": "de-DE",
        "region": "DE",
        "quotesCount": 10,
        "newsCount": 0,
        "enableFuzzyQuery": True,
        "enableCb": False,
    }
    try:
        resp = requests.get(
            _YAHOO_SEARCH_URL,
            params=params,
            headers=_YAHOO_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        quotes = resp.json().get("quotes", [])
    except requests.exceptions.Timeout:
        return [{"error": "Timeout bei Yahoo Finance Suche (>10s)"}]
    except requests.exceptions.ConnectionError:
        return [{"error": "Keine Verbindung zu Yahoo Finance möglich"}]
    except Exception as exc:
        return [{"error": str(exc)}]

    out: list[dict] = []
    seen: set[str] = set()
    for q in quotes:
        symbol = q.get("symbol", "")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        out.append({
            "symbol": symbol,
            "name": q.get("longname") or q.get("shortname") or symbol,
            "exchange": q.get("exchange", ""),
            "type": _TYPE_MAP.get(q.get("quoteType", ""), q.get("quoteType", "–")),
            "wkn": "",      # Yahoo liefert keine WKN; Feld für Konsistenz
        })

    # XETRA (.DE) vor deutschen Regionalbörsen (.F, .MU, .BE, …) vor Rest.
    # Stabile Sortierung: Reihenfolge innerhalb jeder Gruppe bleibt erhalten.
    _DE_SFXS = frozenset({"F", "MU", "BE", "HM", "DU", "HA"})

    def _xetra_rank(r: dict) -> int:
        sym = r.get("symbol", "")
        if sym.endswith(".DE"):
            return 0
        sfx = sym.rsplit(".", 1)[-1] if "." in sym else ""
        return 1 if sfx in _DE_SFXS else 2

    out.sort(key=_xetra_rank)
    return out


def _search_crypto_static(query: str) -> list[dict]:
    """Sucht in der statischen Krypto-Liste. Gibt Treffer bei Ticker- oder Namensübereinstimmung zurück."""
    q = query.strip().upper()
    q_lower = query.strip().lower()

    # Generische Krypto-Suche: alle zeigen
    if q_lower in _CRYPTO_KEYWORDS:
        return list(_CRYPTO_STATIC)

    matches = []
    for c in _CRYPTO_STATIC:
        base = c["symbol"].replace("-USD", "")   # z. B. "BTC" aus "BTC-USD"
        if q == base or c["name"].upper().startswith(q) or q in c["name"].upper():
            matches.append(c)
    return matches


# Rückwärtskompatibilität für ui_components.py
def search_ticker(query: str) -> list[dict]:
    """Alias für search_stocks() (Rückwärtskompatibilität)."""
    return search_stocks(query)


def resolve_ticker(query: str) -> Optional[str]:
    """Gibt das erste Ticker-Symbol für einen Suchbegriff zurück, oder None."""
    for r in search_stocks(query):
        if "error" not in r and r.get("symbol"):
            return r["symbol"]
    return None


# ---------------------------------------------------------------------------
# 2. WKN → Yahoo Finance Symbol
# ---------------------------------------------------------------------------

def get_wkn_symbol(wkn: str) -> str:
    """
    Versucht eine WKN in ein Yahoo Finance Ticker-Symbol umzuwandeln.

    Strategie (Fallback-Kette):
    1. Bekannte statische Mappings (häufige deutsche Standardwerte)
    2. Yahoo Finance Search API – sucht WKN als Freitext
    3. Suche mit Xetra-Suffix-Variante "{WKN}.DE"

    Returns:
        Yahoo Finance Symbol (z.B. "SAP.DE") oder "" wenn nicht gefunden.
    """
    wkn = wkn.strip().upper()

    # --- Statisches Mapping für die häufigsten deutschen Standardwerte ---
    _STATIC: dict[str, str] = {
        "716460": "SAP.DE",
        "840400": "DBK.DE",
        "519000": "BMW.DE",
        "710000": "DAI.DE",      # Mercedes (ehem. Daimler)
        "766403": "MBG.DE",      # Mercedes-Benz Group
        "555750": "DTE.DE",      # Deutsche Telekom
        "515100": "BAS.DE",      # BASF
        "575200": "BAY.DE",      # Bayer
        "604843": "ADS.DE",      # Adidas
        "695200": "ALV.DE",      # Allianz
        "521000": "MUV2.DE",     # Munich Re
        "555200": "RWE.DE",
        "ENAG99": "EOAN.DE",     # E.ON
        "703712": "VOW3.DE",     # Volkswagen Vz.
        "760177": "VOW.DE",      # Volkswagen St.
        "677650": "FRE.DE",      # Fresenius SE
        "578560": "FME.DE",      # Fresenius Medical Care
        "543900": "HEN3.DE",     # Henkel Vz.
        "604700": "INF.DE",      # Infineon — eigentlich IFX.DE
        "623100": "IFX.DE",      # Infineon
        "648300": "LIN.DE",      # Linde
        "555480": "SIE.DE",      # Siemens
        "766030": "AIR.DE",      # Airbus
        "A14Y8F": "DHER.DE",     # Delivery Hero
        "A2E4K2": "PUM.DE",      # Puma
    }
    if wkn in _STATIC:
        return _STATIC[wkn]

    # --- Yahoo Finance Suche mit WKN als Query ---
    results = _yahoo_search(wkn)
    for r in results:
        if "error" not in r and r.get("symbol"):
            return r["symbol"]

    return ""


# ---------------------------------------------------------------------------
# 3. OHLCV-Download-Helfer
# ---------------------------------------------------------------------------

def _normalize_raw(raw: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Normalisiert einen rohen yfinance-DataFrame auf OHLCV-Spalten ohne Zeitzone."""
    if raw is None or raw.empty:
        return None
    raw = raw.copy()
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    ohlcv = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in raw.columns]
    if len(ohlcv) < 5:
        return None
    df = raw[list(ohlcv)].dropna(subset=["Close"])
    return df if len(df) >= 2 else None


def _fetch_yf_history(symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    """Primärer yfinance-Download via Ticker.history() – robuster als yf.download()."""
    try:
        raw = yf.Ticker(symbol).history(
            period=period, interval=interval,
            auto_adjust=True,
        )
        if raw is None or raw.empty:
            logger.warning(f"yf.Ticker.history: keine Daten für {symbol} (period={period})")
            return None
        return _normalize_raw(raw)
    except Exception as exc:
        logger.warning(f"yf.Ticker.history fehlgeschlagen ({symbol}): {exc}")
        return None


def _fetch_yf_download(symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    """Fallback-Download via yf.download() mit MultiIndex-Normalisierung."""
    try:
        raw = yf.download(
            symbol, period=period, interval=interval,
            progress=False, auto_adjust=True,
        )
        if raw is None or raw.empty:
            logger.warning(f"yf.download: keine Daten für {symbol} (period={period})")
            return None
        return _normalize_raw(raw)
    except Exception as exc:
        logger.warning(f"yf.download fehlgeschlagen ({symbol}): {exc}")
        return None


def _fetch_binance_ohlcv(symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    """
    OHLCV von Binance REST API für Krypto-Symbole (Format: BTC-USD → BTCUSDT).
    Kein API-Key erforderlich für öffentliche Kurs-Daten.
    """
    if not symbol.endswith("-USD"):
        return None
    base = symbol[:-4]   # "BTC" aus "BTC-USD"
    binance_sym = base + "USDT"
    limit = _BINANCE_PERIOD_LIMIT.get(period, 365)
    b_interval = _BINANCE_INTERVAL_MAP.get(interval, "1d")
    try:
        resp = requests.get(
            _BINANCE_URL,
            params={"symbol": binance_sym, "interval": b_interval, "limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        klines = resp.json()
        if not klines or not isinstance(klines, list):
            return None
        rows = [
            {
                "Date":   pd.Timestamp(k[0], unit="ms"),
                "Open":   float(k[1]),
                "High":   float(k[2]),
                "Low":    float(k[3]),
                "Close":  float(k[4]),
                "Volume": float(k[5]),
            }
            for k in klines
        ]
        df = pd.DataFrame(rows).set_index("Date")
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df if len(df) >= 2 else None
    except Exception as exc:
        logger.debug(f"Binance fetch fehlgeschlagen ({binance_sym}): {exc}")
        return None


# ---------------------------------------------------------------------------
# 4. OHLCV + Technische Indikatoren (mit Cache)
# ---------------------------------------------------------------------------

def fetch_ohlcv(
    symbol: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
) -> pd.DataFrame:
    """
    Lädt OHLCV-Daten und berechnet technische Indikatoren.

    Download-Strategie:
    - Krypto (endet auf -USD): Binance API → yf.Ticker.history() → yf.download()
    - Aktien/ETFs/Indizes:     yf.Ticker.history() → yf.download()
    - Deutsche Regionalbörse (z. B. BMW3.F): automatischer XETRA-Fallback (.DE)

    Berechnet automatisch RSI, MACD, Bollinger Bands, SMA, EMA.
    Ergebnisse werden 24h lokal gecacht (data/cache/).

    Returns:
        DataFrame mit OHLCV + Indikatoren.
        Bei Fehler: leeres DataFrame mit df.attrs["error"] gesetzt – kein Crash.
    """
    symbol = symbol.strip().upper()

    # Cache prüfen
    cached = _load_cache(symbol, period, interval)
    if cached is not None:
        return cached

    # Download: Reihenfolge je Asset-Typ
    raw: Optional[pd.DataFrame] = None
    if symbol.endswith("-USD"):
        # Krypto: Binance zuerst (zuverlässiger für Crypto), dann yfinance
        raw = _fetch_binance_ohlcv(symbol, period, interval)
        if raw is None:
            raw = _fetch_yf_history(symbol, period, interval)
        if raw is None:
            raw = _fetch_yf_download(symbol, period, interval)
    else:
        # Aktien/ETFs/Indizes: yf.Ticker.history() zuerst (robuster gegen Auth-Änderungen),
        # yf.download() als Fallback
        raw = _fetch_yf_history(symbol, period, interval)
        if raw is None:
            raw = _fetch_yf_download(symbol, period, interval)

    if raw is None:
        # Fallback: deutsche Regionalbörse (z. B. BMW3.F) → XETRA (BMW.DE) probieren
        parts = symbol.rsplit(".", 1)
        if len(parts) == 2 and parts[1] in _DE_SFXS:
            xetra = parts[0] + ".DE"
            raw = _fetch_yf_history(xetra, period, interval)
            if raw is None:
                raw = _fetch_yf_download(xetra, period, interval)
            if raw is not None:
                symbol = xetra
            else:
                logger.warning(f"Alle Quellen erfolglos für {symbol} + {xetra}")
                return _empty_df(
                    f"Keine Daten für '{symbol}' (auch '{xetra}' erfolglos). "
                    f"Bitte Ticker prüfen – Xetra-Symbole enden auf '.DE'."
                )
        else:
            logger.warning(f"Alle Quellen erfolglos für {symbol} (period={period})")
            return _empty_df(
                f"Keine Daten für '{symbol}' — alle Quellen erfolglos "
                f"(period={period}, interval={interval}). "
                "Ticker prüfen: Aktien = SYMBOL.DE, Krypto = SYMBOL-USD (z. B. BTC-USD), "
                "US-Aktien = AAPL / MSFT, Indizes = ^GDAXI / ^DJI."
            )

    df = raw.copy()

    # Indikatoren berechnen
    df = _add_indicators(df)

    # Tatsächlich verwendeten Ticker speichern (nach möglichem .DE-Fallback)
    df.attrs["symbol"] = symbol

    # Cachen
    _save_cache(symbol, period, interval, df)

    return df


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Berechnet alle technischen Indikatoren und fügt sie als Spalten hinzu."""
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]

    try:
        from ta.momentum import RSIIndicator
        from ta.trend import MACD, EMAIndicator, SMAIndicator
        from ta.volatility import BollingerBands

        # RSI(14)
        rsi = RSIIndicator(close=close, window=14)
        df["rsi"] = rsi.rsi()

        # MACD(12/26/9)
        macd_obj = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
        df["macd"]        = macd_obj.macd()
        df["macd_signal"] = macd_obj.macd_signal()
        df["macd_diff"]   = macd_obj.macd_diff()

        # Bollinger Bands(20, 2σ)
        bb = BollingerBands(close=close, window=20, window_dev=2)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()
        df["bb_mid"]   = bb.bollinger_mavg()
        df["bb_pband"] = bb.bollinger_pband()   # Position innerhalb der Bänder (0–1)
        df["bb_wband"] = bb.bollinger_wband()   # Bandbreite (Volatilität)

        # SMAs
        for w in (20, 50, 200):
            if len(df) >= w:
                df[f"sma_{w}"] = SMAIndicator(close=close, window=w).sma_indicator()

        # EMAs
        for w in (12, 26):
            df[f"ema_{w}"] = EMAIndicator(close=close, window=w).ema_indicator()

    except ImportError:
        logger.debug("ta-Bibliothek nicht installiert – verwende manuellen Indikator-Fallback")
        df = _add_indicators_manual(df)
    except Exception as _exc:
        logger.warning(f"Indikator-Berechnung fehlgeschlagen, OHLCV ohne Indikatoren: {_exc}")

    return df


def _add_indicators_manual(df: pd.DataFrame) -> pd.DataFrame:
    """Fallback-Indikatorberechnung ohne ta-Bibliothek."""
    import numpy as np

    close = df["Close"]

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"]        = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_diff"]   = df["macd"] - df["macd_signal"]
    df["ema_12"] = ema12
    df["ema_26"] = ema26

    # Bollinger Bands
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["bb_mid"]   = bb_mid
    df["bb_upper"] = bb_mid + 2 * bb_std
    df["bb_lower"] = bb_mid - 2 * bb_std
    band_range = df["bb_upper"] - df["bb_lower"]
    df["bb_pband"] = (close - df["bb_lower"]) / band_range.replace(0, float("nan"))
    df["bb_wband"] = band_range / bb_mid.replace(0, float("nan"))

    # SMAs
    for w in (20, 50, 200):
        if len(df) >= w:
            df[f"sma_{w}"] = close.rolling(w).mean()

    return df


# ---------------------------------------------------------------------------
# 4. Fetch-Info (unverändert für app.py-Kompatibilität)
# ---------------------------------------------------------------------------

def fetch_info(ticker: str) -> dict:
    """
    Gibt Basis-Metadaten eines Tickers zurück (Name, Sektor, Währung, …).
    Gibt bei Fehler ein Dict mit 'error'-Key zurück – kein Crash.
    """
    ticker = ticker.strip().upper()
    try:
        info = yf.Ticker(ticker).info
        return {
            "symbol": ticker,
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", "–"),
            "industry": info.get("industry", "–"),
            "currency": info.get("currency", "USD"),
            "country": info.get("country", "–"),
            "market_cap": info.get("marketCap"),
            "website": info.get("website", ""),
            "description": info.get("longBusinessSummary", ""),
        }
    except Exception as exc:
        logger.warning(f"fetch_info({ticker}): {exc}")
        return {"symbol": ticker, "error": str(exc)}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def is_valid_ticker(ticker: str) -> bool:
    """Prüft ob ein Ticker syntaktisch plausibel ist (1–12 Zeichen: Buchstaben, Ziffern, .)."""
    return bool(re.match(r'^[A-Za-z0-9.^]{1,12}$', ticker.strip()))


def is_wkn(query: str) -> bool:
    """Gibt True zurück wenn der String eine WKN sein könnte (6 alphanumerische Zeichen)."""
    return bool(_WKN_RE.match(query.strip()))


def cache_info(symbol: str, period: str = DEFAULT_PERIOD, interval: str = DEFAULT_INTERVAL) -> dict:
    """
    Gibt Metadaten zum Cache-Eintrag zurück.
    Returns: {"cached": bool, "age_minutes": float | None, "path": str}
    """
    path = _cache_path(symbol, period, interval)
    if not path.exists():
        return {"cached": False, "age_minutes": None, "path": str(path)}
    age = time.time() - path.stat().st_mtime
    return {
        "cached": age < _CACHE_TTL_S,
        "age_minutes": round(age / 60, 1),
        "path": str(path),
    }


def invalidate_cache(symbol: str, period: str = DEFAULT_PERIOD, interval: str = DEFAULT_INTERVAL) -> bool:
    """Löscht den Cache-Eintrag für ein Symbol. Returns True wenn eine Datei gelöscht wurde."""
    path = _cache_path(symbol, period, interval)
    if path.exists():
        path.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Cache-Implementierung (intern)
# ---------------------------------------------------------------------------

def _cache_path(symbol: str, period: str, interval: str) -> Path:
    """Berechnet den Dateipfad für einen Cache-Eintrag."""
    # Absoluter Pfad relativ zur Projektroot (Verzeichnis über modules/)
    root = Path(os.path.dirname(os.path.dirname(__file__)))
    cache_dir = root / CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Dateiname: sicher, eindeutig
    safe_symbol = re.sub(r'[^A-Za-z0-9]', '_', symbol)
    key = f"{safe_symbol}_{period}_{interval}"
    return cache_dir / f"{key}.parquet"


def _load_cache(symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    """Lädt gecachte Daten wenn vorhanden und nicht abgelaufen."""
    path = _cache_path(symbol, period, interval)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > _CACHE_TTL_S:
        return None     # Abgelaufen – nicht löschen, wird beim nächsten Fetch überschrieben
    try:
        return pd.read_parquet(path)
    except Exception as _exc:
        logger.debug(f"Cache-Datei korrupt oder unlesbar ({path.name}): {_exc}")
        return None


def _save_cache(symbol: str, period: str, interval: str, df: pd.DataFrame) -> None:
    """Persistiert einen DataFrame als Cache-Eintrag."""
    path = _cache_path(symbol, period, interval)
    try:
        df.to_parquet(path, compression="snappy")
    except Exception as _exc:
        logger.warning(f"Cache-Schreiben fehlgeschlagen ({path.name}): {_exc}")


def _empty_df(error_msg: str) -> pd.DataFrame:
    """Gibt ein leeres DataFrame mit gesetztem error-Attribut zurück."""
    df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df.attrs["error"] = error_msg
    return df

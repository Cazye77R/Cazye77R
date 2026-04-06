"""
StockMind – Marktdaten-Modul
Lädt OHLCV-Daten via yfinance; unterstützt Suche per Ticker, WKN oder Name.
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DEFAULT_PERIOD, DEFAULT_INTERVAL


# ---------------------------------------------------------------------------
# Ticker-Suche (OpenSearch / Yahoo Finance Suggest)
# ---------------------------------------------------------------------------

def search_ticker(query: str) -> list[dict]:
    """
    Sucht nach Ticker-Symbolen anhand eines Freitexts (Name, WKN, ISIN, Kürzel).
    Nutzt die Yahoo Finance Query-API (keine Authentifizierung nötig).

    Returns:
        Liste von Dicts mit keys: symbol, name, exchange, type
    """
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {
        "q": query,
        "lang": "de-DE",
        "region": "DE",
        "quotesCount": 10,
        "newsCount": 0,
        "enableFuzzyQuery": True,
        "enableCb": False,
    }
    headers = {"User-Agent": "StockMind/0.1"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        quotes = resp.json().get("quotes", [])
        return [
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("longname") or q.get("shortname", ""),
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", ""),
            }
            for q in quotes
            if q.get("symbol")
        ]
    except Exception as exc:
        return [{"error": str(exc)}]


def resolve_ticker(query: str) -> Optional[str]:
    """
    Gibt das erste passende Ticker-Symbol für einen Suchbegriff zurück.
    Gibt None zurück wenn nichts gefunden wird.
    """
    results = search_ticker(query)
    for r in results:
        if "error" not in r and r.get("symbol"):
            return r["symbol"]
    return None


# ---------------------------------------------------------------------------
# Marktdaten laden
# ---------------------------------------------------------------------------

def fetch_ohlcv(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
) -> pd.DataFrame:
    """
    Lädt OHLCV-Daten für ein Ticker-Symbol.

    Returns:
        DataFrame mit Spalten: Open, High, Low, Close, Volume
        Index: DatetimeIndex (UTC normalisiert)
    Raises:
        ValueError: wenn keine Daten verfügbar sind
    """
    ticker = ticker.strip().upper()
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"Keine Daten für Ticker '{ticker}' (period={period}, interval={interval})")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    # Flatten MultiIndex columns (yfinance ≥0.2 gibt (Field, Ticker) zurück)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close", "Volume"]].copy()


def fetch_info(ticker: str) -> dict:
    """
    Gibt Basis-Metadaten eines Tickers zurück (Name, Sektor, Währung, …).
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
        return {"symbol": ticker, "error": str(exc)}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def is_valid_ticker(ticker: str) -> bool:
    """Prüft ob ein Ticker syntaktisch plausibel ist (1–10 alphanumerische Zeichen + .)."""
    return bool(re.match(r'^[A-Za-z0-9.]{1,12}$', ticker.strip()))

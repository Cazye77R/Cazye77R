"""
StockMind – Autopilot: handelt die automatisch gewählte Strategie im Paper-Trading.

Läuft ohne Streamlit. Pro Durchlauf und Ticker:
  1. Strategie wählen bzw. alle ``reselect_days`` neu wählen (Walk-Forward, 10 Jahre)
  2. Bei Urteil "schlechter"/"zu wenig Daten" nicht handeln (außer erzwungen)
  3. Sonst ``PaperTrader.strategy_trade`` ausführen (idempotent)

Handelt ausschließlich ein separates Paper-Portfolio ("autopilot"). Ein
Durchlauf ist idempotent und darf beliebig oft wiederholt werden.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from config import DATA_DIR

from modules.backtester import PaperTrader
from modules.data_fetcher import fetch_ohlcv
from modules.logger import logger
from modules.strategy_selector import select_strategy

STOP_FILE = "AUTOPILOT_STOP"
TRADEABLE_VERDICTS = {"besser", "unklar"}


def _root() -> Path:
    return Path(os.path.dirname(os.path.dirname(__file__))) / DATA_DIR


def state_path() -> Path:
    return _root() / "autopilot_state.json"


def stop_path() -> Path:
    return _root() / STOP_FILE


def load_state(path: Path | None = None) -> dict:
    p = path or state_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict, path: Path | None = None) -> None:
    p = path or state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _needs_reselect(entry: dict | None, reselect_days: int, now: datetime) -> bool:
    if not entry or "selected_at" not in entry:
        return True
    try:
        age = now - datetime.fromisoformat(entry["selected_at"])
    except ValueError:
        return True
    return age >= timedelta(days=reselect_days)


def run_once(
    tickers: list[str],
    trader: PaperTrader | None = None,
    reselect_days: int = 7,
    invest_pct: float = 0.2,
    force_trade: bool = False,
    state_file: Path | None = None,
    now: datetime | None = None,
    log: Callable[[str], None] = logger.info,
) -> list[dict]:
    """Ein Durchlauf über alle Ticker. Fehler eines Tickers stoppen die anderen nicht."""
    trader = trader or PaperTrader(name="autopilot")
    now = now or datetime.now()
    state = load_state(state_file)
    results: list[dict] = []

    for ticker in tickers:
        try:
            entry = state.get(ticker)
            if _needs_reselect(entry, reselect_days, now):
                df = fetch_ohlcv(ticker, period="10y")
                if df.empty:
                    raise RuntimeError(df.attrs.get("error", "Keine Daten"))
                res = select_strategy(df)
                if not res.current:
                    raise RuntimeError("Keine Strategie wählbar")
                entry = {
                    "key": res.current["key"],
                    "params": res.current["params"],
                    "label": res.current["strategy"],
                    "verdict": res.verdict,
                    "excess_tstat": res.metrics["excess_tstat"],
                    "selected_at": now.isoformat(timespec="seconds"),
                }
                state[ticker] = entry
                save_state(state, state_file)
                log(
                    f"[{ticker}] Neue Strategie: {entry['label']} "
                    f"(Urteil: {entry['verdict']}, t={entry['excess_tstat']:+.2f})"
                )

            assert entry is not None
            if entry["verdict"] not in TRADEABLE_VERDICTS and not force_trade:
                msg = f"nicht gehandelt – Urteil '{entry['verdict']}'"
                log(f"[{ticker}] {msg}")
                results.append({"ticker": ticker, "decision": "SKIP", "reason": msg})
                continue

            out = trader.strategy_trade(
                ticker, entry["key"], entry["params"], invest_pct=invest_pct, label=entry["label"]
            )
            log(f"[{ticker}] {entry['label']} → {out.get('decision')}")
            results.append({"ticker": ticker, **out})
        except Exception as exc:  # ein defekter Ticker darf den Lauf nicht beenden
            logger.warning(f"[{ticker}] Autopilot-Fehler: {exc}")
            results.append({"ticker": ticker, "decision": "ERROR", "reason": str(exc)})
    return results


def run_forever(
    tickers: list[str],
    interval_min: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
    max_runs: int | None = None,
    **kwargs,
) -> int:
    """Wiederholt ``run_once`` bis Strg+C oder die Stop-Datei existiert. Gibt die Zahl der Läufe zurück."""
    runs = 0
    while max_runs is None or runs < max_runs:
        if stop_path().exists():
            logger.info("Stop-Datei gefunden – Autopilot beendet.")
            break
        run_once(tickers, **kwargs)
        runs += 1
        if max_runs is not None and runs >= max_runs:
            break
        # In kleinen Schritten schlafen, damit die Stop-Datei schnell wirkt
        waited = 0.0
        while waited < interval_min * 60 and not stop_path().exists():
            sleep(min(30.0, interval_min * 60 - waited))
            waited += 30.0
    return runs

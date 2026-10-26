"""Autopilot-Start: handelt die automatisch gewählte Strategie dauerhaft im Paper-Trading.

Beispiele:
    python autopilot.py AAPL MSFT BMW.DE            # läuft bis Strg+C
    python autopilot.py AAPL --once                 # ein Durchlauf, z. B. per Cron
    python autopilot.py AAPL --interval 30 --reselect-days 14

Beenden: Strg+C oder Datei data/AUTOPILOT_STOP anlegen.
"""

from __future__ import annotations

import argparse
import sys

from modules.autopilot import run_forever, run_once, stop_path
from modules.backtester import PaperTrader


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("tickers", nargs="+", help="Ticker, z. B. AAPL BMW.DE BTC-USD")
    ap.add_argument("--once", action="store_true", help="Nur ein Durchlauf, dann beenden")
    ap.add_argument("--interval", type=float, default=60.0, help="Minuten zwischen Läufen")
    ap.add_argument("--reselect-days", type=int, default=7, help="Strategie alle N Tage neu wählen")
    ap.add_argument("--invest-pct", type=float, default=0.2, help="Cash-Anteil je Kauf (0.05–0.5)")
    ap.add_argument(
        "--budget", type=float, default=None, help="Startkapital des Autopilot-Portfolios"
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Auch bei Urteil 'schlechter' / 'zu wenig Daten' handeln",
    )
    args = ap.parse_args(argv)
    if not 0.05 <= args.invest_pct <= 0.5:
        ap.error("--invest-pct muss zwischen 0.05 und 0.5 liegen")
    if args.interval <= 0 or args.reselect_days < 1:
        ap.error("--interval muss > 0 und --reselect-days >= 1 sein")

    stop_path().unlink(missing_ok=True)
    trader = PaperTrader(name="autopilot", **({"start_budget": args.budget} if args.budget else {}))
    print(f"Autopilot für {', '.join(args.tickers)} – Paper-Trading, Portfolio 'autopilot'.")
    print(f"Beenden: Strg+C oder Datei {stop_path()} anlegen.")
    common = dict(
        trader=trader,
        reselect_days=args.reselect_days,
        invest_pct=args.invest_pct,
        force_trade=args.force,
        log=print,
    )
    try:
        if args.once:
            run_once(args.tickers, **common)
        else:
            run_forever(args.tickers, interval_min=args.interval, **common)
    except KeyboardInterrupt:
        print("\nAutopilot beendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

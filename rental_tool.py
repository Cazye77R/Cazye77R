"""
Lokal ausführbares Tool zur Auswertung von Vermietungsobjekten.
Berechnet zentrale Kennzahlen und erzeugt Diagramme aus JSON-Konfigurationen.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List


@dataclass
class RentalScenario:
    name: str
    purchase_price: float
    closing_costs: float
    down_payment: float
    interest_rate: float
    loan_years: int
    monthly_rent: float
    vacancy_rate: float
    monthly_operating_expenses: float
    property_management_rate: float
    maintenance_reserve_rate: float
    annual_rent_growth: float
    annual_expense_growth: float
    projection_years: int = 10

    @property
    def loan_amount(self) -> float:
        return self.purchase_price - self.down_payment

    @property
    def monthly_interest_rate(self) -> float:
        return self.interest_rate / 12

    @property
    def total_investment(self) -> float:
        return self.down_payment + self.closing_costs


@dataclass
class RentalMetrics:
    monthly_mortgage: float
    monthly_effective_rent: float
    monthly_property_management: float
    monthly_maintenance: float
    monthly_noi: float
    annual_noi: float
    cap_rate: float
    cash_flow_monthly: float
    cash_flow_annual: float
    cash_on_cash: float
    dscr: float
    grm: float
    break_even_occupancy: float


class ScenarioValidationError(ValueError):
    """Fehlermeldung mit klaren Hinweisen auf ungültige Eingaben."""


def amortized_payment(principal: float, monthly_interest: float, months: int) -> float:
    if monthly_interest == 0:
        return principal / months
    numerator = principal * monthly_interest * (1 + monthly_interest) ** months
    denominator = (1 + monthly_interest) ** months - 1
    return numerator / denominator


def calculate_metrics(scenario: RentalScenario) -> RentalMetrics:
    monthly_mortgage = amortized_payment(
        scenario.loan_amount, scenario.monthly_interest_rate, scenario.loan_years * 12
    )
    monthly_effective_rent = scenario.monthly_rent * (1 - scenario.vacancy_rate)
    monthly_property_management = scenario.monthly_rent * scenario.property_management_rate
    monthly_maintenance = scenario.monthly_rent * scenario.maintenance_reserve_rate
    monthly_noi = (
        monthly_effective_rent
        - scenario.monthly_operating_expenses
        - monthly_property_management
        - monthly_maintenance
    )
    annual_noi = monthly_noi * 12
    cap_rate = annual_noi / scenario.purchase_price
    cash_flow_monthly = monthly_noi - monthly_mortgage
    cash_flow_annual = cash_flow_monthly * 12
    cash_on_cash = cash_flow_annual / scenario.total_investment if scenario.total_investment else 0
    dscr = annual_noi / (monthly_mortgage * 12) if monthly_mortgage else 0
    grm = scenario.purchase_price / (scenario.monthly_rent * 12)
    break_even_occupancy = (
        (scenario.monthly_operating_expenses + monthly_property_management + monthly_maintenance + monthly_mortgage)
        / scenario.monthly_rent
    )

    return RentalMetrics(
        monthly_mortgage=monthly_mortgage,
        monthly_effective_rent=monthly_effective_rent,
        monthly_property_management=monthly_property_management,
        monthly_maintenance=monthly_maintenance,
        monthly_noi=monthly_noi,
        annual_noi=annual_noi,
        cap_rate=cap_rate,
        cash_flow_monthly=cash_flow_monthly,
        cash_flow_annual=cash_flow_annual,
        cash_on_cash=cash_on_cash,
        dscr=dscr,
        grm=grm,
        break_even_occupancy=break_even_occupancy,
    )


def project_cash_flow(scenario: RentalScenario) -> Dict[str, List[float]]:
    metrics = calculate_metrics(scenario)
    balances = []
    rents = []
    noi_list = []
    mortgage_payments = []
    cash_flow = []

    monthly_payment = metrics.monthly_mortgage
    outstanding = scenario.loan_amount
    months = scenario.loan_years * 12
    monthly_growth_rent = (1 + scenario.annual_rent_growth) ** (1 / 12) - 1
    monthly_growth_expenses = (1 + scenario.annual_expense_growth) ** (1 / 12) - 1
    monthly_rent = scenario.monthly_rent
    monthly_expenses = scenario.monthly_operating_expenses

    for month in range(1, scenario.projection_years * 12 + 1):
        interest_payment = outstanding * scenario.monthly_interest_rate
        principal_payment = monthly_payment - interest_payment
        outstanding = max(outstanding - principal_payment, 0)

        monthly_rent *= 1 + monthly_growth_rent
        monthly_expenses *= 1 + monthly_growth_expenses

        effective_rent = monthly_rent * (1 - scenario.vacancy_rate)
        management_fee = monthly_rent * scenario.property_management_rate
        maintenance_reserve = monthly_rent * scenario.maintenance_reserve_rate
        noi = effective_rent - monthly_expenses - management_fee - maintenance_reserve
        monthly_cash_flow = noi - monthly_payment

        rents.append(effective_rent)
        noi_list.append(noi)
        mortgage_payments.append(monthly_payment)
        cash_flow.append(monthly_cash_flow)
        balances.append(outstanding)

        if outstanding <= 0 and month >= months:
            monthly_payment = 0

    return {
        "effective_rent": rents,
        "noi": noi_list,
        "mortgage": mortgage_payments,
        "cash_flow": cash_flow,
        "outstanding_balance": balances,
    }


def plot_projection(scenario: RentalScenario, output: Path) -> None:
    import matplotlib.pyplot as plt

    projection = project_cash_flow(scenario)
    months = list(range(1, len(projection["cash_flow"]) + 1))

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    axes[0].plot(months, projection["cash_flow"], label="Monatlicher Cashflow")
    axes[0].plot(months, projection["noi"], label="NOI", linestyle="--")
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_ylabel("EUR")
    axes[0].set_title(f"Cashflow-Projektion: {scenario.name}")
    axes[0].legend()

    axes[1].plot(months, projection["outstanding_balance"], color="tab:orange")
    axes[1].set_ylabel("Restschuld (EUR)")
    axes[1].set_xlabel("Monate")
    axes[1].set_title("Darlehensverlauf")

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    print(f"Diagramm gespeichert unter {output}")


def load_scenarios(path: Path) -> List[RentalScenario]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise ScenarioValidationError(f"Konfigurationsdatei nicht gefunden: {path}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ScenarioValidationError(f"Ungültiges JSON in {path}: {exc}") from exc

    scenarios: List[RentalScenario] = []
    entries = data.get("scenarios")
    if not isinstance(entries, list):
        raise ScenarioValidationError("Die Datei muss ein 'scenarios'-Array enthalten.")

    for idx, entry in enumerate(entries):
        _validate_scenario_dict(entry, idx)
        scenarios.append(RentalScenario(**entry))
    return scenarios


def _validate_scenario_dict(entry: Dict[str, object], index: int) -> None:
    required_fields = {
        "name",
        "purchase_price",
        "closing_costs",
        "down_payment",
        "interest_rate",
        "loan_years",
        "monthly_rent",
        "vacancy_rate",
        "monthly_operating_expenses",
        "property_management_rate",
        "maintenance_reserve_rate",
        "annual_rent_growth",
        "annual_expense_growth",
    }

    if not isinstance(entry, dict):
        raise ScenarioValidationError(f"Szenario #{index + 1} muss ein Objekt sein.")

    missing = required_fields - set(entry)
    if missing:
        raise ScenarioValidationError(
            f"Szenario '{entry.get('name', index + 1)}' fehlt: {', '.join(sorted(missing))}"
        )

    numeric_fields = required_fields - {"name"}
    for field in numeric_fields:
        value = entry[field]
        if not isinstance(value, (int, float)):
            raise ScenarioValidationError(
                f"Feld '{field}' in Szenario '{entry.get('name', index + 1)}' muss numerisch sein."
            )
        if field.endswith("rate") and value < 0:
            raise ScenarioValidationError(
                f"Feld '{field}' in Szenario '{entry.get('name', index + 1)}' darf nicht negativ sein."
            )

    if entry.get("projection_years", 1) <= 0:
        raise ScenarioValidationError(
            f"Feld 'projection_years' in Szenario '{entry.get('name', index + 1)}' muss größer 0 sein."
        )


def print_metrics(name: str, metrics: RentalMetrics) -> None:
    print(f"\nKennzahlen: {name}")
    print("- Monatliche Kreditrate:        {:.2f} €".format(metrics.monthly_mortgage))
    print("- Effektive Miete nach Leerstand:{:.2f} €".format(metrics.monthly_effective_rent))
    print("- NOI pro Monat:                {:.2f} €".format(metrics.monthly_noi))
    print("- NOI pro Jahr:                 {:.2f} €".format(metrics.annual_noi))
    print("- Cap Rate:                     {:.2%}".format(metrics.cap_rate))
    print("- Cashflow pro Monat:           {:.2f} €".format(metrics.cash_flow_monthly))
    print("- Cashflow pro Jahr:            {:.2f} €".format(metrics.cash_flow_annual))
    print("- Cash-on-Cash:                 {:.2%}".format(metrics.cash_on_cash))
    print("- DSCR:                         {:.2f}".format(metrics.dscr))
    print("- GRM:                          {:.2f}".format(metrics.grm))
    print("- Break-even-Auslastung:        {:.2%}".format(metrics.break_even_occupancy))


def build_ui_payload(scenarios: List[RentalScenario]) -> Dict[str, List[Dict[str, object]]]:
    payload = []
    for scenario in scenarios:
        metrics = calculate_metrics(scenario)
        projection = project_cash_flow(scenario)
        payload.append(
            {
                "scenario": asdict(scenario),
                "metrics": asdict(metrics),
                "projection": projection,
            }
        )
    return {"scenarios": payload}


def render_html() -> str:
    return """
<!doctype html>
<html lang=\"de\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Vermietungsanalyse</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #0f172a;
        --panel: #1e293b;
        --border: #334155;
        --text: #e2e8f0;
        --muted: #94a3b8;
        --accent: #38bdf8;
        --accent-2: #a855f7;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        padding: 0;
        font-family: \"Inter\", system-ui, -apple-system, sans-serif;
        background: radial-gradient(circle at 20% 20%, rgba(56,189,248,0.08), transparent 35%),
                    radial-gradient(circle at 80% 10%, rgba(168,85,247,0.08), transparent 30%),
                    var(--bg);
        color: var(--text);
        min-height: 100vh;
      }
      header {
        padding: 24px;
        border-bottom: 1px solid var(--border);
        backdrop-filter: blur(10px);
        position: sticky;
        top: 0;
      }
      h1 { margin: 0 0 6px 0; font-weight: 700; }
      p { margin: 0; color: var(--muted); }
      .layout { display: grid; grid-template-columns: 320px 1fr; gap: 16px; padding: 16px; }
      .card {
        background: linear-gradient(145deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 16px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.35);
      }
      label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
      select, button, input[type=file] {
        width: 100%;
        border-radius: 10px;
        border: 1px solid var(--border);
        background: #0b1222;
        color: var(--text);
        padding: 10px 12px;
        margin-bottom: 10px;
      }
      button {
        cursor: pointer;
        border: none;
        background: linear-gradient(90deg, var(--accent), var(--accent-2));
        color: #0b1222;
        font-weight: 600;
        box-shadow: 0 10px 30px rgba(56,189,248,0.3);
      }
      button.secondary { background: #0b1222; color: var(--text); border: 1px solid var(--border); box-shadow: none; }
      .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
      .metric { padding: 12px; border-radius: 12px; border: 1px solid var(--border); background: #111828; }
      .metric .label { color: var(--muted); font-size: 12px; }
      .metric .value { font-size: 18px; font-weight: 700; margin-top: 4px; }
      canvas { width: 100%; height: 260px; border-radius: 12px; background: #0b1222; border: 1px solid var(--border); }
      .actions { display: flex; gap: 8px; }
      .actions button { flex: 1; }
      footer { padding: 16px; color: var(--muted); text-align: center; }
      @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <header>
      <h1>Vermietungsanalyse</h1>
      <p>Moderne Dark-UI mit Diagrammen, Import und Export von Szenarien.</p>
    </header>
    <div class=\"layout\">
      <section class=\"card\">
        <label for=\"scenarioSelect\">Szenario auswählen</label>
        <select id=\"scenarioSelect\"></select>
        <div class=\"actions\">
          <button id=\"exportBtn\">Daten exportieren</button>
          <button class=\"secondary\" id=\"refreshBtn\">Aktualisieren</button>
        </div>
        <label for=\"importFile\" style=\"margin-top:8px\">JSON importieren</label>
        <input type=\"file\" id=\"importFile\" accept=\"application/json\" />
      </section>
      <section class=\"card\">
        <div class=\"metrics\" id=\"metrics\"></div>
      </section>
    </div>
    <div class=\"layout\">
      <section class=\"card\">
        <h3>Monatlicher Cashflow & NOI</h3>
        <canvas id=\"cashCanvas\" width=\"800\" height=\"260\"></canvas>
      </section>
      <section class=\"card\">
        <h3>Darlehensverlauf</h3>
        <canvas id=\"balanceCanvas\" width=\"800\" height=\"260\"></canvas>
      </section>
    </div>
    <footer>Gespeicherte Datei: <span id=\"dataPath\"></span></footer>
    <script>
      const fmtCurrency = (v) => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(v);
      const fmtPercent = (v) => `${(v * 100).toFixed(2)} %`;

      let scenarios = [];
      let currentIndex = 0;
      let dataPath = '';

      async function fetchScenarios() {
        const res = await fetch('/api/scenarios');
        const data = await res.json();
        scenarios = data.scenarios;
        dataPath = data.data_path;
        document.getElementById('dataPath').textContent = dataPath;
        renderSelect();
        renderScenario();
      }

      function renderSelect() {
        const select = document.getElementById('scenarioSelect');
        select.innerHTML = '';
        scenarios.forEach((item, idx) => {
          const opt = document.createElement('option');
          opt.value = idx;
          opt.textContent = item.scenario.name;
          select.appendChild(opt);
        });
        select.value = currentIndex;
      }

      function renderScenario() {
        if (!scenarios.length) return;
        const entry = scenarios[currentIndex];
        const metricsEl = document.getElementById('metrics');
        metricsEl.innerHTML = '';
        const metrics = entry.metrics;
        const items = [
          ['Monatliche Kreditrate', fmtCurrency(metrics.monthly_mortgage)],
          ['Effektive Miete', fmtCurrency(metrics.monthly_effective_rent)],
          ['NOI / Monat', fmtCurrency(metrics.monthly_noi)],
          ['NOI / Jahr', fmtCurrency(metrics.annual_noi)],
          ['Cap Rate', fmtPercent(metrics.cap_rate)],
          ['Cashflow / Monat', fmtCurrency(metrics.cash_flow_monthly)],
          ['Cash-on-Cash', fmtPercent(metrics.cash_on_cash)],
          ['DSCR', metrics.dscr.toFixed(2)],
          ['GRM', metrics.grm.toFixed(2)],
          ['Break-even-Auslastung', fmtPercent(metrics.break_even_occupancy)],
        ];
        items.forEach(([label, value]) => {
          const m = document.createElement('div');
          m.className = 'metric';
          m.innerHTML = `<div class=\"label\">${label}</div><div class=\"value\">${value}</div>`;
          metricsEl.appendChild(m);
        });
        drawLineChart('cashCanvas', entry.projection.cash_flow, entry.projection.noi, ['Cashflow', 'NOI']);
        drawLineChart('balanceCanvas', entry.projection.outstanding_balance, null, ['Restschuld']);
      }

      function drawLineChart(canvasId, seriesA, seriesB, labels) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = '#0b1222';
        ctx.fillRect(0, 0, w, h);
        const padding = 40;
        const allValues = [...seriesA, ...(seriesB || [])];
        const minVal = Math.min(...allValues);
        const maxVal = Math.max(...allValues);
        const range = maxVal - minVal || 1;
        const scaleX = (w - padding * 2) / (seriesA.length - 1 || 1);
        const scaleY = (h - padding * 2) / range;
        const toY = (v) => h - padding - (v - minVal) * scaleY;
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding, padding);
        ctx.lineTo(padding, h - padding);
        ctx.lineTo(w - padding, h - padding);
        ctx.stroke();
        plotLine(ctx, seriesA, '#38bdf8', padding, toY, scaleX);
        if (seriesB) plotLine(ctx, seriesB, '#a855f7', padding, toY, scaleX);
        ctx.fillStyle = '#e2e8f0';
        ctx.font = '12px Inter, sans-serif';
        ctx.fillText(labels[0], padding + 8, padding + 14);
        if (labels[1]) ctx.fillText(labels[1], padding + 8, padding + 30);
      }

      function plotLine(ctx, series, color, padding, toY, scaleX) {
        ctx.beginPath();
        ctx.lineWidth = 2;
        ctx.strokeStyle = color;
        series.forEach((v, i) => {
          const x = padding + i * scaleX;
          const y = toY(v);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }

      document.getElementById('scenarioSelect').addEventListener('change', (e) => {
        currentIndex = Number(e.target.value);
        renderScenario();
      });

      document.getElementById('refreshBtn').addEventListener('click', fetchScenarios);

      document.getElementById('exportBtn').addEventListener('click', async () => {
        const res = await fetch('/api/export');
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'rental_export.json';
        a.click();
        URL.revokeObjectURL(url);
      });

      document.getElementById('importFile').addEventListener('change', async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const text = await file.text();
        try {
          JSON.parse(text);
        } catch (err) {
          alert('Ungültige JSON-Datei');
          return;
        }
        await fetch('/api/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: text });
        await fetchScenarios();
      });

      fetchScenarios();
    </script>
  </body>
</html>
"""


class RentalUIHandler(BaseHTTPRequestHandler):
    scenarios: List[RentalScenario] = []
    data_path: Path = Path("saved_scenarios.json")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - API-Signatur
        print("[UI]" + format % args)

    def _send_json(self, payload: Dict[str, object], status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/":
            html = render_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        if self.path.startswith("/api/scenarios"):
            payload = build_ui_payload(type(self).scenarios)
            payload["data_path"] = str(type(self).data_path)
            self._send_json(payload)
            return

        if self.path.startswith("/api/export"):
            export_data = {"scenarios": [asdict(s) for s in type(self).scenarios]}
            self._send_json(export_data)
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path.startswith("/api/import"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
                scenarios_data = data.get("scenarios")
                if not isinstance(scenarios_data, list):
                    raise ValueError("JSON muss ein 'scenarios'-Array enthalten")
                scenarios = [RentalScenario(**entry) for entry in scenarios_data]
                type(self).scenarios = scenarios
                type(self).data_path.parent.mkdir(parents=True, exist_ok=True)
                type(self).data_path.write_text(json.dumps({"scenarios": scenarios_data}, indent=2), encoding="utf-8")
                self._send_json({"ok": True, "count": len(scenarios), "data_path": str(type(self).data_path)})
            except Exception as exc:  # pragma: no cover - defensive
                self._send_json({"ok": False, "error": str(exc)}, status=400)
            return

        self.send_error(404, "Not Found")


def run_server(initial_scenarios: List[RentalScenario], host: str, port: int, data_path: Path) -> None:
    if data_path.exists():
        try:
            loaded = load_scenarios(data_path)
            print(f"Gespeicherte Daten geladen aus {data_path}")
            initial_scenarios = loaded
        except ScenarioValidationError as exc:  # pragma: no cover - defensive
            print(f"Konnte {data_path} nicht laden ({exc}), verwende Konfigurationsdatei.")

    RentalUIHandler.scenarios = initial_scenarios
    RentalUIHandler.data_path = data_path

    server = ThreadingHTTPServer((host, port), RentalUIHandler)
    print(f"Weboberfläche läuft unter http://{host}:{port} (Drücken Sie STRG+C zum Stoppen)")
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lokales Auswertungstool für Vermietungsszenarien auf Basis einer JSON-Datei.",
    )
    parser.add_argument(
        "config",
        type=Path,
        help="Pfad zu einer JSON-Datei mit einer 'scenarios'-Liste.",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        metavar="DATEI",
        help="Optionaler Pfad, um ein Cashflow-Diagramm für das erste Szenario zu speichern.",
    )
    parser.add_argument(
        "--export",
        type=Path,
        metavar="DATEI",
        help="Exportiert berechnete Kennzahlen als JSON.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Startet eine lokale Weboberfläche mit dunklem Theme (Standard: http://localhost:8000).",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host für die Weboberfläche (Standard: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port für die Weboberfläche (Standard: 8000).",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=Path("saved_scenarios.json"),
        help="Pfad, unter dem Import/Export in der UI gespeichert werden (Standard: saved_scenarios.json).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        scenarios = load_scenarios(args.config)
    except ScenarioValidationError as exc:
        sys.exit(str(exc))

    if args.serve:
        try:
            run_server(scenarios, args.host, args.port, args.data_path)
        except KeyboardInterrupt:
            print("Server beendet.")
        sys.exit(0)

    all_metrics = []
    for scenario in scenarios:
        metrics = calculate_metrics(scenario)
        print_metrics(scenario.name, metrics)
        all_metrics.append({"scenario": scenario.name, **asdict(metrics)})

    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(json.dumps({"metrics": all_metrics}, indent=2), encoding="utf-8")
        print(f"Kennzahlen exportiert nach {args.export}")

    if args.plot and scenarios:
        plot_projection(scenarios[0], args.plot)


if __name__ == "__main__":
    main()

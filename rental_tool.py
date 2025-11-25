"""
Lokal ausführbares Tool zur Auswertung von Vermietungsobjekten.
Berechnet zentrale Kennzahlen und erzeugt Diagramme aus JSON-Konfigurationen.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
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
    data = json.loads(path.read_text(encoding="utf-8"))
    scenarios = []
    for entry in data.get("scenarios", []):
        scenarios.append(RentalScenario(**entry))
    return scenarios


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenarios = load_scenarios(args.config)

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

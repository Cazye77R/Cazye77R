# Lokales Vermietungs-Analysetool

Dieses Repository enthält ein lokal ausführbares Python-Tool, mit dem sich Vermietungsobjekte anhand zentraler Kennzahlen bewerten und visualisieren lassen. Die Berechnungen basieren auf JSON-Konfigurationen, in denen beliebig viele Szenarien gepflegt werden können.

## Funktionsumfang
- Berechnung gängiger Kennzahlen (NOI, Cap Rate, Cash-on-Cash, DSCR, GRM, Break-even-Auslastung u. a.)
- Projektion von Cashflows mit Mieten- und Kostenwachstum
- Diagrammexport (Cashflow und Restschuldverlauf) via Matplotlib
- Export der Kennzahlen als JSON für weitere Auswertungen

## Installation
Stelle sicher, dass Python 3.10+ installiert ist. Installiere die benötigten Pakete in einer virtuellen Umgebung:

```bash
python -m venv .venv
source .venv/bin/activate
pip install matplotlib
```

## Nutzung
1. Passe die Beispielkonfiguration `example_property.json` an oder erstelle eigene JSON-Dateien. Die Datei enthält eine `scenarios`-Liste, in der jedes Szenario Felder für Kaufpreis, Finanzierung, Miete und Kosten definiert.
2. Führe das Tool aus und übergib die Konfigurationsdatei:

```bash
python rental_tool.py example_property.json
```

3. Optional: Speichere Kennzahlen als JSON und erstelle ein Diagramm (erstes Szenario der Datei):

```bash
python rental_tool.py example_property.json --export reports/metrics.json --plot reports/cashflow.png
```

## Beispiel
In `example_property.json` sind zwei Szenarien hinterlegt. Der Aufruf oben gibt die Kennzahlen beider Szenarien in der Konsole aus und erzeugt auf Wunsch eine Cashflow-Grafik sowie einen JSON-Report.

## Erweiterungsideen
- Weitere Diagrammtypen wie Sensitivitätsanalysen
- CSV-Import/-Export für Monatswerte
- Ergänzung um steuerliche Effekte und Abschreibungen


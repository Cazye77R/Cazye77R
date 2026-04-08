# 🧠 StockMind

**Lokales KI-gestütztes Aktienanalyse-Tool** – läuft vollständig auf deinem Rechner.
Keine Cloud, keine API-Kosten, keine Datenweitergabe.

> ⚠️ **Haftungsausschluss:** StockMind ist ein experimentelles Bildungs- und
> Unterhaltungsprojekt. Alle Analysen stellen **keine Anlageberatung** dar.

---

## 📸 Screenshots

| Dashboard | Paper Trading | Modell-Manager |
|---|---|---|
| *(Screenshot folgt)* | *(Screenshot folgt)* | *(Screenshot folgt)* |

---

## Voraussetzungen

| Komponente | Version | Hinweis |
|---|---|---|
| **Python** | 3.11+ | `python --version` |
| **Ollama** | aktuell | [ollama.ai](https://ollama.ai) – für KI-Funktionen |
| **pip** | aktuell | `pip install --upgrade pip` |

> **Nur Marktdaten & Charts** benötigen kein Ollama – sie funktionieren sofort.

---

## Installation

```bash
cd stockmind
pip install -r requirements.txt
```

> **Zum Aktualisieren der Pins** (nach Änderungen in `requirements.in`):
> ```bash
> pip install pip-tools
> pip-compile requirements.in
> ```
> `requirements.in` enthält die gewünschten Abhängigkeiten ohne Versionspins.
> `requirements.txt` enthält die gepinnten Versionen für reproduzierbare Builds.

---

## Schnellstart in 3 Schritten

### 1. Abhängigkeiten installieren

```bash
cd stockmind
pip install -r requirements.txt
```

### 2. Ollama starten & Modell laden *(optional, für KI-Analyse)*

```bash
# Ollama installieren: https://ollama.ai
ollama serve          # in separatem Terminal
ollama pull llama3    # ~4 GB, einmalig
```

### 3. App starten

```bash
streamlit run app.py
```

Browser öffnet sich automatisch unter **http://localhost:8501**

---

## Features

### 📊 Tab 1 – Analyse & Training
- **Suche** nach Ticker, WKN oder Firmenname (z. B. `SAP.DE`, `519000`, `Apple`)
- **Interaktiver Candlestick-Chart** mit Indikatoren (RSI, MACD, Bollinger Bands, SMAs)
- **LLM-Training**: KI analysiert historische Kerzen und lernt Muster
- **Auto-Modus**: UCB1-Algorithmus wählt automatisch die beste Methode
- **Backtesting**: Strategie-Backtest mit Equity Curve & Sharpe Ratio

### 💰 Tab 2 – Paper Trading
- Starte mit virtuellem Kapital (Standard: 10.000 €)
- Manuelle Orders oder vollautomatischer KI-Handel
- Portfolio-Übersicht mit Gewinn/Verlust, Win-Rate und Performance-Chart
- Konfigurierbare Ordergebühren & Spreads

### ⚙️ Tab 3 – Modell-Manager
- Ollama-Status auf einen Blick
- Modelle herunterladen mit Echtzeit-Fortschrittsanzeige
- Vergleichstabelle für alle unterstützten Modelle

---

## Projektstruktur

```
stockmind/
├── app.py                  # Streamlit-Dashboard (Einstiegspunkt)
├── config.py               # Zentrale Konfiguration
├── requirements.txt
├── modules/
│   ├── data_fetcher.py     # yfinance, WKN-Suche, OHLCV + Indikatoren
│   ├── model_manager.py    # Ollama-Integration, Modell-Download
│   ├── trainer.py          # LLM-Trainingszyklen, UCB1, sklearn GBM
│   ├── backtester.py       # PaperTrader, Backtest, Lambo-Konverter
│   ├── predictor.py        # Signal-Berechnung (SMA, RSI, MACD, BB)
│   ├── easter_eggs.py      # 🤫 Überraschungen
│   └── ui_components.py    # Wiederverwendbare Streamlit-Komponenten
└── data/                   # Lokal generierte Daten (gitignore)
    ├── cache/              # OHLCV-Cache (24h TTL)
    ├── training_state/     # Trainierter Modell-Zustand je Aktie
    └── portfolio/          # Paper-Trading-Portfolio
```

### Architektur-Prinzip

`app.py` ist der **einzige Orchestrierer** – es importiert alle Module
und gibt Daten als Parameter weiter. Module importieren sich nicht gegenseitig.

---

## Unterstützte Modelle

| Modell | Größe | Beschreibung |
|---|---|---|
| `llama3` | ~4.7 GB | ⭐ Empfohlen – ausgewogen, gut für Analyse |
| `mistral` | ~4.1 GB | Schnell & effizient |
| `phi3` | ~2.3 GB | Klein & sparsam, ideal für schwache Hardware |
| `gemma2` | ~5.5 GB | Googles Modell, detaillierte Erklärungen |
| `qwen2` | ~4.4 GB | Mehrsprachig (DE/EN besonders gut) |

---

## Konfiguration

Alle Parameter in `config.py` anpassbar:

```python
ORDER_COST_EUR   = 5.0        # Ordergebühr
SPREAD_PERCENT   = 0.1        # Spread in %
DEFAULT_BUDGET   = 10_000.0   # Startkapital Paper-Trading
LAMBO_PRICE_EUR  = 536_000.0  # 🏎️ Das große Ziel
CACHE_TTL_HOURS  = 24         # OHLCV-Cache Lebensdauer
```

---

## Easter Eggs 🥚

StockMind enthält einige versteckte Überraschungen.

Hinweis: Schau genau hin – manchmal lohnt es sich, öfter auf dasselbe zu klicken.
Und wer fleißig trainiert, wird belohnt... 🤫

---

## Lizenz

MIT – do whatever you want, but don't blame us for YOLO trades.

# StockMind-Workspace

Drei eigenständige Teilprojekte rund um Aktienanalyse. ⚠️ Alles ist ein
experimentelles Bildungsprojekt und **keine Anlageberatung**.

| Ordner | Was es ist | Start | Doku |
|---|---|---|---|
| [`stockmind/`](stockmind/README.md) | Streamlit-Dashboard: Marktdaten, technische Indikatoren, lokale LLM-Analyse (Ollama/NVIDIA), Bandit-Training, Paper-Trading, Backtests | `./start.sh` (Linux/macOS) bzw. `stockmind/start.bat` (Windows) | [stockmind/README.md](stockmind/README.md) |
| [`stock_model/`](stock_model/README.md) | PyTorch-LSTM, das aus Renditefenstern die nächste Rendite prognostiziert (CLI-Training + Streamlit-UI) | `streamlit run run.py` | [stock_model/README.md](stock_model/README.md) |
| [`frontend/`](frontend/README.md) | Next.js-16-Weboberfläche (aktuell auf Mock-Daten, kein Backend angebunden) | `cd frontend && npm install && npm run dev` | [frontend/README.md](frontend/README.md) |

## Entwicklung

```bash
pip install -r requirements.txt      # alle Python-Teilprojekte
pytest tests/                         # Tests (stock_model-Tests brauchen torch)
ruff check stockmind/ stock_model/    # Lint
cd frontend && npm ci && npm run lint && npm run build
```

Die CI (`.github/workflows/ci.yml`) führt Lint, Typprüfung und Tests für
alle drei Teilprojekte aus.

`AUDIT_REPORT.md` enthält das ursprüngliche Sicherheits-/Qualitäts-Audit;
die dort genannten kritischen Befunde sind inzwischen behoben (siehe
Git-Historie, Commits `fix: …`).

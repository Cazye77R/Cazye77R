# StockMind Audit Report – 2026-05-22

## Zusammenfassung (Top of mind)

**Bester Befund:** Die sklearn-ML-Pipeline ist sauber implementiert — `TimeSeriesSplit` ohne Shuffle, `StandardScaler` ausschließlich auf den Trainings-Fold gefittet, `compute_sample_weight("balanced")` in jedem Fold, Target-Labels-NaN-Zeilen werden korrekt gedroppt. Kein messbarer Look-Ahead-Bias in der sklearn-Pipeline.

**Schlechtester Befund:** Der `RiskManager` (risk_manager.py) ist vollständig implementiert — Stop-Loss via ATR, Drawdown-Limit, Exposure-Limit, risikobas. Positionsgröße — aber **nirgendwo in `auto_trade()` tatsächlich aufgerufen**. Die Auto-Trade-Schleife investiert stumpf 20 % des Cash pro Signal, ignoriert Drawdown-Grenzen und hat keinen Stop-Loss.

Weitere Auffälligkeiten: Pydantic-Modelle in `models.py` vorhanden aber in den eigentlichen Modulen nicht genutzt. Cache-Invalidierung nur TTL-basiert (Splits vergiften 24h-Cache). Backtest invest 95 % Cash pro BUY (All-In).

---

## 1. Security

### 1.1 Pickle-Verwendung

**Befund:** Eine Stelle. Ausschließlich im Legacy-Migrationspfad.

**Schweregrad:** 🟡 MITTEL

**Stellen:**
- `modules/trainer.py:1238` → `pickle.load(fh)` — liest `data/training_state/{TICKER}_model.pkl` (nur wenn joblib-Datei fehlt, einmalige Migration)

**Kontext:** Der Code ist mit `# noqa: S301 – einmalige Migration bekannter Dateien` kommentiert. Die Datei wird aus einem vom Anwendungscode kontrollierten Pfad geladen, nicht aus User-Input. Kein `pickle.dump` im aktiven Pfad (Persistenz läuft über `joblib`). Risiko: Falls ein Angreifer eine `.pkl`-Datei im `data/training_state/`-Verzeichnis platzieren kann, ist Remote Code Execution möglich.

---

### 1.2 Subprocess-Aufrufe

**Befund:** Ein Aufruf, korrekt abgesichert.

**Schweregrad:** 🟢 NIEDRIG

**Stellen:**
- `modules/model_manager.py:106` → `subprocess.Popen(["ollama", "pull", model_name], ...)`

**Bewertung:**
- `shell=False` (Argumente als **Liste**) — kein Shell-Injection-Vektor ✓
- `model_name` kommt aus Streamlit-UI-Selectbox (nicht aus freier Texteingabe)
- Umgebung: `env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"}` — sauber
- Timeout: kein explizites `timeout=` bei `Popen`, aber `proc.wait()` blockiert unbegrenzt → theoretischer DoS wenn `ollama pull` hängt

---

### 1.3 Requests ohne Timeout

**Befund:** Alle `requests`-Aufrufe haben explizite Timeouts.

**Schweregrad:** 🟢 NIEDRIG

| Datei:Zeile | Endpoint | Timeout |
|---|---|---|
| `data_fetcher.py:166` | Yahoo Finance Search | `timeout=10` |
| `data_fetcher.py:371` | Binance klines | `timeout=10` |
| `model_manager.py:207` | Ollama /api/chat (stream) | `timeout=OLLAMA_TIMEOUT_S` (120 s) |
| `ollama_provider.py:52` | Ollama /api/tags (health) | `timeout=3` |
| `ollama_provider.py:101` | Ollama /api/tags (models) | `timeout=5` |
| `ollama_provider.py:177` | Ollama /api/chat (HTTP) | `timeout=self._timeout` (120 s) |
| `nvidia_provider.py:95` | NVIDIA NIM | `timeout=60` |

---

## 2. ML-Pipeline – Look-Ahead-Bias & Data Leakage

### 2.1 Train/Test-Aufteilung

**Befund:** Korrekt — kein Shuffle.

**Schweregrad:** 🟢 NIEDRIG

**Stellen:**
- `modules/trainer.py:1162` → `tscv = TimeSeriesSplit(n_splits=5)` — strenge zeitliche Reihenfolge ✓

**LLM-Training-Backtest** (`run_training_cycle`):
- `trainer.py:506-510` → `train_df = df.iloc[:-1]` (letzter Balken = Validierung) — einfacher 1-Step-Ahead-Test, kein roll-forward, aber kein Look-Ahead-Bias ✓

---

### 2.2 StandardScaler Fitting

**Befund:** Korrekt — kein Leakage.

**Schweregrad:** 🟢 NIEDRIG

**Stellen:**
- `modules/trainer.py:1170-1172`:
  ```python
  sc = StandardScaler()
  X_tr_s = sc.fit_transform(X_tr)   # fit NUR auf Train ✓
  X_te_s = sc.transform(X_te)       # transform (kein fit) auf Test ✓
  ```
  Pro Fold ein frischer Scaler — kein Leakage über Fold-Grenzen hinweg.

---

### 2.3 Technische Indikatoren

**Befund:** Kein Look-Ahead-Bias.

**Schweregrad:** 🟢 NIEDRIG

Alle Indikatoren in `build_features()` und `_format_indicators()` verwenden:
- `close.rolling(n).mean()` — rückwärtsfenster ✓
- `close.ewm(span=n, adjust=False).mean()` — rückwärtsfenster ✓
- `close.pct_change(n)` — rückwärtsfenster ✓

Kein `expanding()`, kein Zugriff auf Future-Werte.

---

### 2.4 Target-Variable

**Befund:** Korrekt — NaN-Zeilen werden gedroppt.

**Schweregrad:** 🟢 NIEDRIG

**Stelle:** `modules/trainer.py:1132-1134`:
```python
future_ret = df["Close"].pct_change(horizon).shift(-horizon)
valid_mask = future_ret.notna()
return (future_ret[valid_mask] >= threshold).astype(int)
```
Die letzten `horizon` Zeilen ohne bekannten Future-Return werden über `valid_mask` ausgeschlossen. Kein NaN→0-Cast-Problem ✓

---

### 2.5 Klassen-Balance

**Befund:** Korrekt per-Fold balanciert.

**Schweregrad:** 🟢 NIEDRIG

**Stelle:** `modules/trainer.py:1175`:
```python
sw = compute_sample_weight("balanced", y_tr)
clf.fit(X_tr_s, y_tr, sample_weight=sw)
```
Wird in jedem TimeSeriesSplit-Fold neu berechnet ✓

---

## 3. Backtest & Risk Management

### 3.1 Risk-Mechanismen

**Befund:** RiskManager vollständig implementiert, aber **nicht in auto_trade() eingebunden**.

**Schweregrad:** 🔴 KRITISCH (für auto_trade) / 🟡 MITTEL (für Backtest)

| Mechanismus | Implementiert | Aufgerufen aus auto_trade() | Aufgerufen aus backtest_signals() |
|---|---|---|---|
| Stop-Loss (ATR) | ✓ `risk_manager.py:131` | ✗ | ✗ |
| Take-Profit (ATR) | ✓ `risk_manager.py:131` | ✗ | ✗ |
| Drawdown-Limit | ✓ `risk_manager.py:182` | ✗ | ✗ |
| Exposure-Limit | ✓ `risk_manager.py:211` | ✗ | ✗ |
| Risk-basierte Positionsgröße | ✓ `risk_manager.py:92` | ✗ | ✗ |

`RiskManager.validate_trade()` existiert (`risk_manager.py:252`) und implementiert alle 4 Checks — aber `auto_trade()` (`backtester.py:460`) ruft ihn nie auf.

---

### 3.2 Order-Größen-Berechnung

**Befund:** Zwei verschiedene Ansätze, keiner risk-basiert im Live-Modus.

**Schweregrad:** 🟠 HOCH

| Kontext | Formel | Datei:Zeile |
|---|---|---|
| `backtest_signals()` | `invest = cash * 0.95` — effektiv All-In | `backtester.py:899` |
| `auto_trade()` | `invest_eur = state.cash * invest_pct` (Default 20 %) | `backtester.py:531` |
| `RiskManager.position_size()` | `max_risk_eur / risk_per_share` (2 % Risiko) | `risk_manager.py:118` |

`RiskManager.position_size()` wird im Paper-Trading-Loop nicht verwendet.

---

### 3.3 Performance-Metriken

**`BacktestResult`-Dataclass** (`backtester.py:830`):

| Metrik | In BacktestResult | In compute_metrics() |
|---|---|---|
| Total Return | ✓ | ✓ |
| Buy-and-Hold-Vergleich | ✓ | ✗ |
| CAGR | ✗ | ✓ |
| Sharpe Ratio | ✓ | ✓ |
| Sortino Ratio | ✗ | ✓ |
| Calmar Ratio | ✗ | ✓ |
| Max Drawdown | ✓ | ✓ |
| Max Drawdown Duration | ✗ | ✓ |
| Win Rate | ✓ | ✓ |
| Profit Factor | ✗ | ✓ |
| Expectancy | ✗ | ✓ |
| Payoff Ratio | ✗ | ✓ |
| Max Consecutive Losses | ✗ | ✓ |
| Avg Trade Duration | ✗ | ✓ |

`compute_metrics()` ist vollständig, aber es gibt keine direkte Verknüpfung: `backtest_signals()` gibt `BacktestResult` zurück, nicht `compute_metrics()`-Output.

---

### 3.4 Slippage-Modell

**Befund:** Volumenabhängiges Modell vorhanden.

**Schweregrad:** 🟢 NIEDRIG

`backtester.py:708-734` — `compute_slippage()`:
```
slippage_pct = base_pct + volume_factor × (order_size / avg_daily_volume)
```
- Basis-Spread: `SLIPPAGE_BASE_PCT` (0,05 %, konfigurierbar via `.env`)
- Volumen-Impact: `SLIPPAGE_VOLUME_FACTOR` (0,1, konfigurierbar)
- Fallback auf fixen `spread_pct` wenn kein Volume-Feld vorhanden
- Kein Bid/Ask aus yfinance (auf täglicher Auflösung nicht verfügbar)

---

## 4. UCB1 / Auto-Modus

### 4.1 Implementierung

**Befund:** Drei Algorithmen, korrekt implementiert.

**Schweregrad:** 🟢 NIEDRIG

| Algorithmus | Klasse | Datei:Zeile | Typ |
|---|---|---|---|
| UCB1 | `UCB1Bandit` | `trainer.py:62` | Standard, alle Rewards gleichgewichtet |
| D-UCB | `DiscountedUCB1` | `trainer.py:96` | Kocsis & Szepesvári 2006, γ=0.95 |
| Thompson | `ThompsonSamplingBandit` | `trainer.py:159` | Beta-Prior, kein Tuning-Parameter |

Factory: `get_bandit(name)` (`trainer.py:205`) — auswählbar per UI.

---

### 4.2 Arme (Methoden)

`_METHODS` = ANALYSIS_METHODS ohne "Auto (KI wählt)" (`trainer.py:40`):
- "SMA Crossover", "RSI", "MACD", "Bollinger Bands", "Support/Resistance", "Candlestick Patterns"

---

### 4.3 Reward

**Befund:** Binär, nicht risk-adjusted.

**Schweregrad:** 🟡 MITTEL

- Reward 1.0 wenn `prediction == actual_dir` (UP/DOWN), sonst 0.0
- Pro Zyklus einmal berechnet
- NEUTRAL-Vorhersagen sind **immer falsch** (actual_dir ist immer UP oder DOWN) — UCB1 bestraft NEUTRAL-geneigte Methoden systematisch

---

### 4.4 History-Reset

**Befund:** UCB1 kein Reset; D-UCB implizites Vergessen über γ.

**Schweregrad:** 🟡 MITTEL

- `UCB1Bandit`: läuft ewig, kein Regime-Change-Erkennung
- `DiscountedUCB1`: `γ=0.95` gewichtet letzte ~20 Zyklen stärker — handhabt stille Marktregime-Wechsel implizit
- Kein expliziter Reset-Mechanismus

---

## 5. LLM-Integration

### 5.1 Direkte Ollama-Imports

**Befund:** Ausschließlich in `ollama_provider.py`.

**Schweregrad:** 🟢 NIEDRIG

- `modules/llm_providers/ollama_provider.py:150` → `import ollama` (lazy, innerhalb von `_chat_via_client()`)

---

### 5.2 Provider-Abstraktion

**Befund:** Vollständige ABC-Abstraktion vorhanden.

**Schweregrad:** 🟢 NIEDRIG

- `llm_providers/base.py` — `LLMProvider(ABC)` mit 5 abstrakten Methoden + `query()` Convenience-Methode
- `llm_providers/ollama_provider.py` — Ollama-Implementierung
- `llm_providers/nvidia_provider.py` — NVIDIA NIM (OpenAI-kompatibel)
- `llm_providers/factory.py` — `get_provider(name)` liest `LLM_PROVIDER` aus env
- Wechsel per `LLM_PROVIDER=nvidia` env-Var ohne Code-Änderung möglich ✓

---

### 5.3 Was das LLM tut

| Nutzung | Funktion | Datei | Ausgabe |
|---|---|---|---|
| Tagesrichtungs-Vorhersage | `run_training_cycle()` | `trainer.py:518` | UP/DOWN/NEUTRAL als **Trade-Signal** |
| News-Sentiment | `analyze_news()` | `sentiment_analyzer.py:37` | Float −1…+1 als ML-Feature |
| Entscheidungs-Erklärung | `explain_decision()` | `explainer.py:46` | Freitext-Erklärung (kein Signal) |
| Markt-Analyse | `analyze_stock()` | `model_manager.py:240` | Freitext-Analyse |

Relevanter Prompt-Kern (`trainer.py:730-735`):
```
Erstelle basierend auf der Methode "{method}" eine Vorhersage für den NÄCHSTEN Handelstag.
Antworte NUR mit exakt diesem JSON:
{"prediction": "UP", "confidence": 0.75, "reasoning": "..."}
prediction: "UP" | "DOWN" | "NEUTRAL"
```

---

### 5.4 Fehlerpfad wenn LLM offline

**Befund:** Vollständig behandelt.

**Schweregrad:** 🟢 NIEDRIG

`trainer.py:514`:
```python
if not is_llm_ready():
    return self._error_result("KI-Anbieter nicht erreichbar", symbol, method)
```
`_error_result()` gibt strukturiertes Dict mit `prediction=None`, `error=str` zurück — kein Crash. Retry-Logik in `query_model()` (`model_manager.py:167`): 3 Versuche mit exponential backoff (2s, 4s).

---

## 6. Daten-Qualität

### 6.1 `auto_adjust=True`

**Befund:** Konsistent in beiden yfinance-Download-Pfaden.

**Schweregrad:** 🟢 NIEDRIG

- `data_fetcher.py:326-327`: `auto_adjust=True, back_adjust=False` in `_fetch_yf_history()`
- `data_fetcher.py:344-348`: identisch in `_fetch_yf_download()`

---

### 6.2 Datenqualitäts-Behandlung

**Befund:** Teilweise — Splits vergiften Cache.

**Schweregrad:** 🟡 MITTEL

| Problem | Behandlung | Datei:Zeile |
|---|---|---|
| Zeitreihen-Lücken | ✓ `get_data_quality_report()` zählt fehlende Werktage | `data_fetcher.py:682` |
| 0-Volume-Tage | ✓ Warning wenn > 0 Tage | `data_fetcher.py:689` |
| Outlier (>20 % Tagesbewegung) | ✓ Warning | `data_fetcher.py:710` |
| Split-Cache-Vergiftung | ✗ Cache wird nicht bei Splits/Dividenden invalidiert | — |
| Survivorship-Bias-Disclaimer im UI | ✗ Nur in `get_data_quality_report()` Docstring | `data_fetcher.py:645` |

---

### 6.3 Cache-Invalidierung

**Befund:** Nur TTL-basiert.

**Schweregrad:** 🟡 MITTEL

- Cache TTL: `CACHE_TTL_HOURS` (Standard 24 h) — Parquet-Dateien unter `data/cache/`
- **Kein Event-basiertes Invalidieren**: Ein Aktien-Split in Stunde 1 bleibt bis zu 24 h im Cache mit gemischten Pre/Post-Split-Preisen
- `invalidate_cache()` Funktion vorhanden (`data_fetcher.py:627`) — muss manuell aufgerufen werden

---

## 7. Code-Qualität

### 7.1 Type-Hints-Coverage (Schätzung)

| Modul | Coverage | Anmerkung |
|---|---|---|
| `risk_manager.py` | ~95 % | Vollständige Signaturen |
| `trainer.py` | ~90 % | `dict` ohne generics an einigen Stellen |
| `backtester.py` | ~85 % | Legacy-Kompatibilitätsfunktionen ohne Hints |
| `data_fetcher.py` | ~85 % | Konsistent in öffentlichen Funktionen |
| `predictor.py` | ~80 % | |
| `model_manager.py` | ~80 % | |
| `sentiment_analyzer.py` | ~70 % | `provider: Any` statt konkreter Typ |
| `explainer.py` | ~70 % | `provider: Any` statt konkreter Typ |
| `app.py` | ~40 % | Streamlit-Code weitgehend untypisiert |

---

### 7.2 Pydantic-Nutzung

**Befund:** Modelle definiert, aber nicht in der Produktionspipeline genutzt.

**Schweregrad:** 🟡 MITTEL

- `models.py` definiert vollständige Pydantic v2 Modelle: `OHLCVBar`, `TradeSignal`, `Position`, `Portfolio`, `BacktestResult`, `RiskConfig`
- **Keine dieser Klassen wird in `trainer.py`, `backtester.py` oder `predictor.py` verwendet**
- Module nutzen stattdessen `@dataclass` (backtester.py) oder rohe `dict`-Rückgaben
- Pydantic-Validierung (`high ≥ low`, `confidence ∈ [0,1]`, etc.) greift damit nicht

---

### 7.3 Fehlerbehandlung

**Befund:** Keine nackten `except:` — aber einige Exceptions werden verschluckt.

**Schweregrad:** 🟢 NIEDRIG

- `except Exception as exc` überall — kein `except:` ohne Binden ✓
- `data_fetcher.py:524`: `except Exception as _exc:` → `logger.warning` + OHLCV ohne Indikatoren zurückgegeben (kein Crash, aber stille Degradierung)
- `walk_forward.py:73`: `except Exception as exc:` → Fold-Fehler protokolliert, Loop läuft weiter ✓
- `predictor.py:197`: `except Exception as exc:` → Warning-Append + Skip ✓

---

### 7.4 Tests

**Befund:** Gute Grundabdeckung, kritische Pfade ungetestet.

**Schweregrad:** 🟡 MITTEL

Test-Dateien: `test_modules.py`, `test_bandits.py`, `test_llm_providers.py`, `test_metrics.py`, `test_persistence.py`, `test_risk_manager.py`, `test_data_quality.py`, `test_sentiment.py`

| Bereich | Getestet |
|---|---|
| Config-Konstanten | ✓ |
| Easter Eggs | ✓ |
| Predictor (offline) | ✓ alle Methoden |
| PaperTrader BUY/SELL | ✓ |
| RiskManager (isoliert) | ✓ |
| Bandit-Algorithmen | ✓ |
| Data Fetcher (offline) | ✓ |
| **Backtest-Signal-Logik** | ✗ keine Tests |
| **TimeSeriesSplit-Korrektheit** | ✗ |
| **RiskManager in auto_trade** | ✗ — nicht integriert, daher nicht testbar |
| **PnL-Berechnung edge cases** | ✗ |

---

## 8. Architektur-Check

### 8.1 Cross-Imports zwischen Modulen

**Befund:** Zwei Stellen — eine problematisch, eine akzeptabel.

**Schweregrad:** 🟡 MITTEL

| Import | Datei:Zeile | Bewertung |
|---|---|---|
| `backtester.py` → `modules.data_fetcher` | `backtester.py:486` (lazy, in Funktion) | Tolerierbar — dokumentierter Design-Kompromiss |
| `backtester.py` → `modules.trainer` | `backtester.py:487` (lazy, in Funktion) | Tolerierbar — lazy import verhindert Circular |
| `ui_components.py` → `modules.easter_eggs` | `ui_components.py:19` | Akzeptabel |
| `sentiment_analyzer.py` → `modules.llm_providers` | lazy in Funktion | Akzeptabel |

Alle Cross-Imports sind lazy (innerhalb von Funktionen) — kein Circular-Import-Problem beim Start ✓

---

### 8.2 Magic Numbers

**Befund:** Zwei produktionskritische Magic Numbers.

**Schweregrad:** 🟡 MITTEL

| Wert | Datei:Zeile | Problem |
|---|---|---|
| `0.95` — 95 % Cash je BUY | `backtester.py:899` | Nicht in config, nicht dokumentiert |
| `0.15` / `-0.15` — Signal-Schwellen | `predictor.py:241-245` | Nicht in config, nicht per Parameter änderbar |
| `60`, `15`, `20` in StockTrainer | `trainer.py:409-412` | Class-Attribute, dokumentiert ✓ |

---

### 8.3 Streamlit `@st.cache_data`

**Befund:** Alle teuren Operationen gecacht.

**Schweregrad:** 🟢 NIEDRIG

| Gecachte Funktion | TTL | Datei:Zeile |
|---|---|---|
| `_check_ollama()` | 60 s | `app.py:86` |
| `_ollama_status()` | 60 s | `app.py:92` |
| `_models_list()` | 60 s | `app.py:104` |
| `_ohlcv(ticker, period)` | 300 s | `app.py:116` |
| `_info(ticker)` | 3600 s | `app.py:122` |
| `_search(query)` | 120 s | `app.py:128` |

---

## Severity-Übersicht

| Bereich | Schweregrad | Anzahl Findings |
|---|---|---|
| 1. Security | 🟡 | 2 (Pickle-Migration, Popen ohne wait-timeout) |
| 2. ML-Pipeline | 🟢 | 0 kritisch |
| 3. Backtest & Risk | 🔴🟠 | 2 (RiskManager nicht integriert, 95%-All-In) |
| 4. UCB1 / Auto | 🟡 | 2 (NEUTRAL-Bias, kein Reset) |
| 5. LLM-Integration | 🟢 | 0 kritisch |
| 6. Daten-Qualität | 🟡 | 2 (Split-Cache, kein UI-Survivorship-Disclaimer) |
| 7. Code-Qualität | 🟡 | 3 (Pydantic ungenutzt, app.py Typen, Tests lückenhaft) |
| 8. Architektur | 🟡 | 2 (Magic Numbers, Cross-Imports dokumentiert) |

---

## Empfohlene Reihenfolge der Behebung

1. **3.1 / 3.2** — `RiskManager.validate_trade()` in `auto_trade()` einbinden; Positionsgröße auf risk-based umstellen (Security: Kapitalverlust-Risiko)
2. **3.2** — 95 %-All-In in `backtest_signals()` auf konfigurierbaren Parameter auslagern
3. **6.3** — Event-basierte Cache-Invalidierung für Splits/Dividenden
4. **7.2** — Pydantic-Modelle tatsächlich in der Produktionspipeline nutzen (Validierung für OHLCV-Eingaben, Trade-Signale)
5. **4.3** — Reward risk-adjusted machen (z. B. return-weighted statt binär)
6. **7.4** — Tests für Backtest-Signal-Logik, PnL-Berechnung, TimeSeriesSplit-Korrektheit
7. **8.2** — Magic Numbers (`0.95`, `0.15`) in `config/trading.py` auslagern
8. **1.1** — Nach vollständiger Joblib-Migration: `load_model()` Pickle-Fallback entfernen
9. **6.2** — Survivorship-Bias-Hinweis im UI anzeigen (nicht nur im Docstring)
10. **4.4** — Expliziten Reset-Mechanismus für UCB1 bei Marktregime-Wechsel ergänzen

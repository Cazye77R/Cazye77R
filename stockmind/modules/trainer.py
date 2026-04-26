"""
StockMind – Trainings-Engine
StockTrainer-Klasse: LLM-gestützte Zyklen, Methoden-Scoring, Persistenz je Symbol.
Modul-Funktionen bleiben erhalten (Compat: predictor.py, app.py).
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    ANALYSIS_METHODS,
    DUCB_GAMMA,
    EXPLORATION_CONSTANT,
    TRAINING_STATE_DIR,
)

from modules.logger import logger

logger.debug(f"Module loaded: {__name__}")

# Methoden ohne "Auto (KI wählt)"
_METHODS = [m for m in ANALYSIS_METHODS if m != "Auto (KI wählt)"]


# ===========================================================================
# Multi-Armed Bandit – Algorithmen
# ===========================================================================

class BanditBase(ABC):
    """Gemeinsames Interface für alle Bandit-Algorithmen."""

    @abstractmethod
    def select(self, state: dict, methods: list[str]) -> str:
        """
        Wählt die nächste zu testende Methode anhand des aktuellen Zustands.

        Ungetestete Methoden werden von StockTrainer._select_next_method()
        bereits vor dem Bandit-Aufruf priorisiert, daher darf hier
        angenommen werden, dass alle Methoden mindestens einmal beobachtet
        wurden.
        """


class UCB1Bandit(BanditBase):
    """
    Standard-UCB1 (Upper Confidence Bound 1).

    score(m) = accuracy(m) + sqrt(c * ln(total+1) / count(m))

    Alle historischen Rewards werden gleich gewichtet – gut für
    stationäre Reward-Verteilungen.
    """

    def __init__(self, c: float = EXPLORATION_CONSTANT) -> None:
        self.c = c

    def select(self, state: dict, methods: list[str]) -> str:
        history       = state.get("accuracy_history", [])
        method_scores = state.get("method_scores", {})
        total         = max(1, state.get("cycles", 1))

        counts: dict[str, int] = {}
        for entry in history:
            m = entry.get("method", "")
            if m:
                counts[m] = counts.get(m, 0) + 1

        best_method, best_score = methods[0], -1.0
        for m in methods:
            acc = method_scores.get(m, 0.5)
            n   = max(1, counts.get(m, 1))
            ucb = acc + math.sqrt(self.c * math.log(total + 1) / n)
            if ucb > best_score:
                best_score, best_method = ucb, m
        return best_method


class DiscountedUCB1(BanditBase):
    """
    Discounted UCB1 (D-UCB) für nicht-stationäre Reward-Verteilungen.

    Bei Regime-Wechseln (Bull/Bear/Sideways) werden neuere Rewards
    stärker gewichtet als ältere.

    Formeln (Kocsis & Szepesvári 2006, Moulines & Menard 2019):

      N_t,i(γ) = Σ_{s=1..t} γ^(t-s) · 1{a_s = i}
      X_t,i    = Σ_{s=1..t} γ^(t-s) · 1{a_s = i} · r_s / N_t,i(γ)
      ucb_t,i  = X_t,i + c · sqrt( ln(n_t(γ)) / N_t,i(γ) )

    mit n_t(γ) = Σ_{s=1..t} γ^(t-s)  (diskontierter Gesamtzähler)

    Args:
        gamma: Discount-Faktor γ ∈ (0, 1). Default 0.95.
               γ nahe 1 → langsames Vergessen (ähnlich wie UCB1)
               γ nahe 0 → schnelles Vergessen (letzter Reward dominiert)
        c:     Explorations-Konstante (wie UCB1).
    """

    def __init__(
        self,
        gamma: float = DUCB_GAMMA,
        c:     float = EXPLORATION_CONSTANT,
    ) -> None:
        if not (0.0 < gamma < 1.0):
            raise ValueError(f"gamma muss in (0, 1) liegen, nicht {gamma!r}.")
        self.gamma = gamma
        self.c     = c

    def select(self, state: dict, methods: list[str]) -> str:
        history = state.get("accuracy_history", [])
        t       = len(history)          # Gesamtanzahl Beobachtungen

        # Diskontierte Summen pro Methode berechnen
        disc_count:  dict[str, float] = {m: 0.0 for m in methods}
        disc_reward: dict[str, float] = {m: 0.0 for m in methods}

        for s, entry in enumerate(history):
            m = entry.get("method", "")
            if m not in disc_count:
                continue
            weight = self.gamma ** (t - 1 - s)          # γ^(t-s), s läuft ab 0
            r      = 1.0 if entry.get("correct", False) else 0.0
            disc_count[m]  += weight
            disc_reward[m] += weight * r

        # Diskontierter Gesamtzähler n_t(γ) = (1 - γ^t) / (1 - γ)
        n_total = (1.0 - self.gamma ** t) / (1.0 - self.gamma) if t > 0 else 1.0

        best_method, best_ucb = methods[0], -1.0
        for m in methods:
            n_i = max(disc_count[m], 1e-9)
            x_i = disc_reward[m] / n_i
            exploration = self.c * math.sqrt(math.log(max(n_total, 1.0)) / n_i)
            ucb = x_i + exploration
            if ucb > best_ucb:
                best_ucb, best_method = ucb, m
        return best_method


class ThompsonSamplingBandit(BanditBase):
    """
    Thompson Sampling mit Beta-Prior.

    Modelliert den Erfolg jeder Methode als Beta(α, β)-Verteilung und
    zieht pro Methode eine Probe. Die Methode mit dem höchsten Sample
    wird gewählt.

      α_i = Anzahl korrekter Vorhersagen + 1  (Pseudo-Prior)
      β_i = Anzahl falscher Vorhersagen  + 1

    Konvergiert automatisch gegen die beste Methode ohne Tuning-Parameter.
    """

    def __init__(self, rng_seed: int | None = None) -> None:
        self._rng = np.random.default_rng(rng_seed)

    def select(self, state: dict, methods: list[str]) -> str:
        history = state.get("accuracy_history", [])

        wins:   dict[str, int] = {m: 0 for m in methods}
        losses: dict[str, int] = {m: 0 for m in methods}

        for entry in history:
            m = entry.get("method", "")
            if m not in wins:
                continue
            if entry.get("correct", False):
                wins[m]   += 1
            else:
                losses[m] += 1

        samples = {
            m: float(self._rng.beta(wins[m] + 1, losses[m] + 1))
            for m in methods
        }
        return max(samples, key=lambda k: samples[k])


# ---------------------------------------------------------------------------
# Bandit-Factory
# ---------------------------------------------------------------------------

_BANDIT_NAMES = ("UCB1", "D-UCB", "Thompson")


def get_bandit(
    name: str,
    gamma: float = DUCB_GAMMA,
    c:     float = EXPLORATION_CONSTANT,
) -> BanditBase:
    """
    Erstellt eine Bandit-Instanz anhand des Namens.

    Args:
        name:  "UCB1" | "D-UCB" | "Thompson"
        gamma: Discount-Faktor für D-UCB.
        c:     Explorations-Konstante für UCB1 / D-UCB.
    """
    n = name.strip().upper()
    if n in ("D-UCB", "DUCB", "DISCOUNTED"):
        return DiscountedUCB1(gamma=gamma, c=c)
    if n in ("THOMPSON", "TS"):
        return ThompsonSamplingBandit()
    return UCB1Bandit(c=c)


# ---------------------------------------------------------------------------
# A/B-Vergleich: compare_bandits
# ---------------------------------------------------------------------------

def compare_bandits(
    history: list[dict],
    methods: list[str],
    gamma:   float = DUCB_GAMMA,
    c:       float = EXPLORATION_CONSTANT,
) -> dict:
    """
    Vergleicht UCB1, D-UCB und Thompson Sampling auf einem historischen
    Reward-Stream (offline-Evaluation).

    Jeder Bandit bekommt dieselben Beobachtungen sequenziell präsentiert.
    An jedem Schritt t wählt der Bandit basierend auf den ersten t−1
    Beobachtungen eine Methode. Wenn diese mit der tatsächlich gewählten
    Methode übereinstimmt, erhält er den echten Reward; sonst den bisher
    beobachteten Durchschnitt der Methode.

    Args:
        history: accuracy_history-Liste (dicts mit "method", "correct").
        methods: Liste der möglichen Methoden.
        gamma:   Discount-Faktor für D-UCB.
        c:       Explorations-Konstante für UCB1 / D-UCB.

    Returns:
        dict mit:
          "cumulative_rewards": {bandit_name: list[float]}
          "final_rewards":      {bandit_name: float}
          "selections":         {bandit_name: list[str]}
          "figure":             plotly.graph_objects.Figure
    """
    import plotly.graph_objects as go

    if len(history) < 2 or not methods:
        return {
            "cumulative_rewards": {},
            "final_rewards": {},
            "selections": {},
            "figure": go.Figure(),
        }

    bandits: dict[str, BanditBase] = {
        "UCB1":     UCB1Bandit(c=c),
        "D-UCB":    DiscountedUCB1(gamma=gamma, c=c),
        "Thompson": ThompsonSamplingBandit(rng_seed=42),
    }

    cum_rewards:  dict[str, list[float]] = {n: [] for n in bandits}
    selections:   dict[str, list[str]]   = {n: [] for n in bandits}
    running_totals: dict[str, float]     = {n: 0.0 for n in bandits}

    # Laufende Methoden-Durchschnitte für Counterfactual-Rewards
    method_wins: dict[str, int]   = {m: 0 for m in methods}
    method_cnt:  dict[str, int]   = {m: 0 for m in methods}

    for t, obs in enumerate(history):
        actual_method = obs.get("method", "")
        actual_reward = 1.0 if obs.get("correct", False) else 0.0

        for bname, bandit in bandits.items():
            # Simulierten Zustand bis t aufbauen
            sim_state = {
                "accuracy_history": history[:t],
                "method_scores": _replay_method_scores(history[:t], methods),
                "cycles": t,
            }

            # Ungetestete Methoden zuerst (wie _select_next_method)
            tested = {e.get("method") for e in history[:t]}
            untested = [m for m in methods if m not in tested]
            if untested:
                chosen = untested[0]
            else:
                chosen = bandit.select(sim_state, methods)

            selections[bname].append(chosen)

            # Counterfactual-Reward
            if chosen == actual_method:
                reward = actual_reward
            else:
                cnt = method_cnt.get(chosen, 0)
                reward = method_wins.get(chosen, 0) / cnt if cnt > 0 else 0.5

            running_totals[bname] += reward
            cum_rewards[bname].append(running_totals[bname])

        # Beobachtung registrieren
        if actual_method in method_wins:
            method_wins[actual_method] += int(actual_reward)
            method_cnt[actual_method]  += 1

    fig = _make_comparison_figure(cum_rewards, history)

    return {
        "cumulative_rewards": cum_rewards,
        "final_rewards":      {n: round(v[-1], 2) for n, v in cum_rewards.items() if v},
        "selections":         selections,
        "figure":             fig,
    }


def _replay_method_scores(history: list[dict], methods: list[str]) -> dict[str, float]:
    """Recomputes method_scores dict from partial history."""
    wins:   dict[str, int] = {m: 0 for m in methods}
    counts: dict[str, int] = {m: 0 for m in methods}
    for entry in history:
        m = entry.get("method", "")
        if m in wins:
            counts[m] += 1
            if entry.get("correct", False):
                wins[m] += 1
    return {
        m: round(wins[m] / counts[m], 4) if counts[m] > 0 else 0.5
        for m in methods
    }


def _make_comparison_figure(
    cum_rewards: dict[str, list[float]],
    history: list[dict],
) -> object:
    """Erstellt Plotly-Chart für den Bandit-Vergleich."""
    import plotly.graph_objects as go

    _DARK_BG = {
        "plot_bgcolor":  "#0d1117",
        "paper_bgcolor": "#0d1117",
        "font":          {"color": "#c9d1d9", "family": "IBM Plex Mono, monospace"},
        "margin":        {"t": 40, "b": 30, "l": 40, "r": 10},
    }
    _COLORS = {"UCB1": "#58a6ff", "D-UCB": "#00ff88", "Thompson": "#f0b429"}

    x = list(range(1, len(history) + 1))
    fig = go.Figure()
    for bname, rewards in cum_rewards.items():
        if not rewards:
            continue
        fig.add_trace(go.Scatter(
            x=x[:len(rewards)],
            y=rewards,
            mode="lines",
            name=bname,
            line=dict(color=_COLORS.get(bname, "#aaa"), width=2),
        ))

    fig.update_layout(
        **_DARK_BG,
        height=280,
        title="Kumulativer Reward – Bandit-Vergleich",
        xaxis_title="Trainings-Zyklus",
        yaxis_title="Kumulativer Reward",
        legend=dict(orientation="h", y=1.1),
    )
    return fig




# ===========================================================================
# StockTrainer – Klasse
# ===========================================================================

class StockTrainer:
    """
    LLM-gestützte Trainings-Engine pro Aktien-Symbol.

    Persistiert Zustand als JSON unter data/training_state/{SYMBOL}.json.
    Jeder Trainingszyklus:
      1. Lädt OHLCV-Daten (6 Monate)
      2. Bereitet Kontext der letzten 60 Kerzen vor
      3. Fragt das LLM nach einer Richtungsvorhersage (UP/DOWN/NEUTRAL)
      4. Validiert gegen die tatsächliche letzte Kerze (Backtest)
      5. Speichert Ergebnis und aktualisiert method_scores

    State-Schema:
      symbol, cycles, accuracy_history, current_accuracy,
      best_method, method_scores, last_trained, model_used, insights,
      accuracy (Legacy), feature_importance (Legacy), training_log (Legacy)
    """

    TRAINING_PERIOD   = "6mo"
    CANDLE_WINDOW     = 60      # Kerzen im LLM-Kontext
    MAX_INSIGHTS      = 15      # Maximale gespeicherte Insights
    TABLE_ROWS        = 20      # Detailzeilen in der Kerzen-Tabelle

    def __init__(self, base_dir: str | None = None):
        root = Path(os.path.dirname(os.path.dirname(__file__)))
        self._state_dir = root / (base_dir or TRAINING_STATE_DIR)
        self._state_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # State-Verwaltung
    # ------------------------------------------------------------------

    def _state_path(self, symbol: str) -> Path:
        return self._state_dir / f"{symbol.upper()}.json"

    def _default_state(self, symbol: str) -> dict:
        return {
            # Neue Felder (Spec)
            "symbol":           symbol.upper(),
            "cycles":           0,
            "accuracy_history": [],
            "current_accuracy": 0.0,
            "best_method":      None,
            "method_scores":    {},
            "last_trained":     None,
            "model_used":       None,
            "insights":         [],
            # Legacy-Felder (app.py / predictor.py)
            "accuracy":          None,
            "feature_importance": {},
            "training_log":      [],
        }

    def load_state(self, symbol: str) -> dict:
        """Lädt Zustand aus JSON, füllt fehlende Schlüssel mit Defaults."""
        path = self._state_path(symbol)
        if not path.exists():
            return self._default_state(symbol)
        with open(path) as f:
            state = json.load(f)
        # Schema-Migration: fehlende Schlüssel ergänzen
        defaults = self._default_state(symbol)
        for key, val in defaults.items():
            state.setdefault(key, val)
        # "ticker" → "symbol" Migration (alte Dateien)
        if "ticker" in state and "symbol" not in state:
            state["symbol"] = state["ticker"]
        return state

    def _save_state(self, state: dict) -> None:
        path = self._state_path(state["symbol"])
        with open(path, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def list_trained(self) -> list[str]:
        return [p.stem for p in self._state_dir.glob("*.json")]


    # ------------------------------------------------------------------
    # 3. run_training_cycle
    # ------------------------------------------------------------------

    def run_training_cycle(
        self,
        symbol: str,
        method: str,
        model_name: str,
    ) -> dict:
        """
        Führt einen Trainingszyklus durch:
        - Lädt OHLCV-Daten (6 Monate)
        - Erstellt LLM-Prompt mit letzten 60 Kerzen + Methoden-Indikatoren
        - Holt Vorhersage vom LLM (UP / DOWN / NEUTRAL)
        - Validiert gegen tatsächliche letzte Kerze
        - Aktualisiert State und gibt Ergebnis zurück

        Returns:
            {"prediction": "UP", "confidence": 0.73, "reasoning": "...",
             "correct": True, "actual": "UP", "cycle": 5,
             "method": "RSI", "method_accuracy": 0.6, "overall_accuracy": 0.64}
        """
        from modules.data_fetcher import fetch_ohlcv
        from modules.model_manager import is_llm_ready, query_model

        # --- Daten laden ---
        df = fetch_ohlcv(symbol, period=self.TRAINING_PERIOD)
        if df.empty:
            err = df.attrs.get("error", "Keine Daten verfügbar")
            return self._error_result(err, symbol, method)

        if len(df) < 30:
            return self._error_result(
                f"Zu wenige Datenpunkte: {len(df)} (mind. 30)", symbol, method
            )

        # --- Backtest-Setup: letzter Balken als Validierung ---
        train_df   = df.iloc[:-1]       # alles bis auf letzte Kerze
        close_prev = float(df["Close"].iloc[-2])
        close_now  = float(df["Close"].iloc[-1])
        actual_dir = "UP" if close_now > close_prev else "DOWN"
        actual_chg = (close_now - close_prev) / close_prev * 100

        # --- LLM-Anfrage ---
        if not is_llm_ready():
            return self._error_result("KI-Anbieter nicht erreichbar", symbol, method)

        prompt = self._build_prompt(symbol, train_df, method)
        system = self._system_prompt()
        try:
            raw_response = query_model(model_name, prompt, system, temperature=0.1)
        except Exception as exc:
            logger.error(f"LLM-Anfrage fehlgeschlagen ({symbol}, {method}): {exc}")
            return self._error_result(str(exc), symbol, method)

        # --- Antwort parsen ---
        parsed     = self._parse_llm_response(raw_response)
        prediction = parsed.get("prediction", "NEUTRAL")
        confidence = float(parsed.get("confidence", 0.5))
        reasoning  = str(parsed.get("reasoning", raw_response[:300]))

        correct = (prediction == actual_dir)

        # --- State aktualisieren ---
        state = self.load_state(symbol)
        state["cycles"]     += 1
        state["last_trained"] = datetime.now().isoformat()
        state["model_used"]   = model_name

        # Method score (laufender Durchschnitt)
        prev_score = state["method_scores"].get(method)
        n_method   = sum(
            1 for e in state["accuracy_history"] if e.get("method") == method
        )
        if prev_score is None:
            new_score = 1.0 if correct else 0.0
        else:
            new_score = (prev_score * n_method + (1.0 if correct else 0.0)) / (n_method + 1)
        state["method_scores"][method] = round(new_score, 4)

        # Best method
        state["best_method"] = max(
            state["method_scores"], key=lambda k: state["method_scores"][k]
        )

        # Gesamtgenauigkeit
        prev_correct = sum(
            1 for e in state["accuracy_history"] if e.get("correct", False)
        )
        state["current_accuracy"] = round(
            (prev_correct + (1 if correct else 0)) / state["cycles"], 4
        )
        state["accuracy"] = state["current_accuracy"]   # Legacy

        # Accuracy-History-Eintrag
        state["accuracy_history"].append({
            "cycle":             state["cycles"],
            "timestamp":         state["last_trained"],
            "method":            method,
            "prediction":        prediction,
            "actual":            actual_dir,
            "actual_change_pct": round(actual_chg, 3),
            "correct":           correct,
            "confidence":        round(confidence, 3),
            "accuracy_snapshot": state["current_accuracy"],
        })

        # Insight speichern
        tick = "✓" if correct else "✗"
        insight = (
            f"[{state['cycles']}] {method}: {prediction} → {actual_dir} {tick} "
            f"({actual_chg:+.2f}%) | {reasoning[:180]}"
        )
        state["insights"].append(insight)
        state["insights"] = state["insights"][-self.MAX_INSIGHTS:]

        # Legacy training_log
        state["training_log"].append({
            "cycle":     state["cycles"],
            "timestamp": state["last_trained"],
            "method":    method,
            "accuracy":  state["current_accuracy"],
        })

        self._save_state(state)

        return {
            "prediction":       prediction,
            "confidence":       round(confidence, 3),
            "reasoning":        reasoning,
            "correct":          correct,
            "actual":           actual_dir,
            "actual_change_pct": round(actual_chg, 3),
            "cycle":            state["cycles"],
            "method":           method,
            "method_accuracy":  round(new_score, 3),
            "overall_accuracy": state["current_accuracy"],
            "symbol":           symbol.upper(),
        }

    # ------------------------------------------------------------------
    # 4. auto_mode
    # ------------------------------------------------------------------

    def auto_mode(
        self,
        symbol:      str,
        model_name:  str,
        bandit_name: str = "UCB1",
    ) -> dict:
        """
        Wählt automatisch die nächste zu testende Methode nach dem gewählten
        Bandit-Algorithmus.

        Args:
            symbol:      Aktien-Symbol.
            model_name:  LLM-Modellname.
            bandit_name: "UCB1" | "D-UCB" | "Thompson"

        Returns:
            run_training_cycle-Ergebnis + {"selected_method", "preferred_method",
            "bandit_used"}
        """
        bandit          = get_bandit(bandit_name)
        state           = self.load_state(symbol)
        selected_method = self._select_next_method(state, bandit=bandit)
        result          = self.run_training_cycle(symbol, selected_method, model_name)

        updated_state = self.load_state(symbol)
        result["selected_method"]  = selected_method
        result["preferred_method"] = updated_state.get("best_method") or selected_method
        result["bandit_used"]      = bandit_name
        return result

    def _select_next_method(
        self,
        state:  dict,
        bandit: BanditBase | None = None,
    ) -> str:
        """
        Wählt die nächste Methode.

        Ungetestete Methoden werden immer zuerst priorisiert.
        Danach entscheidet der übergebene Bandit.

        Args:
            state:  Aktueller Trainingszustand.
            bandit: BanditBase-Instanz; None → UCB1Bandit (Rückwärtskompatibilität).
        """
        method_scores = state.get("method_scores", {})

        untested = [m for m in _METHODS if m not in method_scores]
        if untested:
            return untested[0]

        if bandit is None:
            bandit = UCB1Bandit()

        return bandit.select(state, _METHODS)

    # ------------------------------------------------------------------
    # 5. get_next_prediction
    # ------------------------------------------------------------------

    def get_next_prediction(self, symbol: str, model_name: str) -> dict:
        """
        Gibt eine neue Vorhersage mit der bisher besten Methode zurück.
        Fällt auf die erste verfügbare Methode zurück wenn kein Training vorliegt.

        Returns:
            run_training_cycle-Ergebnis (validiert gegen letzte bekannte Kerze)
        """
        state       = self.load_state(symbol)
        best_method = state.get("best_method")
        if not best_method or best_method not in state.get("method_scores", {}):
            best_method = _METHODS[0]
        result = self.run_training_cycle(symbol, best_method, model_name)
        result["is_best_method_prediction"] = True
        return result


    # ------------------------------------------------------------------
    # Prompt-Aufbau
    # ------------------------------------------------------------------

    def _system_prompt(self) -> str:
        return (
            "Du bist ein quantitativer Finanzanalyst bei StockMind. "
            "Du analysierst Kursdaten und technische Indikatoren. "
            "Antworte AUSSCHLIESSLICH mit dem verlangten JSON-Objekt. "
            "Kein Text außerhalb des JSON. Antworte auf Deutsch."
        )

    def _build_prompt(self, symbol: str, df: pd.DataFrame, method: str) -> str:
        """
        Erstellt einen strukturierten LLM-Prompt mit:
        - Kompakter Kerzen-Tabelle (letzte 20 Zeilen im Detail)
        - 60-Tage-Zusammenfassung
        - Methoden-spezifischen Indikatoren
        """
        ctx = df.tail(self.CANDLE_WINDOW)
        n   = len(ctx)

        summary  = self._format_summary(ctx)
        table    = self._format_candle_table(ctx)
        ind_text = self._format_indicators(ctx, method)

        latest_close = float(ctx["Close"].iloc[-1])
        prev_close   = float(ctx["Close"].iloc[-2])
        day_chg      = (latest_close - prev_close) / prev_close * 100

        return (
            f"Aktie: {symbol.upper()}  |  Analyse-Methode: {method}\n\n"
            f"=== {n}-TAGE-ZUSAMMENFASSUNG ===\n{summary}\n\n"
            f"=== KERZEN-DETAILS (letzte {self.TABLE_ROWS} Handelstage) ===\n{table}\n\n"
            f"=== AKTUELLE INDIKATOREN ({method}) ===\n{ind_text}\n\n"
            f"Letzter Schlusskurs : {latest_close:.2f}  ({day_chg:+.2f}% zum Vortag)\n\n"
            "=== AUFGABE ===\n"
            f'Erstelle basierend auf der Methode "{method}" eine Vorhersage '
            "für den NÄCHSTEN Handelstag.\n"
            "Antworte NUR mit exakt diesem JSON (kein weiterer Text):\n\n"
            '{"prediction": "UP", "confidence": 0.75, '
            '"reasoning": "Kurze Begründung auf Deutsch"}\n\n'
            'prediction: "UP" (Kurs steigt) | "DOWN" (Kurs fällt) | "NEUTRAL" (seitwärts)\n'
            "confidence: 0.0 (unsicher) … 1.0 (sehr sicher)"
        )

    def _format_summary(self, df: pd.DataFrame) -> str:
        close   = df["Close"]
        volume  = df["Volume"]
        start_p = float(close.iloc[0])
        end_p   = float(close.iloc[-1])
        trend   = (end_p - start_p) / start_p * 100
        lines   = [
            f"Zeitraum   : {str(df.index[0])[:10]} – {str(df.index[-1])[:10]} ({len(df)} Tage)",
            f"Kurs-Range : {float(close.min()):.2f} – {float(close.max()):.2f}",
            f"Trend      : {trend:+.2f}% (Start {start_p:.2f} → Aktuell {end_p:.2f})",
            f"Ø Volumen  : {float(volume.mean()):,.0f}  |  "
            f"Vol-Trend  : {'zunehmend' if float(volume.iloc[-5:].mean()) > float(volume.iloc[-20:-5].mean()) else 'abnehmend'}",
        ]
        return "\n".join(lines)

    def _format_candle_table(self, df: pd.DataFrame) -> str:
        """Letzte TABLE_ROWS Kerzen als kompakte Tabelle."""
        rows   = df.tail(self.TABLE_ROWS)
        header = "Datum       | Schluss | Δ%    | Volumen"
        lines  = [header, "-" * len(header)]
        prev   = float(rows["Close"].iloc[0])
        for i, (idx, row) in enumerate(rows.iterrows()):
            c   = float(row["Close"])
            chg = (c - prev) / prev * 100 if i > 0 else 0.0
            vol = float(row["Volume"])
            vol_str = f"{vol/1e6:.1f}M" if vol >= 1e6 else f"{vol/1e3:.0f}K"
            lines.append(
                f"{str(idx)[:10]} | {c:7.2f}  | {chg:+5.2f} | {vol_str}"
            )
            prev = c
        return "\n".join(lines)

    def _format_indicators(self, df: pd.DataFrame, method: str) -> str:
        """Berechnet und formatiert methoden-spezifische Indikatoren."""
        close = df["Close"]
        lines: list[str] = []

        # --- RSI ---
        rsi_val = self._get_rsi(close)
        rsi_txt = "überkauft" if rsi_val > 70 else ("überverkauft" if rsi_val < 30 else "neutral")
        lines.append(f"RSI(14)         : {rsi_val:.1f}  [{rsi_txt}]")

        # --- MACD ---
        ema12   = close.ewm(span=12, adjust=False).mean()
        ema26   = close.ewm(span=26, adjust=False).mean()
        macd    = ema12 - ema26
        sig     = macd.ewm(span=9, adjust=False).mean()
        hist    = macd - sig
        h_last  = float(hist.iloc[-1])
        h_prev  = float(hist.iloc[-2])
        cross   = "Bullish Crossover" if h_last > 0 > h_prev else (
                  "Bearish Crossover" if h_last < 0 < h_prev else "")
        lines.append(
            f"MACD-Histogramm : {h_last:+.4f}  "
            f"({'steigend' if h_last > h_prev else 'fallend'})"
            f"{'  ← ' + cross if cross else ''}"
        )

        # --- Bollinger Bands ---
        bb_mid  = close.rolling(20).mean()
        bb_std  = close.rolling(20).std()
        bb_up   = bb_mid + 2 * bb_std
        bb_lo   = bb_mid - 2 * bb_std
        bb_pct  = (close - bb_lo) / (bb_up - bb_lo).replace(0, float("nan"))
        bpct    = float(bb_pct.iloc[-1]) if not bb_pct.isna().iloc[-1] else 0.5
        lines.append(
            f"Bollinger %B    : {bpct:.2f}  "
            f"({'über oberem Band' if bpct > 1 else 'unter unterem Band' if bpct < 0 else f'{bpct*100:.0f}% der Bandbreite'})"
        )

        # --- SMAs ---
        for w in (20, 50, 200):
            if len(close) >= w:
                sma   = float(close.rolling(w).mean().iloc[-1])
                price = float(close.iloc[-1])
                pos   = "darüber" if price > sma else "darunter"
                lines.append(f"SMA({w:<3})         : {sma:.2f}  [Kurs {pos}]")

        # --- Methoden-spezifische Extras ---
        if method == "SMA Crossover":
            if len(close) >= 50:
                sma20 = float(close.rolling(20).mean().iloc[-1])
                sma50 = float(close.rolling(50).mean().iloc[-1])
                prev20 = float(close.rolling(20).mean().iloc[-2])
                prev50 = float(close.rolling(50).mean().iloc[-2])
                if prev20 <= prev50 and sma20 > sma50:
                    lines.append("SMA-Signal      : Golden Cross (bullisch)")
                elif prev20 >= prev50 and sma20 < sma50:
                    lines.append("SMA-Signal      : Death Cross (bärisch)")
                else:
                    lines.append(f"SMA-Signal      : SMA20 {'>' if sma20 > sma50 else '<'} SMA50")

        elif method == "Support/Resistance":
            sr_levels = self._calc_support_resistance(df)
            price = float(close.iloc[-1])
            resistances = sorted([lv for lv in sr_levels if lv > price])[:2]
            supports    = sorted([lv for lv in sr_levels if lv <= price], reverse=True)[:2]
            lines.append(f"Widerstände     : {', '.join(f'{x:.2f}' for x in resistances) or 'keine'}")
            lines.append(f"Unterstützungen : {', '.join(f'{x:.2f}' for x in supports) or 'keine'}")

        elif method == "Candlestick Patterns":
            patterns = self._detect_candle_patterns(df.tail(5))
            lines.append(
                f"Kerzen-Muster   : {', '.join(patterns) if patterns else 'kein klares Muster'}"
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Technische Hilfsberechnungen
    # ------------------------------------------------------------------

    @staticmethod
    def _get_rsi(close: pd.Series, period: int = 14) -> float:
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss.replace(0, float("nan"))
        rsi   = 100 - (100 / (1 + rs))
        val   = float(rsi.iloc[-1])
        return val if not math.isnan(val) else 50.0

    @staticmethod
    def _calc_support_resistance(df: pd.DataFrame, window: int = 5) -> list[float]:
        """Lokale Hochs und Tiefs als Support/Resistance-Niveaus."""
        highs  = df["High"]
        lows   = df["Low"]
        levels: list[float] = []
        for i in range(window, len(df) - window):
            h = float(highs.iloc[i])
            lo = float(lows.iloc[i])
            if h == float(highs.iloc[i - window:i + window + 1].max()):
                levels.append(h)
            if lo == float(lows.iloc[i - window:i + window + 1].min()):
                levels.append(lo)
        # Cluster: Niveaus innerhalb 0.5% zusammenfassen
        merged: list[float] = []
        for lv in sorted(levels):
            if not merged or abs(lv - merged[-1]) / merged[-1] > 0.005:
                merged.append(lv)
        return merged

    @staticmethod
    def _detect_candle_patterns(df: pd.DataFrame) -> list[str]:
        """Erkennt einfache Candlestick-Muster in den letzten Kerzen."""
        patterns: list[str] = []
        if len(df) < 2:
            return patterns

        for i in range(len(df)):
            o = float(df["Open"].iloc[i])
            h = float(df["High"].iloc[i])
            lo = float(df["Low"].iloc[i])
            c = float(df["Close"].iloc[i])
            body   = abs(c - o)
            rng    = h - lo if h != lo else 1e-9
            up_shd = h - max(c, o)
            dn_shd = min(c, o) - lo

            if body / rng < 0.1:
                patterns.append("Doji")
            elif dn_shd > 2 * body and up_shd < body:
                patterns.append("Hammer" if c > o else "Hanging Man")
            elif up_shd > 2 * body and dn_shd < body:
                patterns.append("Shooting Star" if c < o else "Inverted Hammer")

        # Engulfing (letzten 2 Kerzen)
        if len(df) >= 2:
            prev_o = float(df["Open"].iloc[-2])
            prev_c = float(df["Close"].iloc[-2])
            curr_o = float(df["Open"].iloc[-1])
            curr_c = float(df["Close"].iloc[-1])
            if curr_c > curr_o and prev_c < prev_o:
                if curr_o <= prev_c and curr_c >= prev_o:
                    patterns.append("Bullish Engulfing")
            elif curr_c < curr_o and prev_c > prev_o:
                if curr_o >= prev_c and curr_c <= prev_o:
                    patterns.append("Bearish Engulfing")

        return list(dict.fromkeys(patterns))  # Deduplizieren

    # ------------------------------------------------------------------
    # LLM-Antwort parsen
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_response(response: str) -> dict:
        """
        Parst die LLM-Antwort mit 4-stufiger Fallback-Strategie:
        1. Direkte json.loads() auf die Antwort
        2. JSON-Block aus ```json … ``` oder dem ersten {…}
        3. Regex-Extraktion von prediction + confidence
        4. Keyword-Suche (UP/DOWN/NEUTRAL, KAUFEN/VERKAUFEN)
        """
        clean = response.strip()

        # 1. Direkte Konvertierung
        try:
            data = json.loads(clean)
            return _normalize_parsed(data)
        except Exception:
            logger.debug("LLM-Antwort kein direktes JSON – versuche Extraktion")

        # 2. JSON-Block suchen
        # ```json { ... } ``` oder erstes vollständiges { ... }
        block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
        if not block_match:
            block_match = re.search(r"(\{[^{}]*\})", clean, re.DOTALL)
        if block_match:
            try:
                data = json.loads(block_match.group(1))
                return _normalize_parsed(data)
            except Exception:
                logger.debug("JSON-Block in LLM-Antwort nicht parsebar – verwende Regex")

        # 3. Regex-Extraktion
        pred_match = re.search(
            r'\b(UP|DOWN|NEUTRAL'
            r'|STEIG[ET]N?|F[AÄ]LLT?|F[AÄ]LLEN'
            r'|SEITW[ÄA]RTS|KAUFEN|VERKAUFEN|HALTEN'
            r'|BUY|SELL|HOLD)\b',
            clean, re.IGNORECASE,
        )
        conf_match = re.search(
            r'(?:confidence|konfidenz|wahrscheinlichkeit)[^\d]*([01]?\.\d+)',
            clean, re.IGNORECASE,
        )
        if not conf_match:
            conf_match = re.search(r'\b(0\.\d{1,3}|1\.0)\b', clean)

        prediction = "NEUTRAL"
        if pred_match:
            raw = pred_match.group(1).upper()
            # Normalisierung auf UP / DOWN / NEUTRAL
            if re.match(r'UP|STEIG|KAUFEN|BUY', raw):
                prediction = "UP"
            elif re.match(r'DOWN|F[AÄ]LL|VERKAUFEN|SELL', raw):
                prediction = "DOWN"
            else:
                prediction = "NEUTRAL"

        confidence = float(conf_match.group(1)) if conf_match else 0.5

        return {
            "prediction": prediction,
            "confidence": round(min(max(confidence, 0.0), 1.0), 3),
            "reasoning":  clean[:400],
        }

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    @staticmethod
    def _error_result(error: str, symbol: str, method: str) -> dict:
        return {
            "error":            error,
            "prediction":       None,
            "confidence":       0.0,
            "reasoning":        error,
            "correct":          None,
            "actual":           None,
            "cycle":            0,
            "method":           method,
            "method_accuracy":  None,
            "overall_accuracy": None,
            "symbol":           symbol.upper(),
        }


def _normalize_parsed(data: dict) -> dict:
    """Normalisiert ein gepartes Dict auf einheitliche Schlüssel + Typen."""
    # prediction
    raw_pred = str(data.get("prediction", data.get("direction", "NEUTRAL"))).upper()
    mapping  = {
        "UP": "UP", "STEIGT": "UP", "KAUFEN": "UP", "BUY": "UP",
        "DOWN": "DOWN", "FÄLLT": "DOWN", "VERKAUFEN": "DOWN", "SELL": "DOWN",
        "NEUTRAL": "NEUTRAL", "HOLD": "NEUTRAL", "HALTEN": "NEUTRAL", "SEITWÄRTS": "NEUTRAL",
    }
    prediction = mapping.get(raw_pred, "NEUTRAL")

    # confidence
    try:
        confidence = float(data.get("confidence", data.get("konfidenz", 0.5)))
        confidence = min(max(confidence, 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.5

    # reasoning
    reasoning = str(data.get("reasoning", data.get("begründung", data.get("reason", ""))))

    return {"prediction": prediction, "confidence": round(confidence, 3), "reasoning": reasoning}


# ===========================================================================
# Modul-Funktionen (Backward-Kompatibilität für app.py und predictor.py)
# ===========================================================================

def _state_path(ticker: str) -> Path:
    path = Path(TRAINING_STATE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{ticker.upper()}.json"


def _model_path(ticker: str) -> Path:
    path = Path(TRAINING_STATE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{ticker.upper()}_model.joblib"


def _legacy_pkl_path(ticker: str) -> Path:
    return Path(TRAINING_STATE_DIR) / f"{ticker.upper()}_model.pkl"


def load_state(ticker: str) -> dict:
    """Lädt Trainingszustand (kompatibel mit neuem und altem Schema)."""
    t = StockTrainer()
    return t.load_state(ticker)


def save_state(ticker: str, state: dict) -> None:
    """Persistiert den Zustand als JSON."""
    p = _state_path(ticker)
    with open(p, "w") as f:
        json.dump(state, f, indent=2, default=str)


def list_trained_stocks() -> list[str]:
    """Gibt alle Symbole zurück, für die ein Trainingszustand existiert."""
    t = StockTrainer()
    return t.list_trained()


# ---------------------------------------------------------------------------
# Feature-Engineering (predictor.py)
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame, sentiment_score: float = 0.0) -> pd.DataFrame:
    """
    Berechnet numerische ML-Features aus OHLCV-Daten.

    Args:
        df:              OHLCV-DataFrame.
        sentiment_score: Aktueller News-Sentiment-Score [-1, +1].
                         Beim Training historischer Daten auf 0.0 (neutral) belassen,
                         da historische Sentiment-Daten nicht verfügbar sind.
                         Bei Live-Vorhersagen den echten Wert aus analyze_news() übergeben.
    """
    feat   = pd.DataFrame(index=df.index)
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]

    feat["ret_1d"]        = close.pct_change(1)
    feat["ret_5d"]        = close.pct_change(5)
    feat["ret_20d"]       = close.pct_change(20)
    feat["sma_20"]        = close.rolling(20).mean() / close - 1
    feat["sma_50"]        = close.rolling(50).mean() / close - 1
    feat["sma_cross"]     = feat["sma_20"] - feat["sma_50"]
    feat["volatility_20d"] = close.pct_change().rolling(20).std()
    feat["vol_ratio"]     = volume / volume.rolling(20).mean()

    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    feat["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))

    ema12   = close.ewm(span=12, adjust=False).mean()
    ema26   = close.ewm(span=26, adjust=False).mean()
    macd    = ema12 - ema26
    signal  = macd.ewm(span=9, adjust=False).mean()
    feat["macd_hist"] = macd - signal

    bb_mid  = close.rolling(20).mean()
    bb_std  = close.rolling(20).std()
    feat["bb_pos"]  = (close - bb_mid) / (2 * bb_std)
    feat["hl_range"] = (high - low) / close

    feat["sentiment"] = float(sentiment_score)

    feat.dropna(inplace=True)
    return feat


def build_labels(
    df: pd.DataFrame, horizon: int = 5, threshold: float = 0.01
) -> pd.Series:
    """
    Binäre Labels: 1 = Kurs steigt ≥ threshold in `horizon` Tagen.

    Die letzten `horizon` Zeilen haben keinen bekannten Future-Return und werden
    explizit gedroppt. Ohne diesen Drop würde NaN → 0 (False) gecasted,
    was einen Look-Ahead-Bias-ähnlichen Fehler beim Training verursacht.
    """
    future_ret = df["Close"].pct_change(horizon).shift(-horizon)
    valid_mask = future_ret.notna()
    return (future_ret[valid_mask] >= threshold).astype(int)


# ---------------------------------------------------------------------------
# sklearn-Training (app.py Trainingsseite)
# ---------------------------------------------------------------------------

def train(ticker: str, df: pd.DataFrame, horizon: int = 5) -> dict:
    """
    Trainiert ein GradientBoosting-Modell für einen Ticker.
    Persistiert Modell (pkl) + State (json).
    Returns aktualisierter State-Dict.
    """
    state    = load_state(ticker)
    features = build_features(df)
    labels   = build_labels(df, horizon=horizon)

    idx = features.index.intersection(labels.index)
    X   = features.loc[idx].values
    y   = labels.loc[idx].values

    if len(X) < 60:
        raise ValueError(
            f"Zu wenige Datenpunkte für Training: {len(X)} (mind. 60 nötig)"
        )

    # TimeSeriesSplit: kein zufälliges Sampling, strenge zeitliche Reihenfolge.
    # Jeder Fold: Scaler nur auf Train-Slice fitten (kein Data Leakage).
    tscv       = TimeSeriesSplit(n_splits=5)
    cv_scores  = []
    model, scaler = None, None

    for fold_train_idx, fold_test_idx in tscv.split(X):
        X_tr, X_te = X[fold_train_idx], X[fold_test_idx]
        y_tr, y_te = y[fold_train_idx], y[fold_test_idx]

        sc = StandardScaler()
        X_tr_s = sc.fit_transform(X_tr)   # fit NUR auf Train
        X_te_s = sc.transform(X_te)       # transform (kein fit) auf Test

        # GBC unterstützt kein class_weight → sample_weights für Balance
        sw  = compute_sample_weight("balanced", y_tr)
        clf = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
        clf.fit(X_tr_s, y_tr, sample_weight=sw)

        cv_scores.append(float(clf.score(X_te_s, y_te)))
        model, scaler = clf, sc  # letzter Fold = aktuellstes Training

    accuracy = float(np.mean(cv_scores))

    joblib.dump(
        {"model": model, "scaler": scaler, "feature_names": list(features.columns)},
        _model_path(ticker),
        compress=3,
    )

    # State aktualisieren (neues + Legacy-Schema)
    state["symbol"]           = ticker.upper()
    state["cycles"]           = state.get("cycles", 0) + 1
    state["last_trained"]     = datetime.now().isoformat()
    state["accuracy"]         = round(accuracy, 4)
    state["current_accuracy"] = round(accuracy, 4)
    state["feature_importance"] = dict(
        zip(features.columns, [round(v, 4) for v in model.feature_importances_])
    )
    state["training_log"].append({
        "cycle":       state["cycles"],
        "timestamp":   state["last_trained"],
        "accuracy":    state["accuracy"],
        "samples":     len(X),
        "horizon_days": horizon,
    })
    state["accuracy_history"].append({
        "cycle":             state["cycles"],
        "timestamp":         state["last_trained"],
        "method":            "sklearn/GBM",
        "correct":           None,
        "accuracy_snapshot": state["accuracy"],
    })
    save_state(ticker, state)
    return state


def load_model(ticker: str) -> Optional[dict]:
    """
    Lädt gespeichertes sklearn-Modell + Scaler.

    Migration: Falls nur eine alte .pkl-Datei existiert, wird sie einmalig
    mit pickle geladen, als .joblib gespeichert und die .pkl-Datei gelöscht.
    Gibt None zurück wenn kein Modell existiert.
    """
    import pickle  # lokaler Import – nur für Migrations-Pfad benötigt

    p     = _model_path(ticker)
    p_old = _legacy_pkl_path(ticker)

    if p.exists():
        return joblib.load(p)

    if p_old.exists():
        logger.warning(
            f"Migriere Legacy-Modell {p_old.name} → {p.name} (pickle → joblib)."
        )
        with open(p_old, "rb") as fh:
            payload = pickle.load(fh)  # noqa: S301 – einmalige Migration bekannter Dateien
        joblib.dump(payload, p, compress=3)
        p_old.unlink()
        logger.info(f"Migration abgeschlossen. Alte Datei {p_old.name} gelöscht.")
        return payload

    return None

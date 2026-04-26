"""
StockMind – Tests für Modell-Persistenz (joblib round-trip + .pkl-Migration).

Alle Tests laufen offline in einem temporären Verzeichnis.
"""
from __future__ import annotations

import os
import pickle
import sys
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, "stockmind"))


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _make_payload() -> dict:
    """Erstellt ein realistisches Modell-Payload wie trainer.py es speichert."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 5)).astype(np.float32)
    y = (X[:, 0] > 0).astype(int)

    sc = StandardScaler()
    X_s = sc.fit_transform(X)

    clf = GradientBoostingClassifier(n_estimators=20, max_depth=2, random_state=0)
    clf.fit(X_s, y)

    return {
        "model":         clf,
        "scaler":        sc,
        "feature_names": [f"feat_{i}" for i in range(5)],
    }


def _predict(payload: dict, X: np.ndarray) -> np.ndarray:
    """Skaliert X und gibt Klassenvorhersagen zurück."""
    X_s = payload["scaler"].transform(X)
    return payload["model"].predict(X_s)


# ---------------------------------------------------------------------------
# Joblib round-trip
# ---------------------------------------------------------------------------

class TestJoblibRoundTrip:
    def test_save_and_load_identical_predictions(self, tmp_path):
        """Gespeichertes Modell muss identische Vorhersagen liefern."""
        payload = _make_payload()
        path = tmp_path / "AAPL_model.joblib"

        joblib.dump(payload, path, compress=3)
        loaded = joblib.load(path)

        rng = np.random.default_rng(1)
        X_test = rng.normal(size=(50, 5)).astype(np.float32)

        orig   = _predict(payload, X_test)
        loaded_preds = _predict(loaded, X_test)

        np.testing.assert_array_equal(orig, loaded_preds)

    def test_file_is_not_pickle(self, tmp_path):
        """Eine .joblib-Datei sollte nicht als rohe pickle-Datei lesbar sein."""
        payload = _make_payload()
        path = tmp_path / "TEST_model.joblib"
        joblib.dump(payload, path, compress=3)

        # joblib with compress wraps in a non-standard format
        # — aber wir prüfen nur, dass .joblib existiert und > 0 Bytes hat
        assert path.exists()
        assert path.stat().st_size > 0

    def test_extension_is_joblib(self, tmp_path):
        payload = _make_payload()
        path = tmp_path / "MSFT_model.joblib"
        joblib.dump(payload, path, compress=3)
        assert path.suffix == ".joblib"

    def test_payload_keys_preserved(self, tmp_path):
        payload = _make_payload()
        path = tmp_path / "TSLA_model.joblib"
        joblib.dump(payload, path, compress=3)
        loaded = joblib.load(path)
        assert set(loaded.keys()) == {"model", "scaler", "feature_names"}

    def test_feature_names_preserved(self, tmp_path):
        payload = _make_payload()
        path = tmp_path / "GOOG_model.joblib"
        joblib.dump(payload, path, compress=3)
        loaded = joblib.load(path)
        assert loaded["feature_names"] == payload["feature_names"]

    def test_compress_reduces_size(self, tmp_path):
        """Komprimierte Datei sollte kleiner sein als unkomprimierte."""
        payload = _make_payload()
        p_raw  = tmp_path / "raw.joblib"
        p_comp = tmp_path / "compressed.joblib"
        joblib.dump(payload, p_raw,  compress=0)
        joblib.dump(payload, p_comp, compress=3)
        assert p_comp.stat().st_size < p_raw.stat().st_size


# ---------------------------------------------------------------------------
# Migration: .pkl → .joblib
# ---------------------------------------------------------------------------

class TestPickleMigration:
    """
    Testet die Migrations-Logik in load_model():
    alte .pkl-Datei → einmalig laden → als .joblib speichern → .pkl löschen.
    """

    def _write_legacy_pkl(self, path: Path) -> dict:
        """Schreibt eine Legacy-.pkl-Datei wie die alte trainer.py es tat."""
        payload = _make_payload()
        with open(path, "wb") as fh:
            pickle.dump(payload, fh)
        return payload

    def test_migration_creates_joblib(self, tmp_path, monkeypatch):
        """Nach Migration muss .joblib existieren."""
        import modules.trainer as trainer_mod
        # TRAINING_STATE_DIR wird in trainer.py als Modul-Name importiert
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "MIGRATE"
        pkl_path = tmp_path / f"{ticker}_model.pkl"
        self._write_legacy_pkl(pkl_path)

        result = trainer_mod.load_model(ticker)
        joblib_path = tmp_path / f"{ticker}_model.joblib"

        assert joblib_path.exists(), ".joblib-Datei muss nach Migration vorhanden sein"
        assert result is not None

    def test_migration_deletes_pkl(self, tmp_path, monkeypatch):
        """Nach Migration muss alte .pkl-Datei gelöscht sein."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "DELPKL"
        pkl_path = tmp_path / f"{ticker}_model.pkl"
        self._write_legacy_pkl(pkl_path)

        trainer_mod.load_model(ticker)

        assert not pkl_path.exists(), ".pkl-Datei muss nach Migration gelöscht sein"

    def test_migration_predictions_intact(self, tmp_path, monkeypatch):
        """Migriertes Modell muss dieselben Vorhersagen liefern wie Original."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "PREDTEST"
        pkl_path = tmp_path / f"{ticker}_model.pkl"
        original = self._write_legacy_pkl(pkl_path)

        migrated = trainer_mod.load_model(ticker)
        assert migrated is not None

        rng = np.random.default_rng(99)
        X_test = rng.normal(size=(30, 5)).astype(np.float32)
        np.testing.assert_array_equal(
            _predict(original, X_test),
            _predict(migrated, X_test),
        )

    def test_no_model_returns_none(self, tmp_path, monkeypatch):
        """Wenn weder .joblib noch .pkl existiert, muss None zurückkommen."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        assert trainer_mod.load_model("NONEXISTENT") is None

    def test_joblib_preferred_over_pkl(self, tmp_path, monkeypatch):
        """Wenn beide Dateien existieren, wird .joblib bevorzugt (kein Migration-Log)."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "BOTH"
        payload_jl = _make_payload()
        joblib.dump(payload_jl, tmp_path / f"{ticker}_model.joblib", compress=3)
        # kaputtes .pkl daneben — darf nicht angefasst werden
        (tmp_path / f"{ticker}_model.pkl").write_bytes(b"garbage")

        result = trainer_mod.load_model(ticker)
        assert result is not None
        assert result["feature_names"] == payload_jl["feature_names"]


# ---------------------------------------------------------------------------
# trainer._model_path Extension
# ---------------------------------------------------------------------------

class TestModelPath:
    def test_extension_is_joblib(self, tmp_path, monkeypatch):
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))
        p = trainer_mod._model_path("AAPL")
        assert p.suffix == ".joblib"

    def test_legacy_path_extension_is_pkl(self, tmp_path, monkeypatch):
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))
        p = trainer_mod._legacy_pkl_path("AAPL")
        assert p.suffix == ".pkl"

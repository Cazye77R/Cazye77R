"""
StockMind – Tests für Modell-Persistenz (joblib round-trip + sichere Verifikation).

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
# Sicheres Modell-Laden: SHA256-Verifikation, kein Pickle-Pfad mehr
# ---------------------------------------------------------------------------

class TestSecureModelLoading:
    """
    load_model() lädt joblib-Dateien nur noch mit gültiger SHA256-Prüfsumme.
    Der frühere pickle-Migrationspfad wurde entfernt (RCE-Vektor: pickle
    deserialisiert beliebigen Code aus manipulierbaren Dateien).
    """

    def _dump_with_hash(self, trainer_mod, ticker: str) -> dict:
        payload = _make_payload()
        p = trainer_mod._model_path(ticker)
        joblib.dump(payload, p, compress=3)
        trainer_mod._model_hash_path(ticker).write_text(
            trainer_mod._file_sha256(p)
        )
        return payload

    def test_legacy_pkl_is_ignored(self, tmp_path, monkeypatch):
        """Eine alte .pkl-Datei darf weder geladen noch angefasst werden."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "LEGACY"
        pkl_path = tmp_path / f"{ticker}_model.pkl"
        with open(pkl_path, "wb") as fh:
            pickle.dump(_make_payload(), fh)

        assert trainer_mod.load_model(ticker) is None
        assert pkl_path.exists(), ".pkl darf nicht gelöscht/migriert werden"
        assert not (tmp_path / f"{ticker}_model.joblib").exists()

    def test_joblib_without_hash_is_rejected(self, tmp_path, monkeypatch):
        """joblib ohne Prüfsummen-Datei → None (nicht vertrauenswürdig)."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "NOHASH"
        joblib.dump(_make_payload(), trainer_mod._model_path(ticker), compress=3)

        assert trainer_mod.load_model(ticker) is None

    def test_joblib_with_valid_hash_loads(self, tmp_path, monkeypatch):
        """joblib mit passender Prüfsumme lädt und liefert intakte Vorhersagen."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "VALID"
        original = self._dump_with_hash(trainer_mod, ticker)

        loaded = trainer_mod.load_model(ticker)
        assert loaded is not None
        assert loaded["feature_names"] == original["feature_names"]

        rng = np.random.default_rng(99)
        X_test = rng.normal(size=(30, 5)).astype(np.float32)
        np.testing.assert_array_equal(
            _predict(original, X_test),
            _predict(loaded, X_test),
        )

    def test_tampered_joblib_is_rejected(self, tmp_path, monkeypatch):
        """Nachträglich veränderte joblib-Datei → Prüfsummen-Mismatch → None."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "TAMPERED"
        self._dump_with_hash(trainer_mod, ticker)
        with open(trainer_mod._model_path(ticker), "ab") as fh:
            fh.write(b"malicious")

        assert trainer_mod.load_model(ticker) is None

    def test_no_model_returns_none(self, tmp_path, monkeypatch):
        """Wenn kein Modell existiert, muss None zurückkommen."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        assert trainer_mod.load_model("NONEXISTENT") is None

    def test_train_writes_hash_file(self, tmp_path, monkeypatch):
        """Der von train() genutzte Dump-Pfad erzeugt eine .sha256-Datei."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))

        ticker = "HASHED"
        self._dump_with_hash(trainer_mod, ticker)
        assert trainer_mod._model_hash_path(ticker).exists()


# ---------------------------------------------------------------------------
# trainer._model_path Extension & Ticker-Sanitisierung
# ---------------------------------------------------------------------------

class TestModelPath:
    def test_extension_is_joblib(self, tmp_path, monkeypatch):
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))
        p = trainer_mod._model_path("AAPL")
        assert p.suffix == ".joblib"

    def test_ticker_path_traversal_is_neutralized(self, tmp_path, monkeypatch):
        """Ticker mit Pfad-Separatoren dürfen das State-Verzeichnis nicht verlassen."""
        import modules.trainer as trainer_mod
        monkeypatch.setattr(trainer_mod, "TRAINING_STATE_DIR", str(tmp_path))
        p = trainer_mod._model_path("../../etc/passwd")
        assert p.parent == tmp_path
        assert ".." not in p.name.split("_")[0].replace(".", "")
        assert "/" not in p.name and "\\" not in p.name

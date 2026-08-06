import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


@pytest.fixture
def pm(tmp_path, monkeypatch):
    """profile_manager pointed at a throwaway HANDCURSOR_HOME."""
    monkeypatch.setenv("HANDCURSOR_HOME", str(tmp_path))
    import profile_manager
    import importlib
    importlib.reload(profile_manager)
    return profile_manager


def _settings(**over):
    data = {
        "smooth_factor": 0.4, "pinch_threshold": 0.03, "click_cooldown": 0.3,
        "scroll_sensitivity": 8, "drag_threshold": 0.25,
        "double_click_window": 0.3, "map_x": (0.08, 0.92), "map_y": (0.05, 0.95),
    }
    data.update(over)
    return data


class TestRoundTrip:
    def test_save_then_load_preserves_all_settings(self, pm):
        pm.save_profile("p", {"name": "P", **_settings()})
        loaded = pm.load_profile("p")
        for key in config.SETTING_KEYS:
            assert key in loaded, f"{key} ging beim Speichern verloren"

    def test_map_ranges_survive_round_trip(self, pm):
        pm.save_profile("p", {"name": "P", **_settings()})
        loaded = pm.load_profile("p")
        assert loaded["map_x"] == (0.08, 0.92)
        assert loaded["map_y"] == (0.05, 0.95)

    def test_save_writes_into_user_dir(self, pm, tmp_path):
        path = pm.save_profile("p", {"name": "P", **_settings()})
        assert path == tmp_path / "profiles" / "p.json"
        assert path.is_file()

    def test_creates_nested_directory(self, pm, tmp_path):
        assert not (tmp_path / "profiles").exists()
        pm.save_profile("p", _settings())
        assert (tmp_path / "profiles").is_dir()


class TestListing:
    def test_empty_when_nothing_saved(self, pm):
        assert pm.list_profiles() == []

    def test_lists_saved_profiles_sorted(self, pm):
        for name in ("zulu", "alpha"):
            pm.save_profile(name, _settings())
        assert pm.list_profiles() == ["alpha", "zulu"]

    def test_active_pointer_is_not_listed_as_a_profile(self, pm):
        pm.save_profile("p", _settings())
        pm.set_active_profile_name("p")
        assert pm.list_profiles() == ["p"]


class TestActivePointer:
    def test_none_before_anything_is_set(self, pm):
        assert pm.get_active_profile_name() is None

    def test_round_trip(self, pm):
        pm.set_active_profile_name("gaming")
        assert pm.get_active_profile_name() == "gaming"

    def test_survives_corrupt_pointer_file(self, pm, tmp_path):
        directory = tmp_path / "profiles"
        directory.mkdir(parents=True)
        (directory / "active_profile.json").write_text("{ kaputt")
        assert pm.get_active_profile_name() is None


class TestErrors:
    def test_missing_profile_raises_filenotfound(self, pm):
        with pytest.raises(FileNotFoundError):
            pm.load_profile("gibtsnicht")

    def test_empty_name_raises_valueerror(self, pm):
        with pytest.raises(ValueError):
            pm.load_profile("")

    def test_path_separator_in_name_is_rejected(self, pm):
        with pytest.raises(ValueError):
            pm.save_profile("../escape", _settings())

    def test_unknown_keys_are_not_persisted(self, pm):
        pm.save_profile("p", {**_settings(), "voellig_unbekannt": 123})
        raw = json.loads((pm.user_dir() / "p.json").read_text())
        assert "voellig_unbekannt" not in raw

    def test_malformed_value_is_skipped_not_fatal(self, pm):
        pm.user_dir().mkdir(parents=True)
        (pm.user_dir() / "p.json").write_text(json.dumps(
            {"name": "P", "smooth_factor": "keine-zahl", "pinch_threshold": 0.05}))
        loaded = pm.load_profile("p")
        assert "smooth_factor" not in loaded
        assert loaded["pinch_threshold"] == 0.05

    def test_degenerate_map_range_is_skipped(self, pm):
        # hi <= lo would divide by zero in the coordinate mapping
        pm.save_profile("p", {**_settings(), "map_x": (0.5, 0.5)})
        assert "map_x" not in pm.load_profile("p")

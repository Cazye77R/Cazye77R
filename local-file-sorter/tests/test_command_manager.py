"""Tests for CommandManager – saved commands / rule profiles (target_folder)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.commands.manager import Command, CommandManager


@pytest.fixture()
def mgr(tmp_path: Path) -> CommandManager:
    return CommandManager(commands_dir=tmp_path)


def test_save_and_load_roundtrip_without_target_folder(mgr: CommandManager) -> None:
    cmd = Command(name="Fotos", description="", prompt_text="Sortiere nach Datum",
                  default_recursive=True)
    mgr.save_command(cmd)
    loaded = mgr.load_command("fotos")
    assert loaded.prompt_text == "Sortiere nach Datum"
    assert loaded.default_recursive is True
    assert loaded.target_folder == ""


def test_save_and_load_roundtrip_with_target_folder(mgr: CommandManager) -> None:
    cmd = Command(name="Downloads-Profil", prompt_text="Sortiere nach Dateiendung",
                  target_folder="/home/user/Downloads")
    mgr.save_command(cmd)
    loaded = mgr.load_command("downloads_profil")
    assert loaded.target_folder == "/home/user/Downloads"


def test_list_commands_exposes_target_folder(mgr: CommandManager) -> None:
    mgr.save_command(Command(name="Mit Profil", prompt_text="x",
                              target_folder="/tmp/ziel"))
    mgr.save_command(Command(name="Ohne Profil", prompt_text="y"))
    metas = {m.name: m for m in mgr.list_commands()}
    assert metas["Mit Profil"].target_folder == "/tmp/ziel"
    assert metas["Ohne Profil"].target_folder == ""


def test_legacy_yaml_without_target_folder_field_loads_fine(mgr: CommandManager, tmp_path: Path) -> None:
    """Older command files saved before this field existed must still load."""
    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(
        "name: Legacy\ndescription: ''\nprompt_text: Sortiere\n"
        "default_recursive: false\ncreated_at: '2024-01-01T00:00:00'\n",
        encoding="utf-8",
    )
    loaded = mgr.load_command("legacy")
    assert loaded.target_folder == ""
    assert loaded.prompt_text == "Sortiere"

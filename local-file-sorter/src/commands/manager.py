"""Custom command persistence – YAML store in config/commands/."""
from __future__ import annotations

import datetime as dt
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

_COMMANDS_DIR = Path(__file__).parent.parent.parent / "config" / "commands"
_TRASH_DIR    = _COMMANDS_DIR / "_trash"


def make_slug(name: str) -> str:
    """Lowercase filename slug; resolves German umlauts before stripping."""
    s = name
    for ch, rep in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                    ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue")):
        s = s.replace(ch, rep)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "befehl"


@dataclass
class CommandMeta:
    name: str
    slug: str
    description: str
    created_at: str


@dataclass
class Command:
    name: str
    description: str = ""
    prompt_text: str = ""
    default_recursive: bool = False
    created_at: str = ""


class CommandManager:
    def __init__(self, commands_dir: Path = _COMMANDS_DIR) -> None:
        self._dir = commands_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def list_commands(self) -> list[CommandMeta]:
        metas: list[CommandMeta] = []
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                data: dict = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                metas.append(CommandMeta(
                    name=data.get("name", path.stem),
                    slug=path.stem,
                    description=data.get("description", ""),
                    created_at=str(data.get("created_at", "")),
                ))
            except Exception:
                continue
        return metas

    def load_command(self, slug: str) -> Command:
        path = self._dir / f"{slug}.yaml"
        data: dict = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return Command(
            name=data.get("name", slug),
            description=data.get("description", ""),
            prompt_text=data.get("prompt_text", ""),
            default_recursive=bool(data.get("default_recursive", False)),
            created_at=str(data.get("created_at", "")),
        )

    def save_command(self, command: Command) -> Path:
        if not command.created_at:
            command.created_at = dt.datetime.now().isoformat(timespec="seconds")
        slug = make_slug(command.name)
        path = self._dir / f"{slug}.yaml"
        payload = {
            "name":              command.name,
            "description":       command.description,
            "prompt_text":       command.prompt_text,
            "default_recursive": command.default_recursive,
            "created_at":        command.created_at,
        }
        path.write_text(
            yaml.dump(payload, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        return path

    def delete_command_file(self, slug: str) -> bool:
        """Move the YAML config to _trash/. Does NOT touch any user files."""
        src = self._dir / f"{slug}.yaml"
        if not src.exists():
            return False
        trash = self._dir / "_trash"
        trash.mkdir(parents=True, exist_ok=True)
        dst = trash / f"{slug}.yaml"
        if dst.exists():
            ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = trash / f"{slug}_{ts}.yaml"
        shutil.move(str(src), str(dst))
        return True

"""LLM smoke-test – zeigt den von Ollama generierten Plan, führt NICHTS aus.

Voraussetzung: Ollama läuft und qwen2.5:7b-instruct-q4_K_M ist gepullt.

    python scripts/test_llm.py           # echter Ollama-Aufruf
    python scripts/test_llm.py --mock    # Mock-Plan (ohne Ollama)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.scanner import scan_folder
from src.llm.ollama_client import OllamaClient, PlanValidationError
from src.llm.schemas import OpType, SortAction, SortPlan

console = Console()
TMP = Path("./tmp_test")
USER_COMMAND = "Sortiere nach Dateiendung in Unterordner"


def load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with cfg_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ensure_test_files() -> None:
    """Legt Dummy-Dateien an, falls tmp_test noch nicht existiert."""
    if TMP.exists() and any(TMP.iterdir()):
        return
    TMP.mkdir(parents=True, exist_ok=True)
    samples = {
        "report_2024.pdf": 1_000,
        "photo_vacation.jpg": 2_000,
        "notes.txt": 500,
        "budget.xlsx": 800,
        "archive.zip": 5_000,
    }
    for name, size in samples.items():
        (TMP / name).write_bytes(b"x" * size)
    console.print(f"[dim]Dummy-Dateien in {TMP} angelegt.[/dim]")


def print_plan(plan) -> None:
    console.print()
    console.print(Panel(f"[bold]{plan.summary}[/bold]", title="Plan-Zusammenfassung"))

    table = Table(title="Geplante Aktionen", show_lines=True, expand=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Op", style="cyan", width=14)
    table.add_column("Source", style="yellow")
    table.add_column("Destination", style="green")
    table.add_column("Grund", style="white")

    for i, action in enumerate(plan.actions, 1):
        src_str = str(action.source) if action.source else "[dim]–[/dim]"
        op_color = "cyan" if action.op_type == OpType.create_folder else "magenta"
        table.add_row(
            str(i),
            f"[{op_color}]{action.op_type.value}[/{op_color}]",
            src_str,
            str(action.destination),
            action.reason,
        )

    console.print(table)
    console.print(
        f"\n[bold green]Gesamt:[/bold green] {len(plan.actions)} Aktion(en) – "
        f"[dim]nichts wird ausgeführt (Vorschau-Modus)[/dim]"
    )


def make_mock_plan(target_folder: Path) -> SortPlan:
    """Returns a hardcoded plan that mirrors what the LLM would produce."""
    tf = target_folder
    return SortPlan(
        summary="Dateien nach Dateiendung in Unterordner PDF, JPG, TXT, XLSX und ZIP sortiert.",
        actions=[
            SortAction(op_type=OpType.create_folder, source=None, destination=tf / "PDF",  reason="Ordner für PDF-Dateien"),
            SortAction(op_type=OpType.create_folder, source=None, destination=tf / "JPG",  reason="Ordner für JPEG-Bilder"),
            SortAction(op_type=OpType.create_folder, source=None, destination=tf / "TXT",  reason="Ordner für Textdateien"),
            SortAction(op_type=OpType.create_folder, source=None, destination=tf / "XLSX", reason="Ordner für Excel-Dateien"),
            SortAction(op_type=OpType.create_folder, source=None, destination=tf / "ZIP",  reason="Ordner für Archive"),
            SortAction(op_type=OpType.move, source=tf / "report_2024.pdf",    destination=tf / "PDF"  / "report_2024.pdf",    reason="PDF-Dokument"),
            SortAction(op_type=OpType.move, source=tf / "photo_vacation.jpg", destination=tf / "JPG"  / "photo_vacation.jpg", reason="JPEG-Bild"),
            SortAction(op_type=OpType.move, source=tf / "notes.txt",          destination=tf / "TXT"  / "notes.txt",          reason="Textdatei"),
            SortAction(op_type=OpType.move, source=tf / "budget.xlsx",        destination=tf / "XLSX" / "budget.xlsx",        reason="Excel-Tabelle"),
            SortAction(op_type=OpType.move, source=tf / "archive.zip",        destination=tf / "ZIP"  / "archive.zip",        reason="ZIP-Archiv"),
        ],
    )


def main() -> None:
    use_mock = "--mock" in sys.argv

    console.rule("[bold blue]LLM-Test – Sortierplan generieren")

    cfg = load_config()
    model = cfg["ollama"]["model"]
    base_url = cfg["ollama"]["base_url"]

    console.print(f"Modell : [cyan]{model}[/cyan]")
    console.print(f"Ollama : [cyan]{base_url}[/cyan]")
    console.print(f"Befehl : [yellow]{USER_COMMAND}[/yellow]")
    if use_mock:
        console.print("[yellow bold]Modus  : MOCK (kein echtes Ollama)[/yellow bold]\n")
    else:
        console.print()

    ensure_test_files()

    files = [f for f in scan_folder(TMP, recursive=False) if not f.is_dir]
    console.print(f"[dim]{len(files)} Datei(en) gescannt aus {TMP}[/dim]\n")

    if not files:
        console.print("[red]Keine Dateien zum Sortieren gefunden.[/red]")
        sys.exit(1)

    if use_mock:
        plan = make_mock_plan(TMP.resolve())
    else:
        client = OllamaClient(model=model, base_url=base_url)
        console.print("[dim]Sende Anfrage an Ollama …[/dim]")
        try:
            plan = client.generate_plan(
                files=files,
                user_command=USER_COMMAND,
                target_folder=TMP,
            )
        except PlanValidationError as exc:
            console.print(f"[red bold]Plan-Validierungsfehler:[/red bold]\n{exc}")
            sys.exit(1)
        except Exception as exc:
            console.print(f"[red bold]Unerwarteter Fehler:[/red bold] {exc}")
            sys.exit(1)

    print_plan(plan)


if __name__ == "__main__":
    main()

"""CLI smoke-test for the core modules. Run from the project root:

    python scripts/test_core.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

from src.core.logger import OperationLogger
from src.core.mover import create_folder, move_file
from src.core.scanner import scan_folder
from src.core.undo import undo_session

console = Console()
TMP = Path("./tmp_test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_dummy_files() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    files = {
        "report_2024.pdf": (1_000, 1_700_000_000),
        "photo_vacation.jpg": (2_000, 1_710_000_000),
        "notes.txt": (500, 1_720_000_000),
        "budget.xlsx": (800, 1_730_000_000),
        "archive.zip": (5_000, 1_740_000_000),
    }
    for name, (size, mtime) in files.items():
        p = TMP / name
        p.write_bytes(b"x" * size)
        os.utime(p, (mtime, mtime))
    console.print(f"[green]Dummy-Dateien erstellt in {TMP}[/green]")


def print_scan(files: list) -> None:
    table = Table(title="Scan-Ergebnis", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Ext", style="yellow")
    table.add_column("Größe (B)", justify="right")
    table.add_column("Geändert")
    for f in files:
        table.add_row(
            f.name,
            f.extension or "(kein)",
            str(f.size_bytes),
            f.modified.strftime("%Y-%m-%d"),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def main() -> None:
    console.rule("[bold blue]PHASE 1 – Setup & Scan")
    make_dummy_files()

    files = scan_folder(TMP, recursive=False)
    print_scan(files)
    assert len(files) == 5, f"Erwartet 5 Dateien, gefunden {len(files)}"

    log_dir = Path("./logs")
    logger = OperationLogger(log_dir)
    log_path = logger.get_session_path()
    console.print(f"[dim]Log: {log_path}[/dim]")

    console.rule("[bold blue]PHASE 2 – Ordner anlegen & Dateien verschieben")

    docs_dir = TMP / "Dokumente"
    ok = create_folder(docs_dir)
    logger.log_folder(docs_dir, ok)
    console.print(f"Ordner erstellt: {docs_dir} → {'OK' if ok else 'FEHLER'}")

    bilder_dir = TMP / "Bilder"
    ok2 = create_folder(bilder_dir)
    logger.log_folder(bilder_dir, ok2)

    moves = [
        (TMP / "report_2024.pdf", docs_dir / "report_2024.pdf"),
        (TMP / "budget.xlsx", docs_dir / "budget.xlsx"),
        (TMP / "photo_vacation.jpg", bilder_dir / "photo_vacation.jpg"),
    ]

    for src, dst in moves:
        result = move_file(src, dst)
        logger.log_move(result)
        status = "[green]OK[/green]" if result.success else f"[red]FEHLER: {result.error}[/red]"
        console.print(f"  {src.name} → {dst.parent.name}/ {status}")

    logger.close()

    console.rule("[bold blue]PHASE 3 – Undo")
    time.sleep(0.05)  # sicherstellen, dass close() fertig ist

    undo_results = undo_session(log_path)
    for r in undo_results:
        if r.success:
            console.print(f"  [green]Zurück:[/green] {r.destination_final.name}")
        else:
            console.print(f"  [red]Fehler:[/red] {r.error}")

    console.rule("[bold blue]PHASE 4 – Verifikation")

    expected_back = [TMP / "report_2024.pdf", TMP / "budget.xlsx", TMP / "photo_vacation.jpg"]
    all_ok = True
    for p in expected_back:
        if p.exists():
            console.print(f"  [green]✓[/green] {p.name} zurück am Ursprung")
        else:
            console.print(f"  [red]✗[/red] {p.name} FEHLT!")
            all_ok = False

    assert all_ok, "Nicht alle Dateien wurden erfolgreich zurückverschoben!"

    console.rule("[bold green]Alle Tests bestanden")

    # Aufräumen: nur Dateien verschieben, nie löschen
    console.print("[dim]Hinweis: tmp_test/ bleibt bestehen (kein automatisches Löschen).[/dim]")


if __name__ == "__main__":
    main()

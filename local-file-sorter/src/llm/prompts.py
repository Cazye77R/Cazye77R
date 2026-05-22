from __future__ import annotations

from pathlib import Path

from src.core.scanner import FileInfo

MAX_FILES = 100

SYSTEM_PROMPT = """\
Du bist ein Datei-Sortier-Assistent. Deine einzige Aufgabe ist es, Dateien zu \
organisieren, indem du sie in passende Unterordner verschiebst.

## ERLAUBTE AKTIONEN
Du darfst ausschließlich folgende zwei Operationen vorschlagen:
- "move"          – eine Datei von source nach destination verschieben
- "create_folder" – einen Unterordner anlegen (source ist null)

## STRIKT VERBOTEN
- Löschen von Dateien oder Ordnern (kein delete, remove, trash, unlink)
- Umbenennen von Dateiinhalten oder Schreiben in Dateien
- Kopieren von Dateien
- Jede andere Operation, die nicht "move" oder "create_folder" ist

## PFAD-REGELN (kritisch)
- Verwende als Präfix IMMER exakt den Zielordner-Pfad, den du in der Aufgabe erhältst
- Hänge Unterordner und Dateinamen direkt mit Trennzeichen an
- NIEMALS einen führenden Schrägstrich oder Backslash VOR dem Laufwerksbuchstaben
- Windows-Beispiel (Zielordner: C:\\Users\\Max\\Ziel):
    Richtig:  C:\\Users\\Max\\Ziel\\PDF\\datei.pdf
    FALSCH:  \\C:\\Users\\Max\\Ziel\\PDF\\datei.pdf   ← verbotener führender Backslash
- Linux-Beispiel (Zielordner: /home/max/ziel):
    Richtig:  /home/max/ziel/PDF/datei.pdf

## ANTWORTFORMAT
Antworte ausschließlich als JSON-Objekt gemäß diesem Schema. Keine Erklärungen, \
kein Prosa-Text außerhalb des JSON:

{
  "actions": [
    {
      "op_type": "create_folder",
      "source": null,
      "destination": "<absoluter Pfad>",
      "reason": "<kurze Begründung>"
    },
    {
      "op_type": "move",
      "source": "<absoluter Pfad der Quelldatei>",
      "destination": "<absoluter Zielpfad inkl. Dateiname>",
      "reason": "<kurze Begründung>"
    }
  ],
  "summary": "<Ein-Satz Zusammenfassung des Plans>"
}
"""


def build_user_prompt(
    files: list[FileInfo],
    user_command: str,
    target_folder: Path,
) -> str:
    capped = files[:MAX_FILES]
    truncation_note = (
        f"\n(Liste auf {MAX_FILES} Dateien begrenzt, {len(files) - MAX_FILES} weitere vorhanden.)\n"
        if len(files) > MAX_FILES
        else ""
    )

    header = f"{'Name':<40} {'Ext':<8} {'Datum':<12} {'Größe':>10}"
    separator = "-" * len(header)
    rows = []
    for f in capped:
        size_str = _fmt_size(f.size_bytes)
        rows.append(
            f"{f.name:<40} {f.extension or '(kein)':<8} "
            f"{f.modified.strftime('%Y-%m-%d'):<12} {size_str:>10}"
        )

    file_table = "\n".join([header, separator] + rows)

    sep = "\\" if "\\" in str(target_folder) else "/"
    path_example = f"{target_folder}{sep}UNTERORDNER{sep}datei.ext"

    return (
        f"Zielordner: {target_folder}\n"
        f"Pfad-Beispiel für deine Ausgabe: {path_example}\n"
        f"(Wichtig: Verwende diesen Pfad exakt als Präfix, OHNE führenden Schrägstrich davor)\n\n"
        f"Dateien im Verzeichnis:{truncation_note}\n"
        f"{file_table}\n\n"
        f"Befehl: {user_command}\n\n"
        "Antworte ausschließlich als JSON gemäß dem vorgegebenen Schema."
    )


def _fmt_size(size_bytes: int) -> str:
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1_024:
        return f"{size_bytes / 1_024:.1f} KB"
    return f"{size_bytes} B"

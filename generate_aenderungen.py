"""Generiert zufaellige Aenderungsmitteilungen fuer ein Konstruktionsbuero.

Aufruf:
    python generate_aenderungen.py --count 5000 --output-dir ./aenderungen
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import aenderungen_data as D


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _rand_date(rng: random.Random, start: date, end: date) -> str:
    delta = (end - start).days
    return (start + timedelta(days=rng.randint(0, delta))).strftime("%d.%m.%Y")


def _rand_name(rng: random.Random) -> str:
    return f"{rng.choice(D.VORNAMEN)} {rng.choice(D.NACHNAMEN)}"


def _rand_val(rng: random.Random, lo: float, hi: float, digits: int = 1) -> str:
    return str(round(rng.uniform(lo, hi), digits))


def _rand_sachnummer(rng: random.Random) -> str:
    return f"SNR-{rng.randint(100000, 999999)}-{rng.randint(10, 99)}"


def _rand_zeichnung(rng: random.Random) -> str:
    return f"ZNR-{rng.randint(10000, 99999)}"


def _rand_kdnr(rng: random.Random) -> str:
    return f"KD-{rng.randint(1000, 9999)}-{rng.randint(10, 99)}"


def _rand_gnr(rng: random.Random) -> str:
    return f"GB-{rng.randint(100, 999)}"


def _rand_doc_id(rng: random.Random) -> str:
    return f"DOC-{rng.randint(10000, 99999)}"


# ---------------------------------------------------------------------------
# Datenklasse fuer eine vollstaendige Aenderungsmitteilung
# ---------------------------------------------------------------------------

@dataclass
class NotificationSpec:
    index: int
    doc_nr: str
    datum: str
    bearbeiter: str
    freigabe_person: str
    abteilung: str
    thema: str
    prioritaet: str
    status: str
    sachnummer: str
    bauteil: str
    zeichnungsnummer: str
    revision: str
    rev_new: str
    baugruppe: str
    detail_level: str
    # Slot-Werte fuer Templates
    wert: str
    wert2: str
    mat1: str
    mat2: str
    norm: str
    kdnr: str
    gnr: str
    umsetzungstermin: str
    erstserienanw: str
    verantwortlich: str


# ---------------------------------------------------------------------------
# Factory: erzeugt eine zufaellige NotificationSpec
# ---------------------------------------------------------------------------

def build_spec(rng: random.Random, index: int, topics: list[str] | None = None) -> NotificationSpec:
    start = date(2020, 1, 1)
    end = date(2025, 6, 30)

    thema_pool = topics if topics else D.THEMEN
    thema = rng.choice(thema_pool)

    detail_level = rng.choices(D.DETAIL_LEVELS, weights=D.DETAIL_WEIGHTS, k=1)[0]

    bauteil = rng.choice(D.BAUTEILNAMEN)
    mat1, mat2 = rng.sample(D.WERKSTOFFE, 2)

    rev_letters = list("ABCDEFG")
    rev = rng.choice(rev_letters[:-1])
    rev_new = rev_letters[rev_letters.index(rev) + 1]

    datum = _rand_date(rng, start, end)
    utd = _rand_date(rng, date(2025, 7, 1), date(2026, 6, 30))
    esa = _rand_date(rng, date(2026, 1, 1), date(2026, 12, 31))

    return NotificationSpec(
        index=index,
        doc_nr=f"AM-{rng.randint(2020, 2025)}-{index:04d}",
        datum=datum,
        bearbeiter=_rand_name(rng),
        freigabe_person=_rand_name(rng),
        abteilung=rng.choice(D.ABTEILUNGEN),
        thema=thema,
        prioritaet=rng.choice(D.PRIORITAETEN),
        status=rng.choice(D.STATUSWERTE),
        sachnummer=_rand_sachnummer(rng),
        bauteil=bauteil,
        zeichnungsnummer=_rand_zeichnung(rng),
        revision=rev,
        rev_new=rev_new,
        baugruppe=rng.choice(D.BAUGRUPPEN),
        detail_level=detail_level,
        wert=_rand_val(rng, 0.2, 50.0),
        wert2=_rand_val(rng, 50.1, 200.0),
        mat1=mat1,
        mat2=mat2,
        norm=rng.choice(D.NORMEN),
        kdnr=_rand_kdnr(rng),
        gnr=_rand_gnr(rng),
        umsetzungstermin=utd,
        erstserienanw=esa,
        verantwortlich=_rand_name(rng),
    )


# ---------------------------------------------------------------------------
# Slot-Fueller: ersetzt Platzhalter in einem Template-Satz
# ---------------------------------------------------------------------------

def _fill(template: str, s: NotificationSpec) -> str:
    return template.format(
        bauteil=s.bauteil,
        wert=s.wert,
        wert2=s.wert2,
        mat1=s.mat1,
        mat2=s.mat2,
        norm=s.norm,
        kdnr=s.kdnr,
        gnr=s.gnr,
        znr=s.zeichnungsnummer,
        rev=s.revision,
        rev_new=s.rev_new,
        datum=s.datum,
    )


# ---------------------------------------------------------------------------
# Renderer: Header
# ---------------------------------------------------------------------------
_SEP = "=" * 60
_LINE = "-" * 60


def render_header(s: NotificationSpec) -> str:
    lines = [
        _SEP,
        " AENDERUNGSMITTEILUNG",
        _SEP,
        f"Dokument-Nr.:       {s.doc_nr}",
        f"Datum:              {s.datum}",
        f"Bearbeiter:         {s.bearbeiter}",
        f"Abteilung:          {s.abteilung}",
        f"Freigabe durch:     {s.freigabe_person}",
        f"Aenderungstyp:      {s.thema}",
        f"Prioritaet:         {s.prioritaet}",
        f"Status:             {s.status}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Renderer: Bauteil-Abschnitt
# ---------------------------------------------------------------------------

def render_bauteil(s: NotificationSpec) -> str:
    lines = [
        "",
        _LINE,
        "1. BETROFFENES BAUTEIL / BAUGRUPPE",
        _LINE,
        f"Sachnummer:             {s.sachnummer}",
        f"Bauteilbezeichnung:     {s.bauteil}",
        f"Zeichnungsnummer:       {s.zeichnungsnummer}",
        f"Revision (aktuell):     Rev. {s.revision}",
        f"Revision (neu):         Rev. {s.rev_new}",
        f"Baugruppe:              {s.baugruppe}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Renderer: Beschreibung der Aenderung
# ---------------------------------------------------------------------------

def render_beschreibung(s: NotificationSpec, rng: random.Random) -> str:
    pool = D.TOPIC_BESCHREIBUNG[s.thema]
    if s.detail_level == "kurz":
        count = 1
    elif s.detail_level == "mittel":
        count = rng.randint(2, 3)
    else:
        count = rng.randint(3, 4)

    sentences = rng.sample(pool, min(count, len(pool)))
    filled = [_fill(t, s) for t in sentences]

    lines = [
        "",
        _LINE,
        "2. AENDERUNGSBESCHREIBUNG",
        _LINE,
    ]
    lines += [f"   {sent}" for sent in filled]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Renderer: Begruendung / Ursachenanalyse  (nur mittel + lang)
# ---------------------------------------------------------------------------

def render_begruendung(s: NotificationSpec, rng: random.Random) -> str:
    pool = D.TOPIC_BEGRUENDUNG[s.thema]
    count = 1 if s.detail_level == "mittel" else rng.randint(2, 3)
    sentences = rng.sample(pool, min(count, len(pool)))
    filled = [_fill(t, s) for t in sentences]

    lines = [
        "",
        _LINE,
        "3. BEGRUENDUNG / URSACHENANALYSE",
        _LINE,
    ]
    lines += [f"   {sent}" for sent in filled]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Renderer: Technische Massnahmen
# ---------------------------------------------------------------------------

def render_massnahmen(s: NotificationSpec, rng: random.Random) -> str:
    pool = D.TOPIC_MASSNAHMEN[s.thema]
    if s.detail_level == "kurz":
        count = 2
    elif s.detail_level == "mittel":
        count = 3
    else:
        count = rng.randint(4, min(5, len(pool)))

    items = rng.sample(pool, min(count, len(pool)))
    filled = [_fill(t, s) for t in items]

    section_nr = "3" if s.detail_level == "kurz" else "4"
    lines = [
        "",
        _LINE,
        f"{section_nr}. TECHNISCHE MASSNAHMEN",
        _LINE,
    ]
    lines += [f"   - {item}" for item in filled]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Renderer: Betroffene Dokumente  (nur mittel + lang)
# ---------------------------------------------------------------------------

def render_dokumente(s: NotificationSpec, rng: random.Random) -> str:
    count = 2 if s.detail_level == "mittel" else rng.randint(3, 4)
    typen = rng.sample(D.DOKUMENTTYPEN, min(count, len(D.DOKUMENTTYPEN)))
    lines = [
        "",
        _LINE,
        "5. BETROFFENE DOKUMENTE",
        _LINE,
    ]
    for typ in typen:
        lines.append(f"   - {typ}: {_rand_doc_id(rng)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Renderer: Terminplanung  (nur lang)
# ---------------------------------------------------------------------------

def render_terminplanung(s: NotificationSpec) -> str:
    lines = [
        "",
        _LINE,
        "6. TERMINPLANUNG",
        _LINE,
        f"   Umsetzungsfrist:    {s.umsetzungstermin}",
        f"   Erstserienanw.:     {s.erstserienanw}",
        f"   Verantwortlich:     {s.verantwortlich}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Renderer: Freigabevermerk
# ---------------------------------------------------------------------------

def render_freigabe(s: NotificationSpec) -> str:
    section_nr = {"kurz": "4", "mittel": "6", "lang": "7"}[s.detail_level]
    lines = [
        "",
        _LINE,
        f"{section_nr}. FREIGABEVERMERK",
        _LINE,
        f"   Aenderung wurde durch {s.freigabe_person} ({s.abteilung}) geprueft und freigegeben.",
        "",
        "   Unterschrift: ___________________________   Datum: ________________",
        _SEP,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gesamter Renderer
# ---------------------------------------------------------------------------

def render_notification(s: NotificationSpec, rng: random.Random) -> str:
    parts = [
        render_header(s),
        render_bauteil(s),
        render_beschreibung(s, rng),
    ]

    if s.detail_level in ("mittel", "lang"):
        parts.append(render_begruendung(s, rng))

    parts.append(render_massnahmen(s, rng))

    if s.detail_level in ("mittel", "lang"):
        parts.append(render_dokumente(s, rng))

    if s.detail_level == "lang":
        parts.append(render_terminplanung(s))

    parts.append(render_freigabe(s))

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Datei-Generator
# ---------------------------------------------------------------------------

def generate_files(
    count: int,
    output_dir: Path,
    seed: int | None,
    topics: list[str] | None,
    prefix: str,
    start_index: int,
) -> None:
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    topic_counts: dict[str, int] = {}
    generated = 0
    i = start_index

    while generated < count:
        spec = build_spec(rng, i, topics)
        text = render_notification(spec, rng)
        filename = output_dir / f"{prefix}_{i:04d}.txt"
        filename.write_text(text, encoding="utf-8")

        topic_counts[spec.thema] = topic_counts.get(spec.thema, 0) + 1
        generated += 1
        i += 1

        if generated % 500 == 0:
            print(f"  ... {generated}/{count} Dateien erstellt")

    print(f"\nFertig: {generated} Dateien in '{output_dir}'")
    print("Verteilung nach Thema:")
    for thema, n in sorted(topic_counts.items()):
        print(f"  {thema:<30} {n:>5}")


# ---------------------------------------------------------------------------
# CLI-Einstiegspunkt
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generiert zufaellige deutsche Aenderungsmitteilungen fuer ein Konstruktionsbuero.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Beispiele:\n"
            "  python generate_aenderungen.py --count 100 --seed 42\n"
            "  python generate_aenderungen.py --count 5000 --output-dir ./aenderungen\n"
            "  python generate_aenderungen.py --count 200 --topics Kundenwunsch Fertigungsfehler\n"
        ),
    )
    parser.add_argument(
        "--count", type=int, default=100,
        help="Anzahl der zu erzeugenden Dateien (Standard: 100, Max: 9999)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("aenderungen"),
        help="Zielverzeichnis fuer die Ausgabedateien (Standard: ./aenderungen)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Zufalls-Seed fuer reproduzierbare Ergebnisse",
    )
    parser.add_argument(
        "--topics", nargs="+",
        choices=D.THEMEN,
        default=None,
        metavar="THEMA",
        help=(
            "Nur bestimmte Themen erzeugen. Moeglich: "
            + ", ".join(D.THEMEN)
        ),
    )
    parser.add_argument(
        "--prefix", type=str, default="aenderung",
        help="Dateinamens-Praefix (Standard: aenderung)",
    )
    parser.add_argument(
        "--start-index", type=int, default=1,
        help="Startnummer fuer Datei-Nummerierung (Standard: 1)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.count < 1 or args.count > 9999:
        raise SystemExit("Fehler: --count muss zwischen 1 und 9999 liegen.")

    print(f"Generiere {args.count} Aenderungsmitteilungen ...")
    print(f"  Ausgabeverzeichnis: {args.output_dir.resolve()}")
    print(f"  Seed:               {args.seed if args.seed is not None else 'zufaellig'}")
    print(f"  Themenfilter:       {args.topics if args.topics else 'alle'}")
    print(f"  Detailstufe:        zufaellig (30% kurz / 40% mittel / 30% lang)")
    print()

    generate_files(
        count=args.count,
        output_dir=args.output_dir,
        seed=args.seed,
        topics=args.topics,
        prefix=args.prefix,
        start_index=args.start_index,
    )


if __name__ == "__main__":
    main()

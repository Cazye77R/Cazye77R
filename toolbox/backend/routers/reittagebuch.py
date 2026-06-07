import io
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..database import get_db
from ..models import Eintrag, Tier, User, eintrag_tiere

router = APIRouter(prefix="/api/reittagebuch", tags=["reittagebuch"])


# ── Schemas ──────────────────────────────────────────────────────

class TierCreate(BaseModel):
    name: str
    typ: str
    emoji: str = "🐴"


class TierUpdate(BaseModel):
    name: Optional[str] = None
    typ: Optional[str] = None
    emoji: Optional[str] = None
    aktiv: Optional[bool] = None


class TierOut(BaseModel):
    id: int
    name: str
    typ: str
    emoji: str
    aktiv: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class EintragCreate(BaseModel):
    datum: date
    aktivitaet: str
    besonderheiten: Optional[str] = None
    anpassungen: Optional[str] = None
    anzahl_kinder: int = 0
    anzahl_jugendliche: int = 0
    tier_ids: list[int] = []


class EintragOut(BaseModel):
    id: int
    datum: date
    aktivitaet: str
    besonderheiten: Optional[str]
    anpassungen: Optional[str]
    anzahl_kinder: int
    anzahl_jugendliche: int
    tiere: list[TierOut]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WochenDurchschnitt(BaseModel):
    kinder: float
    jugendliche: float
    gesamt: float


class TierEinsatz(BaseModel):
    tier_id: int
    name: str
    emoji: str
    anzahl: int


class WocheVerlauf(BaseModel):
    kw: str
    kinder: int
    jugendliche: int


class StatsOut(BaseModel):
    gesamt_einheiten: int
    gesamt_kinder: int
    gesamt_jugendliche: int
    wochen_durchschnitt: WochenDurchschnitt
    tiere_einsaetze: list[TierEinsatz]
    wochen_verlauf: list[WocheVerlauf]


# ── Helpers ──────────────────────────────────────────────────────

def _resolve_tiere(user_id: int, tier_ids: list[int], db: Session) -> list[Tier]:
    """Gibt Tier-Objekte zurück, validiert Ownership. Leere Liste = kein Tier."""
    if not tier_ids:
        return []
    unique_ids = list(set(tier_ids))
    tiere = db.query(Tier).filter(Tier.id.in_(unique_ids), Tier.user_id == user_id).all()
    if len(tiere) != len(unique_ids):
        raise HTTPException(status_code=400, detail="Ein oder mehrere Tiere nicht gefunden")
    return tiere


def _eintraege_query(
    user_id: int,
    von: Optional[date],
    bis: Optional[date],
    tier_id: Optional[int],
    db: Session,
):
    q = (
        db.query(Eintrag)
        .options(selectinload(Eintrag.tiere))
        .filter(Eintrag.user_id == user_id)
    )
    if von:
        q = q.filter(Eintrag.datum >= von)
    if bis:
        q = q.filter(Eintrag.datum <= bis)
    if tier_id:
        q = q.filter(Eintrag.tiere.any(Tier.id == tier_id))
    return q


def _reload(eintrag_id: int, db: Session) -> Eintrag:
    """Lädt Eintrag mit Tieren für die Response."""
    return (
        db.query(Eintrag)
        .options(selectinload(Eintrag.tiere))
        .filter(Eintrag.id == eintrag_id)
        .first()
    )


# ── Tiere ────────────────────────────────────────────────────────

@router.get("/tiere", response_model=list[TierOut])
def list_tiere(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Tier)
        .filter(Tier.user_id == current_user.id)
        .order_by(Tier.aktiv.desc(), Tier.name)
        .all()
    )


@router.post("/tiere", response_model=TierOut, status_code=status.HTTP_201_CREATED)
def create_tier(
    body: TierCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tier = Tier(user_id=current_user.id, **body.model_dump())
    db.add(tier)
    db.commit()
    db.refresh(tier)
    return tier


@router.put("/tiere/{tier_id}", response_model=TierOut)
def update_tier(
    tier_id: int,
    body: TierUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tier = db.query(Tier).filter(Tier.id == tier_id, Tier.user_id == current_user.id).first()
    if not tier:
        raise HTTPException(status_code=404, detail="Tier nicht gefunden")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(tier, field, value)
    db.commit()
    db.refresh(tier)
    return tier


@router.delete("/tiere/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_tier(
    tier_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete: setzt aktiv=False statt zu löschen, damit historische Einträge erhalten bleiben."""
    tier = db.query(Tier).filter(Tier.id == tier_id, Tier.user_id == current_user.id).first()
    if not tier:
        raise HTTPException(status_code=404, detail="Tier nicht gefunden")
    tier.aktiv = False
    db.commit()


# ── Einträge ─────────────────────────────────────────────────────

@router.get("/eintraege", response_model=list[EintragOut])
def list_eintraege(
    von: Optional[date] = None,
    bis: Optional[date] = None,
    tier_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        _eintraege_query(current_user.id, von, bis, tier_id, db)
        .order_by(Eintrag.datum.desc(), Eintrag.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


@router.post("/eintraege", response_model=EintragOut, status_code=status.HTTP_201_CREATED)
def create_eintrag(
    body: EintragCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tiere = _resolve_tiere(current_user.id, body.tier_ids, db)
    eintrag = Eintrag(
        user_id=current_user.id,
        datum=body.datum,
        aktivitaet=body.aktivitaet,
        besonderheiten=body.besonderheiten,
        anpassungen=body.anpassungen,
        anzahl_kinder=body.anzahl_kinder,
        anzahl_jugendliche=body.anzahl_jugendliche,
        tiere=tiere,
    )
    db.add(eintrag)
    db.commit()
    return _reload(eintrag.id, db)


@router.put("/eintraege/{eintrag_id}", response_model=EintragOut)
def update_eintrag(
    eintrag_id: int,
    body: EintragCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    eintrag = (
        db.query(Eintrag)
        .options(selectinload(Eintrag.tiere))
        .filter(Eintrag.id == eintrag_id, Eintrag.user_id == current_user.id)
        .first()
    )
    if not eintrag:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    tiere = _resolve_tiere(current_user.id, body.tier_ids, db)

    eintrag.datum = body.datum
    eintrag.aktivitaet = body.aktivitaet
    eintrag.besonderheiten = body.besonderheiten
    eintrag.anpassungen = body.anpassungen
    eintrag.anzahl_kinder = body.anzahl_kinder
    eintrag.anzahl_jugendliche = body.anzahl_jugendliche
    eintrag.tiere = tiere
    eintrag.updated_at = datetime.utcnow()

    db.commit()
    return _reload(eintrag_id, db)


@router.delete("/eintraege/{eintrag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_eintrag(
    eintrag_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    eintrag = (
        db.query(Eintrag)
        .filter(Eintrag.id == eintrag_id, Eintrag.user_id == current_user.id)
        .first()
    )
    if not eintrag:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    db.delete(eintrag)
    db.commit()


# ── Auswertungen ─────────────────────────────────────────────────

@router.get("/stats", response_model=StatsOut)
def get_stats(
    von: Optional[date] = None,
    bis: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    eintraege = _eintraege_query(current_user.id, von, bis, None, db).all()

    gesamt_kinder = sum(e.anzahl_kinder for e in eintraege)
    gesamt_jugendliche = sum(e.anzahl_jugendliche for e in eintraege)
    gesamt_einheiten = len(eintraege)

    # Wochendurchschnitt über die tatsächliche Zeitspanne
    if eintraege:
        d_min = von or min(e.datum for e in eintraege)
        d_max = bis or max(e.datum for e in eintraege)
        num_weeks = max(1.0, (d_max - d_min).days / 7.0)
    else:
        num_weeks = 1.0

    wochen_durchschnitt = WochenDurchschnitt(
        kinder=round(gesamt_kinder / num_weeks, 1),
        jugendliche=round(gesamt_jugendliche / num_weeks, 1),
        gesamt=round(gesamt_einheiten / num_weeks, 1),
    )

    # Einsätze pro Tier (absteigende Häufigkeit)
    tier_counts: dict[int, dict] = {}
    for e in eintraege:
        for t in e.tiere:
            if t.id not in tier_counts:
                tier_counts[t.id] = {"tier_id": t.id, "name": t.name, "emoji": t.emoji, "anzahl": 0}
            tier_counts[t.id]["anzahl"] += 1
    tiere_einsaetze = sorted(tier_counts.values(), key=lambda x: x["anzahl"], reverse=True)

    # Verlauf pro Kalenderwoche (aufsteigend sortiert)
    wochen: dict[tuple, dict] = {}
    for e in eintraege:
        year, kw, _ = e.datum.isocalendar()
        key = (year, kw)
        if key not in wochen:
            wochen[key] = {"kw": f"KW {kw:02d}", "kinder": 0, "jugendliche": 0}
        wochen[key]["kinder"] += e.anzahl_kinder
        wochen[key]["jugendliche"] += e.anzahl_jugendliche
    wochen_verlauf = [wochen[k] for k in sorted(wochen)]

    return StatsOut(
        gesamt_einheiten=gesamt_einheiten,
        gesamt_kinder=gesamt_kinder,
        gesamt_jugendliche=gesamt_jugendliche,
        wochen_durchschnitt=wochen_durchschnitt,
        tiere_einsaetze=[TierEinsatz(**t) for t in tiere_einsaetze],
        wochen_verlauf=[WocheVerlauf(**w) for w in wochen_verlauf],
    )


# ── Excel-Export ─────────────────────────────────────────────────

@router.get("/export")
def export_xlsx(
    von: Optional[date] = None,
    bis: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    eintraege = (
        _eintraege_query(current_user.id, von, bis, None, db)
        .order_by(Eintrag.datum.asc())
        .all()
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Reittagebuch"

    headers = ["Datum", "Tiere", "Aktivität", "Kinder", "Jugendliche", "Besonderheiten", "Anpassungen"]
    ws.append(headers)

    # Kopfzeile formatieren
    header_fill = PatternFill(start_color="5B7C5E", end_color="5B7C5E", fill_type="solid")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", wrap_text=False)

    # Datenzeilen
    for e in eintraege:
        tiere_str = ", ".join(f"{t.emoji} {t.name}" for t in e.tiere) if e.tiere else "—"
        ws.append([
            e.datum,
            tiere_str,
            e.aktivitaet,
            e.anzahl_kinder,
            e.anzahl_jugendliche,
            e.besonderheiten or "",
            e.anpassungen or "",
        ])

    # Datum-Spalte formatieren
    for row in ws.iter_rows(min_row=2, min_col=1, max_col=1):
        for cell in row:
            cell.number_format = "DD.MM.YYYY"

    # Spaltenbreiten
    for i, width in enumerate([13, 22, 45, 9, 14, 38, 38], start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # Kopfzeile einfrieren
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    von_str = von.isoformat() if von else "alle"
    bis_str = bis.isoformat() if bis else "alle"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="reittagebuch_{von_str}_{bis_str}.xlsx"'},
    )

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

BRANDING_KEY = "branding"

BRANDING_DEFAULTS = {
    "app_name": "Hofblick",
    "animation_theme": "hofblick",
    "custom_subtitle": None,
}


def get_setting(db: Session, key: str, default=None):
    row = db.query(models.AppSettings).filter(models.AppSettings.key == key).first()
    if row is None:
        return default
    return json.loads(row.value)


def set_setting(db: Session, key: str, value, user_id: int):
    row = db.query(models.AppSettings).filter(models.AppSettings.key == key).first()
    serialized = json.dumps(value)
    if row is None:
        row = models.AppSettings(key=key, value=serialized, updated_by=user_id)
        db.add(row)
    else:
        row.value = serialized
        row.updated_by = user_id
        row.updated_at = datetime.utcnow()
    db.commit()


class BrandingConfig(BaseModel):
    app_name: str
    animation_theme: str
    custom_subtitle: Optional[str] = None


@router.get("/branding", response_model=BrandingConfig)
def get_branding(db: Session = Depends(get_db)):
    data = get_setting(db, BRANDING_KEY, BRANDING_DEFAULTS)
    return {**BRANDING_DEFAULTS, **data}


@router.put("/branding", response_model=BrandingConfig)
def update_branding(
    body: BrandingConfig,
    current_user: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    valid_themes = {"hofblick", "koppel", "hufspur", "stallgefluester"}
    if body.animation_theme not in valid_themes:
        raise HTTPException(status_code=400, detail=f"Ungültiges Theme. Erlaubt: {valid_themes}")
    payload = body.model_dump()
    set_setting(db, BRANDING_KEY, payload, current_user.id)
    return payload

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_admin, get_current_user
from ..database import get_db
from ..modules import MODULES

router = APIRouter(prefix="/api/modules", tags=["modules"])


class ModuleOut(BaseModel):
    key: str
    name: str
    description: str
    emoji: str
    route: str


class UserModulesUpdate(BaseModel):
    module_keys: List[str]


@router.get("", response_model=List[ModuleOut])
def get_my_modules(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.UserModuleAccess)
        .filter(models.UserModuleAccess.user_id == current_user.id)
        .all()
    )
    keys = {r.module_key for r in rows}
    return [MODULES[k] for k in MODULES if k in keys]


@router.get("/users/{user_id}", response_model=List[str])
def get_user_modules(
    user_id: int,
    _: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.UserModuleAccess)
        .filter(models.UserModuleAccess.user_id == user_id)
        .all()
    )
    return [r.module_key for r in rows]


@router.put("/users/{user_id}", status_code=204)
def set_user_modules(
    user_id: int,
    body: UserModulesUpdate,
    _: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    valid_keys = {k for k in body.module_keys if k in MODULES}

    db.query(models.UserModuleAccess).filter(
        models.UserModuleAccess.user_id == user_id
    ).delete()

    for key in valid_keys:
        db.add(models.UserModuleAccess(user_id=user_id, module_key=key))

    db.commit()

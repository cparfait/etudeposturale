"""Équipement et premier lancement (onboarding)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from posturale import equipment

router = APIRouter(prefix="/api/equipment")


@router.get("")
def get_equipment() -> dict:
    return equipment.view()


class EquipmentIn(BaseModel):
    items: Optional[dict[str, Optional[bool]]] = None
    onboarding_fait: Optional[bool] = None


@router.put("")
def put_equipment(data: EquipmentIn) -> dict:
    return equipment.view(equipment.save(data.model_dump(exclude_unset=True)))

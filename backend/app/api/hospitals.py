from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_roles
from app.services.fleet import get_hospitals


router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


class Hospital(BaseModel):
    id: int
    name: str
    available_beds: int
    total_beds: int
    specializations: list[str]
    phone: str
    lat: float
    lng: float


@router.get("", response_model=list[Hospital])
async def list_hospitals(_user=Depends(require_roles("staff"))) -> list[Hospital]:
    return [Hospital(**h) for h in get_hospitals()]

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user, require_roles
from app.services.fleet import get_hospitals, hospital_directory, update_hospital_beds


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


class HospitalOption(BaseModel):
    id: int
    name: str


class BedsBody(BaseModel):
    available_beds: int = Field(..., ge=0)
    total_beds: int | None = Field(default=None, ge=1)


def _staff_hospital_id(user: dict) -> int | None:
    raw = (user.get("profile") or {}).get("hospital_id")
    try:
        return int(raw) if raw is not None and raw != "" else None
    except (TypeError, ValueError):
        return None


@router.get("/directory", response_model=list[HospitalOption])
async def list_hospital_options(_user=Depends(get_current_user)) -> list[HospitalOption]:
    return [HospitalOption(**h) for h in hospital_directory()]


@router.get("", response_model=list[Hospital])
async def list_hospitals(_user=Depends(require_roles("staff", "driver", "doctor"))) -> list[Hospital]:
    return [Hospital(**h) for h in get_hospitals()]


@router.patch("/{hospital_id}/beds", response_model=Hospital)
async def patch_hospital_beds(
    hospital_id: int,
    body: BedsBody,
    user: dict = Depends(require_roles("staff", "doctor")),
) -> Hospital:
    role = (user.get("profile") or {}).get("role")
    assigned = _staff_hospital_id(user)
    if role == "main_admin":
        pass
    elif assigned is not None and assigned != hospital_id:
        raise HTTPException(status_code=403, detail="You can only update beds at your own hospital")
    elif role == "doctor" and assigned is None:
        raise HTTPException(status_code=403, detail="You can only update beds at your own hospital")
    try:
        row = update_hospital_beds(hospital_id, body.available_beds, body.total_beds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Hospital(**row)

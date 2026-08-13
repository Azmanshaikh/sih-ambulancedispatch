from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


class Hospital(BaseModel):
    id: int
    name: str
    available_beds: int
    total_beds: int
    specializations: list[str]
    phone: str


@router.get("", response_model=list[Hospital])
async def list_hospitals() -> list[Hospital]:
    return [
        Hospital(
            id=1,
            name="City General Hospital",
            available_beds=12,
            total_beds=50,
            specializations=["Trauma", "Cardiac"],
            phone="555-0101",
        )
    ]

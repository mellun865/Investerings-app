from typing import Dict

from fastapi import APIRouter, Depends

from backend.deps import get_user_id
from backend.schemas import Bevakning, Bolag
from services import persistence_service

router = APIRouter(tags=["portfölj"])


@router.get("/portfolj", response_model=Dict[str, Bolag])
def hamta_portfolj(user_id: str = Depends(get_user_id)):
    return persistence_service._ladda(
        persistence_service.PORTFOLJ_FIL, "portfolj.json",
        dict(persistence_service.STARTPORTFOLJ), user_id,
    )


@router.put("/portfolj", response_model=Dict[str, Bolag])
def spara_portfolj(portfolj: Dict[str, Bolag], user_id: str = Depends(get_user_id)):
    data = {namn: bolag.model_dump() for namn, bolag in portfolj.items()}
    persistence_service._spara(data, persistence_service.PORTFOLJ_FIL, "portfolj.json", user_id)
    return data


@router.get("/bevakning", response_model=Dict[str, Bevakning])
def hamta_bevakning(user_id: str = Depends(get_user_id)):
    return persistence_service._ladda(
        persistence_service.BEVAKNING_FIL, "bevakning.json", {}, user_id,
    )


@router.put("/bevakning", response_model=Dict[str, Bevakning])
def spara_bevakning(bevakning: Dict[str, Bevakning], user_id: str = Depends(get_user_id)):
    data = {namn: b.model_dump() for namn, b in bevakning.items()}
    persistence_service._spara(data, persistence_service.BEVAKNING_FIL, "bevakning.json", user_id)
    return data

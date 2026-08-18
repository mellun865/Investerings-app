from typing import List, Optional

from fastapi import APIRouter, Depends

from backend.deps import get_user_id
from backend.schemas import HistorikRad
from services import history_service, persistence_service

router = APIRouter(tags=["historik"])


@router.get("/historik", response_model=List[HistorikRad])
def hamta_historik(user_id: str = Depends(get_user_id)):
    return persistence_service._ladda(
        persistence_service.HISTORIK_FIL, "historik.json", [], user_id,
    )


@router.post("/historik/registrera", response_model=Optional[List[HistorikRad]])
def registrera_dagens_varde(user_id: str = Depends(get_user_id)):
    """Räknar ut och sparar dagens portföljvärde (samma logik som körs
    automatiskt vid varje sidladdning i Streamlit-appen). Returnerar None
    om portföljen är tom eller inget värde kunde räknas fram."""
    portfolj = persistence_service._ladda(
        persistence_service.PORTFOLJ_FIL, "portfolj.json",
        dict(persistence_service.STARTPORTFOLJ), user_id,
    )
    transaktioner = persistence_service._ladda(
        persistence_service.TRANSAKTIONER_FIL, "transaktioner.json", [], user_id,
    )
    historik = persistence_service._ladda(
        persistence_service.HISTORIK_FIL, "historik.json", [], user_id,
    )
    ny_historik = history_service.registrera_dagens_varde(portfolj, transaktioner, historik)
    if ny_historik is None:
        return None
    persistence_service._spara(ny_historik, persistence_service.HISTORIK_FIL, "historik.json", user_id)
    return ny_historik

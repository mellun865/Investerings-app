from fastapi import APIRouter, Depends

from backend.deps import get_user_id
from services import ai_coach_service, persistence_service

router = APIRouter(prefix="/ai-coach", tags=["ai-coach"])


def _ladda_allt(user_id):
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
    return portfolj, transaktioner, historik


@router.get("/score")
def score(user_id: str = Depends(get_user_id)):
    portfolj, transaktioner, historik = _ladda_allt(user_id)
    return ai_coach_service.berakna_portfoljscore(portfolj, transaktioner, historik)


@router.post("/sammanfattning")
def sammanfattning(user_id: str = Depends(get_user_id)):
    """Kräver GEMINI_API_KEY - annars sätts fel-fältet, precis som i
    Streamlit-appen (aldrig en krasch, alltid en av text/fel)."""
    portfolj, transaktioner, historik = _ladda_allt(user_id)
    score_data = ai_coach_service.berakna_portfoljscore(portfolj, transaktioner, historik)
    text, fel = ai_coach_service.generera_ai_sammanfattning(portfolj, score_data)
    return {"text": text, "fel": fel, "score_data": score_data}

from fastapi import APIRouter

from backend.schemas import Nyhet
from services import sentiment_service

router = APIRouter(prefix="/nyheter", tags=["nyheter"])


@router.get("/{bolag}")
def nyheter(bolag: str, sokterm: str, max_antal: int = 8):
    traffar = sentiment_service.hamta_nyheter_for_bolag(sokterm, max_antal=max_antal)
    return [
        {**n, "relevant": sentiment_service.ar_troligen_relevant(bolag, n["titel"])}
        for n in traffar
    ]


@router.post("/{bolag}/sammanfatta")
def sammanfatta(bolag: str, nyhet: Nyhet):
    """Försöker sammanfatta hela artikeln, faller tillbaka på ren
    rubriktolkning om det inte går - se sentiment_service för detaljer.
    `helartikel` i svaret talar om vilket av de två man fick."""
    text, fel, helartikel = sentiment_service.generera_nyhetssammanfattning(bolag, nyhet.model_dump())
    return {"text": text, "fel": fel, "helartikel": helartikel}

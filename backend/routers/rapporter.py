from fastapi import APIRouter, HTTPException

from services import report_service

router = APIRouter(prefix="/rapporter", tags=["rapporter"])


@router.get("/{ticker}")
def rapport(ticker: str):
    data = report_service.hamta_kvartalsdata(ticker)
    if data is None:
        raise HTTPException(status_code=404, detail="Ingen kvartalsdata hittades")
    return data


@router.post("/{ticker}/sammanfattning")
def rapport_sammanfattning(ticker: str, bolag: str):
    data = report_service.hamta_kvartalsdata(ticker)
    text, fel = report_service.generera_rapportsammanfattning(bolag, data)
    return {"text": text, "fel": fel}

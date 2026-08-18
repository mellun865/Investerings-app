"""
Analysendpoints - tunna wrappers runt de rena, redan Streamlit-fria
tjänsterna (market_data/riktkurs/technical/risk/dividend_service).
Pandas-objekt (DataFrame/Series) konverteras till vanlig JSON här, eftersom
det inte finns någon UI-lada som gör det åt oss som i Streamlit-appen.
"""

import pandas as pd
from fastapi import APIRouter, HTTPException

from services.dividend_service import hamta_utdelningsanalys
from services.market_data_service import hamta_index_historik, hamta_kursdata
from services.riktkurs_service import hamta_riktkurs, sentiment_till_text
from services.risk_service import berakna_beta, berakna_max_drawdown, berakna_sharpe, berakna_volatilitet
from services.technical_service import (
    berakna_atr, berakna_bollinger, berakna_macd, berakna_rsi, golden_death_status,
)

router = APIRouter(tags=["analys"])


def _tal(varde):
    return None if varde is None or pd.isna(varde) else round(float(varde), 4)


def _hist_till_json(hist):
    return [
        {
            "datum": str(idx.date()),
            "open": _tal(rad["Open"]),
            "high": _tal(rad["High"]),
            "low": _tal(rad["Low"]),
            "close": _tal(rad["Close"]),
        }
        for idx, rad in hist.iterrows()
    ]


@router.get("/kursdata/{ticker}")
def kursdata(ticker: str):
    hist, info = hamta_kursdata(ticker)
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail="Ingen kursdata hittades")
    return {
        "historik": _hist_till_json(hist),
        "namn": info.get("shortName") or info.get("longName"),
        "valuta": info.get("currency"),
    }


@router.get("/riktkurser/{borskollen_namn}")
def riktkurser(borskollen_namn: str):
    data = hamta_riktkurs(borskollen_namn)
    if data is None:
        raise HTTPException(status_code=404, detail="Ingen riktkursdata hittades")
    if not data.get("ingen_bevakning"):
        data["sentiment_text"] = sentiment_till_text(data.get("sentiments"))
    return data


@router.get("/teknisk/{ticker}")
def teknisk(ticker: str):
    hist, _ = hamta_kursdata(ticker)
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail="Ingen kursdata hittades")
    close = hist["Close"]
    macd, signal, _diff = berakna_macd(close)
    sma, over, under = berakna_bollinger(close)
    return {
        "rsi": _tal(berakna_rsi(close).iloc[-1]),
        "macd": _tal(macd.iloc[-1]),
        "macd_signal": _tal(signal.iloc[-1]),
        "bollinger_sma": _tal(sma.iloc[-1]),
        "bollinger_over": _tal(over.iloc[-1]),
        "bollinger_under": _tal(under.iloc[-1]),
        "atr": _tal(berakna_atr(hist).iloc[-1]),
        "golden_death_status": golden_death_status(close),
    }


@router.get("/risk/{ticker}")
def risk(ticker: str, jamfor_index: str = "^OMX"):
    hist, _ = hamta_kursdata(ticker)
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail="Ingen kursdata hittades")
    close = hist["Close"]
    index_hist = hamta_index_historik(jamfor_index)
    beta = berakna_beta(close, index_hist["Close"]) if not index_hist.empty else None
    return {
        "volatilitet_pct": _tal(berakna_volatilitet(close)),
        "sharpe": _tal(berakna_sharpe(close)),
        "max_drawdown_pct": _tal(berakna_max_drawdown(close)),
        "beta": _tal(beta),
    }


@router.get("/utdelning/{ticker}")
def utdelning(ticker: str):
    data = hamta_utdelningsanalys(ticker)
    return {
        "historik": [{"datum": str(d.date()), "belopp": _tal(v)} for d, v in data["historik"].items()],
        "tillvaxt_procent": _tal(data["tillvaxt_procent"]),
        "ojamn_historik": data["ojamn_historik"],
        "rapportdatum": str(data["rapportdatum"]) if data["rapportdatum"] else None,
        "rapportdatum_kommande": data["rapportdatum_kommande"],
        "ex_datum": str(data["ex_datum"]) if data["ex_datum"] else None,
        "ex_datum_kommande": data["ex_datum_kommande"],
    }

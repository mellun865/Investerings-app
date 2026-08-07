"""
AI-portföljcoach. Portföljscoren (0-100) räknas alltid ut deterministiskt
i Python utifrån diversifiering, risk och historisk utveckling - Gemini
används bara för att skriva en läsbar sammanfattning/riskbedömning kring
redan uträknade siffror, aldrig för själva matematiken.

Nyckeln hämtas från Streamlit secrets, ALDRIG hårdkodad i filen - den
här koden laddas upp till ett publikt GitHub-repo.
"""

import pandas as pd
import streamlit as st

from services import transactions_service
from services.market_data_service import hamta_kursdata
from services.risk_service import berakna_volatilitet, berakna_max_drawdown
from services.gemini_service import GEMINI_API_KEY, generera_text


def berakna_portfoljscore(portfolj):
    """Räknar ut en portföljscore 0-100: diversifiering (0-30), risk
    (0-30) och historisk utveckling/stabilitet (0-40). Returnerar poängen
    plus de underliggande måtten, så UI:t och AI-prompten visar/använder
    exakt samma siffror."""
    innehav = transactions_service.berakna_innehav(st.session_state.transaktioner)

    marknadsvarden = {}
    volatiliteter = []
    for namn, data in portfolj.items():
        bolagsinnehav = innehav.get(namn)
        antal = bolagsinnehav["antal"] if bolagsinnehav else 0.0
        if not antal:
            continue
        try:
            hist, _ = hamta_kursdata(data["ticker"])
        except Exception:
            hist = None
        if hist is None or hist.empty:
            continue
        marknadsvarden[namn] = antal * hist["Close"].iloc[-1]
        vol = berakna_volatilitet(hist["Close"])
        if vol is not None:
            volatiliteter.append(vol)

    antal_bolag = len(marknadsvarden)
    totalt_varde = sum(marknadsvarden.values())

    storsta_andel_pct = None
    diversifiering_poang = 0.0
    if totalt_varde and antal_bolag:
        storsta_andel_pct = max(marknadsvarden.values()) / totalt_varde * 100
        antal_poang = min(antal_bolag / 8, 1.0) * 20
        koncentration_poang = max(0.0, (100 - storsta_andel_pct) / 100) * 10
        diversifiering_poang = antal_poang + koncentration_poang

    snitt_volatilitet_pct = None
    risk_poang = 15.0
    if volatiliteter:
        snitt_volatilitet_pct = sum(volatiliteter) / len(volatiliteter)
        risk_poang = max(0.0, min(1.0, (50 - snitt_volatilitet_pct) / 35)) * 30

    max_drawdown_pct = None
    utveckling_pct = None
    utveckling_totalt_poang = 20.0
    historik = st.session_state.portfolj_historik
    if len(historik) >= 2:
        varde_serie = pd.Series([r["varde"] for r in historik])
        max_drawdown_pct = berakna_max_drawdown(varde_serie)
        utveckling_pct = (varde_serie.iloc[-1] - varde_serie.iloc[0]) / varde_serie.iloc[0] * 100
        drawdown_poang = max(0.0, min(1.0, (20 + max_drawdown_pct) / 20)) * 25
        trend_poang = max(0.0, min(1.0, (utveckling_pct + 10) / 20)) * 15
        utveckling_totalt_poang = drawdown_poang + trend_poang

    score = round(diversifiering_poang + risk_poang + utveckling_totalt_poang)

    return {
        "score": max(0, min(100, score)),
        "antal_bolag": antal_bolag,
        "totalt_varde": round(totalt_varde, 0),
        "storsta_andel_pct": round(storsta_andel_pct, 1) if storsta_andel_pct is not None else None,
        "snitt_volatilitet_pct": round(snitt_volatilitet_pct, 1) if snitt_volatilitet_pct is not None else None,
        "max_drawdown_pct": round(max_drawdown_pct, 1) if max_drawdown_pct is not None else None,
        "utveckling_pct": round(utveckling_pct, 1) if utveckling_pct is not None else None,
    }


def _bygg_prompt(portfolj, score_data):
    return f"""Du är en nykter, pedagogisk portföljcoach för en svensk privatsparare.
Utgå ENDAST från siffrorna nedan - hitta inte på egna siffror och
rekommendera inte enskilda köp/sälj av specifika aktier (det här är
information och lärande, inte finansiell rådgivning).

Innehav: {", ".join(sorted(portfolj.keys()))}
Antal bolag med registrerat innehav: {score_data['antal_bolag']}
Största innehavets andel av portföljen: {score_data['storsta_andel_pct']} %
Genomsnittlig årlig volatilitet bland innehaven: {score_data['snitt_volatilitet_pct']} %
Portföljens största nedgång (drawdown) i loggad historik: {score_data['max_drawdown_pct']} %
Utveckling sedan första loggade dagen: {score_data['utveckling_pct']} %
Redan uträknad portföljscore (0-100, återge denna siffra oförändrad): {score_data['score']}

Skriv på svenska, kort (max ca 150 ord), i tre korta stycken utan rubriker:
1) Daglig sammanfattning av läget.
2) Riskbedömning (koncentration, volatilitet, drawdown).
3) En allmän förbättringstanke (t.ex. diversifiering eller riskspridning),
   utan att peka ut enskilda aktier att köpa eller sälja."""


def generera_ai_sammanfattning(portfolj, score_data):
    return generera_text(_bygg_prompt(portfolj, score_data))

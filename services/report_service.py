"""
Rapportsammanfattningar: hämtar bolagets senaste kvartalssiffror
(omsättning, resultat m.m.) via yfinance och låter Gemini skriva en kort
sammanfattning av utvecklingen jämfört med föregående kvartal och samma
kvartal föregående år - baserat ENDAST på dessa faktiska siffror.
"""

import pandas as pd
import streamlit as st
import yfinance as yf

from services.gemini_service import generera_text

NYCKELTAL = {
    "Total Revenue": "Omsättning",
    "Operating Income": "Rörelseresultat",
    "Net Income": "Nettoresultat",
    "Diluted EPS": "Resultat per aktie",
}


@st.cache_data(ttl=3600 * 12)
def hamta_kvartalsdata(ticker):
    """Returnerar de senaste kvartalens nyckeltal (nyast först) samt
    uppskattat nästa rapportdatum, eller None om data saknas."""
    aktie = yf.Ticker(ticker)
    qf = aktie.quarterly_financials
    if qf is None or qf.empty:
        return None

    kvartal = []
    for datum in qf.columns[:5]:
        rad = {"datum": str(datum.date())}
        for engelskt, svenskt in NYCKELTAL.items():
            varde = qf.loc[engelskt, datum] if engelskt in qf.index else None
            rad[svenskt] = None if varde is None or pd.isna(varde) else float(varde)
        kvartal.append(rad)

    try:
        valuta = aktie.info.get("currency") or "kr"
    except Exception:
        valuta = "kr"

    nasta_rapportdatum = None
    try:
        kalender = aktie.calendar or {}
        datum_lista = kalender.get("Earnings Date")
        if datum_lista:
            nasta_rapportdatum = str(datum_lista[0])
    except Exception:
        pass

    return {"kvartal": kvartal, "valuta": valuta, "nasta_rapportdatum": nasta_rapportdatum}


def _forandring_pct(nytt, gammalt):
    if nytt is None or gammalt is None or gammalt == 0:
        return None
    return (nytt - gammalt) / abs(gammalt) * 100


def _bygg_prompt(bolag, kvartalsdata):
    kvartal = kvartalsdata["kvartal"]
    senaste, foregaende = kvartal[0], kvartal[1] if len(kvartal) > 1 else None
    forra_aret = kvartal[4] if len(kvartal) > 4 else None

    rader = []
    for namn in NYCKELTAL.values():
        varde = senaste.get(namn)
        if varde is None:
            continue
        qoq = _forandring_pct(varde, foregaende.get(namn)) if foregaende else None
        yoy = _forandring_pct(varde, forra_aret.get(namn)) if forra_aret else None
        rader.append(
            f"{namn}: {varde:,.0f} {kvartalsdata['valuta']} "
            f"(mot föregående kvartal: {f'{qoq:+.1f}%' if qoq is not None else 'okänd'}, "
            f"mot samma kvartal föregående år: {f'{yoy:+.1f}%' if yoy is not None else 'okänd'})"
        )

    return f"""Du är en nykter, pedagogisk analytiker för en svensk privatsparare.
Utgå ENDAST från siffrorna nedan för {bolag}s senaste rapporterade kvartal
({senaste['datum']}) - hitta inte på egna siffror eller händelser, och ge
inga köp-/säljrekommendationer.

{chr(10).join(rader)}

Skriv på svenska, kort och lättläst, som en punktlista med exakt dessa
punkter (markdown-format, fet rubrik på varje punkt):
- **Utveckling:** vad siffrorna visar (bättre/sämre än föregående kvartal
  och samma kvartal förra året).
- **Påverkan på bolaget:** vad utvecklingen kan betyda för {bolag}s
  verksamhet (t.ex. marginaler, tillväxttakt, lönsamhet).
- **Påverkan på aktien:** hur det här typiskt kan tolkas av marknaden och
  vad en {bolag}-aktieägare bör hålla ögonen på framåt.
Max ca 130 ord totalt. Ingen köp-/säljrekommendation. Ingen inledande eller
avslutande text utanför listan."""


def generera_rapportsammanfattning(bolag, kvartalsdata):
    if not kvartalsdata or len(kvartalsdata["kvartal"]) < 2:
        return None, "För lite kvartalsdata för att skriva en sammanfattning."
    return generera_text(_bygg_prompt(bolag, kvartalsdata))

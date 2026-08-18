"""
Portföljhistorik - registrerar portföljens totala marknadsvärde en gång
per dag (i st.session_state.portfolj_historik, sparat via
persistence_service.spara_historik) så att en utvecklingsgraf och
drawdown-beräkning kan byggas upp över tid. Bygger på samma
innehavsberäkning som "Översikt"-fliken (transactions_service) och
nuvarande kurser (market_data_service).
"""

from datetime import date

import pandas as pd

from services import transactions_service
from services.market_data_service import hamta_index_historik, hamta_kursdata

BENCHMARKS = {
    "OMXS30 (Stockholmsbörsen)": "^OMX",
    "S&P 500 (USA)": "^GSPC",
    "MSCI World (globalt)": "URTH",
}


def berakna_totalt_marknadsvarde(portfolj, transaktioner):
    """Räknar ihop portföljens totala marknadsvärde just nu, utifrån
    nuvarande antal aktier (från transaktionsloggen) och senaste kurs
    per bolag. OBS: summerar olika valutor rakt av utan växelkursomräkning,
    precis som totalsumman i "Översikt"-fliken."""
    innehav = transactions_service.berakna_innehav(transaktioner)
    totalt = 0.0
    for namn, data in portfolj.items():
        bolagsinnehav = innehav.get(namn)
        antal_aktier = bolagsinnehav["antal"] if bolagsinnehav else 0.0
        if not antal_aktier:
            continue
        try:
            hist, _ = hamta_kursdata(data["ticker"])
            senaste_pris = hist["Close"].iloc[-1] if not hist.empty else None
        except Exception:
            senaste_pris = None
        if senaste_pris:
            totalt += antal_aktier * senaste_pris
    return totalt


def registrera_dagens_varde(portfolj, transaktioner, historik):
    """Räknar fram dagens portföljvärde och returnerar en NY historiklista
    med dagens rad tillagd (skriver över dagens rad om den redan finns, så
    historiken inte svämmar över vid flera körningar samma dag). Returnerar
    None om ingenting ska registreras (tom portfölj eller inget värde att
    räkna) - anroparen ansvarar själv för att spara resultatet."""
    if not portfolj:
        return None
    totalt = berakna_totalt_marknadsvarde(portfolj, transaktioner)
    if not totalt:
        return None

    idag = str(date.today())
    ny_historik = [rad for rad in historik if rad["datum"] != idag]
    ny_historik.append({"datum": idag, "varde": round(totalt, 2)})
    ny_historik.sort(key=lambda r: r["datum"])
    return ny_historik


def berakna_jamforelse(historik_df, ticker):
    """Bygger en tvåkolumns-DataFrame (Portfölj/Index) med utveckling i %
    sedan första loggade dagen, så portföljens kurva kan jämföras med ett
    index oavsett att de har helt olika absoluta nivåer (kr vs indexpoäng).
    Indexets dagskurser forward-fillas till portföljens (glesare) datum -
    helger/dagar utan öppen app får då gårdagens senaste indexvärde."""
    index_hist = hamta_index_historik(ticker, period="2y")
    if index_hist.empty:
        return None

    index_close = index_hist["Close"]
    index_close.index = index_close.index.tz_localize(None)
    index_close = index_close[index_close.index <= historik_df.index[-1]]
    index_pa_datum = index_close.reindex(
        index_close.index.union(historik_df.index)
    ).sort_index().ffill().reindex(historik_df.index)

    if index_pa_datum.isna().all() or pd.isna(index_pa_datum.iloc[0]):
        return None

    portfolj_pct = (historik_df["varde"] - historik_df["varde"].iloc[0]) / historik_df["varde"].iloc[0] * 100
    index_pct = (index_pa_datum - index_pa_datum.iloc[0]) / index_pa_datum.iloc[0] * 100

    return pd.DataFrame({"Portfölj": portfolj_pct, "Index": index_pct}, index=historik_df.index)

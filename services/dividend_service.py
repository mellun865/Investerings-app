"""
Utdelningsanalys: historik, tillväxt, samt kommande rapport-/ex-datum.
"""

import datetime

import yfinance as yf


def hamta_utdelningsanalys(ticker):
    aktie = yf.Ticker(ticker)
    idag = datetime.date.today()

    resultat = {
        "historik": aktie.dividends,
        "tillvaxt_procent": None,
        "ojamn_historik": False,
        "rapportdatum": None,
        "rapportdatum_kommande": False,
        "ex_datum": None,
        "ex_datum_kommande": False,
    }

    utdelningar = resultat["historik"]
    if not utdelningar.empty and len(utdelningar) >= 2:
        senaste = utdelningar.tail(5)
        forsta, sista = senaste.iloc[0], senaste.iloc[-1]
        if forsta > 0:
            resultat["tillvaxt_procent"] = (sista / forsta - 1) * 100

        datum_lista = list(senaste.index)
        if len(datum_lista) >= 2:
            gap_dagar = [(datum_lista[i + 1] - datum_lista[i]).days for i in range(len(datum_lista) - 1)]
            resultat["ojamn_historik"] = max(gap_dagar) > 450

    try:
        kalender = aktie.calendar
        rapportdatum_lista = kalender.get("Earnings Date", [])
        if rapportdatum_lista:
            resultat["rapportdatum"] = rapportdatum_lista[0]
            resultat["rapportdatum_kommande"] = rapportdatum_lista[0] >= idag
        ex_datum = kalender.get("Ex-Dividend Date")
        if ex_datum:
            resultat["ex_datum"] = ex_datum
            resultat["ex_datum_kommande"] = ex_datum >= idag
    except Exception:
        pass

    return resultat

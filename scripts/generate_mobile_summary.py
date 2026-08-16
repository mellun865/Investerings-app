"""
Fristående skript (körs INTE via `streamlit run`) som räknar ihop en liten
sammanfattning av portföljen (totalvärde, dagens utveckling, innehav,
senaste relevanta nyheter, portföljscore) och publicerar den som en HEMLIG
GitHub Gist - en fil på en ogissningsbar URL, inte listad någonstans.

Tänkt att köras periodiskt via GitHub Actions (samma workflow som
news_notify.py, eller en egen) så att mobil-PWA:n (pwa/) kan hämta färdig
data direkt utan att själv prata med GitHub/yfinance/Gemini och utan att
behöva några hemliga nycklar i webbläsaren.

Publicerar BARA aggregerad data (totalvärde, %-utveckling, portföljscore,
per-bolag dagens förändring, nyhetsrubriker) - INGA transaktioner, GAV,
antal aktier eller andra detaljer som vore känsligare att läcka.

Kräver GIST_TOKEN (en Personal Access Token med "gist"-behörighet, skild
från datarepots DATA_REPO_TOKEN eftersom gist-skrivning är en
kontobehörighet, inte repo-specifik) i secrets. Skapar en ny hemlig gist
första gången och sparar dess ID i den privata datarepot
(mobile_gist_id.txt) - efterföljande körningar uppdaterar samma gist.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from services import persistence_service, transactions_service, sentiment_service
from services.market_data_service import hamta_kursdata
from services import ai_coach_service

GIST_TOKEN = st.secrets.get("GIST_TOKEN", "")
GIST_ID_FIL = "mobile_gist_id.txt"
GIST_BESKRIVNING = "Min portföljanalys - mobilsammanfattning (auto-genererad, rör inte manuellt)"
MAX_NYHETER = 8


def _gist_konfigurerad():
    return bool(GIST_TOKEN)


def _gist_headers():
    return {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def _hamta_sparat_gist_id():
    data = persistence_service.ladda_lista(
        os.path.join(persistence_service._PROJEKT_ROT, GIST_ID_FIL), GIST_ID_FIL, None
    )
    return data if isinstance(data, str) and data else None


def _spara_gist_id(gist_id):
    if persistence_service._github_konfigurerad():
        persistence_service._github_spara(GIST_ID_FIL, gist_id)
    else:
        with open(os.path.join(persistence_service._PROJEKT_ROT, GIST_ID_FIL), "w", encoding="utf-8") as f:
            json.dump(gist_id, f)


def _publicera_gist(innehall_json):
    body = {
        "description": GIST_BESKRIVNING,
        "public": False,
        "files": {"portfolj_sammanfattning.json": {"content": innehall_json}},
    }
    gist_id = _hamta_sparat_gist_id()
    if gist_id:
        svar = requests.patch(
            f"https://api.github.com/gists/{gist_id}", headers=_gist_headers(), json=body, timeout=10
        )
        if svar.status_code == 404:
            gist_id = None
        else:
            svar.raise_for_status()
            return gist_id

    svar = requests.post("https://api.github.com/gists", headers=_gist_headers(), json=body, timeout=10)
    svar.raise_for_status()
    nytt_id = svar.json()["id"]
    _spara_gist_id(nytt_id)
    return nytt_id


def _bygg_sammanfattning(portfolj, transaktioner, historik):
    innehav = transactions_service.berakna_innehav(transaktioner)

    totalt_varde = 0.0
    totalt_varde_igar = 0.0
    innehav_ut = []

    for bolag, data in portfolj.items():
        bolagsinnehav = innehav.get(bolag)
        antal = bolagsinnehav["antal"] if bolagsinnehav else 0.0
        if not antal:
            continue
        try:
            hist, _ = hamta_kursdata(data["ticker"])
        except Exception:
            continue
        if hist is None or hist.empty:
            continue

        senaste_pris = hist["Close"].iloc[-1]
        varde = antal * senaste_pris
        totalt_varde += varde

        forandring_pct = None
        if len(hist) >= 2:
            foregaende_pris = hist["Close"].iloc[-2]
            if foregaende_pris:
                forandring_pct = (senaste_pris - foregaende_pris) / foregaende_pris * 100
                totalt_varde_igar += antal * foregaende_pris
        if forandring_pct is None:
            totalt_varde_igar += varde

        innehav_ut.append({
            "bolag": bolag,
            "varde": round(varde, 0),
            "dagens_forandring_pct": round(forandring_pct, 2) if forandring_pct is not None else None,
        })

    innehav_ut.sort(key=lambda r: r["varde"], reverse=True)

    dagens_forandring_kr = None
    dagens_forandring_pct = None
    if totalt_varde_igar:
        dagens_forandring_kr = round(totalt_varde - totalt_varde_igar, 0)
        dagens_forandring_pct = round((totalt_varde - totalt_varde_igar) / totalt_varde_igar * 100, 2)

    st.session_state.transaktioner = transaktioner
    st.session_state.portfolj_historik = historik
    score_data = ai_coach_service.berakna_portfoljscore(portfolj)

    nyheter_ut = []
    for bolag, data in portfolj.items():
        try:
            nyheter = sentiment_service.hamta_nyheter_for_bolag(data["sok"], max_antal=3)
        except Exception:
            continue
        for nyhet in nyheter:
            if not sentiment_service.ar_troligen_relevant(bolag, nyhet["titel"]):
                continue
            nyheter_ut.append({
                "bolag": bolag,
                "titel": nyhet["titel"],
                "lank": nyhet.get("lank"),
                "kalla": nyhet.get("kalla"),
                "datum": nyhet.get("datum"),
            })
    nyheter_ut.sort(key=lambda n: n.get("datum") or "", reverse=True)
    nyheter_ut = nyheter_ut[:MAX_NYHETER]

    return {
        "uppdaterad": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "totalt_varde": round(totalt_varde, 0),
        "dagens_forandring_kr": dagens_forandring_kr,
        "dagens_forandring_pct": dagens_forandring_pct,
        "portfoljscore": score_data["score"] if score_data["antal_bolag"] else None,
        "innehav": innehav_ut,
        "nyheter": nyheter_ut,
    }


def main():
    if not _gist_konfigurerad():
        print("GIST_TOKEN saknas i secrets - avbryter (mobilsammanfattningen genereras inte).")
        return

    portfolj = persistence_service.ladda_lista(
        persistence_service.PORTFOLJ_FIL, "portfolj.json", persistence_service.STARTPORTFOLJ
    )
    if not portfolj:
        print("Ingen portfölj konfigurerad, avbryter.")
        return

    transaktioner = persistence_service.ladda_lista(
        persistence_service.TRANSAKTIONER_FIL, "transaktioner.json", []
    )
    historik = persistence_service.ladda_lista(persistence_service.HISTORIK_FIL, "historik.json", [])

    sammanfattning = _bygg_sammanfattning(portfolj, transaktioner, historik)
    gist_id = _publicera_gist(json.dumps(sammanfattning, ensure_ascii=False, indent=2))
    print(f"Klart. Gist uppdaterad: https://gist.githubusercontent.com/raw/{gist_id}/portfolj_sammanfattning.json")


if __name__ == "__main__":
    main()

"""
Startportfölj samt lagring av portfölj, bevakningslista, transaktioner och
historik.

Lagras antingen som lokala JSON-filer (vid lokal körning) eller i ett
separat, PRIVAT GitHub-repo via GitHub Contents API (vid molndeploy, t.ex.
Streamlit Community Cloud, vars filsystem nollställs vid omstart/redeploy).
Vilket som används avgörs av om GITHUB_TOKEN + GITHUB_DATA_REPO finns i
secrets - annars faller den tillbaka på lokala filer, så lokal utveckling
(venv/start.sh) fungerar precis som förut utan några nycklar.

OBS: datarepot MÅSTE vara privat - appkodens repo är publikt (se
gemini_service.py), men de faktiska innehaven/beloppen får inte vara det.
"""

import os
import json
import base64

import requests
import streamlit as st


STARTPORTFOLJ = {
    "Axfood":          {"ticker": "AXFO.ST",   "borskollen": "axfood",                "sok": "Axfood"},
    "Avarda Bank":     {"ticker": "AVARDA.ST", "borskollen": "tf-bank",               "sok": "Avarda"},
    "Saab B":          {"ticker": "SAAB-B.ST", "borskollen": "saab",                  "sok": "Saab"},
    "Handelsbanken A": {"ticker": "SHB-A.ST",  "borskollen": "svenska-handelsbanken", "sok": "Handelsbanken"},
    "Cloetta":         {"ticker": "CLA-B.ST",  "borskollen": "cloetta",               "sok": "Cloetta"},
    "SEB C":           {"ticker": "SEB-C.ST",  "borskollen": "seb",                   "sok": "SEB bank"},
    "Telia":           {"ticker": "TELIA.ST",  "borskollen": "telia-company",         "sok": "Telia"},
    "Nordea":          {"ticker": "NDA-SE.ST", "borskollen": "nordea",                "sok": "Nordea"},
    "Swedbank A":      {"ticker": "SWED-A.ST", "borskollen": "swedbank",              "sok": "Swedbank"},
}

_PROJEKT_ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLJ_FIL = os.path.join(_PROJEKT_ROT, "portfolj_data.json")
BEVAKNING_FIL = os.path.join(_PROJEKT_ROT, "bevakning_data.json")
TRANSAKTIONER_FIL = os.path.join(_PROJEKT_ROT, "transaktioner_data.json")
HISTORIK_FIL = os.path.join(_PROJEKT_ROT, "portfolj_historik.json")

GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
GITHUB_DATA_REPO = st.secrets.get("GITHUB_DATA_REPO", "")
GITHUB_DATA_BRANCH = st.secrets.get("GITHUB_DATA_BRANCH", "main")


def _github_konfigurerad():
    return bool(GITHUB_TOKEN) and bool(GITHUB_DATA_REPO)


def _github_url(sokvag):
    return f"https://api.github.com/repos/{GITHUB_DATA_REPO}/contents/{sokvag}?ref={GITHUB_DATA_BRANCH}"


def _github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def _github_lasa(sokvag, standard):
    try:
        svar = requests.get(_github_url(sokvag), headers=_github_headers(), timeout=10)
        if svar.status_code == 404:
            return standard
        svar.raise_for_status()
        innehall = base64.b64decode(svar.json()["content"]).decode("utf-8")
        return json.loads(innehall)
    except Exception:
        return standard


def _github_spara(sokvag, data):
    url = f"https://api.github.com/repos/{GITHUB_DATA_REPO}/contents/{sokvag}"
    innehall = json.dumps(data, ensure_ascii=False, indent=2)
    body = {
        "message": f"Uppdatera {sokvag}",
        "content": base64.b64encode(innehall.encode("utf-8")).decode("utf-8"),
        "branch": GITHUB_DATA_BRANCH,
    }
    befintlig = requests.get(_github_url(sokvag), headers=_github_headers(), timeout=10)
    if befintlig.status_code == 200:
        body["sha"] = befintlig.json()["sha"]
    svar = requests.put(url, headers=_github_headers(), json=body, timeout=10)
    svar.raise_for_status()


def spara_lista(session_nyckel, fil, github_sokvag):
    data = st.session_state[session_nyckel]
    if _github_konfigurerad():
        _github_spara(github_sokvag, data)
    else:
        with open(fil, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def ladda_lista(fil, github_sokvag, standard):
    if _github_konfigurerad():
        return _github_lasa(github_sokvag, standard)
    if os.path.exists(fil):
        try:
            with open(fil, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return standard


def spara_portfolj():
    spara_lista("portfolj", PORTFOLJ_FIL, "portfolj.json")


def spara_bevakning():
    spara_lista("bevakning", BEVAKNING_FIL, "bevakning.json")


def spara_transaktioner():
    spara_lista("transaktioner", TRANSAKTIONER_FIL, "transaktioner.json")


def spara_historik():
    spara_lista("portfolj_historik", HISTORIK_FIL, "historik.json")


def init_session_state():
    if "portfolj" not in st.session_state:
        st.session_state.portfolj = ladda_lista(PORTFOLJ_FIL, "portfolj.json", dict(STARTPORTFOLJ))
    if "bevakning" not in st.session_state:
        st.session_state.bevakning = ladda_lista(BEVAKNING_FIL, "bevakning.json", {})
    if "transaktioner" not in st.session_state:
        st.session_state.transaktioner = ladda_lista(TRANSAKTIONER_FIL, "transaktioner.json", [])
    if "portfolj_historik" not in st.session_state:
        st.session_state.portfolj_historik = ladda_lista(HISTORIK_FIL, "historik.json", [])

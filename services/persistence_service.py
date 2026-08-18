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

Om Google-inloggning är konfigurerad (se auth-sektionen i app.py) lagras
varje inloggad användares data separat, under en mapp per användar-ID
(sanerad e-postadress) - se _anvandar_id/_lokal_sokvag/_github_sokvag.
Utan inloggning (lokal utveckling, eller fristående skript utanför en
Streamlit-session) används samma delade rotsökvägar som innan
flerpersonsstödet.
"""

import os
import re
import json
import base64

import requests
import streamlit as st

from services.config import get_secret


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

GITHUB_TOKEN = get_secret("GITHUB_TOKEN")
GITHUB_DATA_REPO = get_secret("GITHUB_DATA_REPO")
GITHUB_DATA_BRANCH = get_secret("GITHUB_DATA_BRANCH", "main")


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


def _anvandar_id():
    """Filsystemsäkert ID för inloggad användare (Google-e-post via
    st.login()), t.ex. "lbmelwin_gmail_com". Tom sträng om inloggning inte
    är konfigurerad/aktiv - lokal utveckling utan auth-secrets i
    secrets.toml, eller ett fristående skript som news_notify.py som körs
    utan Streamlit-session. Då används exakt samma rotsökvägar som innan
    flerpersonsstödet, så den ursprungliga datan inte flyttas/påverkas."""
    try:
        if "auth" not in st.secrets or not st.user.is_logged_in:
            return ""
        epost = st.user.email or ""
    except Exception:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", epost.lower()).strip("_")


def _lokal_sokvag(fil, uid):
    if not uid:
        return fil
    katalog = os.path.join(os.path.dirname(fil), "anvandardata", uid)
    os.makedirs(katalog, exist_ok=True)
    return os.path.join(katalog, os.path.basename(fil))


def _github_sokvag(sokvag, uid):
    return f"users/{uid}/{sokvag}" if uid else sokvag


def _spara(data, fil, github_sokvag, user_id=""):
    """Ren skrivfunktion - tar emot user_id explicit istället för att
    härleda det från st.user, så den kan anropas utan en Streamlit-session
    (t.ex. från FastAPI-backend eller fristående skript)."""
    if _github_konfigurerad():
        _github_spara(_github_sokvag(github_sokvag, user_id), data)
    else:
        with open(_lokal_sokvag(fil, user_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _ladda(fil, github_sokvag, standard, user_id=""):
    """Ren läsfunktion - se _spara."""
    if _github_konfigurerad():
        return _github_lasa(_github_sokvag(github_sokvag, user_id), standard)
    fil = _lokal_sokvag(fil, user_id)
    if os.path.exists(fil):
        try:
            with open(fil, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return standard


def spara_lista(session_nyckel, fil, github_sokvag):
    _spara(st.session_state[session_nyckel], fil, github_sokvag, _anvandar_id())


def ladda_lista(fil, github_sokvag, standard):
    return _ladda(fil, github_sokvag, standard, _anvandar_id())


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

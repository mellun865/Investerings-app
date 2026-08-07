"""
Startportfölj samt lagring av portfölj och bevakningslista till lokala
JSON-filer, så att egna tillägg/borttag, målkurser och önskade köpkurser
finns kvar nästa gång appen startas, istället för att återställas varje gång.
"""

import os
import json

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


def spara_lista(session_nyckel, fil):
    with open(fil, "w", encoding="utf-8") as f:
        json.dump(st.session_state[session_nyckel], f, ensure_ascii=False, indent=2)


def ladda_lista(fil, standard):
    if os.path.exists(fil):
        try:
            with open(fil, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return standard


def spara_portfolj():
    spara_lista("portfolj", PORTFOLJ_FIL)


def spara_bevakning():
    spara_lista("bevakning", BEVAKNING_FIL)


def spara_transaktioner():
    spara_lista("transaktioner", TRANSAKTIONER_FIL)


def init_session_state():
    if "portfolj" not in st.session_state:
        st.session_state.portfolj = ladda_lista(PORTFOLJ_FIL, dict(STARTPORTFOLJ))
    if "bevakning" not in st.session_state:
        st.session_state.bevakning = ladda_lista(BEVAKNING_FIL, {})
    if "transaktioner" not in st.session_state:
        st.session_state.transaktioner = ladda_lista(TRANSAKTIONER_FIL, [])

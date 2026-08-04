"""
Makroekonomiska indikatorer från FRED (Federal Reserve Economic Data).

Nyckeln hämtas från Streamlit secrets, ALDRIG hårdkodad i filen - den
här koden laddas upp till ett publikt GitHub-repo, och en nyckel i
klartext där skulle vara synlig för vem som helst.
"""

import requests
import streamlit as st


FRED_API_KEY = st.secrets.get("FRED_API_KEY", "")

MAKRO_SERIER = {
    "Styrränta USA (Fed funds rate)":        {"id": "FEDFUNDS",        "enhet": "%",      "units": None},
    "Inflation USA (årlig förändring KPI)":  {"id": "CPIAUCSL",        "enhet": "%",      "units": "pc1"},
    "Arbetslöshet USA":                      {"id": "UNRATE",          "enhet": "%",      "units": None},
    "10-årig statsobligationsränta USA":     {"id": "GS10",            "enhet": "%",      "units": None},
    "USD/SEK (kronor per dollar)":           {"id": "DEXSDUS",         "enhet": "kr/USD", "units": None},
    "10-årig statsobligationsränta Sverige": {"id": "IRLTLT01SEM156N", "enhet": "%",      "units": None},
}


@st.cache_data(ttl=3600 * 12)
def hamta_fred_varde(series_id, api_key, units=None):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id, "api_key": api_key, "file_type": "json",
        "sort_order": "desc", "limit": 1,
    }
    if units:
        params["units"] = units
    svar = requests.get(url, params=params, timeout=10)
    try:
        data = svar.json()
    except ValueError:
        return None, None, f"Ogiltigt svar (statuskod {svar.status_code})"
    if "error_message" in data:
        return None, None, data["error_message"]
    if not data.get("observations"):
        return None, None, "Inga observationer hittades"
    obs = data["observations"][0]
    try:
        varde = f"{float(obs['value']):.2f}"
    except ValueError:
        varde = obs["value"]
    return obs["date"], varde, None

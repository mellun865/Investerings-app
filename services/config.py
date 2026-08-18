"""
Delad secrets/env-läsning. Streamlit-appen har hittills läst nycklar
direkt via st.secrets (secrets.toml) - denna funktion låter samma kod
fungera lika bra från FastAPI-backend eller fristående skript, som inte
har någon st.secrets att läsa (vanliga miljövariabler, t.ex. via en
.env-fil lokalt eller riktiga env vars i molnet). st.secrets prioriteras
när den finns, så Streamlit-appens beteende är oförändrat.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_secret(key, default=""):
    try:
        import streamlit as st
        varde = st.secrets.get(key)
        if varde:
            return varde
    except Exception:
        pass
    return os.environ.get(key, default)

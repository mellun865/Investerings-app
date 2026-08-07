"""
Delad Gemini-klient. Nyckeln hämtas från Streamlit secrets, ALDRIG
hårdkodad i filen - den här koden laddas upp till ett publikt
GitHub-repo. Används av AI-coachen och rapportsammanfattningarna, som
båda bara skickar redan uträknade siffror till Gemini för att få text -
aldrig för att räkna ut siffrorna själva.
"""

import streamlit as st

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GEMINI_MODELL = "gemini-flash-latest"


def generera_text(prompt):
    """Returnerar (text, felmeddelande) - exakt en av de två är satt."""
    if not GEMINI_API_KEY:
        return None, "Ingen Gemini API-nyckel konfigurerad."
    try:
        from google import genai
    except ImportError:
        return None, "Paketet google-genai är inte installerat."

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        svar = client.models.generate_content(model=GEMINI_MODELL, contents=prompt)
        return svar.text, None
    except Exception as e:
        return None, str(e)

"""
Portföljanalys - komplett app som slår ihop allt vi byggt och testat:
nyhetssentiment, nyckeltal, kurshistorik, analytikers riktkurser,
teknisk analys, riskmått, utdelningar och makroekonomi. Användare kan
lägga till och ta bort egna innehav i sidopanelen.

Körs lokalt med: streamlit run app.py
Eller publiceras gratis via share.streamlit.io.
"""

import streamlit as st

from services import persistence_service, history_service
from ui import sidebar, tabs


st.set_page_config(page_title="Min portföljanalys", layout="wide")

# Google-inloggning (st.login) är valfri - styrs av en [auth]-sektion i
# secrets.toml. Utan den körs appen precis som innan, enanvändarläge utan
# inloggning (t.ex. lokal utveckling som inte satt upp Google OAuth än).
AUTH_KONFIGURERAD = "auth" in st.secrets

if AUTH_KONFIGURERAD and not st.user.is_logged_in:
    st.title("📊 Min portföljanalys")
    st.caption(
        "Ett verktyg för information och lärande - inte finansiell rådgivning. "
        "Analytikers riktkurser och sentiment är hjälpmedel, inte facit."
    )
    st.info("Logga in med Google för att se och hantera din egen portfölj.")
    st.button("🔐 Logga in med Google", on_click=st.login)
    st.stop()

persistence_service.init_session_state()
ny_historik = history_service.registrera_dagens_varde(
    st.session_state.portfolj, st.session_state.transaktioner, st.session_state.portfolj_historik
)
if ny_historik is not None:
    st.session_state.portfolj_historik = ny_historik
    persistence_service.spara_historik()
sidebar.render_sidebar()

st.title("📊 Min portföljanalys")
st.caption(
    "Ett verktyg för information och lärande - inte finansiell rådgivning. "
    "Analytikers riktkurser och sentiment är hjälpmedel, inte facit."
)

if not st.session_state.portfolj:
    st.info("Din portfölj är tom - lägg till en aktie i sidopanelen för att komma igång.")
    st.stop()

vald_flik = st.tabs([
    "🏠 Dashboard", "💼 Portfölj", "🤖 AI-coach", "📊 Analys",
    "📰 Nyheter & Rapporter", "🌍 Makro & Bevakning",
])
PORTFOLJ = st.session_state.portfolj

with vald_flik[0]:
    tabs.render_dashboard(PORTFOLJ)

with vald_flik[1]:
    tabs.render_portfolj_grupp(PORTFOLJ)

with vald_flik[2]:
    tabs.render_ai_coach(PORTFOLJ)

with vald_flik[3]:
    tabs.render_analys_grupp(PORTFOLJ)

with vald_flik[4]:
    tabs.render_nyheter_rapporter_grupp(PORTFOLJ)

with vald_flik[5]:
    tabs.render_makro_bevakning_grupp()

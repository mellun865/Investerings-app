"""
Portföljanalys - komplett app som slår ihop allt vi byggt och testat:
nyhetssentiment, nyckeltal, kurshistorik, analytikers riktkurser,
teknisk analys, riskmått, utdelningar och makroekonomi. Användare kan
lägga till och ta bort egna innehav i sidopanelen.

Körs lokalt med: streamlit run app.py
Eller publiceras gratis via share.streamlit.io.
"""

import streamlit as st

from services import persistence_service
from ui import sidebar, tabs


persistence_service.init_session_state()
sidebar.render_sidebar()

st.set_page_config(page_title="Min portföljanalys", layout="wide")
st.title("📊 Min portföljanalys")
st.caption(
    "Ett verktyg för information och lärande - inte finansiell rådgivning. "
    "Analytikers riktkurser och sentiment är hjälpmedel, inte facit."
)

if not st.session_state.portfolj:
    st.info("Din portfölj är tom - lägg till en aktie i sidopanelen för att komma igång.")
    st.stop()

vald_flik = st.tabs([
    "Översikt", "Nyheter & sentiment", "Nyckeltal", "Kursutveckling",
    "Riktkurser", "Teknisk analys", "Risk & korrelation", "Utdelningar",
    "Makroekonomi", "🔭 Bevakningslista",
])
PORTFOLJ = st.session_state.portfolj

with vald_flik[0]:
    tabs.render_oversikt(PORTFOLJ)

with vald_flik[1]:
    tabs.render_nyheter_sentiment(PORTFOLJ)

with vald_flik[2]:
    tabs.render_nyckeltal(PORTFOLJ)

with vald_flik[3]:
    tabs.render_kursutveckling(PORTFOLJ)

with vald_flik[4]:
    tabs.render_riktkurser(PORTFOLJ)

with vald_flik[5]:
    tabs.render_teknisk_analys(PORTFOLJ)

with vald_flik[6]:
    tabs.render_risk_korrelation(PORTFOLJ)

with vald_flik[7]:
    tabs.render_utdelningar(PORTFOLJ)

with vald_flik[8]:
    tabs.render_makroekonomi()

with vald_flik[9]:
    tabs.render_bevakningslista()

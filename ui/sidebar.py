"""
Sidopanel - lägg till/ta bort egna innehav och bevakningar.
"""

import streamlit as st

from services import persistence_service
from services.market_data_service import sok_bolag, bolagsinfo_fran_traff


def render_sidebar():
    with st.sidebar:
        st.header("Din portfölj")
        sokterm_ny = st.text_input(
            "Lägg till en aktie (sök på bolagsnamn)",
            placeholder="t.ex. Volvo eller Apple",
        )

        if sokterm_ny.strip():
            traffar = sok_bolag(sokterm_ny)
            if not traffar:
                st.caption("Inga träffar - prova ett annat sökord.")
            else:
                etiketter = [
                    f"{t.get('shortname') or t.get('longname')} ({t['symbol']}, {t.get('exchDisp', '-')})"
                    for t in traffar
                ]
                valt_index = st.selectbox(
                    "Välj rätt bolag/börs",
                    range(len(traffar)),
                    format_func=lambda i: etiketter[i],
                )
                if st.button("➕ Lägg till", use_container_width=True):
                    info = bolagsinfo_fran_traff(traffar[valt_index])
                    st.session_state.portfolj[info["namn"]] = {
                        "ticker": info["ticker"],
                        "borskollen": info["borskollen"],
                        "sok": info["sok"],
                        "malkurs": None,
                    }
                    persistence_service.spara_portfolj()
                    st.success(f"{info['namn']} tillagd!")

        st.divider()
        st.caption("Dina innehav:")
        for namn in list(st.session_state.portfolj.keys()):
            c1, c2 = st.columns([5, 1])
            c1.write(namn)
            if c2.button("✕", key=f"tabort_{namn}"):
                del st.session_state.portfolj[namn]
                persistence_service.spara_portfolj()
                st.rerun()

        st.divider()
        st.header("🔭 Bevakningslista")
        st.caption("Bolag du inte äger än men vill hålla koll på.")
        sokterm_bevakning = st.text_input(
            "Lägg till en bevakning (sök på bolagsnamn)",
            placeholder="t.ex. Volvo eller Apple",
            key="sok_bevakning",
        )

        if sokterm_bevakning.strip():
            traffar_bevakning = sok_bolag(sokterm_bevakning)
            if not traffar_bevakning:
                st.caption("Inga träffar - prova ett annat sökord.")
            else:
                etiketter_bevakning = [
                    f"{t.get('shortname') or t.get('longname')} ({t['symbol']}, {t.get('exchDisp', '-')})"
                    for t in traffar_bevakning
                ]
                valt_index_bevakning = st.selectbox(
                    "Välj rätt bolag/börs",
                    range(len(traffar_bevakning)),
                    format_func=lambda i: etiketter_bevakning[i],
                    key="valt_bevakning",
                )
                if st.button("➕ Lägg till bevakning", use_container_width=True):
                    info = bolagsinfo_fran_traff(traffar_bevakning[valt_index_bevakning])
                    st.session_state.bevakning[info["namn"]] = {
                        "ticker": info["ticker"],
                        "borskollen": info["borskollen"],
                        "sok": info["sok"],
                        "onskad_kop": None,
                    }
                    persistence_service.spara_bevakning()
                    st.success(f"{info['namn']} tillagd i bevakningslistan!")

        if st.session_state.bevakning:
            st.caption("Dina bevakade bolag:")
            for namn in list(st.session_state.bevakning.keys()):
                c1, c2 = st.columns([5, 1])
                c1.write(namn)
                if c2.button("✕", key=f"tabort_bevakning_{namn}"):
                    del st.session_state.bevakning[namn]
                    persistence_service.spara_bevakning()
                    st.rerun()

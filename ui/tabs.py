"""
Innehållet i appens flikar - en render_*-funktion per flik.
"""

import datetime

import pandas as pd
import numpy as np
import streamlit as st

from services import persistence_service, transactions_service, ai_coach_service, report_service
from services.gemini_service import GEMINI_API_KEY
from services.market_data_service import hamta_kursdata, flagga, hamta_index_historik
from services.sentiment_service import hamta_nyheter_for_bolag, ar_troligen_relevant, analysera_sentiment
from services.riktkurs_service import hamta_riktkurs, sentiment_till_text
from services.technical_service import (
    berakna_rsi, berakna_macd, berakna_bollinger, berakna_atr, golden_death_status,
)
from services.risk_service import berakna_volatilitet, berakna_sharpe, berakna_max_drawdown, berakna_beta
from services.dividend_service import hamta_utdelningsanalys
from services.macro_service import FRED_API_KEY, MAKRO_SERIER, hamta_fred_varde


def render_oversikt(PORTFOLJ):
    st.subheader("Snabböverblick över alla innehav")
    st.caption(
        "Tips: sätt en egen målkurs i sista kolumnen - du ser direkt i "
        "\"Målkurs nådd\" om kursen har nått den."
    )
    innehav = transactions_service.berakna_innehav(st.session_state.transaktioner)

    rader = []
    totalt_marknadsvarde = 0.0
    totalt_anskaffningsvarde = 0.0
    for namn, data in PORTFOLJ.items():
        senaste_pris = None
        valuta = "kr"
        try:
            hist, info = hamta_kursdata(data["ticker"])
            senaste_pris = hist["Close"].iloc[-1] if not hist.empty else None
            valuta = info.get("currency") or "kr"
        except Exception:
            pass

        riktkurs_data = hamta_riktkurs(data["borskollen"])
        riktkurs = None
        if riktkurs_data and not riktkurs_data.get("ingen_bevakning"):
            riktkurs = riktkurs_data.get("riktkurs")

        uppsida = None
        if riktkurs and senaste_pris:
            uppsida = (riktkurs - senaste_pris) / senaste_pris * 100

        malkurs = data.get("malkurs")
        malkurs_status = "–"
        if malkurs and senaste_pris:
            if senaste_pris >= malkurs:
                malkurs_status = "✅ Nådd"
            else:
                malkurs_status = f"{(malkurs - senaste_pris) / senaste_pris * 100:.1f}% kvar"

        bolagsinnehav = innehav.get(namn)
        antal_aktier = bolagsinnehav["antal"] if bolagsinnehav else 0.0
        gav = bolagsinnehav["gav"] if bolagsinnehav else 0.0
        marknadsvarde = antal_aktier * senaste_pris if (antal_aktier and senaste_pris) else None
        oreal_vinst_pct = None
        if antal_aktier and gav and senaste_pris:
            oreal_vinst_pct = (senaste_pris - gav) / gav * 100
            totalt_marknadsvarde += marknadsvarde
            totalt_anskaffningsvarde += antal_aktier * gav

        rader.append({
            "Bolag": namn,
            "Antal aktier": round(antal_aktier, 4) if antal_aktier else None,
            "GAV": f"{gav:.2f} {valuta}" if antal_aktier else None,
            "Kurs": f"{senaste_pris:.1f} {valuta}" if senaste_pris else None,
            "Marknadsvärde": f"{marknadsvarde:,.0f} {valuta}".replace(",", " ") if marknadsvarde else None,
            "Orealiserad vinst %": round(oreal_vinst_pct, 1) if oreal_vinst_pct is not None else None,
            "Riktkurs": f"{riktkurs:.1f} {valuta}" if riktkurs else None,
            "Uppsida %": round(uppsida, 1) if uppsida is not None else None,
            "Min målkurs (i aktiens valuta)": float(malkurs) if malkurs else np.nan,
            "Målkurs nådd": malkurs_status,
        })

    if totalt_anskaffningsvarde:
        totalt_vinst_pct = (totalt_marknadsvarde - totalt_anskaffningsvarde) / totalt_anskaffningsvarde * 100
        c1, c2, c3 = st.columns(3)
        c1.metric("Totalt marknadsvärde", f"{totalt_marknadsvarde:,.0f} kr".replace(",", " "))
        c2.metric("Totalt anskaffningsvärde", f"{totalt_anskaffningsvarde:,.0f} kr".replace(",", " "))
        c3.metric("Orealiserad vinst", f"{totalt_vinst_pct:+.1f} %")
    else:
        st.info(
            "Inga transaktioner loggade än, så antal aktier/marknadsvärde saknas nedan. "
            "Logga dina köp under fliken \"💰 Transaktioner\" för att få dessa siffror."
        )

    oversikt_df = pd.DataFrame(rader)
    redigerad_df = st.data_editor(
        oversikt_df,
        column_config={
            "Bolag": st.column_config.TextColumn(disabled=True),
            "Antal aktier": st.column_config.NumberColumn(disabled=True),
            "GAV": st.column_config.TextColumn(disabled=True),
            "Kurs": st.column_config.TextColumn(disabled=True),
            "Marknadsvärde": st.column_config.TextColumn(disabled=True),
            "Orealiserad vinst %": st.column_config.NumberColumn(disabled=True, format="%.1f"),
            "Riktkurs": st.column_config.TextColumn(disabled=True),
            "Uppsida %": st.column_config.NumberColumn(disabled=True, format="%.1f"),
            "Min målkurs (i aktiens valuta)": st.column_config.NumberColumn(
                min_value=0.0, step=0.5, format="%.1f",
                help="Din egen målkurs, i samma valuta som kursen (t.ex. USD för amerikanska "
                     "aktier) - flaggas som nådd när kursen är på eller över detta.",
            ),
            "Målkurs nådd": st.column_config.TextColumn(disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        key="oversikt_malkurs_editor",
    )

    andrat = False
    for i, namn in enumerate(PORTFOLJ.keys()):
        ny_malkurs = redigerad_df.loc[i, "Min målkurs (i aktiens valuta)"]
        ny_malkurs = float(ny_malkurs) if pd.notna(ny_malkurs) else None
        if PORTFOLJ[namn].get("malkurs") != ny_malkurs:
            PORTFOLJ[namn]["malkurs"] = ny_malkurs
            andrat = True
    if andrat:
        persistence_service.spara_portfolj()


def render_transaktioner(PORTFOLJ):
    st.subheader("Transaktioner")
    st.caption(
        "Logga dina köp, sälj, utdelningar och splitar. Det här är grunden för "
        "antal aktier, anskaffningsvärde (GAV) och verklig avkastning i \"Översikt\"."
    )

    st.markdown("##### Lägg till transaktion")
    c1, c2, c3 = st.columns(3)
    bolag = c1.selectbox("Bolag", list(PORTFOLJ.keys()), key="transaktion_bolag")
    typ = c2.selectbox("Typ", transactions_service.TYPER, key="transaktion_typ")
    datum = c3.date_input("Datum", value=datetime.date.today(), key="transaktion_datum")

    with st.form("ny_transaktion_form", clear_on_submit=True):
        if typ in ("Köp", "Sälj"):
            fc1, fc2, fc3 = st.columns(3)
            antal = fc1.number_input("Antal aktier", min_value=0.0, step=1.0)
            pris = fc2.number_input("Pris per aktie (i aktiens valuta)", min_value=0.0, step=0.5)
            avgift = fc3.number_input("Avgift/courtage", min_value=0.0, step=1.0, value=0.0)
        elif typ == "Utdelning":
            antal = st.number_input("Totalt utdelningsbelopp (i aktiens valuta)", min_value=0.0, step=1.0)
            pris, avgift = 0.0, 0.0
        else:
            antal = st.number_input(
                "Splitfaktor (t.ex. 2 för 2:1-split, 0.5 för omvänd split 1:2)",
                min_value=0.0, step=0.5, value=2.0,
            )
            pris, avgift = 0.0, 0.0

        if st.form_submit_button("➕ Lägg till transaktion"):
            transactions_service.lagg_till_transaktion(bolag, typ, datum, antal, pris, avgift)
            persistence_service.spara_transaktioner()
            st.success("Transaktion tillagd!")
            st.rerun()

    st.divider()
    st.markdown("##### Historik")
    if not st.session_state.transaktioner:
        st.caption("Inga transaktioner loggade än.")
    else:
        ordnade = sorted(
            enumerate(st.session_state.transaktioner),
            key=lambda pair: pair[1]["datum"],
            reverse=True,
        )
        for orig_index, t in ordnade:
            if t["typ"] in ("Köp", "Sälj"):
                detaljer = f"{t['antal']:g} st à {t['pris']:g} (avgift {t['avgift']:g})"
            elif t["typ"] == "Utdelning":
                detaljer = f"{t['antal']:g}"
            else:
                detaljer = f"Faktor {t['antal']:g}"

            c1, c2, c3, c4, c5 = st.columns([1.3, 2, 1.3, 3, 0.6])
            c1.write(t["datum"])
            c2.write(t["bolag"])
            c3.write(t["typ"])
            c4.write(detaljer)
            if c5.button("✕", key=f"tabort_transaktion_{orig_index}"):
                transactions_service.ta_bort_transaktion(orig_index)
                persistence_service.spara_transaktioner()
                st.rerun()


def render_historik(PORTFOLJ):
    st.subheader("Portföljens utveckling över tid")
    st.caption(
        "En punkt läggs till automatiskt varje dag du öppnar appen - historiken byggs "
        "alltså upp framåt i tiden och saknar data bakåt innan du började logga."
    )

    historik = st.session_state.portfolj_historik
    if len(historik) < 2:
        st.info(
            "För få datapunkter ännu. Öppna appen på olika dagar så byggs en graf upp "
            "här av sig själv - inget mer du behöver göra."
        )
        return

    historik_df = pd.DataFrame(historik)
    historik_df["datum"] = pd.to_datetime(historik_df["datum"])
    historik_df = historik_df.set_index("datum")

    forsta_varde = historik_df["varde"].iloc[0]
    sista_varde = historik_df["varde"].iloc[-1]
    forandring_pct = (sista_varde - forsta_varde) / forsta_varde * 100 if forsta_varde else None
    max_drawdown = berakna_max_drawdown(historik_df["varde"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Senaste portföljvärde", f"{sista_varde:,.0f} kr".replace(",", " "))
    c2.metric(
        "Utveckling sedan första loggade dagen",
        f"{forandring_pct:+.1f} %" if forandring_pct is not None else "–",
    )
    c3.metric("Största nedgång (drawdown)", f"{max_drawdown:.1f} %")

    st.line_chart(historik_df["varde"])


@st.fragment
def _ai_sammanfattning_fragment(PORTFOLJ, score_data):
    if st.button("✨ Generera AI-sammanfattning"):
        with st.spinner("Coachen tänker..."):
            text, fel = ai_coach_service.generera_ai_sammanfattning(PORTFOLJ, score_data)
        if fel:
            st.error(f"Kunde inte hämta AI-sammanfattning: {fel}")
        else:
            st.session_state.ai_sammanfattning = text

    if st.session_state.get("ai_sammanfattning"):
        st.markdown(st.session_state.ai_sammanfattning)


def render_ai_coach(PORTFOLJ):
    st.subheader("🤖 AI-portföljcoach")
    st.caption(
        "Portföljscoren räknas alltid ut lokalt utifrån dina siffror (diversifiering, "
        "risk, historisk utveckling). Sammanfattningen nedan skrivs av Google Gemini "
        "utifrån exakt dessa siffror - inget annat om dig eller din portfölj skickas iväg."
    )

    score_data = ai_coach_service.berakna_portfoljscore(PORTFOLJ)
    if not score_data["antal_bolag"]:
        st.info(
            "Inga innehav med registrerade transaktioner ännu - logga köp under "
            "\"💰 Transaktioner\" för att få en portföljscore."
        )
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Portföljscore", f"{score_data['score']} / 100")
    c2.metric(
        "Största innehavets andel",
        f"{score_data['storsta_andel_pct']} %" if score_data["storsta_andel_pct"] is not None else "–",
    )
    c3.metric(
        "Snittvolatilitet",
        f"{score_data['snitt_volatilitet_pct']} %" if score_data["snitt_volatilitet_pct"] is not None else "–",
    )
    c4.metric(
        "Max drawdown (historik)",
        f"{score_data['max_drawdown_pct']} %" if score_data["max_drawdown_pct"] is not None else "–",
    )

    st.divider()

    if not ai_coach_service.GEMINI_API_KEY:
        st.warning(
            "Ingen Gemini API-nyckel konfigurerad. Skapa en gratis nyckel på "
            "aistudio.google.com/apikey och lägg till den som GEMINI_API_KEY i "
            ".streamlit/secrets.toml (lokalt) eller Streamlit Cloud → Settings → Secrets."
        )
        return

    _ai_sammanfattning_fragment(PORTFOLJ, score_data)


@st.fragment
def _rapport_sammanfattning_fragment(valt_bolag, kvartalsdata):
    if st.button("✨ Sammanfatta senaste rapporten", key=f"rapport_btn_{valt_bolag}"):
        with st.spinner("Läser rapporten..."):
            text, fel = report_service.generera_rapportsammanfattning(valt_bolag, kvartalsdata)
        if fel:
            st.error(f"Kunde inte hämta sammanfattning: {fel}")
        else:
            st.session_state[f"rapport_sammanfattning_{valt_bolag}"] = text

    sparad_text = st.session_state.get(f"rapport_sammanfattning_{valt_bolag}")
    if sparad_text:
        st.markdown(sparad_text)


def render_rapporter(PORTFOLJ):
    st.subheader("📄 Rapportsammanfattningar")
    st.caption(
        "AI-sammanfattning av bolagets senaste kvartalsrapport, baserat på faktiska "
        "nyckeltal (omsättning, resultat) hämtade från Yahoo Finance - inte gissningar."
    )

    valt_bolag = st.selectbox("Välj bolag", list(PORTFOLJ.keys()), key="rapport_val")
    ticker = PORTFOLJ[valt_bolag]["ticker"]
    kvartalsdata = report_service.hamta_kvartalsdata(ticker)

    if not kvartalsdata or len(kvartalsdata["kvartal"]) < 2:
        st.info("Kunde inte hitta tillräckligt med kvartalsdata för det här bolaget.")
        return

    if kvartalsdata["nasta_rapportdatum"]:
        st.caption(f"Nästa rapportdatum (uppskattat): {kvartalsdata['nasta_rapportdatum']}")

    valuta = kvartalsdata["valuta"]
    tabell_rader = []
    for rad in kvartalsdata["kvartal"]:
        formaterad = {"Kvartal": rad["datum"]}
        for namn in report_service.NYCKELTAL.values():
            varde = rad.get(namn)
            if varde is None:
                formaterad[namn] = "–"
            elif namn == "Resultat per aktie":
                formaterad[namn] = f"{varde:.2f} {valuta}"
            else:
                formaterad[namn] = f"{varde:,.0f} {valuta}".replace(",", " ")
        tabell_rader.append(formaterad)
    st.dataframe(pd.DataFrame(tabell_rader), use_container_width=True, hide_index=True)

    st.divider()

    if not GEMINI_API_KEY:
        st.warning(
            "Ingen Gemini API-nyckel konfigurerad. Se \"🤖 AI-coach\"-fliken för "
            "instruktioner om hur du lägger till en."
        )
        return

    _rapport_sammanfattning_fragment(valt_bolag, kvartalsdata)


def render_nyheter_sentiment(PORTFOLJ):
    st.subheader("Senaste relevanta nyheter per bolag")
    valt_bolag = st.selectbox("Välj bolag", list(PORTFOLJ.keys()), key="nyheter_val")
    sokterm = PORTFOLJ[valt_bolag]["sok"]

    try:
        alla_rubriker = hamta_nyheter_for_bolag(sokterm)
        relevanta = [r for r in alla_rubriker if ar_troligen_relevant(sokterm, r)]

        if not relevanta:
            st.info("Inga färska, relevanta nyheter hittades just nu.")
        for rubrik in relevanta:
            poang, bedomning = analysera_sentiment(rubrik)
            farg = {"POSITIV": "green", "NEGATIV": "red", "NEUTRAL": "gray"}[bedomning]
            st.markdown(f":{farg}[**{bedomning}**] ({poang:+d})  {rubrik}")
    except Exception as e:
        st.error(f"Kunde inte hämta nyheter: {e}")


def render_nyckeltal(PORTFOLJ):
    st.subheader("Grundläggande nyckeltal")
    st.caption("⚠ = ovanligt högt värde - jämför gärna mot Avanza innan du litar på siffran.")

    with st.expander("ℹ️ Vad betyder nyckeltalen?"):
        st.markdown("""
- **P/E (pris/vinst):** Hur mycket du betalar per krona i vinst bolaget gör.
  Lågt *kan* betyda billigt, men kan också betyda att marknaden väntar sig
  problem - jämför alltid inom samma bransch.
- **P/B (pris/bokfört värde):** Priset jämfört med vad som skulle vara kvar
  om bolaget sålde av allt och betalade sina skulder.
- **Direktavkastning:** Årlig utdelning i procent av aktiekursen.
- **Vinstmarginal:** Hur stor andel av omsättningen som blir faktisk vinst.
  Banker ser strukturellt högre ut här - inte för att de är mer lönsamma,
  utan för hur intäkter räknas i deras verksamhet.
- **ROE (avkastning på eget kapital):** Hur effektivt bolaget använder
  ägarnas pengar för att skapa vinst.
- **Börsvärde:** Bolagets totala prislapp på börsen.
        """)

    nyckeltal_rader = []
    for namn, data in PORTFOLJ.items():
        try:
            _, info = hamta_kursdata(data["ticker"])
            div = info.get("dividendYield")
            marg = info.get("profitMargins")
            roe = info.get("returnOnEquity")
            mcap = info.get("marketCap")
            valuta_nyckeltal = info.get("currency") or "kr"
            nyckeltal_rader.append({
                "Bolag": namn,
                "P/E": flagga(info.get("trailingPE"), 100),
                "P/B": flagga(info.get("priceToBook"), 15),
                "Direktavk. %": f"{div:.1f}" if div is not None else "–",
                "Vinstmarg. %": f"{marg * 100:.1f}" if marg is not None else "–",
                "ROE %": flagga(roe * 100 if roe is not None else None, 60),
                "Börsvärde (mdr)": f"{mcap / 1e9:.1f} {valuta_nyckeltal}" if mcap else "–",
            })
        except Exception:
            nyckeltal_rader.append({"Bolag": namn, "P/E": "fel", "P/B": "-", "Direktavk. %": "-", "Vinstmarg. %": "-", "ROE %": "-", "Börsvärde (mdr)": "-"})

    st.dataframe(pd.DataFrame(nyckeltal_rader), use_container_width=True, hide_index=True)


def render_kursutveckling(PORTFOLJ):
    st.subheader("Kursutveckling senaste året")

    vy = st.radio(
        "Visa",
        ["Alla bolag (jämförelse)", "Enskilt bolag"],
        horizontal=True,
        key="kursutv_vy",
    )

    if vy == "Alla bolag (jämförelse)":
        st.caption("Normaliserat, start = 100 - för att kunna jämföra utveckling oavsett kurs.")
        visa_index_alla = st.checkbox("Jämför med index (OMXS30)", value=True, key="visa_index_alla")
        normaliserad_df = pd.DataFrame()
        for namn, data in PORTFOLJ.items():
            try:
                hist, _ = hamta_kursdata(data["ticker"])
                if not hist.empty:
                    normaliserad_df[namn] = hist["Close"] / hist["Close"].iloc[0] * 100
            except Exception:
                continue
        if visa_index_alla:
            try:
                index_hist = hamta_index_historik()
                if not index_hist.empty:
                    normaliserad_df["OMXS30 (index)"] = index_hist["Close"] / index_hist["Close"].iloc[0] * 100
            except Exception:
                pass
        st.line_chart(normaliserad_df)
    else:
        valt_bolag_kurs = st.selectbox("Välj bolag", list(PORTFOLJ.keys()), key="kursutv_bolag")
        jamfor_index_enskilt = st.checkbox(
            "Jämför med index (OMXS30, normaliserat)", value=False, key="jamfor_index_enskilt",
        )
        ticker_kurs = PORTFOLJ[valt_bolag_kurs]["ticker"]
        try:
            hist, _ = hamta_kursdata(ticker_kurs)
            if hist.empty:
                st.warning("Ingen kursdata hittades för det här bolaget.")
            elif jamfor_index_enskilt:
                jamforelse_df = pd.DataFrame()
                jamforelse_df[valt_bolag_kurs] = hist["Close"] / hist["Close"].iloc[0] * 100
                try:
                    index_hist = hamta_index_historik()
                    if not index_hist.empty:
                        jamforelse_df["OMXS30 (index)"] = index_hist["Close"] / index_hist["Close"].iloc[0] * 100
                except Exception:
                    pass
                st.caption("Normaliserat, start = 100.")
                st.line_chart(jamforelse_df)
            else:
                st.line_chart(hist["Close"].rename(valt_bolag_kurs))
        except Exception as e:
            st.error(f"Kunde inte hämta kursdata: {e}")


def render_riktkurser(PORTFOLJ):
    st.subheader("Analytikers riktkurser och sentiment")
    st.caption(
        "Riktkurs = genomsnittet av vad analytiker/banker tror aktien BORDE vara värd. "
        "Fungerar bara pålitligt för kända, större bolag - mindre eller utländska "
        "innehav visar ofta 'hittades inte'."
    )
    riktkurs_rader = []
    for namn, data in PORTFOLJ.items():
        resultat = hamta_riktkurs(data["borskollen"])
        try:
            _, info_riktkurs = hamta_kursdata(data["ticker"])
            valuta = info_riktkurs.get("currency") or "kr"
        except Exception:
            valuta = "kr"

        if resultat is None:
            riktkurs_rader.append({"Bolag": namn, "Riktkurs": "hittades inte", "Analytikersentiment": "-"})
        elif resultat.get("ingen_bevakning"):
            riktkurs_rader.append({"Bolag": namn, "Riktkurs": "ingen bevakning", "Analytikersentiment": "-"})
        else:
            riktkurs_rader.append({
                "Bolag": namn,
                "Riktkurs": f"{resultat['riktkurs']:.1f} {valuta}" if resultat.get("riktkurs") else "-",
                "Analytikersentiment": sentiment_till_text(resultat.get("sentiments")),
            })
    st.dataframe(pd.DataFrame(riktkurs_rader), use_container_width=True, hide_index=True)


def render_teknisk_analys(PORTFOLJ):
    st.subheader("Teknisk analys")
    valt_bolag_tech = st.selectbox("Välj bolag", list(PORTFOLJ.keys()), key="tech_val")
    ticker_tech = PORTFOLJ[valt_bolag_tech]["ticker"]

    try:
        hist, info_tech = hamta_kursdata(ticker_tech)
        close = hist["Close"]
        valuta_tech = info_tech.get("currency") or "kr"

        if len(close) < 30:
            st.warning("För lite historik för meningsfull teknisk analys.")
        else:
            rsi = berakna_rsi(close)
            senaste_rsi = rsi.iloc[-1]
            rsi_tolkning = (
                "Överköpt (>70)" if senaste_rsi > 70
                else "Översåld (<30)" if senaste_rsi < 30
                else "Neutral"
            )

            macd_linje, signal_linje, _ = berakna_macd(close)
            macd_tolkning = (
                "positivt momentum" if macd_linje.iloc[-1] > signal_linje.iloc[-1]
                else "negativt momentum"
            )

            _, ovre_band, nedre_band = berakna_bollinger(close)
            senaste_pris = close.iloc[-1]
            if senaste_pris > ovre_band.iloc[-1]:
                bollinger_tolkning = "över övre bandet (kan indikera överköpt)"
            elif senaste_pris < nedre_band.iloc[-1]:
                bollinger_tolkning = "under nedre bandet (kan indikera översåld)"
            else:
                bollinger_tolkning = "inom banden (normal rörelse)"

            atr = berakna_atr(hist)

            col1, col2, col3 = st.columns(3)
            col1.metric(
                "RSI (14 dagar)", f"{senaste_rsi:.1f}", rsi_tolkning,
                help="0-100. Över 70 = 'överköpt'. Under 30 = 'översåld'. Historiska mönster, ingen garanti.",
            )
            col2.metric(
                "MACD", f"{macd_linje.iloc[-1]:.2f}", macd_tolkning,
                help="Skillnaden mellan ett kort och ett långt glidande medelvärde - visar momentum.",
            )
            col3.metric(
                f"ATR ({valuta_tech})", f"{atr.iloc[-1]:.2f}",
                help="Genomsnittlig daglig prisrörelse senaste 14 dagarna - mått på volatilitet.",
            )

            st.markdown(
                f"**Bollinger Bands:** pris {senaste_pris:.1f} {valuta_tech} är {bollinger_tolkning} "
                f"(övre: {ovre_band.iloc[-1]:.1f}, nedre: {nedre_band.iloc[-1]:.1f})"
            )
            st.markdown(f"**Golden/Death Cross:** {golden_death_status(close)}")

            with st.expander("ℹ️ Vad betyder Bollinger Bands och Golden/Death Cross?"):
                st.markdown("""
- **Bollinger Bands:** Ett "normalintervall" runt priset baserat på hur
  mycket kursen svängt senaste tiden.
- **Golden/Death Cross:** När det kortare glidande medelvärdet (50 dagar)
  korsar det längre (200 dagar). Ett efterföljande mönster, inte en
  förutsägelse - stämmer långt ifrån alltid.
                """)

            ma_df = pd.DataFrame({
                "Pris": close,
                "MA20": close.rolling(20).mean(),
                "MA50": close.rolling(50).mean(),
                "MA100": close.rolling(100).mean(),
                "MA200": close.rolling(200).mean(),
            })
            st.line_chart(ma_df)
    except Exception as e:
        st.error(f"Kunde inte beräkna teknisk analys: {e}")


def render_risk_korrelation(PORTFOLJ):
    st.subheader("Riskmått per innehav")
    st.caption("Beta beräknas mot OMXS30 (^OMX). Riskfri ränta antagen till 2%.")

    with st.expander("ℹ️ Vad betyder riskmåtten?"):
        st.markdown("""
- **Volatilitet:** Hur mycket kursen svänger, omräknat till ett årligt
  procenttal.
- **Sharpe-kvot:** Avkastning i förhållande till risken som togs för att
  få den. Högre är bättre.
- **Max drawdown:** Den största nedgången från en topp till en
  efterföljande botten senaste året.
- **Beta:** Hur mycket aktien rör sig i förhållande till hela börsen.
  Beta 1 = som index. Över 1 = svänger mer. Under 1 = svänger mindre.
        """)

    riskrader = []
    avkastningar_dict = {}
    try:
        index_close = hamta_index_historik()["Close"]
    except Exception:
        index_close = None

    for namn, data in PORTFOLJ.items():
        try:
            hist, _ = hamta_kursdata(data["ticker"])
            close = hist["Close"]
            avkastningar_dict[namn] = close.pct_change(fill_method=None)

            volatilitet = berakna_volatilitet(close)
            sharpe = berakna_sharpe(close)
            max_dd = berakna_max_drawdown(close)
            beta = berakna_beta(close, index_close) if index_close is not None else None

            riskrader.append({
                "Bolag": namn,
                "Volatilitet % (årlig)": f"{volatilitet:.1f}" if volatilitet is not None else "–",
                "Sharpe-kvot": f"{sharpe:.2f}" if sharpe is not None else "–",
                "Max drawdown %": f"{max_dd:.1f}" if max_dd is not None else "–",
                "Beta (mot OMXS30)": f"{beta:.2f}" if beta is not None else "–",
            })
        except Exception:
            riskrader.append({
                "Bolag": namn, "Volatilitet % (årlig)": "fel", "Sharpe-kvot": "-",
                "Max drawdown %": "-", "Beta (mot OMXS30)": "-",
            })

    st.dataframe(pd.DataFrame(riskrader), use_container_width=True, hide_index=True)

    st.subheader("Korrelation mellan dina innehav")
    st.caption(
        "Nära +1 = rör sig likadant (mindre riskspridning om du äger båda). "
        "Nära -1 = rör sig motsatt. Nära 0 = i princip orelaterat (bättre riskspridning)."
    )
    try:
        avkastningar_df = pd.DataFrame(avkastningar_dict).dropna()
        korrelation = avkastningar_df.corr()
        st.dataframe(
            korrelation.style.format("{:.2f}").background_gradient(cmap="RdYlGn", vmin=-1, vmax=1),
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Kunde inte beräkna korrelation: {e}")


def render_utdelningar(PORTFOLJ):
    st.subheader("Utdelningar")
    valt_bolag_utd = st.selectbox("Välj bolag", list(PORTFOLJ.keys()), key="utd_val")
    ticker_utd = PORTFOLJ[valt_bolag_utd]["ticker"]

    try:
        utd = hamta_utdelningsanalys(ticker_utd)
        if utd["historik"].empty:
            st.info("Ingen utdelningshistorik hittades för det här bolaget.")
        else:
            st.bar_chart(utd["historik"].tail(10))

            if utd["tillvaxt_procent"] is not None:
                st.metric("Förändring (senaste utdelningarna)", f"{utd['tillvaxt_procent']:+.1f}%")
                if utd["ojamn_historik"]:
                    st.warning(
                        "Ojämna utdelningsintervall upptäckta - bolaget verkar ha missat "
                        "utdelning nåt år, så tillväxtsiffran ovan är mindre tillförlitlig."
                    )

            if utd["rapportdatum"]:
                if utd["rapportdatum_kommande"]:
                    dagar = (utd["rapportdatum"] - datetime.date.today()).days
                    st.markdown(f"**Nästa rapportdatum:** {utd['rapportdatum']} (om {dagar} dagar)")
                else:
                    st.markdown(f"**Senast kända rapportdatum:** {utd['rapportdatum']} (redan passerat, nästa inte tillgängligt än)")

            if utd["ex_datum"]:
                if utd["ex_datum_kommande"]:
                    st.markdown(f"**Nästa ex-utdelningsdag:** {utd['ex_datum']}")
                else:
                    st.markdown(f"**Senast kända ex-utdelningsdag:** {utd['ex_datum']} (redan passerat)")
    except Exception as e:
        st.error(f"Kunde inte hämta utdelningsdata: {e}")


def render_makroekonomi():
    st.subheader("Makroekonomiska indikatorer")
    if not FRED_API_KEY:
        st.warning(
            "Ingen FRED API-nyckel konfigurerad. Lägg till din nyckel under "
            "Streamlit Cloud → Settings → Secrets (se instruktionerna i chatten)."
        )
    else:
        makro_rader = []
        for namn, info in MAKRO_SERIER.items():
            datum, varde, fel = hamta_fred_varde(info["id"], FRED_API_KEY, info["units"])
            makro_rader.append({
                "Mått": namn,
                "Värde": f"{varde} {info['enhet']}" if varde else "–",
                "Datum": datum if datum else "–",
                "Status": fel if fel else "OK",
            })
        st.dataframe(pd.DataFrame(makro_rader), use_container_width=True, hide_index=True)


def render_bevakningslista():
    st.subheader("Bevakningslista")
    st.caption(
        "Bolag du inte äger än men vill hålla koll på inför en framtida "
        "investering. Sätt en önskad köpkurs så ser du direkt i \"Köpläge\" "
        "om kursen har nått ner till den."
    )

    if not st.session_state.bevakning:
        st.info("Bevakningslistan är tom - lägg till en aktie i sidopanelen.")
    else:
        BEVAKNING = st.session_state.bevakning
        bevakning_rader = []
        for namn, data in BEVAKNING.items():
            senaste_pris = None
            valuta = "kr"
            try:
                hist, info = hamta_kursdata(data["ticker"])
                senaste_pris = hist["Close"].iloc[-1] if not hist.empty else None
                valuta = info.get("currency") or "kr"
            except Exception:
                pass

            riktkurs_data = hamta_riktkurs(data["borskollen"])
            riktkurs = None
            if riktkurs_data and not riktkurs_data.get("ingen_bevakning"):
                riktkurs = riktkurs_data.get("riktkurs")

            onskad_kop = data.get("onskad_kop")
            kopläge_status = "–"
            if onskad_kop and senaste_pris:
                if senaste_pris <= onskad_kop:
                    kopläge_status = "✅ Läge att köpa"
                else:
                    kopläge_status = f"{(senaste_pris - onskad_kop) / onskad_kop * 100:.1f}% kvar ner"

            bevakning_rader.append({
                "Bolag": namn,
                "Kurs": f"{senaste_pris:.1f} {valuta}" if senaste_pris else None,
                "Riktkurs": f"{riktkurs:.1f} {valuta}" if riktkurs else None,
                "Önskad köpkurs (i aktiens valuta)": float(onskad_kop) if onskad_kop else np.nan,
                "Köpläge": kopläge_status,
            })

        bevakning_df = pd.DataFrame(bevakning_rader)
        redigerad_bevakning_df = st.data_editor(
            bevakning_df,
            column_config={
                "Bolag": st.column_config.TextColumn(disabled=True),
                "Kurs": st.column_config.TextColumn(disabled=True),
                "Riktkurs": st.column_config.TextColumn(disabled=True),
                "Önskad köpkurs (i aktiens valuta)": st.column_config.NumberColumn(
                    min_value=0.0, step=0.5, format="%.1f",
                    help="Kursen du vill köpa vid, i samma valuta som kursen (t.ex. USD för "
                         "amerikanska aktier) - flaggas som köpläge när kursen är på eller under detta.",
                ),
                "Köpläge": st.column_config.TextColumn(disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="bevakning_kop_editor",
        )

        andrat_bevakning = False
        for i, namn in enumerate(BEVAKNING.keys()):
            ny_onskad_kop = redigerad_bevakning_df.loc[i, "Önskad köpkurs (i aktiens valuta)"]
            ny_onskad_kop = float(ny_onskad_kop) if pd.notna(ny_onskad_kop) else None
            if BEVAKNING[namn].get("onskad_kop") != ny_onskad_kop:
                BEVAKNING[namn]["onskad_kop"] = ny_onskad_kop
                andrat_bevakning = True
        if andrat_bevakning:
            persistence_service.spara_bevakning()

        st.divider()
        st.caption("Bestämt dig för att köpa, eller vill ta bort en bevakning?")
        for namn in list(BEVAKNING.keys()):
            c1, c2, c3 = st.columns([4, 2, 2])
            c1.write(namn)
            if c2.button("➕ Flytta till portfölj", key=f"flytta_{namn}"):
                flyttad_data = BEVAKNING[namn]
                st.session_state.portfolj[namn] = {
                    "ticker": flyttad_data["ticker"],
                    "borskollen": flyttad_data["borskollen"],
                    "sok": flyttad_data["sok"],
                    "malkurs": None,
                }
                del st.session_state.bevakning[namn]
                persistence_service.spara_portfolj()
                persistence_service.spara_bevakning()
                st.success(f"{namn} flyttad till portföljen!")
                st.rerun()
            if c3.button("✕ Ta bort", key=f"tabort_bevakning_tab_{namn}"):
                del st.session_state.bevakning[namn]
                persistence_service.spara_bevakning()
                st.rerun()

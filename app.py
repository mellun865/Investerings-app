"""
Portföljanalys - komplett app som slår ihop allt vi byggt och testat:
nyhetssentiment, nyckeltal, kurshistorik, analytikers riktkurser,
teknisk analys, riskmått, utdelningar och makroekonomi. Användare kan
lägga till och ta bort egna innehav i sidopanelen.

Körs lokalt med: streamlit run app.py
Eller publiceras gratis via share.streamlit.io.
"""

import os
import re
import json
import datetime
import urllib.parse
import xml.etree.ElementTree as ET

import requests
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np


# ================================================================
# DEL 1: Startportfölj (bara för att fylla i nåt vid första besöket -
# användaren kan lägga till/ta bort fritt i sidopanelen)
# ================================================================

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

# Portföljen och bevakningslistan sparas till lokala JSON-filer så att egna
# tillägg/borttag, målkurser och önskade köpkurser finns kvar nästa gång
# appen startas, istället för att återställas varje gång.
PORTFOLJ_FIL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolj_data.json")
BEVAKNING_FIL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bevakning_data.json")


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


if "portfolj" not in st.session_state:
    st.session_state.portfolj = ladda_lista(PORTFOLJ_FIL, dict(STARTPORTFOLJ))
if "bevakning" not in st.session_state:
    st.session_state.bevakning = ladda_lista(BEVAKNING_FIL, {})


@st.cache_data(ttl=3600)
def sok_bolag(sokterm):
    """
    Söker upp bolag på namn (t.ex. "Volvo" eller "Apple") via yfinance.
    Returnerar en lista med träffar (aktier) som användaren kan välja
    rätt bolag/börs ur, utan att behöva känna till exakt ticker.
    """
    sokterm = sokterm.strip()
    if len(sokterm) < 2:
        return []
    try:
        traffar = yf.Search(sokterm, max_results=8).quotes
        return [
            t for t in traffar
            if t.get("quoteType") == "EQUITY" and t.get("symbol") and (t.get("shortname") or t.get("longname"))
        ]
    except Exception:
        return []


def bolagsinfo_fran_traff(traff):
    """
    Bygger portföljinfo utifrån en träff från sok_bolag().
    """
    namn = traff.get("shortname") or traff.get("longname")
    # Gissning för Börskollen-riktkurs - stämmer ofta INTE (vi vet det
    # efter mycket testande), men hamta_riktkurs hanterar redan en
    # felaktig gissning snyggt utan att krascha.
    borskollen_gissning = namn.lower().replace(" ", "-").replace(".", "").replace(",", "")
    return {
        "namn": namn,
        "ticker": traff["symbol"],
        "borskollen": borskollen_gissning,
        "sok": namn.split()[0].rstrip(",.;:"),
    }


# ================================================================
# DEL 2: Sentimentanalys
# ================================================================

def stamform(ord):
    andelser = ["ande", "ing", "ade", "are", "ed", "es", "ar", "er", "en", "et", "s", "a"]
    for andelse in andelser:
        if ord.endswith(andelse) and len(ord) - len(andelse) >= 4:
            return ord[: -len(andelse)]
    return ord


POSITIVA_ORD = {
    "stiger", "stigit", "uppgång", "vinst", "vinster", "rekord",
    "stark", "starkt", "tillväxt", "framgång", "optimism", "överträffar",
    "återhämtning", "stabil", "stabilitet", "överraskar",
    "positiv", "positivt", "rally", "toppnotering", "uppgraderar",
    "rise", "rises", "risen", "rising", "surge", "surges", "record",
    "growth", "strong", "profit", "profits", "gains", "gain",
    "recovery", "stable", "stability", "beats", "beat", "upgrade",
    "upgrades", "boost", "boosts", "soar", "soars", "higher", "up",
}

NEGATIVA_ORD = {
    "faller", "fallit", "nedgång", "förlust", "förluster", "kris",
    "recession", "osäkerhet", "oro", "konflikt", "eskalerar", "sjunker",
    "svag", "svagt", "pressar", "pressad", "chock", "panik", "ras",
    "negativ", "negativt", "varning", "nedskrivning", "nedgraderar",
    "bakslag", "undersöker", "försenat", "försenad",
    "falls", "fall", "fallen", "falling", "drop", "drops", "decline",
    "declines", "crisis", "loss", "losses", "uncertainty",
    "conflict", "escalate", "escalates", "escalating", "sinks", "weak",
    "weakens", "warns", "warning", "downgrade", "downgrades", "setback",
    "strike", "strikes", "collapse", "plunge", "plunges", "crash",
    "slump", "lower", "down",
}

POSITIVA_STAMMAR = {stamform(o) for o in POSITIVA_ORD}
NEGATIVA_STAMMAR = {stamform(o) for o in NEGATIVA_ORD}


def analysera_sentiment(rubrik):
    ord_i_rubriken = rubrik.lower().replace(",", "").replace(".", "").replace(";", "").split()
    antal_positiva = antal_negativa = 0
    for ord in ord_i_rubriken:
        stam = stamform(ord)
        if stam in POSITIVA_STAMMAR:
            antal_positiva += 1
        elif stam in NEGATIVA_STAMMAR:
            antal_negativa += 1
    poang = antal_positiva - antal_negativa
    bedomning = "POSITIV" if poang > 0 else "NEGATIV" if poang < 0 else "NEUTRAL"
    return poang, bedomning


def ar_troligen_relevant(bolag, rubrik):
    rubrik_lower = rubrik.lower()
    kortnamn = bolag.split()[0].lower()

    if kortnamn not in rubrik_lower:
        return False

    borjar_med_bolaget = rubrik_lower.startswith(kortnamn)
    analytiker_ord = ["höjer", "sänker", "köpstämplar", "säljer", "köper", "robur"]
    innehaller_analytikerord = any(ord in rubrik_lower for ord in analytiker_ord)
    egen_riktkurs = f"för {kortnamn}" in rubrik_lower
    if borjar_med_bolaget and innehaller_analytikerord and not egen_riktkurs:
        return False

    KANDA_KROCKAR = {
        "nordea": ["open", "tennis", "popyrin", "båstad"],
        "saab": ["cabriolet", "kultbil", "fantasten"],
    }
    if any(ord in rubrik_lower for ord in KANDA_KROCKAR.get(kortnamn, [])):
        return False

    return True


@st.cache_data(ttl=1800)
def hamta_nyheter_for_bolag(sokterm, max_antal=8):
    fraga = urllib.parse.quote(sokterm)
    url = f"https://news.google.com/rss/search?q={fraga}&hl=sv&gl=SE&ceid=SE:sv"
    request = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    root = ET.fromstring(request.content)
    return [item.find("title").text for item in root.findall(".//item")][:max_antal]


# ================================================================
# DEL 3: Aktiekurser och nyckeltal
# ================================================================

@st.cache_data(ttl=900)
def hamta_kursdata(ticker):
    aktie = yf.Ticker(ticker)
    hist = aktie.history(period="1y")
    hist = hist.dropna(subset=["Close"])
    info = aktie.info
    return hist, info


def flagga(varde, grans):
    if varde is None:
        return "–"
    text = f"{varde:.1f}"
    if varde > grans:
        text += " ⚠"
    return text


# ================================================================
# DEL 4: Riktkurser från Börskollen
# ================================================================

@st.cache_data(ttl=3600 * 6)
def hamta_riktkurs(url_namn):
    url = f"https://www.borskollen.se/aktie/{url_namn}/riktkurs"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
    svar = requests.get(url, headers=headers, timeout=10)
    if svar.status_code != 200:
        return None

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        svar.text, re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        recs = data["props"]["pageProps"]["recs"]
        if not recs.get("items"):
            return {"ingen_bevakning": True}
        return {
            "riktkurs": recs.get("averageRecPrice"),
            "sentiments": recs.get("sentiments"),
            "ingen_bevakning": False,
        }
    except (KeyError, json.JSONDecodeError, TypeError):
        return None


def sentiment_till_text(sentiments):
    if not sentiments:
        return "–"
    delar = [f"{s['sentiment']}: {s['count']}" for s in sentiments if s.get("count", 0) > 0]
    return ", ".join(delar) if delar else "–"


# ================================================================
# DEL 5: Teknisk analys och riskmått
# ================================================================

def berakna_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def berakna_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_linje = ema12 - ema26
    signal_linje = macd_linje.ewm(span=9, adjust=False).mean()
    return macd_linje, signal_linje, macd_linje - signal_linje


def berakna_bollinger(close, period=20, antal_std=2):
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    return sma, sma + antal_std * std, sma - antal_std * std


def berakna_atr(hist, period=14):
    high_low = hist["High"] - hist["Low"]
    high_close = (hist["High"] - hist["Close"].shift()).abs()
    low_close = (hist["Low"] - hist["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def golden_death_status(close):
    ma50, ma200 = close.rolling(50).mean(), close.rolling(200).mean()
    if pd.isna(ma50.iloc[-1]) or pd.isna(ma200.iloc[-1]):
        return "Otillräcklig historik (behöver minst 200 dagars data)"
    return ("Golden Cross-läge (MA50 över MA200, historiskt bullish)" if ma50.iloc[-1] > ma200.iloc[-1]
            else "Death Cross-läge (MA50 under MA200, historiskt bearish)")


def berakna_volatilitet(close):
    r = close.pct_change(fill_method=None).dropna()
    return r.std() * (252 ** 0.5) * 100 if len(r) > 1 else None


def berakna_sharpe(close, riskfri_ranta=0.02):
    r = close.pct_change(fill_method=None).dropna()
    if len(r) < 2 or r.std() == 0:
        return None
    return (r.mean() * 252 - riskfri_ranta) / (r.std() * (252 ** 0.5))


def berakna_max_drawdown(close):
    topp = close.cummax()
    return ((close - topp) / topp).min() * 100


@st.cache_data(ttl=900)
def hamta_index_historik(ticker="^OMX", period="1y"):
    hist = yf.Ticker(ticker).history(period=period)
    return hist.dropna(subset=["Close"])


def berakna_beta(aktie_close, index_close):
    gemensamt = pd.concat(
        [aktie_close.pct_change(fill_method=None), index_close.pct_change(fill_method=None)],
        axis=1, join="inner",
    ).dropna()
    if len(gemensamt) < 30:
        return None
    varians = gemensamt.iloc[:, 1].var()
    if varians == 0:
        return None
    return gemensamt.iloc[:, 0].cov(gemensamt.iloc[:, 1]) / varians


# ================================================================
# DEL 6: Utdelningar
# ================================================================

def hamta_utdelningsanalys(ticker):
    aktie = yf.Ticker(ticker)
    idag = datetime.date.today()

    resultat = {
        "historik": aktie.dividends,
        "tillvaxt_procent": None,
        "ojamn_historik": False,
        "rapportdatum": None,
        "rapportdatum_kommande": False,
        "ex_datum": None,
        "ex_datum_kommande": False,
    }

    utdelningar = resultat["historik"]
    if not utdelningar.empty and len(utdelningar) >= 2:
        senaste = utdelningar.tail(5)
        forsta, sista = senaste.iloc[0], senaste.iloc[-1]
        if forsta > 0:
            resultat["tillvaxt_procent"] = (sista / forsta - 1) * 100

        datum_lista = list(senaste.index)
        if len(datum_lista) >= 2:
            gap_dagar = [(datum_lista[i + 1] - datum_lista[i]).days for i in range(len(datum_lista) - 1)]
            resultat["ojamn_historik"] = max(gap_dagar) > 450

    try:
        kalender = aktie.calendar
        rapportdatum_lista = kalender.get("Earnings Date", [])
        if rapportdatum_lista:
            resultat["rapportdatum"] = rapportdatum_lista[0]
            resultat["rapportdatum_kommande"] = rapportdatum_lista[0] >= idag
        ex_datum = kalender.get("Ex-Dividend Date")
        if ex_datum:
            resultat["ex_datum"] = ex_datum
            resultat["ex_datum_kommande"] = ex_datum >= idag
    except Exception:
        pass

    return resultat


# ================================================================
# DEL 7: Makroekonomi (FRED)
# ================================================================
# Nyckeln hämtas från Streamlit secrets, ALDRIG hårdkodad i filen - den
# här filen laddas upp till ett publikt GitHub-repo, och en nyckel i
# klartext där skulle vara synlig för vem som helst.

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


# ================================================================
# DEL 8: Sidopanel - lägg till/ta bort egna innehav
# ================================================================

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
                spara_portfolj()
                st.success(f"{info['namn']} tillagd!")

    st.divider()
    st.caption("Dina innehav:")
    for namn in list(st.session_state.portfolj.keys()):
        c1, c2 = st.columns([5, 1])
        c1.write(namn)
        if c2.button("✕", key=f"tabort_{namn}"):
            del st.session_state.portfolj[namn]
            spara_portfolj()
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
                spara_bevakning()
                st.success(f"{info['namn']} tillagd i bevakningslistan!")

    if st.session_state.bevakning:
        st.caption("Dina bevakade bolag:")
        for namn in list(st.session_state.bevakning.keys()):
            c1, c2 = st.columns([5, 1])
            c1.write(namn)
            if c2.button("✕", key=f"tabort_bevakning_{namn}"):
                del st.session_state.bevakning[namn]
                spara_bevakning()
                st.rerun()


# ================================================================
# DEL 9: Själva appen (gränssnittet)
# ================================================================

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


# ---------- Flik 1: Översikt ----------
with vald_flik[0]:
    st.subheader("Snabböverblick över alla innehav")
    st.caption(
        "Tips: sätt en egen målkurs i sista kolumnen - du ser direkt i "
        "\"Målkurs nådd\" om kursen har nått den."
    )
    rader = []
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

        rader.append({
            "Bolag": namn,
            "Kurs": f"{senaste_pris:.1f} {valuta}" if senaste_pris else None,
            "Riktkurs": f"{riktkurs:.1f} {valuta}" if riktkurs else None,
            "Uppsida %": round(uppsida, 1) if uppsida is not None else None,
            "Min målkurs (i aktiens valuta)": float(malkurs) if malkurs else np.nan,
            "Målkurs nådd": malkurs_status,
        })

    oversikt_df = pd.DataFrame(rader)
    redigerad_df = st.data_editor(
        oversikt_df,
        column_config={
            "Bolag": st.column_config.TextColumn(disabled=True),
            "Kurs": st.column_config.TextColumn(disabled=True),
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
        spara_portfolj()


# ---------- Flik 2: Nyheter & sentiment ----------
with vald_flik[1]:
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


# ---------- Flik 3: Nyckeltal ----------
with vald_flik[2]:
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


# ---------- Flik 4: Kursutveckling ----------
with vald_flik[3]:
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


# ---------- Flik 5: Riktkurser ----------
with vald_flik[4]:
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


# ---------- Flik 6: Teknisk analys ----------
with vald_flik[5]:
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


# ---------- Flik 7: Risk & korrelation ----------
with vald_flik[6]:
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


# ---------- Flik 8: Utdelningar ----------
with vald_flik[7]:
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


# ---------- Flik 9: Makroekonomi ----------
with vald_flik[8]:
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


# ---------- Flik 10: Bevakningslista ----------
with vald_flik[9]:
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
            spara_bevakning()

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
                spara_portfolj()
                spara_bevakning()
                st.success(f"{namn} flyttad till portföljen!")
                st.rerun()
            if c3.button("✕ Ta bort", key=f"tabort_bevakning_tab_{namn}"):
                del st.session_state.bevakning[namn]
                spara_bevakning()
                st.rerun()

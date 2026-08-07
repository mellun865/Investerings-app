"""
Sökning efter bolag samt hämtning av kurshistorik, bolagsinfo och
indexhistorik via yfinance.
"""

import streamlit as st
import yfinance as yf


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


@st.cache_data(ttl=900)
def hamta_index_historik(ticker="^OMX", period="1y"):
    hist = yf.Ticker(ticker).history(period=period)
    return hist.dropna(subset=["Close"])


@st.cache_data(ttl=1800)
def hamta_yahoo_nyheter(ticker, max_antal=5):
    """Nyheter från Yahoo Finance - till skillnad från Google News RSS ger
    den här källan en riktig kort sammanfattning per nyhet (ingen AI
    behövs), men täcker mest engelskspråkiga/internationella källor."""
    try:
        rad_nyheter = yf.Ticker(ticker).news or []
    except Exception:
        return []

    nyheter = []
    for post in rad_nyheter[:max_antal]:
        innehall = post.get("content", {})
        titel = innehall.get("title")
        lank = (innehall.get("clickThroughUrl") or {}).get("url")
        if not titel or not lank:
            continue
        nyheter.append({
            "titel": titel,
            "sammanfattning": innehall.get("summary"),
            "lank": lank,
            "kalla": (innehall.get("provider") or {}).get("displayName"),
            "datum": (innehall.get("pubDate") or "")[:10] or None,
        })
    return nyheter

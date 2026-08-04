"""
Sentimentanalys av nyhetsrubriker samt hämtning av nyheter per bolag.
"""

import urllib.parse
import xml.etree.ElementTree as ET

import requests
import streamlit as st


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

"""
Sentimentanalys av nyhetsrubriker samt hämtning av nyheter per bolag.
"""

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests
import streamlit as st
from bs4 import BeautifulSoup

from services.gemini_service import generera_text

_GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


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


def _formatera_pubdate(text):
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=1800)
def hamta_nyheter_for_bolag(sokterm, max_antal=8):
    """Hämtar nyheter (titel, länk, datum, källa) från Google News RSS."""
    fraga = urllib.parse.quote(sokterm)
    url = f"https://news.google.com/rss/search?q={fraga}&hl=sv&gl=SE&ceid=SE:sv"
    request = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    root = ET.fromstring(request.content)

    nyheter = []
    for item in root.findall(".//item")[:max_antal]:
        titel = item.findtext("title")
        if not titel:
            continue
        nyheter.append({
            "titel": titel,
            "lank": item.findtext("link"),
            "datum": _formatera_pubdate(item.findtext("pubDate")),
            "kalla": item.findtext("source"),
        })
    return nyheter


def generera_nyhetstolkning(bolag, nyhet):
    """AI-tolkning av en nyhetsrubrik. Bygger ENDAST på rubriken (Google
    News RSS ger ingen artikeltext), så det här är en tolkning av vad
    rubriken sannolikt betyder - inte en sammanfattning av artikeln."""
    prompt = f"""Du är en nykter, pedagogisk nyhetsanalytiker för en svensk
privatsparare. Du har ENDAST rubriken nedan att gå på, inte artikeltexten -
hitta inte på detaljer som inte framgår av rubriken, och var tydlig med att
det här är en tolkning av rubriken, inte en sammanfattning av artikeln.

Bolag: {bolag}
Rubrik: "{nyhet['titel']}"
Källa: {nyhet.get('kalla') or 'okänd'}
Datum: {nyhet.get('datum') or 'okänt'}

Skriv 2-3 korta meningar på svenska: vad rubriken sannolikt handlar om för
{bolag} och varför det kan vara relevant för en aktieägare. Ge ingen
köp-/säljrekommendation."""
    return generera_text(prompt)


def _avkoda_google_news_lank(lank):
    """Avkodar en Google News RSS-omdirigeringslänk till artikelns riktiga
    URL. Bygger på att efterlikna ett internt, odokumenterat Google-anrop
    (samma teknik som community-verktyg för det här använder) - INTE ett
    officiellt API, så det kan sluta fungera om Google ändrar sitt format.
    En Googlebot-User-Agent kringgår Googles cookie-samtyckessida, som
    annars blockerar vanliga anrop."""
    sida = requests.get(lank, headers={"User-Agent": _GOOGLEBOT_UA}, timeout=10)
    signatur = re.search(r'data-n-a-sg="([^"]+)"', sida.text)
    tidsstampel = re.search(r'data-n-a-ts="([^"]+)"', sida.text)
    artikel_id = re.search(r'data-n-a-id="([^"]+)"', sida.text)
    if not (signatur and tidsstampel and artikel_id):
        return None

    nyttolast = [
        "Fbv4je",
        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",'
        'null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,'
        f'null,0,0,null,0],"{artikel_id.group(1)}",{tidsstampel.group(1)},'
        f'"{signatur.group(1)}"]',
    ]
    svar = requests.post(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        headers={
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            "user-agent": _GOOGLEBOT_UA,
        },
        data={"f.req": json.dumps([[nyttolast]])},
        timeout=10,
    )
    kropp = svar.text.split("\n\n", 1)[1]
    inre = json.loads(json.loads(kropp)[0][2])
    return inre[1]


def _hamta_artikeltext(url, max_tecken=6000):
    sida = requests.get(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=10,
    )
    soup = BeautifulSoup(sida.text, "html.parser")
    stycken = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(s for s in stycken if len(s) > 40)
    return text[:max_tecken] if text else None


def _bygg_artikel_prompt(bolag, nyhet, artikeltext):
    return f"""Du är en nykter, pedagogisk nyhetsanalytiker för en svensk
privatsparare. Nedan är den fulla artikeltexten om {bolag} - sammanfatta
ENDAST det som faktiskt står där, hitta inte på något extra, och ge ingen
köp-/säljrekommendation.

Rubrik: "{nyhet['titel']}"
Källa: {nyhet.get('kalla') or 'okänd'}
Datum: {nyhet.get('datum') or 'okänt'}

Artikeltext:
{artikeltext}

Skriv på svenska, kort (max ca 130 ord), i löpande text: vad handlar
artikeln om, och varför kan det vara relevant för en {bolag}-aktieägare."""


def generera_nyhetssammanfattning(bolag, nyhet):
    """Försöker sammanfatta HELA artikeln: avkodar Google News-länken och
    hämtar sidans text. Går det inte (betalvägg, avkodningen misslyckas,
    för lite text hittas) faller den tillbaka på att bara tolka rubriken.
    Returnerar (text, felmeddelande, helartikel) - helartikel är True om
    sammanfattningen bygger på den faktiska artikeltexten."""
    artikeltext = None
    try:
        if nyhet.get("lank"):
            verklig_url = _avkoda_google_news_lank(nyhet["lank"])
            if verklig_url:
                artikeltext = _hamta_artikeltext(verklig_url)
    except Exception:
        artikeltext = None

    if artikeltext and len(artikeltext) > 300:
        text, fel = generera_text(_bygg_artikel_prompt(bolag, nyhet, artikeltext))
        return text, fel, True

    text, fel = generera_nyhetstolkning(bolag, nyhet)
    return text, fel, False

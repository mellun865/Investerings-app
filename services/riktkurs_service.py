"""
Riktkurser och analytikersentiment skrapat från Börskollen.
"""

import re
import json

import requests
import streamlit as st


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

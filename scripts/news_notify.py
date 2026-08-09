"""
Fristående skript (körs INTE via `streamlit run`) som kollar om det finns
nya, relevanta nyheter för portföljens bolag och skickar en Telegram-notis
per ny nyhet. Tänkt att köras periodiskt via GitHub Actions
(.github/workflows/news_notify.yml) eftersom Streamlit-appen bara kör kod
när någon har sidan öppen och inte kan schemaläggas i bakgrunden.

Håller reda på redan notifierade nyheter i notified_news.json (en lista av
länkar) i samma lagring som portföljen (privat GitHub-repo vid molndrift,
annars en lokal fil), så samma nyhet inte skickas flera gånger. Första
körningen skickar INGA notiser - den bara "seedar" listan med redan
existerande nyheter, så man inte får en flodvåg av gamla nyheter direkt.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import persistence_service, sentiment_service, telegram_service

NOTIFIED_FIL = os.path.join(persistence_service._PROJEKT_ROT, "notified_news.json")
NOTIFIED_SOKVAG = "notified_news.json"
MAX_SPARADE_LANKAR = 500


def _spara_notifierade(lankar):
    lankar = lankar[-MAX_SPARADE_LANKAR:]
    if persistence_service._github_konfigurerad():
        persistence_service._github_spara(NOTIFIED_SOKVAG, lankar)
    else:
        with open(NOTIFIED_FIL, "w", encoding="utf-8") as f:
            json.dump(lankar, f, ensure_ascii=False, indent=2)


def main():
    if not telegram_service.telegram_konfigurerad():
        print("Telegram är inte konfigurerat (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID saknas) - avbryter.")
        return

    portfolj = persistence_service.ladda_lista(
        persistence_service.PORTFOLJ_FIL, "portfolj.json", persistence_service.STARTPORTFOLJ
    )
    if not portfolj:
        print("Ingen portfölj konfigurerad, avbryter.")
        return

    tidigare_notifierade = persistence_service.ladda_lista(NOTIFIED_FIL, NOTIFIED_SOKVAG, [])
    forsta_korningen = len(tidigare_notifierade) == 0
    kanda_lankar = set(tidigare_notifierade)
    nya_lankar = list(tidigare_notifierade)
    antal_skickade = 0

    for bolag, data in portfolj.items():
        try:
            nyheter = sentiment_service.hamta_nyheter_for_bolag(data["sok"])
        except Exception as e:
            print(f"Kunde inte hämta nyheter för {bolag}: {e}")
            continue

        for nyhet in nyheter:
            lank = nyhet.get("lank")
            if not lank or lank in kanda_lankar:
                continue
            kanda_lankar.add(lank)
            nya_lankar.append(lank)

            if forsta_korningen or not sentiment_service.ar_troligen_relevant(bolag, nyhet["titel"]):
                continue

            text = (
                f"📰 *{bolag}*\n{nyhet['titel']}\n"
                f"{nyhet.get('kalla') or ''} · {nyhet.get('datum') or ''}\n{lank}"
            )
            if telegram_service.skicka_telegram_meddelande(text):
                antal_skickade += 1

    if len(nya_lankar) != len(tidigare_notifierade):
        _spara_notifierade(nya_lankar)

    if forsta_korningen:
        print(f"Första körningen - seedade {len(nya_lankar)} nyheter utan att notifiera.")
    else:
        print(f"Klart. {antal_skickade} nya notiser skickade.")


if __name__ == "__main__":
    main()

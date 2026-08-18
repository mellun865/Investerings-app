"""
Skickar notiser via Telegram Bot API. Kräver TELEGRAM_BOT_TOKEN (skapas
gratis via @BotFather i Telegram) och TELEGRAM_CHAT_ID (ditt eget chatt-id,
t.ex. från @userinfobot) i secrets. Helt valfri funktion - saknas nycklarna
görs ingenting, resten av appen/skripten fungerar precis som förut.
"""

import requests

from services.config import get_secret

TELEGRAM_BOT_TOKEN = get_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = get_secret("TELEGRAM_CHAT_ID")


def telegram_konfigurerad():
    return bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID)


def skicka_telegram_meddelande(text):
    """Skickar ett meddelande. Returnerar True vid lyckad sändning, annars
    False - kastar aldrig, så ett Telegram-fel inte stoppar resten av ett
    notisskript som loopar över flera bolag/nyheter."""
    if not telegram_konfigurerad():
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        svar = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        svar.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram-notis misslyckades: {e}")
        return False

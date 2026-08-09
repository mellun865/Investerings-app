"""
Engångsskript för att verifiera att TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID i
.streamlit/secrets.toml fungerar, utan att vänta på nästa schemalagda
körning av news_notify.py. Kör: python scripts/testa_telegram.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import telegram_service

if not telegram_service.telegram_konfigurerad():
    print("TELEGRAM_BOT_TOKEN och/eller TELEGRAM_CHAT_ID saknas i .streamlit/secrets.toml.")
    sys.exit(1)

if telegram_service.skicka_telegram_meddelande("✅ Testmeddelande från Investerings-appen."):
    print("Skickat! Kolla din Telegram-chatt.")
else:
    print("Misslyckades - se felmeddelandet ovan.")

"""
Tillfällig auth-stub tills Supabase Auth är på plats (steg 3 i
CLAUDE.md:s omstartsplan). Läser en frivillig X-User-Id-header och
saniterar den likadant som Streamlit-appens _anvandar_id() saniterar
en Google-e-post - saknas headern blir user_id="", vilket ger exakt
samma delade root-datasökväg som Streamlit-appen använder utan
inloggning idag.

När Supabase Auth kommer in byts bara innehållet i get_user_id ut mot
riktig JWT-verifiering - ingen route eller service behöver ändras,
eftersom alla bara bryr sig om den slutgiltiga saniterade strängen.
"""

import re
from typing import Optional

from fastapi import Header


def get_user_id(x_user_id: Optional[str] = Header(default=None)) -> str:
    if not x_user_id:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", x_user_id.lower()).strip("_")

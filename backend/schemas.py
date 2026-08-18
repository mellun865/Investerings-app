"""
Pydantic-modeller för request-/response-bodies. Speglar de datastrukturer
services/persistence_service.py redan lagrar (portfolj/bevakning/
transaktioner/historik) - inga nya fält, bara typade för FastAPI.
"""

from typing import Optional

from pydantic import BaseModel


class Bolag(BaseModel):
    ticker: str
    borskollen: str
    sok: str
    malkurs: Optional[float] = None


class Bevakning(BaseModel):
    ticker: str
    borskollen: str
    sok: str
    onskad_kop: Optional[float] = None


class Transaktion(BaseModel):
    bolag: str
    typ: str
    datum: str
    antal: float
    pris: float = 0.0
    avgift: float = 0.0


class NyTransaktion(BaseModel):
    bolag: str
    typ: str
    datum: str
    antal: float
    pris: float = 0.0
    avgift: float = 0.0


class HistorikRad(BaseModel):
    datum: str
    varde: float


class Nyhet(BaseModel):
    titel: str
    lank: Optional[str] = None
    datum: Optional[str] = None
    kalla: Optional[str] = None

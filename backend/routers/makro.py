from fastapi import APIRouter

from services.macro_service import FRED_API_KEY, MAKRO_SERIER, hamta_fred_varde

router = APIRouter(prefix="/makro", tags=["makro"])


@router.get("")
def makro():
    if not FRED_API_KEY:
        return {"konfigurerad": False, "serier": []}
    serier = []
    for namn, info in MAKRO_SERIER.items():
        datum, varde, fel = hamta_fred_varde(info["id"], FRED_API_KEY, info["units"])
        serier.append({"namn": namn, "enhet": info["enhet"], "datum": datum, "varde": varde, "fel": fel})
    return {"konfigurerad": True, "serier": serier}

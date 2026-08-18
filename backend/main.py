"""
FastAPI-wrapper runt services/-mappen (steg 2 i CLAUDE.md:s omstartsplan
mot en riktig mobilapp). Körs lokalt med:
    uvicorn backend.main:app --reload

All affärslogik ligger kvar oförändrad i services/ - routrarna här är
tunna och delar samma tjänster som Streamlit-appen (app.py/ui/) redan
använder. Auth är en tillfällig header-stub (se backend/deps.py) tills
Supabase Auth är på plats.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import ai_coach, analys, historik, makro, nyheter, portfolj, rapporter, transaktioner

app = FastAPI(title="Min portföljanalys - API")

# Tillåter alla origins under utveckling - begränsas till Expo-appens
# faktiska domän/scheme när den byggs (steg 4).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (portfolj.router, transaktioner.router, historik.router, ai_coach.router,
               analys.router, nyheter.router, rapporter.router, makro.router):
    app.include_router(router)


@app.get("/")
def status():
    return {"status": "ok"}

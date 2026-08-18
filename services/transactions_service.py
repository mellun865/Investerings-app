"""
Transaktionslogg (köp/sälj/utdelning/split) samt beräkning av nuvarande
innehav (antal aktier, genomsnittligt anskaffningsvärde) och realiserad
vinst utifrån loggen. Portföljlistan i persistence_service håller bara
reda på VILKA bolag man äger - denna modul räknar ut HUR MYCKET.
"""

TYPER = ["Köp", "Sälj", "Utdelning", "Split"]


def lagg_till_transaktion(transaktioner, bolag, typ, datum, antal, pris, avgift=0.0):
    """Returnerar en NY, datumsorterad lista - muterar inte transaktioner
    på plats, så anroparen (Streamlit-session-state eller FastAPI) själv
    äger var listan lagras."""
    nya = transaktioner + [{
        "bolag": bolag,
        "typ": typ,
        "datum": str(datum),
        "antal": float(antal) if antal else 0.0,
        "pris": float(pris) if pris else 0.0,
        "avgift": float(avgift) if avgift else 0.0,
    }]
    nya.sort(key=lambda t: t["datum"])
    return nya


def ta_bort_transaktion(transaktioner, index):
    """Returnerar en NY lista utan transaktionen på angivet index."""
    return [t for i, t in enumerate(transaktioner) if i != index]


def _tomt_innehav():
    return {"antal": 0.0, "anskaffningsvarde": 0.0, "gav": 0.0, "realiserad_vinst": 0.0, "utdelning": 0.0}


def berakna_innehav(transaktioner):
    """Går igenom transaktionerna i datumordning per bolag och räknar fram
    nuvarande antal aktier, genomsnittligt anskaffningsvärde (GAV),
    realiserad vinst/förlust från sälj och totalt mottagen utdelning."""
    innehav = {}
    for t in sorted(transaktioner, key=lambda t: t["datum"]):
        bolag = t["bolag"]
        rad = innehav.setdefault(bolag, _tomt_innehav())

        if t["typ"] == "Köp":
            rad["antal"] += t["antal"]
            rad["anskaffningsvarde"] += t["antal"] * t["pris"] + t["avgift"]
        elif t["typ"] == "Sälj":
            if rad["antal"] > 0:
                saljs = min(t["antal"], rad["antal"])
                rad["realiserad_vinst"] += (t["pris"] - rad["gav"]) * saljs - t["avgift"]
                rad["anskaffningsvarde"] -= rad["gav"] * saljs
                rad["antal"] -= saljs
        elif t["typ"] == "Split":
            if t["antal"] > 0:
                rad["antal"] *= t["antal"]
        elif t["typ"] == "Utdelning":
            rad["utdelning"] += t["antal"]

        rad["gav"] = rad["anskaffningsvarde"] / rad["antal"] if rad["antal"] > 0 else 0.0

    return innehav

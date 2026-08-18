from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import get_user_id
from backend.schemas import NyTransaktion, Transaktion
from services import persistence_service, transactions_service

router = APIRouter(tags=["transaktioner"])


def _ladda(user_id):
    return persistence_service._ladda(
        persistence_service.TRANSAKTIONER_FIL, "transaktioner.json", [], user_id,
    )


def _spara(data, user_id):
    persistence_service._spara(data, persistence_service.TRANSAKTIONER_FIL, "transaktioner.json", user_id)


@router.get("/transaktioner", response_model=List[Transaktion])
def hamta_transaktioner(user_id: str = Depends(get_user_id)):
    return _ladda(user_id)


@router.post("/transaktioner", response_model=List[Transaktion])
def lagg_till(ny: NyTransaktion, user_id: str = Depends(get_user_id)):
    transaktioner = _ladda(user_id)
    nya = transactions_service.lagg_till_transaktion(
        transaktioner, ny.bolag, ny.typ, ny.datum, ny.antal, ny.pris, ny.avgift,
    )
    _spara(nya, user_id)
    return nya


@router.delete("/transaktioner/{index}", response_model=List[Transaktion])
def ta_bort(index: int, user_id: str = Depends(get_user_id)):
    transaktioner = _ladda(user_id)
    if index < 0 or index >= len(transaktioner):
        raise HTTPException(status_code=404, detail="Transaktion hittades inte")
    nya = transactions_service.ta_bort_transaktion(transaktioner, index)
    _spara(nya, user_id)
    return nya

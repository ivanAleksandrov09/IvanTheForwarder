"""Load offers found by the weekly web search. Owner: B."""

from fastapi import APIRouter, HTTPException

from app.loads.search import LoadOffer, read_offers, refresh_loads

router = APIRouter(prefix="/api", tags=["loads"])


@router.get("/loads")
def list_loads() -> list[LoadOffer]:
    return read_offers()


@router.post("/loads/refresh")
def refresh() -> list[LoadOffer]:
    try:
        return refresh_loads()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

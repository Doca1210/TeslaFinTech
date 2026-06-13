from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from screening.engine import ScreeningEngine
from screening.models import ScreeningResult, Transaction
from screening.pep_loader import default_watchlist_path, load_watchlist


def build_engine(watchlist_path: Path | None = None) -> ScreeningEngine:
    path = watchlist_path or default_watchlist_path()
    watchlist = load_watchlist(path)
    return ScreeningEngine(watchlist)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = build_engine()
    yield


app = FastAPI(
    title="TeslaFinTech Name Screening",
    description="Screen payment transactions against PEP and suspicious-name watchlists.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/screen", response_model=ScreeningResult)
def screen_transaction(transaction: Transaction) -> ScreeningResult:
    engine: ScreeningEngine = app.state.engine
    return engine.screen(transaction)


@app.post("/screen/batch", response_model=list[ScreeningResult])
def screen_batch(transactions: list[Transaction]) -> list[ScreeningResult]:
    if not transactions:
        raise HTTPException(status_code=400, detail="At least one transaction is required.")
    engine: ScreeningEngine = app.state.engine
    return engine.screen_batch(transactions)


@app.get("/watchlist/count")
def watchlist_count() -> dict[str, int]:
    engine: ScreeningEngine = app.state.engine
    return {"count": len(engine.watchlist)}

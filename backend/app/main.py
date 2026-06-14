import json
import logging
import os
import threading
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.export.vectorize_export import export_entities
from app.ingestion.ofac_sdn import run_ingestion as run_ofac_sdn_ingestion
from app.ingestion.opensanctions import DEFAULT_LIMIT as OPENSANCTIONS_DEFAULT_LIMIT
from app.ingestion.opensanctions import run_ingestion as run_opensanctions_ingestion
from app.logging_config import configure_logging
from app.models import Entity, EntityName
from app.ownership import OwnershipRiskEngine
from app.schemas import EntityNameOut, EntitySearchResult, IngestionResult
from app.schema_upgrade import ensure_sqlite_schema
from app.suggest import get_ai_suggestion

configure_logging()
logger = logging.getLogger("app")

app = FastAPI(title="AML Sanctions Screening")

# Allow the Vite dev frontend (and any local origin) to call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_sqlite_schema(engine)
Base.metadata.create_all(bind=engine)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    logger.info("--> %s %s params=%s", request.method, request.url.path, dict(request.query_params))
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "<-- %s %s status=%s duration=%.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.post("/ingest/ofac-sdn", response_model=IngestionResult)
def ingest_ofac_sdn() -> IngestionResult:
    logger.info("Starting OFAC SDN ingestion")
    result = run_ofac_sdn_ingestion()
    logger.info(
        "Finished OFAC SDN ingestion: %s entries, published %s",
        result["entries_processed"],
        result["publish_date"],
    )
    return IngestionResult(**result)


@app.post("/ingest/opensanctions-peps", response_model=IngestionResult)
def ingest_opensanctions_peps(limit: int = OPENSANCTIONS_DEFAULT_LIMIT) -> IngestionResult:
    """Ingest the OpenSanctions PEPs collection. Pass limit=0 for the full feed (1M+ rows)."""
    logger.info("Starting OpenSanctions PEPs ingestion (limit=%s)", limit)
    result = run_opensanctions_ingestion(dataset="peps", limit=limit if limit > 0 else None)
    logger.info(
        "Finished OpenSanctions PEPs ingestion: %s entries, published %s",
        result["entries_processed"],
        result["publish_date"],
    )
    return IngestionResult(**result)


@app.post("/ingest/eu-fsf", response_model=IngestionResult)
def ingest_eu_fsf() -> IngestionResult:
    """Ingest the EU Financial Sanctions Files (EU consolidated sanctions list)."""
    logger.info("Starting EU FSF ingestion")
    result = run_opensanctions_ingestion(dataset="eu_fsf", limit=None)
    logger.info(
        "Finished EU FSF ingestion: %s entries, published %s",
        result["entries_processed"],
        result["publish_date"],
    )
    return IngestionResult(**result)


@app.post("/export/vectorize")
def export_vectorize() -> dict:
    """Export all active entities as a JSONL file for downstream embedding/vector indexing."""
    logger.info("Starting vectorization export")
    result = export_entities()
    logger.info("Finished vectorization export: %s entities -> %s", result["entities_exported"], result["output_path"])
    return result


# --------------------------------------------------------------------------- #
# KYB / ownership exposure (Layer C)
# --------------------------------------------------------------------------- #
# Two cached engines: the default seeded-only engine is instant (no model). The
# live engine wires the full ScreeningEngine to re-screen owner names against the
# watchlist, but that encodes ~100k names through an embedding model, so it is
# opt-in (?live=true) and built at most once, guarded against concurrent builds.
_ownership_engine: OwnershipRiskEngine | None = None
_live_ownership_engine: OwnershipRiskEngine | None = None
_engine_lock = threading.Lock()


def get_ownership_engine(live: bool = False) -> OwnershipRiskEngine:
    """Return the ownership engine. ``live=True`` re-screens owners against the
    watchlist (slow first call); default is the instant seeded-only engine."""
    global _ownership_engine, _live_ownership_engine

    if live:
        if _live_ownership_engine is None:
            with _engine_lock:
                if _live_ownership_engine is None:
                    try:
                        from screening_v2.engine import ScreeningEngine

                        logger.info("Ownership: building live ScreeningEngine (encodes watchlist)…")
                        _live_ownership_engine = OwnershipRiskEngine(
                            SessionLocal, engine=ScreeningEngine(SessionLocal)
                        )
                        logger.info("Ownership: live ScreeningEngine ready")
                    except Exception:  # pragma: no cover - defensive, demo robustness
                        logger.exception("Ownership: live engine build failed; using seeded only")
                        _live_ownership_engine = OwnershipRiskEngine(SessionLocal, engine=None)
        return _live_ownership_engine

    if _ownership_engine is None:
        with _engine_lock:
            if _ownership_engine is None:
                _ownership_engine = OwnershipRiskEngine(SessionLocal, engine=None)
    return _ownership_engine


@app.get("/screen/ownership")
def screen_ownership(name: str, max_depth: int = 2, persist: bool = False, live: bool = False) -> dict:
    """Trace the beneficial-ownership graph for a beneficiary name and assess risk.

    Returns the Layer-C verdict (MATCH/REVIEW/NO_MATCH), the risky ownership
    paths with analyst explanations and effective (cumulative) ownership, and a
    node/edge graph for visualization. Pass ``persist=true`` to store the
    assessment as an audit record, and ``live=true`` to re-screen owner names
    against the watchlist (slow on first call — builds the embedding index).
    """
    logger.info("Ownership screen for name=%r max_depth=%s persist=%s live=%s", name, max_depth, persist, live)
    result = get_ownership_engine(live=live).assess(name, max_depth=max_depth, persist=persist)
    logger.info(
        "Ownership screen name=%r -> verdict=%s score=%s traced=%s",
        name, result["verdict"], result["score"], result["related_parties_traced"],
    )
    return result


@app.get("/ownership/exposure")
def ownership_exposure(name: str, max_depth: int = 2) -> dict:
    """Reverse lookup: every company a (typically sanctioned/PEP) party stands behind.

    Turns a single hit into a network view — e.g. "Ivan Petrov controls 3 of the
    companies you transact with".
    """
    logger.info("Ownership exposure for name=%r max_depth=%s", name, max_depth)
    result = get_ownership_engine().exposure(name, max_depth=max_depth)
    logger.info("Ownership exposure name=%r -> controls=%s", name, result["controls_count"])
    return result


# --------------------------------------------------------------------------- #
# Payments dashboard feed (Layers A + B + C over demo scenarios)
# --------------------------------------------------------------------------- #
_screening_engine = None
_transactions_cache: list[dict] | None = None
_TX_CACHE_PATH = os.path.join("data", "demo_transactions.json")


def get_screening_engine():
    """Cached sanctions ScreeningEngine (heavy to build — encodes the watchlist)."""
    global _screening_engine
    if _screening_engine is None:
        with _engine_lock:
            if _screening_engine is None:
                from screening_v2.engine import ScreeningEngine

                logger.info("Building ScreeningEngine for /transactions…")
                _screening_engine = ScreeningEngine(SessionLocal)
    return _screening_engine


@app.get("/transactions")
def list_transactions() -> list[dict]:
    """Demo payment screening results for the Payments dashboard.

    Served from a precomputed cache (``data/demo_transactions.json``) so the page
    loads instantly. Generate it with ``python manage.py generate-transactions``.
    Falls back to building live (slow first call) if the cache is absent.
    """
    global _transactions_cache
    if _transactions_cache is None:
        if os.path.exists(_TX_CACHE_PATH):
            with open(_TX_CACHE_PATH, encoding="utf-8") as f:
                _transactions_cache = json.load(f)
            logger.info("Loaded %d demo transactions from cache", len(_transactions_cache))
        else:
            logger.warning("No transaction cache; building live (slow first call)…")
            from app.payment_demo import build_transactions

            _transactions_cache = build_transactions(
                get_screening_engine(), get_ownership_engine(live=False)
            )
            try:
                with open(_TX_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(_transactions_cache, f, indent=2)
            except OSError:
                logger.exception("Could not persist transaction cache")
    return _transactions_cache


@app.post("/transactions/{tx_id}/suggest")
async def suggest_transaction(tx_id: int) -> dict:
    """Call OpenAI to suggest a compliance verdict for a flagged transaction."""
    transactions = list_transactions()
    tx = next((t for t in transactions if t["id"] == tx_id), None)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        return await get_ai_suggestion(tx)
    except Exception:
        logger.exception("AI suggestion failed for tx_id=%s", tx_id)
        raise HTTPException(status_code=502, detail="AI suggestion unavailable")


@app.get("/entities/search", response_model=list[EntitySearchResult])
def search_entities(name: str, limit: int = 20) -> list[EntitySearchResult]:
    """Placeholder substring search until the fuzzy/embedding matcher exists."""
    logger.info("Searching entities for name=%r limit=%s", name, limit)
    session = SessionLocal()
    try:
        pattern = f"%{name.lower()}%"
        matched_name_rows = (
            session.execute(
                select(EntityName)
                .join(Entity)
                .where(Entity.is_active.is_(True))
                .where(EntityName.full_name.ilike(pattern))
                .limit(limit)
            )
            .scalars()
            .all()
        )

        results: list[EntitySearchResult] = []
        seen_entity_ids: set[int] = set()
        for entity_name in matched_name_rows:
            entity = entity_name.entity
            if entity.id in seen_entity_ids:
                continue
            seen_entity_ids.add(entity.id)
            results.append(
                EntitySearchResult(
                    id=entity.id,
                    entity_type=entity.entity_type,
                    primary_name=entity.primary_name,
                    source_list=entity.source_list.code,
                    programs=[p.program_code for p in entity.programs],
                    matched_names=[
                        EntityNameOut.model_validate(n)
                        for n in entity.names
                        if name.lower() in n.full_name.lower()
                    ],
                )
            )
        logger.info("Search for name=%r matched %s entities", name, len(results))
        return results
    finally:
        session.close()

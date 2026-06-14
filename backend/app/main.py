import logging
import time

from fastapi import FastAPI, Request
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.export.vectorize_export import export_entities
from app.ingestion.ofac_sdn import run_ingestion as run_ofac_sdn_ingestion
from app.ingestion.opensanctions import DEFAULT_LIMIT as OPENSANCTIONS_DEFAULT_LIMIT
from app.ingestion.opensanctions import run_ingestion as run_opensanctions_ingestion
from app.logging_config import configure_logging
from app.models import Entity, EntityName
from app.schemas import EntityNameOut, EntitySearchResult, IngestionResult
from app.schema_upgrade import ensure_sqlite_schema

configure_logging()
logger = logging.getLogger("app")

app = FastAPI(title="AML Sanctions Screening")

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

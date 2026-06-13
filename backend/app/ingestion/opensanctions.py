"""Fetch and ingest OpenSanctions bulk CSV datasets (free, no-login).

OpenSanctions publishes a "simplified CSV" export per dataset at
    https://data.opensanctions.org/datasets/latest/<dataset>/targets.simple.csv

This module is a generic adapter: any dataset published in that format can be
ingested by mapping its rows onto the same Entity/EntityName/... tables used
by the OFAC SDN ingestion. Two datasets are wired up out of the box:

- "peps"   -> OpenSanctions PEPs collection (300+ government PEP registries).
              Large feed (1M+ rows), so capped via --limit by default.
- "eu_fsf" -> EU Financial Sanctions Files (EU consolidated sanctions list).
              Small feed (~2.5MB), ingested in full.

Run with:
    python -m app.ingestion.opensanctions --dataset peps             # default limit
    python -m app.ingestion.opensanctions --dataset peps --limit 0   # full feed
    python -m app.ingestion.opensanctions --dataset eu_fsf
"""

from __future__ import annotations

import csv
import logging
import time
from datetime import datetime, timezone
from typing import Iterator

import httpx

from app.database import Base, SessionLocal, engine
from app.ingestion.common import get_or_create_source_list, upsert_entries

CSV_URL_TEMPLATE = "https://data.opensanctions.org/datasets/latest/{dataset}/targets.simple.csv"
DEFAULT_LIMIT = 20_000

logger = logging.getLogger("app.ingestion.opensanctions")

SCHEMA_TYPE_MAP = {
    "Person": "individual",
    "Organization": "entity",
    "LegalEntity": "entity",
    "Company": "entity",
    "Vessel": "vessel",
    "Airplane": "aircraft",
}

DATASETS: dict[str, dict] = {
    "peps": {
        "source_list_code": "OPENSANCTIONS_PEPS",
        "source_list_name": "OpenSanctions PEPs Collection",
        "list_type": "pep",
        "default_limit": DEFAULT_LIMIT,
    },
    "eu_fsf": {
        "source_list_code": "EU_FSF",
        "source_list_name": "EU Financial Sanctions Files (Consolidated List)",
        "list_type": "sanctions",
        "default_limit": None,
    },
}


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def fetch_rows(dataset: str, limit: int | None) -> Iterator[dict]:
    """Stream-parse an OpenSanctions simplified CSV without loading it all into memory."""
    url = CSV_URL_TEMPLATE.format(dataset=dataset)
    logger.info("Streaming OpenSanctions dataset=%s from %s (limit=%s)", dataset, url, limit)
    with httpx.stream("GET", url, timeout=180.0, follow_redirects=True) as response:
        response.raise_for_status()
        reader = csv.DictReader(response.iter_lines())
        for index, row in enumerate(reader):
            if limit is not None and limit > 0 and index >= limit:
                break
            yield row


def parse_row(row: dict) -> dict:
    schema = (row.get("schema") or "").strip()
    entity_type = SCHEMA_TYPE_MAP.get(schema, "entity")
    primary_name = (row.get("name") or "").strip()

    names: list[dict] = [
        {"name_type": "primary", "quality": None, "full_name": primary_name, "first_name": None, "last_name": None}
    ]
    for alias in _split(row.get("aliases")):
        names.append(
            {"name_type": "aka", "quality": None, "full_name": alias, "first_name": None, "last_name": None}
        )

    addresses = [
        {"address_line": addr, "city": None, "state_province": None, "postal_code": None, "country": None}
        for addr in _split(row.get("addresses"))
    ]

    nationalities = [
        {"relation": "nationality", "country": country.upper()} for country in _split(row.get("countries"))
    ]

    dates_of_birth = _split(row.get("birth_date"))

    # Prefer explicit sanctions program ids; fall back to the originating
    # dataset/registry name (e.g. "Norway State-Owned Enterprises Leadership").
    programs = _split(row.get("program_ids")) or _split(row.get("dataset"))

    identifiers = _split(row.get("identifiers"))
    identifications = [{"id_type": "identifier", "id_number": ident, "id_country": None} for ident in identifiers]

    return {
        "source_uid": (row.get("id") or "").strip(),
        "entity_type": entity_type,
        "primary_name": primary_name,
        "title": None,
        "remarks": f"OpenSanctions schema={schema}" if schema else None,
        "names": names,
        "addresses": addresses,
        "identifications": identifications,
        "programs": programs,
        "dates_of_birth": dates_of_birth,
        "nationalities": nationalities,
    }


def run_ingestion(dataset: str = "peps", limit: int | None = None) -> dict:
    if dataset not in DATASETS:
        raise ValueError(f"Unknown OpenSanctions dataset {dataset!r}. Known: {sorted(DATASETS)}")
    config = DATASETS[dataset]
    if limit is None:
        limit = config["default_limit"]

    start = time.perf_counter()
    Base.metadata.create_all(bind=engine)

    entries = []
    for row in fetch_rows(dataset, limit=limit):
        record = parse_row(row)
        if record["source_uid"] and record["primary_name"]:
            entries.append(record)
    logger.info("Parsed %d entries from dataset=%s", len(entries), dataset)

    session = SessionLocal()
    try:
        source_list = get_or_create_source_list(
            session,
            code=config["source_list_code"],
            name=config["source_list_name"],
            list_type=config["list_type"],
            url=CSV_URL_TEMPLATE.format(dataset=dataset),
        )
        # Soft-delete-on-missing only makes sense when the entries represent the
        # *entire* source list; a capped fetch only sees a slice of it.
        upsert_entries(session, source_list, entries, deactivate_missing=(limit is None))

        source_list.last_fetched_at = datetime.now(timezone.utc)
        source_list.last_published_at = datetime.now(timezone.utc).date().isoformat()

        logger.info("Committing changes to database")
        session.commit()
        duration = time.perf_counter() - start
        logger.info("Ingestion finished in %.1fs", duration)
        return {"source_list": source_list.code, "entries_processed": len(entries), "publish_date": source_list.last_published_at}
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    from app.logging_config import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="peps", help="OpenSanctions dataset to ingest.")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to ingest (0 = no limit).")
    args = parser.parse_args()

    limit = args.limit if args.limit is None or args.limit > 0 else None
    result = run_ingestion(dataset=args.dataset, limit=limit)
    print(result)

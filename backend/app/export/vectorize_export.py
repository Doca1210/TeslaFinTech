"""Export entities into a flat JSONL file ready for embedding into a vector DB.

Each line is one entity, with a single `text` blob (good embedding input) and
a `metadata` dict (for filtering once indexed). This script is the handoff
point between the relational data model and the vector indexing pipeline -
it does not write to any vector store itself.

Run with:
    python -m app.export.vectorize_export                     # -> data/vectorize_export.jsonl
    python -m app.export.vectorize_export --output out.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import Entity

logger = logging.getLogger("app.export.vectorize_export")


def default_output_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "vectorize_export.jsonl"


def build_record(entity: Entity) -> dict:
    primary_name = entity.primary_name
    aliases = sorted({n.full_name for n in entity.names if n.full_name and n.full_name != primary_name})
    countries = sorted({n.country for n in entity.nationalities if n.country})
    programs = sorted({p.program_code for p in entity.programs if p.program_code})
    dates_of_birth = sorted({d.date_of_birth for d in entity.dates_of_birth if d.date_of_birth})
    addresses = [
        ", ".join(part for part in (a.address_line, a.city, a.state_province, a.country) if part)
        for a in entity.addresses
    ]
    addresses = [a for a in addresses if a]

    text_parts = [f"Name: {primary_name}"]
    if aliases:
        text_parts.append(f"Also known as: {', '.join(aliases)}")
    text_parts.append(f"Type: {entity.entity_type}")
    if countries:
        text_parts.append(f"Country/nationality: {', '.join(countries)}")
    if dates_of_birth:
        text_parts.append(f"Date of birth: {', '.join(dates_of_birth)}")
    if addresses:
        text_parts.append(f"Address: {'; '.join(addresses)}")
    if programs:
        text_parts.append(f"Programs/sources: {', '.join(programs)}")
    if entity.title:
        text_parts.append(f"Title: {entity.title}")
    if entity.remarks:
        text_parts.append(f"Remarks: {entity.remarks}")
    text_parts.append(f"List: {entity.source_list.code}")

    return {
        "id": f"{entity.source_list.code}:{entity.source_uid}",
        "text": ". ".join(text_parts) + ".",
        "metadata": {
            "entity_id": entity.id,
            "source_list": entity.source_list.code,
            "source_uid": entity.source_uid,
            "entity_type": entity.entity_type,
            "primary_name": primary_name,
            "aliases": aliases,
            "countries": countries,
            "programs": programs,
            "list_type": entity.source_list.list_type,
        },
    }


def export_entities(output_path: Path | None = None) -> dict:
    start = time.perf_counter()
    output_path = output_path or default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    session = SessionLocal()
    try:
        entities = (
            session.execute(
                select(Entity)
                .where(Entity.is_active.is_(True))
                .options(
                    joinedload(Entity.source_list),
                    joinedload(Entity.names),
                    joinedload(Entity.addresses),
                    joinedload(Entity.programs),
                    joinedload(Entity.dates_of_birth),
                    joinedload(Entity.nationalities),
                )
            )
            .unique()
            .scalars()
            .all()
        )
        logger.info("Exporting %d active entities to %s", len(entities), output_path)

        with output_path.open("w", encoding="utf-8") as f:
            for entity in entities:
                f.write(json.dumps(build_record(entity), ensure_ascii=False) + "\n")

        duration = time.perf_counter() - start
        logger.info("Export finished in %.1fs", duration)
        return {"output_path": str(output_path), "entities_exported": len(entities)}
    finally:
        session.close()


if __name__ == "__main__":
    from app.logging_config import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None, help="Output JSONL path.")
    args = parser.parse_args()

    result = export_entities(output_path=args.output)
    print(result)

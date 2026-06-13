"""Shared upsert/soft-delete logic for ingestion adapters.

Every adapter (OFAC SDN, OpenSanctions, ...) parses its own source format into
a list of plain dicts shaped like:

    {
        "source_uid": str,
        "entity_type": "individual" | "entity" | "vessel" | "aircraft",
        "primary_name": str,
        "title": str | None,
        "remarks": str | None,
        "names": [{"name_type", "quality", "full_name", "first_name", "last_name"}, ...],
        "addresses": [{"address_line", "city", "state_province", "postal_code", "country"}, ...],
        "identifications": [{"id_type", "id_number", "id_country"}, ...],
        "programs": [str, ...],
        "dates_of_birth": [str, ...],
        "nationalities": [{"relation", "country"}, ...],
    }

and hands the list to `upsert_entries`, which is identical across sources.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    Entity,
    EntityAddress,
    EntityDateOfBirth,
    EntityIdentification,
    EntityName,
    EntityNationality,
    EntityProgram,
    SourceList,
)

logger = logging.getLogger("app.ingestion.common")


def get_or_create_source_list(
    session: Session,
    *,
    code: str,
    name: str,
    list_type: str,
    url: str,
) -> SourceList:
    source_list = session.query(SourceList).filter_by(code=code).one_or_none()
    if source_list is None:
        source_list = SourceList(code=code, name=name, list_type=list_type, url=url)
        session.add(source_list)
        session.flush()
    return source_list


def upsert_entries(
    session: Session,
    source_list: SourceList,
    entries: list[dict],
    *,
    deactivate_missing: bool = True,
) -> dict:
    now = datetime.now(timezone.utc)
    seen_uids: set[str] = set()

    existing = {
        entity.source_uid: entity
        for entity in session.query(Entity).filter_by(source_list_id=source_list.id)
    }
    logger.info("Loaded %d existing entities for source list %s", len(existing), source_list.code)

    for index, record in enumerate(entries, start=1):
        uid = record["source_uid"]
        if not uid:
            continue
        seen_uids.add(uid)

        entity = existing.get(uid)
        if entity is None:
            entity = Entity(
                source_list_id=source_list.id,
                source_uid=uid,
                first_seen_at=now,
                raw={},
            )
            session.add(entity)
            existing[uid] = entity

        entity.entity_type = record["entity_type"]
        entity.primary_name = record["primary_name"]
        entity.title = record["title"]
        entity.remarks = record["remarks"]
        entity.is_active = True
        entity.last_seen_at = now
        entity.raw = record

        # Replace child rows wholesale; each refresh is a full re-sync of the source.
        entity.names.clear()
        entity.addresses.clear()
        entity.identifications.clear()
        entity.programs.clear()
        entity.dates_of_birth.clear()
        entity.nationalities.clear()

        for name in record["names"]:
            entity.names.append(EntityName(**name))
        for address in record["addresses"]:
            entity.addresses.append(EntityAddress(**address))
        for ident in record["identifications"]:
            entity.identifications.append(EntityIdentification(**ident))
        for program_code in record["programs"]:
            entity.programs.append(EntityProgram(program_code=program_code))
        for dob in record["dates_of_birth"]:
            entity.dates_of_birth.append(EntityDateOfBirth(date_of_birth=dob))
        for nationality in record["nationalities"]:
            entity.nationalities.append(EntityNationality(**nationality))

        if index % 2000 == 0:
            logger.info("Upserted %d/%d entities", index, len(entries))

    deactivated = 0
    if deactivate_missing:
        for uid, entity in existing.items():
            if uid not in seen_uids:
                entity.is_active = False
                deactivated += 1
    logger.info("Upsert complete: %d processed, %d deactivated", len(entries), deactivated)
    return {"processed": len(entries), "deactivated": deactivated}

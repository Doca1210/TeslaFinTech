"""Import real OFAC relationship data into the ownership graph (Layer C).

OFAC SDN records carry control/affiliation links in their free-text remarks, e.g.
``Hasan NASRALLAH (Linked To: HIZBALLAH)`` or
``... owned or controlled by BANK MELLI IRAN``. This module parses those into
``OwnershipLink`` rows so the ownership graph reflects thousands of *real*
relationships, not just the curated demo fixtures.

Direction follows the graph convention ``owner --relation--> company``: for
"A (Linked To: B)", B is the controlling/parent party, so the edge is
``B --linked_to--> A``. Tracing the smaller entity A surfaces B; reverse-exposure
on B fans out to everything it stands behind.

Both endpoints are resolved to real ``entities.id`` (exact normalized-name
match), and the owner's ``seeded_risk`` is derived from its actual source list,
so the imported graph works both offline (seeded) and with ``?live=true``.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models as m
from screening_v2.normalizer import Normalizer

logger = logging.getLogger("app")

_LINKED_TO = re.compile(r"Linked To:\s*([^;)]+)", re.IGNORECASE)
_OWNED_BY = re.compile(r"owned or controlled by\s+([^.;()]+)", re.IGNORECASE)


def _build_name_index(session: Session, normalizer: Normalizer) -> dict[str, tuple[int, str, str, str]]:
    """normalized name -> (entity_id, primary_name, list_type, source_code)."""
    rows = (
        session.query(
            m.EntityName.full_name,
            m.Entity.id,
            m.Entity.primary_name,
            m.SourceList.list_type,
            m.SourceList.code,
        )
        .join(m.Entity, m.EntityName.entity_id == m.Entity.id)
        .join(m.SourceList, m.Entity.source_list_id == m.SourceList.id)
        .filter(m.Entity.is_active.is_(True))
        .all()
    )
    index: dict[str, tuple[int, str, str, str]] = {}
    for full_name, eid, primary_name, list_type, code in rows:
        key = normalizer.normalize(full_name, "auto").cleaned
        if key:
            index.setdefault(key, (eid, primary_name, list_type, code))
    return index


def import_linked_to(session: Session, limit: int | None = None) -> int:
    """Parse OFAC 'Linked To' / 'owned or controlled by' remarks into edges.

    ``limit`` caps the number of edges created (handy for tests/demos). Returns
    the count of links inserted. Only edges whose controlling party resolves to a
    real watchlist entity are kept, so every imported edge carries a real risk.
    """
    normalizer = Normalizer()
    index = _build_name_index(session, normalizer)

    candidates = (
        session.query(m.Entity)
        .filter(or_(m.Entity.remarks.ilike("%Linked To:%"),
                    m.Entity.remarks.ilike("%owned or controlled by%")))
        .all()
    )

    created = 0
    seen: set[tuple[int, int]] = set()
    for ent in candidates:
        remarks = ent.remarks or ""
        targets = _LINKED_TO.findall(remarks) + _OWNED_BY.findall(remarks)
        for raw in targets:
            key = normalizer.normalize(raw.strip(), "auto").cleaned
            hit = index.get(key)
            if not hit:
                continue
            owner_id, owner_name, owner_list_type, owner_code = hit
            if owner_id == ent.id:
                continue
            dedupe = (owner_id, ent.id)
            if dedupe in seen:
                continue
            seen.add(dedupe)

            risk = "SANCTIONS_MATCH" if owner_list_type == "sanctions" else "PEP_MATCH"
            session.add(
                m.OwnershipLink(
                    from_entity_id=owner_id,
                    from_name=owner_name,
                    to_entity_id=ent.id,
                    to_name=ent.primary_name,
                    relation_type="linked_to",
                    ownership_pct=None,
                    source="ofac_linked_to",
                    seeded_risk={
                        "risk": risk,
                        "source": owner_code,
                        "confidence": 0.95 if owner_list_type == "sanctions" else 0.0,
                    },
                )
            )
            created += 1
            if limit is not None and created >= limit:
                session.commit()
                logger.info("import_linked_to: created %d links (limit reached)", created)
                return created

    session.commit()
    logger.info("import_linked_to: created %d links from OFAC remarks", created)
    return created

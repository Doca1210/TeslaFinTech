from __future__ import annotations

import sqlite3
from pathlib import Path

from screening.models import EntityType, WatchlistEntity

_ENTITY_TYPE_MAP = {
    "individual": EntityType.INDIVIDUAL,
    "entity": EntityType.ORGANIZATION,
    "vessel": EntityType.ORGANIZATION,
    "aircraft": EntityType.ORGANIZATION,
}

_QUERY = """
SELECT
    e.id,
    e.source_uid,
    e.entity_type,
    e.primary_name,
    e.remarks,
    sl.code  AS list_source,
    GROUP_CONCAT(CASE WHEN en.name_type != 'primary' THEN en.full_name END, '||') AS aliases,
    (SELECT nat.country FROM entity_nationalities nat
     WHERE nat.entity_id = e.id
     ORDER BY nat.id LIMIT 1)                                                     AS country,
    (SELECT ep.program_code FROM entity_programs ep
     WHERE ep.entity_id = e.id
     ORDER BY ep.id LIMIT 1)                                                      AS risk_category
FROM entities e
JOIN source_lists sl ON sl.id = e.source_list_id
LEFT JOIN entity_names en ON en.entity_id = e.id
WHERE e.is_active = 1
GROUP BY e.id
"""


def load_watchlist_from_db(db_path: Path | str) -> list[WatchlistEntity]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"AML database not found: {path}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(_QUERY).fetchall()
    finally:
        conn.close()

    result: list[WatchlistEntity] = []
    for row in rows:
        aliases = [a for a in (row["aliases"] or "").split("||") if a]
        result.append(
            WatchlistEntity(
                id=f"{row['list_source']}:{row['source_uid']}",
                full_name=row["primary_name"],
                entity_type=_ENTITY_TYPE_MAP.get(row["entity_type"], EntityType.ORGANIZATION),
                country=row["country"],
                aliases=aliases,
                list_source=row["list_source"],
                risk_category=row["risk_category"] or row["list_source"],
                notes=row["remarks"],
            )
        )
    return result


def default_db_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "aml.db"

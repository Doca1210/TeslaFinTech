from __future__ import annotations
from .models import EntityProfile


def fetch_entity_profiles_by_pks(session_factory, entity_pks: list[int]) -> dict[int, EntityProfile]:
    """Batch fetch EntityProfile for a list of entities.id (PKs). Returns dict keyed by PK."""
    if not entity_pks:
        return {}

    from app.models import Entity, SourceList
    session = session_factory()
    try:
        entities = (
            session.query(Entity)
            .filter(Entity.id.in_(entity_pks), Entity.is_active == True)
            .all()
        )
        result = {}
        for entity in entities:
            sl = entity.source_list
            result[entity.id] = EntityProfile(
                source_uid=entity.source_uid,
                source_list_code=sl.code if sl else "",
                list_type=sl.list_type if sl else "sanctions",
                primary_name=entity.primary_name or "",
                entity_type=entity.entity_type or "individual",
                aliases=[n.full_name for n in entity.names if n.full_name],
                programs=[p.program_code for p in entity.programs],
                nationalities=[n.country for n in entity.nationalities],
                dob=[d.date_of_birth for d in entity.dates_of_birth],
                addresses=[a.address_line for a in entity.addresses if a.address_line],
                ids=[
                    {"type": i.id_type, "number": i.id_number, "country": i.id_country}
                    for i in entity.identifications
                ],
                remarks=entity.remarks,
                list_version=sl.last_published_at if sl else None,
            )
        return result
    finally:
        session.close()


def load_all_profiles(session_factory) -> dict[int, EntityProfile]:
    """Bulk-load all active entity profiles into memory. Call once at startup."""
    from app.models import Entity, SourceList
    session = session_factory()
    try:
        entities = (
            session.query(Entity)
            .filter(Entity.is_active == True)
            .all()
        )
        result = {}
        for entity in entities:
            sl = entity.source_list
            result[entity.id] = EntityProfile(
                source_uid=entity.source_uid,
                source_list_code=sl.code if sl else "",
                list_type=sl.list_type if sl else "sanctions",
                primary_name=entity.primary_name or "",
                entity_type=entity.entity_type or "individual",
                aliases=[n.full_name for n in entity.names if n.full_name],
                programs=[p.program_code for p in entity.programs],
                nationalities=[n.country for n in entity.nationalities],
                dob=[d.date_of_birth for d in entity.dates_of_birth],
                addresses=[a.address_line for a in entity.addresses if a.address_line],
                ids=[
                    {"type": i.id_type, "number": i.id_number, "country": i.id_country}
                    for i in entity.identifications
                ],
                remarks=entity.remarks,
                list_version=sl.last_published_at if sl else None,
            )
        return result
    finally:
        session.close()

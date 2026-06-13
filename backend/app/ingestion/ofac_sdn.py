"""Fetch and ingest the OFAC SDN list (free Treasury XML feed) into our data model.

Run with:
    python -m app.ingestion.ofac_sdn

See docs/design/data_model_and_ofac_ingestion.md for the rationale behind the schema
and the upsert/soft-delete strategy.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx
from lxml import etree

from app.database import Base, SessionLocal, engine
from app.ingestion.common import get_or_create_source_list, upsert_entries

SDN_XML_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
SOURCE_LIST_CODE = "OFAC_SDN"
SOURCE_LIST_NAME = "OFAC Specially Designated Nationals (SDN) List"

logger = logging.getLogger("app.ingestion.ofac_sdn")

ENTITY_TYPE_MAP = {
    "individual": "individual",
    "entity": "entity",
    "vessel": "vessel",
    "aircraft": "aircraft",
}


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def local_findall(elem: etree._Element, path: str) -> list[etree._Element]:
    """Find children by tag name, ignoring the document namespace."""
    parts = path.split("/")
    current = [elem]
    for part in parts:
        next_level: list[etree._Element] = []
        for node in current:
            for child in node:
                if strip_ns(child.tag) == part:
                    next_level.append(child)
        current = next_level
    return current


def local_find_text(elem: etree._Element, path: str) -> str | None:
    found = local_findall(elem, path)
    if found and found[0].text:
        return found[0].text.strip() or None
    return None


def fetch_sdn_xml(url: str = SDN_XML_URL) -> bytes:
    logger.info("Fetching SDN XML from %s", url)
    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    logger.info("Fetched SDN XML (%d bytes)", len(response.content))
    return response.content


def parse_entry(entry: etree._Element) -> dict:
    sdn_type_raw = (local_find_text(entry, "sdnType") or "individual").lower()
    entity_type = ENTITY_TYPE_MAP.get(sdn_type_raw, "entity")

    first_name = local_find_text(entry, "firstName")
    last_name = local_find_text(entry, "lastName")
    primary_name = " ".join(part for part in (first_name, last_name) if part) or last_name or ""

    names: list[dict] = [
        {
            "name_type": "primary",
            "quality": None,
            "full_name": primary_name,
            "first_name": first_name,
            "last_name": last_name,
        }
    ]
    for aka in local_findall(entry, "akaList/aka"):
        aka_first = local_find_text(aka, "firstName")
        aka_last = local_find_text(aka, "lastName")
        aka_full = " ".join(part for part in (aka_first, aka_last) if part) or aka_last or ""
        aka_type = (local_find_text(aka, "type") or "aka").lower()
        names.append(
            {
                "name_type": "fka" if "f.k.a" in aka_type else "nka" if "n.k.a" in aka_type else "aka",
                "quality": (local_find_text(aka, "category") or "").lower() or None,
                "full_name": aka_full,
                "first_name": aka_first,
                "last_name": aka_last,
            }
        )

    addresses: list[dict] = []
    for addr in local_findall(entry, "addressList/address"):
        address_parts = [
            local_find_text(addr, "address1"),
            local_find_text(addr, "address2"),
            local_find_text(addr, "address3"),
        ]
        addresses.append(
            {
                "address_line": ", ".join(p for p in address_parts if p) or None,
                "city": local_find_text(addr, "city"),
                "state_province": local_find_text(addr, "stateOrProvince"),
                "postal_code": local_find_text(addr, "postalCode"),
                "country": local_find_text(addr, "country"),
            }
        )

    identifications: list[dict] = []
    for id_elem in local_findall(entry, "idList/id"):
        id_type = local_find_text(id_elem, "idType")
        id_number = local_find_text(id_elem, "idNumber")
        if not id_type or not id_number:
            continue
        identifications.append(
            {
                "id_type": id_type,
                "id_number": id_number,
                "id_country": local_find_text(id_elem, "idCountry"),
            }
        )

    programs = [
        elem.text.strip()
        for elem in local_findall(entry, "programList/program")
        if elem.text and elem.text.strip()
    ]

    dates_of_birth = [
        elem.text.strip()
        for elem in local_findall(entry, "dateOfBirthList/dateOfBirthItem/dateOfBirth")
        if elem.text and elem.text.strip()
    ]

    nationalities: list[dict] = []
    for elem in local_findall(entry, "nationalityList/nationality/country"):
        if elem.text and elem.text.strip():
            nationalities.append({"relation": "nationality", "country": elem.text.strip()})
    for elem in local_findall(entry, "citizenshipList/citizenship/country"):
        if elem.text and elem.text.strip():
            nationalities.append({"relation": "citizenship", "country": elem.text.strip()})
    for elem in local_findall(entry, "placeOfBirthList/placeOfBirthItem/placeOfBirth"):
        if elem.text and elem.text.strip():
            nationalities.append({"relation": "place_of_birth", "country": elem.text.strip()})

    return {
        "source_uid": local_find_text(entry, "uid") or "",
        "entity_type": entity_type,
        "primary_name": primary_name,
        "title": local_find_text(entry, "title"),
        "remarks": local_find_text(entry, "remarks"),
        "names": names,
        "addresses": addresses,
        "identifications": identifications,
        "programs": programs,
        "dates_of_birth": dates_of_birth,
        "nationalities": nationalities,
    }


def parse_sdn_xml(xml_bytes: bytes) -> tuple[str | None, list[dict]]:
    root = etree.fromstring(xml_bytes)
    publish_date = None
    for pub_info in local_findall(root, "publshInformation"):
        publish_date = local_find_text(pub_info, "Publish_Date")

    entries = [
        parse_entry(entry)
        for entry in root
        if strip_ns(entry.tag) == "sdnEntry"
    ]
    logger.info("Parsed %d SDN entries (publish_date=%s)", len(entries), publish_date)
    return publish_date, entries


def run_ingestion() -> dict:
    start = time.perf_counter()
    Base.metadata.create_all(bind=engine)

    xml_bytes = fetch_sdn_xml()
    publish_date, entries = parse_sdn_xml(xml_bytes)

    session = SessionLocal()
    try:
        source_list = get_or_create_source_list(
            session,
            code=SOURCE_LIST_CODE,
            name=SOURCE_LIST_NAME,
            list_type="sanctions",
            url=SDN_XML_URL,
        )
        upsert_entries(session, source_list, entries)

        source_list.last_fetched_at = datetime.now(timezone.utc)
        source_list.last_published_at = publish_date

        logger.info("Committing changes to database")
        session.commit()
        duration = time.perf_counter() - start
        logger.info("Ingestion finished in %.1fs", duration)
        return {"source_list": source_list.code, "entries_processed": len(entries), "publish_date": publish_date}
    finally:
        session.close()


if __name__ == "__main__":
    from app.logging_config import configure_logging

    configure_logging()
    result = run_ingestion()
    print(result)

"""Demo seed data for the KYB / beneficial-ownership graph (Layer C).

Two layers of data feed the graph:

1. **Curated scenarios** (this file) — a hand-picked set whose *risky leaves are
   real sanctioned / PEP entities* (Russia / B2B-trade flavour, pulled from the
   ingested watchlist) sitting under *constructed* shell-company layers. This is
   the scripted, deterministic demo set. The real leaves mean ``?live=true``
   genuinely re-screens them against the watchlist, and ``seed_demo_ownership``
   best-effort links each real leaf to its actual ``entities.id`` for audit.

2. **Bulk real graph** — ``app.ownership_ingest.import_linked_to`` parses the
   thousands of real OFAC "Linked To:" relationships into the same table.

Run standalone against an in-memory SQLite::

    python -m app.ownership_fixtures
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models as m

# Reusable risk records for the seeded (offline) fallback. Real names also link
# to entities.id at seed time, but seeded_risk keeps the demo working offline.
SANC = {"risk": "SANCTIONS_MATCH", "source": "OFAC_SDN", "confidence": 0.95}
PEP = {"risk": "PEP_MATCH", "source": "OpenSanctions PEPs", "confidence": 0.0}

# from, to, relation, pct, source, seeded_risk
DEMO_OWNERSHIP: list[dict] = [
    # --- Synthetic baseline (kept for a fully self-contained example) ---------
    {"from": "Ivan Petrov", "to": "Crimson Holdings Ltd", "relation": "beneficial_owner",
     "pct": 35.0, "source": "demo_registry", "seeded_risk": PEP},
    {"from": "Crimson Holdings Ltd", "to": "Blue Horizon Trading LLC", "relation": "parent_company",
     "pct": 80.0, "source": "demo_registry", "seeded_risk": None},
    {"from": "Hans Mueller", "to": "Milan Textile GmbH", "relation": "director",
     "pct": 100.0, "source": "demo_registry", "seeded_risk": None},

    # --- Scenario: direct sanctioned owner -> BLOCK (real OFAC individual) -----
    {"from": "Dmitry Olegovich ROGOZIN", "to": "Northwind Commodities DMCC", "relation": "beneficial_owner",
     "pct": 60.0, "source": "manual_kyb", "seeded_risk": SANC},

    # --- Scenario: PEP beneficial owner -> REVIEW (real PEP) ------------------
    {"from": "Vasily Nebenzya", "to": "Adriatic Freight Forwarding doo", "relation": "beneficial_owner",
     "pct": 40.0, "source": "manual_kyb", "seeded_risk": PEP},

    # --- Scenario: deep chain -> REVIEW, effective % (real OFAC at depth 2) ----
    {"from": "Viktor Fedorovych YANUKOVYCH", "to": "Baltic Holding Group Ltd", "relation": "beneficial_owner",
     "pct": 45.0, "source": "manual_kyb", "seeded_risk": SANC},
    {"from": "Baltic Holding Group Ltd", "to": "Lumen Trading FZE", "relation": "parent_company",
     "pct": 75.0, "source": "manual_kyb", "seeded_risk": None},

    # --- Scenario: sanctioned ENTITY as owner (real OFAC bank) ----------------
    {"from": "BANK ROSSIYA", "to": "Saint Petersburg Maritime Services LLC", "relation": "intermediary",
     "pct": 51.0, "source": "manual_kyb", "seeded_risk": SANC},

    # --- Scenario: reverse-exposure hub -- ROGOZIN behind several shells -------
    {"from": "Dmitry Olegovich ROGOZIN", "to": "Ural Metals Export OOO", "relation": "beneficial_owner",
     "pct": 55.0, "source": "manual_kyb", "seeded_risk": SANC},
    {"from": "Dmitry Olegovich ROGOZIN", "to": "Caspian Logistics Holding Ltd", "relation": "beneficial_owner",
     "pct": 70.0, "source": "manual_kyb", "seeded_risk": SANC},

    # --- Scenario: clean control -> NO_MATCH (not on any list) ----------------
    {"from": "Thomas Bergmann", "to": "Alpine Precision Tools AG", "relation": "director",
     "pct": 100.0, "source": "demo_registry", "seeded_risk": None},
]


def _resolve_entity_id(session: Session, name: str) -> int | None:
    """Best-effort link a (real) party name to its entities.id for audit."""
    row = (
        session.query(m.Entity.id)
        .join(m.EntityName, m.EntityName.entity_id == m.Entity.id)
        .filter(func.lower(m.EntityName.full_name) == name.lower())
        .first()
    )
    return row[0] if row else None


def seed_demo_ownership(session: Session) -> int:
    """Insert the curated demo ownership edges. Returns the number created."""
    created = 0
    for d in DEMO_OWNERSHIP:
        link = m.OwnershipLink(
            from_name=d["from"],
            to_name=d["to"],
            relation_type=d["relation"],
            ownership_pct=d.get("pct"),
            source=d.get("source", "demo_registry"),
            seeded_risk=d.get("seeded_risk"),
            from_entity_id=_resolve_entity_id(session, d["from"]),
        )
        session.add(link)
        created += 1
    session.commit()
    return created


def _demo() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.ownership import OwnershipRiskEngine

    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine)

    with SessionLocal() as s:
        seed_demo_ownership(s)

    risk = OwnershipRiskEngine(SessionLocal, engine=None)  # seeded fallback
    for name in (
        "Northwind Commodities DMCC",
        "Adriatic Freight Forwarding doo",
        "Lumen Trading FZE",
        "Alpine Precision Tools AG",
    ):
        r = risk.assess(name)
        print(f"\n=== {name} ===")
        print(f"verdict={r['verdict']} score={r['score']} traced={r['related_parties_traced']}")
        print(f"reason: {r['reason']}")


if __name__ == "__main__":
    _demo()

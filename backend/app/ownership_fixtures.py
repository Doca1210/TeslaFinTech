"""Demo seed data for the KYB / beneficial-ownership graph (Layer C).

The headline scenario is a *clean company name that becomes REVIEW because of a
risky beneficial owner two hops up the chain*:

    Ivan Petrov --beneficial_owner(35%)--> Crimson Holdings Ltd
    Crimson Holdings Ltd --parent_company(80%)--> Blue Horizon Trading LLC

A screen of "Blue Horizon Trading LLC" is clean, but tracing ownership surfaces
Ivan Petrov, a PEP. ``seeded_risk`` makes the demo deterministic even if Ivan is
not in the locally ingested PEP feed; with a live engine wired, a real hit takes
precedence over the seed.

Run standalone against an in-memory SQLite::

    python -m app.ownership_fixtures
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models as m

# from, to, relation, pct, source, seeded_risk
DEMO_OWNERSHIP: list[dict] = [
    {
        "from": "Ivan Petrov",
        "to": "Crimson Holdings Ltd",
        "relation": "beneficial_owner",
        "pct": 35.0,
        "source": "demo_registry",
        "seeded_risk": {"risk": "PEP_MATCH", "source": "OpenSanctions PEPs", "confidence": 0.0},
    },
    {
        "from": "Crimson Holdings Ltd",
        "to": "Blue Horizon Trading LLC",
        "relation": "parent_company",
        "pct": 80.0,
        "source": "demo_registry",
        "seeded_risk": None,
    },
    # Clean control: Milan Textile GmbH (Scenario 1) has a clean sole director.
    {
        "from": "Hans Mueller",
        "to": "Milan Textile GmbH",
        "relation": "director",
        "pct": 100.0,
        "source": "demo_registry",
        "seeded_risk": None,
    },
]


def seed_demo_ownership(session: Session) -> int:
    """Insert the demo ownership edges. Returns the number of links created."""
    links = [
        m.OwnershipLink(
            from_name=d["from"],
            to_name=d["to"],
            relation_type=d["relation"],
            ownership_pct=d.get("pct"),
            source=d["source"],
            seeded_risk=d.get("seeded_risk"),
        )
        for d in DEMO_OWNERSHIP
    ]
    session.add_all(links)
    session.commit()
    return len(links)


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

    # engine=None -> rely on seeded_risk fallback (no ingested watchlist needed).
    risk = OwnershipRiskEngine(SessionLocal, engine=None)
    for name in ("Blue Horizon Trading LLC", "Milan Textile GmbH"):
        result = risk.assess(name)
        print(f"\n=== {name} ===")
        print(f"verdict={result['verdict']} score={result['score']} "
              f"traced={result['related_parties_traced']}")
        print(f"reason: {result['reason']}")
        for p in result["paths"]:
            print(f"  path={' -> '.join(p['path'])} | {p['risk']} "
                  f"({p['matched_via']}, depth {p['depth']}, score {p['score']})")


if __name__ == "__main__":
    _demo()

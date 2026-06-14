"""Tests for the KYB / beneficial-ownership graph (Layer C)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import OwnershipAssessment
from app.ownership import OwnershipRiskEngine, trace_controlled_entities, trace_related_parties
from app.ownership_fixtures import seed_demo_ownership
from screening_v2.composer import VerdictComposer
from screening_v2.models import ScreeningResult


@pytest.fixture()
def session_factory():
    # StaticPool + check_same_thread=False: a single shared in-memory DB that is
    # visible from TestClient's worker thread (used by the endpoint test).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine)
    with SessionLocal() as s:
        seed_demo_ownership(s)
    return SessionLocal


# --------------------------------------------------------------------------- #
# A fake ScreeningEngine to exercise the live-screen branch deterministically.
# --------------------------------------------------------------------------- #
class _FakeEngine:
    """Returns a hit for configured names, NO_MATCH otherwise."""

    def __init__(self, hits: dict[str, tuple[str, str, float, str]]):
        # name -> (verdict, list_type, confidence, source_list_code)
        self._hits = hits

    def screen(self, name: str, entity_type: str = "auto") -> ScreeningResult:
        if name not in self._hits:
            return ScreeningResult(
                "NO_MATCH", 0.0, name, "individual", name.lower(), ["normal"], 1, [], "clean"
            )
        verdict, list_type, conf, source = self._hits[name]
        candidate = SimpleNamespace(
            entity_profile=SimpleNamespace(list_type=list_type, source_list_code=source)
        )
        return ScreeningResult(
            verdict, conf, name, "individual", name.lower(), ["normal"], 1, [candidate], "hit"
        )


# --------------------------------------------------------------------------- #
# Graph traversal
# --------------------------------------------------------------------------- #
def test_trace_resolves_and_walks_two_hops(session_factory):
    with session_factory() as s:
        parties = trace_related_parties(s, "Blue Horizon Trading LLC", max_depth=2)
    names = {p.name: p for p in parties}
    assert "Crimson Holdings Ltd" in names
    assert "Ivan Petrov" in names
    assert names["Crimson Holdings Ltd"].depth == 1
    assert names["Ivan Petrov"].depth == 2
    assert names["Ivan Petrov"].path == [
        "Blue Horizon Trading LLC", "Crimson Holdings Ltd", "Ivan Petrov"
    ]


def test_trace_depth_limit_stops_recursion(session_factory):
    with session_factory() as s:
        parties = trace_related_parties(s, "Blue Horizon Trading LLC", max_depth=1)
    names = {p.name for p in parties}
    assert names == {"Crimson Holdings Ltd"}  # Ivan is depth 2, excluded


def test_trace_fuzzy_resolution(session_factory):
    # Legal-suffix / wording drift still resolves to the node.
    with session_factory() as s:
        parties = trace_related_parties(s, "Blue Horizon Trading", max_depth=2)
    assert any(p.name == "Ivan Petrov" for p in parties)


def test_trace_unknown_beneficiary_returns_empty(session_factory):
    with session_factory() as s:
        assert trace_related_parties(s, "Totally Unrelated Co", max_depth=2) == []


# --------------------------------------------------------------------------- #
# Risk assessment — seeded fallback (engine=None)
# --------------------------------------------------------------------------- #
def test_seeded_pep_owner_yields_review(session_factory):
    result = OwnershipRiskEngine(session_factory, engine=None).assess("Blue Horizon Trading LLC")
    assert result["verdict"] == "REVIEW"
    assert result["related_parties_traced"] == 2
    top = result["paths"][0]
    assert top["risk"] == "PEP_MATCH"
    assert top["matched_via"] == "seeded"
    # PEP base 55 * depth-2 factor 0.7 * pct factor 1.0 (35% is a UBO) = 38.5
    assert top["score"] == pytest.approx(38.5)
    assert top["is_ubo"] is True


def test_clean_company_with_clean_owner_is_no_match(session_factory):
    result = OwnershipRiskEngine(session_factory, engine=None).assess("Milan Textile GmbH")
    assert result["verdict"] == "NO_MATCH"
    assert result["score"] == 0.0
    assert result["paths"] == []


def test_unknown_beneficiary_is_no_match(session_factory):
    result = OwnershipRiskEngine(session_factory, engine=None).assess("Nobody Special Inc")
    assert result["verdict"] == "NO_MATCH"
    assert result["related_parties_traced"] == 0


# --------------------------------------------------------------------------- #
# Risk assessment — live screen precedence & blocking
# --------------------------------------------------------------------------- #
def test_live_screen_takes_precedence_over_seed(session_factory):
    engine = _FakeEngine({"Ivan Petrov": ("REVIEW", "pep", 0.91, "OFAC_PEP")})
    result = OwnershipRiskEngine(session_factory, engine=engine).assess("Blue Horizon Trading LLC")
    top = result["paths"][0]
    assert top["matched_via"] == "live_screen"
    assert top["source"] == "OFAC_PEP"
    assert top["screen_confidence"] == pytest.approx(0.91)


def test_direct_sanctioned_owner_blocks(session_factory):
    # Make Crimson (depth 1) a high-confidence sanctions MATCH.
    engine = _FakeEngine({"Crimson Holdings Ltd": ("MATCH", "sanctions", 0.95, "OFAC_SDN")})
    result = OwnershipRiskEngine(session_factory, engine=engine).assess("Blue Horizon Trading LLC")
    assert result["verdict"] == "MATCH"
    crimson = next(p for p in result["paths"] if p["path"][-1] == "Crimson Holdings Ltd")
    assert crimson["risk"] == "SANCTIONS_MATCH"
    # 90 base * depth-1 1.0 * 80% UBO 1.0 = 90
    assert crimson["score"] == pytest.approx(90.0)


def test_deep_sanctions_match_is_review_not_block(session_factory):
    # Ivan is depth 2 — a sanctions MATCH there should NOT auto-block.
    engine = _FakeEngine({"Ivan Petrov": ("MATCH", "sanctions", 0.95, "OFAC_SDN")})
    result = OwnershipRiskEngine(session_factory, engine=engine).assess("Blue Horizon Trading LLC")
    assert result["verdict"] == "REVIEW"


# --------------------------------------------------------------------------- #
# Composer Layer-C integration
# --------------------------------------------------------------------------- #
def _clean(name: str) -> ScreeningResult:
    return ScreeningResult("NO_MATCH", 0.0, name, "entity", name.lower(), ["normal"], 1, [], "clean")


def test_composer_folds_ownership_review_when_a_and_b_clean():
    ownership = {"verdict": "REVIEW", "score": 38.5, "reason": "risky owner", "paths": []}
    r = VerdictComposer().compose_payment(
        _clean("Orig"), _clean("Blue Horizon"), 0.0, "approve", [], ownership=ownership
    )
    assert r["verdict"] == "REVIEW"
    assert r["recommended_action"] == "MANUAL_REVIEW"
    assert "layer_c_ownership" in r["triggered_layers"]
    assert r["ownership_risk"] is ownership
    assert "Layer C" in r["explanation"]


def test_composer_ownership_match_blocks():
    ownership = {"verdict": "MATCH", "score": 90.0, "reason": "sanctioned owner", "paths": []}
    r = VerdictComposer().compose_payment(
        _clean("Orig"), _clean("Bene"), 0.0, "approve", [], ownership=ownership
    )
    assert r["verdict"] == "MATCH"
    assert r["confidence"] == pytest.approx(0.9)


def test_composer_without_ownership_is_unchanged():
    r = VerdictComposer().compose_payment(_clean("Orig"), _clean("Bene"), 0.0, "approve", [])
    assert r["verdict"] == "NO_MATCH"
    assert "layer_c_ownership" not in r["triggered_layers"]
    assert r["ownership_risk"] is None


# --------------------------------------------------------------------------- #
# Frontend graph payload + per-path explanation
# --------------------------------------------------------------------------- #
def test_result_includes_graph_nodes_and_edges(session_factory):
    result = OwnershipRiskEngine(session_factory, engine=None).assess("Blue Horizon Trading LLC")
    graph = result["graph"]
    node_names = {n["name"] for n in graph["nodes"]}
    assert node_names == {"Blue Horizon Trading LLC", "Crimson Holdings Ltd", "Ivan Petrov"}

    # Beneficiary is the depth-0 root and not flagged; Ivan is flagged.
    root = next(n for n in graph["nodes"] if n["name"] == "Blue Horizon Trading LLC")
    assert root["depth"] == 0 and root["is_flagged"] is False
    ivan = next(n for n in graph["nodes"] if n["name"] == "Ivan Petrov")
    assert ivan["is_flagged"] is True and ivan["risk"] == "PEP_MATCH"

    # Edges point owner -> company it owns.
    edges = {(e["from"], e["to"]): e for e in graph["edges"]}
    assert ("Crimson Holdings Ltd", "Blue Horizon Trading LLC") in edges
    assert ("Ivan Petrov", "Crimson Holdings Ltd") in edges
    assert edges[("Ivan Petrov", "Crimson Holdings Ltd")]["ownership_pct"] == 35.0


def test_graph_empty_for_unknown_beneficiary(session_factory):
    result = OwnershipRiskEngine(session_factory, engine=None).assess("Unknown Co")
    assert result["graph"] == {"nodes": [], "edges": []}


def test_path_has_analyst_explanation(session_factory):
    result = OwnershipRiskEngine(session_factory, engine=None).assess("Blue Horizon Trading LLC")
    explanation = result["paths"][0]["explanation"]
    assert "Ivan Petrov" in explanation
    assert "politically exposed person" in explanation
    assert "direct name screening" in explanation


# --------------------------------------------------------------------------- #
# HTTP endpoint
# --------------------------------------------------------------------------- #
def test_screen_ownership_endpoint(session_factory, monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import app.main as main

    # Bind a seeded in-memory engine so the route does not build the heavy
    # ScreeningEngine (no embedding model needed for the test).
    monkeypatch.setattr(main, "_ownership_engine", OwnershipRiskEngine(session_factory, engine=None))
    client = TestClient(main.app)

    resp = client.get("/screen/ownership", params={"name": "Blue Horizon Trading LLC"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "REVIEW"
    assert body["beneficiary"] == "Blue Horizon Trading LLC"
    assert body["paths"][0]["risk"] == "PEP_MATCH"
    assert len(body["graph"]["nodes"]) == 3


# --------------------------------------------------------------------------- #
# #4 Effective (cumulative) ownership %
# --------------------------------------------------------------------------- #
def test_effective_ownership_is_product_along_chain(session_factory):
    with session_factory() as s:
        parties = {p.name: p for p in trace_related_parties(s, "Blue Horizon Trading LLC", max_depth=2)}
    # Crimson directly owns 80% of Blue Horizon.
    assert parties["Crimson Holdings Ltd"].effective_pct == pytest.approx(80.0)
    # Ivan owns 35% of Crimson which owns 80% of Blue Horizon -> 28% effective.
    assert parties["Ivan Petrov"].effective_pct == pytest.approx(28.0)


def test_effective_ownership_surfaced_in_result(session_factory):
    result = OwnershipRiskEngine(session_factory, engine=None).assess("Blue Horizon Trading LLC")
    top = result["paths"][0]
    assert top["effective_pct"] == pytest.approx(28.0)
    assert top["is_ubo"] is True  # 28% still clears the 25% UBO bar
    assert "effective" in result["reason"].lower()
    assert "28%" in top["explanation"]


def test_missing_pct_in_chain_yields_no_effective(session_factory):
    # Director edge with ownership_pct=None -> effective cannot be computed.
    from app import models as m

    with session_factory() as s:
        s.add(m.OwnershipLink(
            from_name="Mystery Trust", to_name="Crimson Holdings Ltd",
            relation_type="director", ownership_pct=None, source="manual_kyb",
        ))
        s.commit()
        parties = {p.name: p for p in trace_related_parties(s, "Blue Horizon Trading LLC", max_depth=2)}
    assert parties["Mystery Trust"].effective_pct is None


# --------------------------------------------------------------------------- #
# #5 Reverse exposure lookup
# --------------------------------------------------------------------------- #
def test_trace_controlled_entities_walks_downward(session_factory):
    with session_factory() as s:
        controlled = {c.name: c for c in trace_controlled_entities(s, "Ivan Petrov", max_depth=2)}
    assert set(controlled) == {"Crimson Holdings Ltd", "Blue Horizon Trading LLC"}
    assert controlled["Crimson Holdings Ltd"].depth == 1
    assert controlled["Blue Horizon Trading LLC"].depth == 2
    assert controlled["Blue Horizon Trading LLC"].effective_pct == pytest.approx(28.0)


def test_exposure_payload(session_factory):
    result = OwnershipRiskEngine(session_factory, engine=None).exposure("Ivan Petrov")
    assert result["controls_count"] == 2
    companies = {c["company"] for c in result["controls"]}
    assert companies == {"Crimson Holdings Ltd", "Blue Horizon Trading LLC"}


def test_exposure_empty_for_leaf_company(session_factory):
    # Blue Horizon controls nothing downstream.
    result = OwnershipRiskEngine(session_factory, engine=None).exposure("Blue Horizon Trading LLC")
    assert result["controls_count"] == 0


# --------------------------------------------------------------------------- #
# #6 Persisted assessment
# --------------------------------------------------------------------------- #
def test_assess_persists_audit_record(session_factory):
    engine = OwnershipRiskEngine(session_factory, engine=None)
    result = engine.assess("Blue Horizon Trading LLC", persist=True)
    assert "assessment_id" in result

    with session_factory() as s:
        rows = s.query(OwnershipAssessment).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.beneficiary_name == "Blue Horizon Trading LLC"
        assert row.verdict == "REVIEW"
        assert row.related_parties_traced == 2
        assert row.paths and row.graph  # JSON evidence stored


def test_assess_without_persist_writes_nothing(session_factory):
    OwnershipRiskEngine(session_factory, engine=None).assess("Blue Horizon Trading LLC")
    with session_factory() as s:
        assert s.query(OwnershipAssessment).count() == 0


def test_exposure_endpoint(session_factory, monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import app.main as main

    monkeypatch.setattr(main, "_ownership_engine", OwnershipRiskEngine(session_factory, engine=None))
    client = TestClient(main.app)

    resp = client.get("/ownership/exposure", params={"name": "Ivan Petrov"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["controls_count"] == 2


# --------------------------------------------------------------------------- #
# Curated real-leaf scenarios (Russia / B2B flavour)
# --------------------------------------------------------------------------- #
def test_direct_real_sanctioned_owner_blocks(session_factory):
    # Northwind is clean by name, but is 60% owned by a real OFAC individual.
    r = OwnershipRiskEngine(session_factory, engine=None).assess("Northwind Commodities DMCC")
    assert r["verdict"] == "MATCH"
    assert r["paths"][0]["risk"] == "SANCTIONS_MATCH"


def test_real_pep_owner_reviews(session_factory):
    r = OwnershipRiskEngine(session_factory, engine=None).assess("Adriatic Freight Forwarding doo")
    assert r["verdict"] == "REVIEW"
    assert r["paths"][0]["risk"] == "PEP_MATCH"


def test_deep_real_sanctioned_chain_reviews(session_factory):
    # Sanctioned UBO sits at depth 2 -> REVIEW, not auto-block.
    r = OwnershipRiskEngine(session_factory, engine=None).assess("Lumen Trading FZE")
    assert r["verdict"] == "REVIEW"
    top = r["paths"][0]
    assert top["depth"] == 2
    assert top["effective_pct"] == pytest.approx(33.75)  # 45% * 75%


def test_real_sanctioned_owner_reverse_exposure(session_factory):
    # ROGOZIN stands behind three constructed shells.
    r = OwnershipRiskEngine(session_factory, engine=None).exposure("Dmitry Olegovich ROGOZIN")
    assert r["controls_count"] == 3
    companies = {c["company"] for c in r["controls"]}
    assert companies == {
        "Northwind Commodities DMCC",
        "Ural Metals Export OOO",
        "Caspian Logistics Holding Ltd",
    }


def test_clean_real_control_no_match(session_factory):
    r = OwnershipRiskEngine(session_factory, engine=None).assess("Alpine Precision Tools AG")
    assert r["verdict"] == "NO_MATCH"


# --------------------------------------------------------------------------- #
# Bulk import of real OFAC "Linked To" relationships
# --------------------------------------------------------------------------- #
def _ofac_fixture(session):
    """Minimal OFAC-like data: a sanctioned org + two entities linked to it."""
    from app import models as m

    sl = m.SourceList(code="OFAC_SDN", name="OFAC SDN", list_type="sanctions")
    session.add(sl)
    session.flush()

    org = m.Entity(source_list_id=sl.id, source_uid="org1", entity_type="entity",
                   primary_name="HEZBOLLAH FINANCE", raw={})
    a = m.Entity(source_list_id=sl.id, source_uid="a", entity_type="entity",
                 primary_name="Cedar Trading House", remarks="(Linked To: HEZBOLLAH FINANCE)", raw={})
    b = m.Entity(source_list_id=sl.id, source_uid="b", entity_type="individual",
                 primary_name="Karim Haddad",
                 remarks="Owner; owned or controlled by HEZBOLLAH FINANCE.", raw={})
    session.add_all([org, a, b])
    session.flush()
    for ent in (org, a, b):
        session.add(m.EntityName(entity_id=ent.id, name_type="primary", full_name=ent.primary_name))
    session.commit()


def test_import_linked_to_builds_real_edges():
    from app.ownership_ingest import import_linked_to

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    SL = sessionmaker(engine)
    with SL() as s:
        _ofac_fixture(s)
        created = import_linked_to(s)
        assert created == 2  # Cedar + Karim both linked to the org

    # Tracing a linked entity surfaces the sanctioned org as the risky owner.
    r = OwnershipRiskEngine(SL, engine=None).assess("Cedar Trading House")
    assert r["verdict"] == "MATCH"
    assert r["paths"][0]["path"][-1] == "HEZBOLLAH FINANCE"
    assert r["paths"][0]["risk"] == "SANCTIONS_MATCH"

    # Reverse exposure: the org stands behind both linked entities.
    ex = OwnershipRiskEngine(SL, engine=None).exposure("HEZBOLLAH FINANCE")
    assert ex["controls_count"] == 2


def test_import_linked_to_respects_limit():
    from app.ownership_ingest import import_linked_to

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    SL = sessionmaker(engine)
    with SL() as s:
        _ofac_fixture(s)
        created = import_linked_to(s, limit=1)
        assert created == 1

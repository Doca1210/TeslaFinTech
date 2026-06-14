"""KYB / beneficial-ownership exposure graph — Layer C of the payment verdict.

A clean beneficiary name can still be risky if a person *behind* the company is
sanctioned or politically exposed. This module:

1. resolves a beneficiary **name** to a node in the ``ownership_links`` graph
   (normalized-exact, then RapidFuzz fallback — see :func:`trace_related_parties`),
2. walks the graph upward to ``max_depth`` collecting related parties, and
3. assesses each party's risk with a **hybrid** strategy: re-screen the party's
   name through the live :class:`~screening_v2.engine.ScreeningEngine`; if that
   returns ``NO_MATCH`` (or no engine is wired), fall back to the edge's
   ``seeded_risk`` demo record.

The result mirrors ``app.aml_detect.RuleHit`` conventions (machine ``reason`` +
``score`` + structured evidence) and folds into
:meth:`screening_v2.composer.VerdictComposer.compose_payment` as Layer C.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from rapidfuzz.fuzz import token_set_ratio
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from screening_v2.engine import ScreeningEngine
from screening_v2.normalizer import Normalizer

# token_set_ratio is 0-100; 85 ≈ "same company, minor wording difference".
FUZZY_RESOLVE_THRESHOLD = 85.0

# Base score (0-100) per discovered risk kind, before depth / ownership weighting.
RISK_BASE = {
    "SANCTIONS_MATCH": 90.0,
    "SANCTIONS_REVIEW": 60.0,
    "PEP_MATCH": 55.0,
}

UBO_PCT = 25.0  # >= 25% ownership counts as an Ultimate Beneficial Owner.


# --------------------------------------------------------------------------- #
# Data carriers
# --------------------------------------------------------------------------- #
@dataclass
class RelatedParty:
    name: str
    relation: str
    ownership_pct: float | None     # direct stake on the immediate edge
    depth: int                  # hops from the beneficiary (1 = direct owner)
    entity_id: int | None
    seeded_risk: dict | None
    path: list[str] = field(default_factory=list)  # beneficiary -> ... -> this party
    effective_pct: float | None = None  # cumulative stake in the beneficiary (product along the chain)


@dataclass
class ControlledEntity:
    """A company a party controls — the reverse direction of :class:`RelatedParty`."""

    name: str
    relation: str
    ownership_pct: float | None     # direct stake on the immediate edge
    depth: int
    path: list[str] = field(default_factory=list)  # party -> ... -> this company
    effective_pct: float | None = None  # cumulative stake the party holds in this company


@dataclass
class OwnershipFinding:
    party: RelatedParty
    risk: str                   # SANCTIONS_MATCH | SANCTIONS_REVIEW | PEP_MATCH
    matched_via: str            # live_screen | seeded
    source: str
    screen_confidence: float | None
    score: float


# --------------------------------------------------------------------------- #
# Graph traversal
# --------------------------------------------------------------------------- #
def _norm(normalizer: Normalizer, name: str) -> str:
    return normalizer.normalize(name, "auto").cleaned


def _extend_cumulative(cum: float | None, edge_pct: float | None) -> tuple[float | None, float | None]:
    """Multiply a running ownership fraction by one more edge.

    Returns ``(new_fraction, effective_pct)``. Either becomes ``None`` once any
    edge in the chain has an unknown percentage (e.g. a directorship), since the
    cumulative stake can no longer be computed.
    """
    if cum is None or edge_pct is None:
        return None, None
    new_cum = cum * (edge_pct / 100.0)
    return new_cum, round(new_cum * 100.0, 2)


def _resolve_node(session: Session, normalizer: Normalizer, name: str) -> str | None:
    """Map a free-text beneficiary name onto a known graph node name.

    Normalized-exact match wins; otherwise the best RapidFuzz ``token_set_ratio``
    above :data:`FUZZY_RESOLVE_THRESHOLD`.
    """
    target = _norm(normalizer, name)
    if not target:
        return None

    node_names: set[str] = set()
    for link in session.scalars(
        select(m.OwnershipLink).where(m.OwnershipLink.is_active.is_(True))
    ):
        node_names.add(link.from_name)
        node_names.add(link.to_name)

    best_name: str | None = None
    best_score = 0.0
    for original in node_names:
        cleaned = _norm(normalizer, original)
        if cleaned == target:
            return original
        score = token_set_ratio(target, cleaned)
        if score > best_score:
            best_score, best_name = score, original

    return best_name if best_score >= FUZZY_RESOLVE_THRESHOLD else None


def trace_related_parties(
    session: Session,
    beneficiary_name: str,
    max_depth: int = 2,
    normalizer: Normalizer | None = None,
) -> list[RelatedParty]:
    """BFS upward from the beneficiary, collecting owners/controllers to depth N.

    Edges point ``owner --relation--> company``, so "who is behind X" walks edges
    whose ``to_name`` resolves to X and follows them to ``from_name``.
    """
    normalizer = normalizer or Normalizer()
    start = _resolve_node(session, normalizer, beneficiary_name)
    if start is None:
        return []

    # incoming[company] -> [links whose to_name == company]
    incoming: dict[str, list[m.OwnershipLink]] = defaultdict(list)
    for link in session.scalars(
        select(m.OwnershipLink).where(m.OwnershipLink.is_active.is_(True))
    ):
        incoming[_norm(normalizer, link.to_name)].append(link)

    results: list[RelatedParty] = []
    visited: set[str] = {_norm(normalizer, start)}
    # queue carries the running ownership fraction down the chain (root = 100%).
    queue: deque[tuple[str, int, list[str], float | None]] = deque([(start, 0, [start], 1.0)])

    while queue:
        node, depth, path, cum = queue.popleft()
        if depth >= max_depth:
            continue
        for link in incoming.get(_norm(normalizer, node), []):
            owner_key = _norm(normalizer, link.from_name)
            if owner_key in visited:
                continue
            visited.add(owner_key)
            new_path = path + [link.from_name]
            new_cum, effective = _extend_cumulative(cum, link.ownership_pct)
            results.append(
                RelatedParty(
                    name=link.from_name,
                    relation=link.relation_type,
                    ownership_pct=link.ownership_pct,
                    depth=depth + 1,
                    entity_id=link.from_entity_id,
                    seeded_risk=link.seeded_risk,
                    path=new_path,
                    effective_pct=effective,
                )
            )
            queue.append((link.from_name, depth + 1, new_path, new_cum))

    return results


def trace_controlled_entities(
    session: Session,
    party_name: str,
    max_depth: int = 2,
    normalizer: Normalizer | None = None,
) -> list[ControlledEntity]:
    """BFS *downward* from a party: which companies does this party control?

    The reverse of :func:`trace_related_parties` — walks edges whose
    ``from_name`` resolves to the party and follows them to ``to_name``. Used to
    fan a single sanctioned/PEP hit out into the full set of exposed companies.
    """
    normalizer = normalizer or Normalizer()
    start = _resolve_node(session, normalizer, party_name)
    if start is None:
        return []

    # outgoing[party] -> [links whose from_name == party]
    outgoing: dict[str, list[m.OwnershipLink]] = defaultdict(list)
    for link in session.scalars(
        select(m.OwnershipLink).where(m.OwnershipLink.is_active.is_(True))
    ):
        outgoing[_norm(normalizer, link.from_name)].append(link)

    results: list[ControlledEntity] = []
    visited: set[str] = {_norm(normalizer, start)}
    queue: deque[tuple[str, int, list[str], float | None]] = deque([(start, 0, [start], 1.0)])

    while queue:
        node, depth, path, cum = queue.popleft()
        if depth >= max_depth:
            continue
        for link in outgoing.get(_norm(normalizer, node), []):
            company_key = _norm(normalizer, link.to_name)
            if company_key in visited:
                continue
            visited.add(company_key)
            new_path = path + [link.to_name]
            new_cum, effective = _extend_cumulative(cum, link.ownership_pct)
            results.append(
                ControlledEntity(
                    name=link.to_name,
                    relation=link.relation_type,
                    ownership_pct=link.ownership_pct,
                    depth=depth + 1,
                    path=new_path,
                    effective_pct=effective,
                )
            )
            queue.append((link.to_name, depth + 1, new_path, new_cum))

    return results


# --------------------------------------------------------------------------- #
# Risk assessment
# --------------------------------------------------------------------------- #
class OwnershipRiskEngine:
    """Assesses ownership-graph exposure for a payment beneficiary (Layer C).

    Pass a :class:`ScreeningEngine` to enable live re-screening of related
    parties; omit it (``engine=None``) to rely purely on ``seeded_risk`` records.
    """

    def __init__(self, session_factory, engine: ScreeningEngine | None = None) -> None:
        self._session_factory = session_factory
        self._engine = engine
        self._normalizer = Normalizer()

    def assess(self, beneficiary_name: str, max_depth: int = 2, persist: bool = False) -> dict:
        start = time.perf_counter()
        with self._session_factory() as session:
            parties = trace_related_parties(
                session, beneficiary_name, max_depth, self._normalizer
            )

        findings = [f for p in parties if (f := self._assess_party(p)) is not None]
        duration_ms = int((time.perf_counter() - start) * 1000)
        result = self._build_result(beneficiary_name, parties, findings, duration_ms)
        if persist:
            result["assessment_id"] = self._persist(result)
        return result

    def exposure(self, party_name: str, max_depth: int = 2) -> dict:
        """Reverse lookup: every company a (typically risky) party stands behind."""
        with self._session_factory() as session:
            controlled = trace_controlled_entities(
                session, party_name, max_depth, self._normalizer
            )
        return {
            "party": party_name,
            "controls_count": len(controlled),
            "controls": [
                {
                    "company": c.name,
                    "path": c.path,
                    "relation": c.relation,
                    "ownership_pct": c.ownership_pct,
                    "effective_pct": c.effective_pct,
                    "depth": c.depth,
                    "is_ubo": (c.effective_pct if c.effective_pct is not None else c.ownership_pct or 0.0)
                    >= UBO_PCT,
                }
                for c in controlled
            ],
        }

    def _persist(self, result: dict) -> int:
        with self._session_factory() as session:
            row = m.OwnershipAssessment(
                beneficiary_name=result["beneficiary"],
                verdict=result["verdict"],
                score=result["score"],
                reason=result["reason"],
                related_parties_traced=result["related_parties_traced"],
                duration_ms=result["duration_ms"],
                paths=result["paths"],
                graph=result["graph"],
            )
            session.add(row)
            session.commit()
            return row.id

    # -- per-party hybrid risk ------------------------------------------------
    def _assess_party(self, party: RelatedParty) -> OwnershipFinding | None:
        risk = matched_via = source = None
        confidence: float | None = None

        if self._engine is not None:
            sr = self._engine.screen(party.name)
            if sr.verdict != "NO_MATCH" and sr.candidates:
                top = sr.candidates[0]
                confidence = sr.confidence
                if top.entity_profile.list_type == "sanctions":
                    risk = "SANCTIONS_MATCH" if sr.verdict == "MATCH" else "SANCTIONS_REVIEW"
                else:  # pep
                    risk = "PEP_MATCH"
                matched_via = "live_screen"
                source = top.entity_profile.source_list_code

        if risk is None and party.seeded_risk:
            risk = party.seeded_risk.get("risk")
            source = party.seeded_risk.get("source")
            confidence = party.seeded_risk.get("confidence")
            matched_via = "seeded"

        if risk is None:
            return None

        return OwnershipFinding(
            party=party,
            risk=risk,
            matched_via=matched_via or "seeded",
            source=source or "unknown",
            screen_confidence=confidence,
            score=self._score(risk, party),
        )

    @staticmethod
    def _judging_pct(party: RelatedParty) -> float:
        """Stake used for UBO / scoring: cumulative stake in the beneficiary when known."""
        if party.effective_pct is not None:
            return party.effective_pct
        return party.ownership_pct if party.ownership_pct is not None else 0.0

    @staticmethod
    def _score(risk: str, party: RelatedParty) -> float:
        base = RISK_BASE.get(risk, 0.0)
        depth_factor = 1.0 if party.depth <= 1 else 0.7
        pct_factor = 1.0 if OwnershipRiskEngine._judging_pct(party) >= UBO_PCT else 0.6
        return round(base * depth_factor * pct_factor, 1)

    # -- compose the Layer-C result ------------------------------------------
    def _build_result(
        self,
        beneficiary_name: str,
        parties: list[RelatedParty],
        findings: list[OwnershipFinding],
        duration_ms: int,
    ) -> dict:
        verdict = self._verdict(findings)
        score = max((f.score for f in findings), default=0.0)
        return {
            "beneficiary": beneficiary_name,
            "verdict": verdict,
            "score": score,
            "reason": self._reason(findings, verdict),
            "paths": [self._path_payload(f) for f in findings],
            "graph": self._build_graph(beneficiary_name, parties, findings),
            "related_parties_traced": len(parties),
            "duration_ms": duration_ms,
        }

    @staticmethod
    def _verdict(findings: list[OwnershipFinding]) -> str:
        if not findings:
            return "NO_MATCH"
        # A direct (depth-1) high-confidence sanctioned owner blocks the payment.
        for f in findings:
            if (
                f.risk == "SANCTIONS_MATCH"
                and f.party.depth <= 1
                and (f.screen_confidence if f.screen_confidence is not None else 1.0) >= 0.85
            ):
                return "MATCH"
        # Any PEP, indirect sanctions, or deeper exposure is a review, not a block.
        return "REVIEW"

    @staticmethod
    def _reason(findings: list[OwnershipFinding], verdict: str) -> str:
        if not findings:
            return "No related-party risk found in the ownership graph."
        top = max(findings, key=lambda f: f.score)
        kind = {
            "SANCTIONS_MATCH": "a sanctioned party",
            "SANCTIONS_REVIEW": "a possible sanctions match",
            "PEP_MATCH": "a politically exposed person",
        }.get(top.risk, "a high-risk party")
        seeded = " (seeded KYB record)" if top.matched_via == "seeded" else ""
        if top.party.effective_pct is not None and top.party.depth > 1:
            stake = (
                f"effectively {top.party.effective_pct:.0f}% owned "
                f"(through a {top.party.depth}-hop chain)"
            )
        elif top.party.ownership_pct is not None:
            stake = f"{top.party.ownership_pct:.0f}% owned"
        else:
            stake = "controlled (undisclosed stake)"
        return f"Beneficiary is {stake} by {top.party.name}, {kind}{seeded}."

    @staticmethod
    def _path_payload(f: OwnershipFinding) -> dict:
        return {
            "path": f.party.path,
            "relation": f.party.relation,
            "ownership_pct": f.party.ownership_pct,
            "effective_pct": f.party.effective_pct,
            "depth": f.party.depth,
            "is_ubo": OwnershipRiskEngine._judging_pct(f.party) >= UBO_PCT,
            "risk": f.risk,
            "score": f.score,
            "matched_via": f.matched_via,
            "source": f.source,
            "screen_confidence": f.screen_confidence,
            "explanation": OwnershipRiskEngine._path_explanation(f),
        }

    @staticmethod
    def _path_explanation(f: OwnershipFinding) -> str:
        """Analyst-grade narrative for one risky ownership path (mirrors RuleHit.explanation)."""
        chain = " -> ".join(f.party.path)
        pct = (
            f"a {f.party.ownership_pct:.0f}% stake"
            if f.party.ownership_pct is not None
            else "an undisclosed stake"
        )
        kind = {
            "SANCTIONS_MATCH": "a sanctioned party",
            "SANCTIONS_REVIEW": "a possible sanctions match",
            "PEP_MATCH": "a politically exposed person (PEP)",
        }.get(f.risk, "a high-risk party")
        if f.matched_via == "live_screen":
            via = f"a live name screen against {f.source}"
            conf = (
                f" at {f.screen_confidence:.0%} confidence"
                if f.screen_confidence is not None
                else ""
            )
        else:
            via = f"a seeded KYB record from {f.source}"
            conf = ""
        effective = (
            f" That is an effective {f.party.effective_pct:.0f}% beneficial stake "
            f"in the beneficiary across {f.party.depth} hops."
            if f.party.effective_pct is not None and f.party.depth > 1
            else ""
        )
        return (
            f"Ownership chain {chain}: {f.party.name} holds {pct} in the "
            f"{f.party.relation.replace('_', ' ')} role at depth {f.party.depth} "
            f"and was flagged as {kind} via {via}{conf}.{effective} Because this risk "
            f"sits behind the beneficiary rather than on its own name, direct name "
            f"screening of the beneficiary would not surface it."
        )

    @staticmethod
    def _build_graph(
        beneficiary_name: str,
        parties: list[RelatedParty],
        findings: list[OwnershipFinding],
    ) -> dict:
        """Node/edge payload for frontend visualization of the ownership tree.

        Empty when nothing was traced — a lone beneficiary node is not worth drawing.
        """
        if not parties:
            return {"nodes": [], "edges": []}

        risk_by_name = {f.party.name: f for f in findings}
        effective_by_name = {p.name: p.effective_pct for p in parties}
        nodes: dict[str, dict] = {}

        def add_node(name: str, depth: int) -> None:
            if name in nodes:
                return
            f = risk_by_name.get(name)
            nodes[name] = {
                "id": name,
                "name": name,
                "depth": depth,
                "risk": f.risk if f else None,
                "is_flagged": f is not None,
                "effective_pct": effective_by_name.get(name),  # cumulative stake in the beneficiary
            }

        root = parties[0].path[0] if parties else beneficiary_name
        add_node(root, 0)  # the beneficiary being paid

        edges: list[dict] = []
        for p in parties:
            add_node(p.name, p.depth)
            # Edge direction matches storage: owner --relation--> company it owns.
            edges.append(
                {
                    "from": p.name,
                    "to": p.path[-2],
                    "relation": p.relation,
                    "ownership_pct": p.ownership_pct,
                }
            )

        return {"nodes": list(nodes.values()), "edges": edges}

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    JSON,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceList(Base):
    __tablename__ = "source_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    list_type: Mapped[str] = mapped_column(String(32))  # "sanctions" | "pep" | "adverse_media" | ...
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    entities: Mapped[list["Entity"]] = relationship(back_populates="source_list")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("source_list_id", "source_uid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_list_id: Mapped[int] = mapped_column(ForeignKey("source_lists.id"))
    source_uid: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))  # "individual" | "entity" | "vessel" | "aircraft"
    primary_name: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    raw: Mapped[dict] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source_list: Mapped[SourceList] = relationship(back_populates="entities")
    names: Mapped[list["EntityName"]] = relationship(back_populates="entity", cascade="all, delete-orphan")
    addresses: Mapped[list["EntityAddress"]] = relationship(back_populates="entity", cascade="all, delete-orphan")
    identifications: Mapped[list["EntityIdentification"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    programs: Mapped[list["EntityProgram"]] = relationship(back_populates="entity", cascade="all, delete-orphan")
    dates_of_birth: Mapped[list["EntityDateOfBirth"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    nationalities: Mapped[list["EntityNationality"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EntityName(Base):
    __tablename__ = "entity_names"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    name_type: Mapped[str] = mapped_column(String(16))  # "primary" | "aka" | "fka" | "nka"
    quality: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "strong" | "weak"
    full_name: Mapped[str] = mapped_column(Text, index=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity: Mapped[Entity] = relationship(back_populates="names")


class EntityAddress(Base):
    __tablename__ = "entity_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    address_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_province: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity: Mapped[Entity] = relationship(back_populates="addresses")


class EntityIdentification(Base):
    """Passports, national IDs, tax IDs, and OFAC digital-currency wallet addresses."""

    __tablename__ = "entity_identifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    id_type: Mapped[str] = mapped_column(Text)  # e.g. "Passport", "Digital Currency Address - XBT"
    id_number: Mapped[str] = mapped_column(Text, index=True)
    id_country: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity: Mapped[Entity] = relationship(back_populates="identifications")


class EntityProgram(Base):
    __tablename__ = "entity_programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    program_code: Mapped[str] = mapped_column(String(64))

    entity: Mapped[Entity] = relationship(back_populates="programs")


class EntityDateOfBirth(Base):
    __tablename__ = "entity_dates_of_birth"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    date_of_birth: Mapped[str] = mapped_column(String(64))  # kept as text: OFAC gives ranges/partial dates

    entity: Mapped[Entity] = relationship(back_populates="dates_of_birth")


class EntityNationality(Base):
    __tablename__ = "entity_nationalities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    relation: Mapped[str] = mapped_column(String(16))  # "nationality" | "citizenship" | "place_of_birth"
    country: Mapped[str] = mapped_column(Text)

    entity: Mapped[Entity] = relationship(back_populates="nationalities")


class EntityTransaction(Base):
    """A single ledger movement for an entity (client).

    ``direction`` is ``"in"`` or ``"out"`` from the entity's perspective.
    ``counterparty_country`` is an ISO-3166 alpha-2 code when known.
    """

    __tablename__ = "entity_transactions"
    __table_args__ = (
        Index("ix_entity_transactions_entity_occurred", "entity_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)

    external_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    direction: Mapped[str] = mapped_column(String(4))  # "in" | "out"
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)  # wire | card | ach | cash | crypto

    counterparty_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    counterparty_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    counterparty_account_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    counterparty_country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    initiated_from_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    entity_registered_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    usual_operating_countries: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | cleared | flagged
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    entity: Mapped["Entity"] = relationship()


# --------------------------------------------------------------------------- #
# Decisions produced by the detection engine
# --------------------------------------------------------------------------- #
class TransactionDecision(Base):
    __tablename__ = "transaction_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("entity_transactions.id"), unique=True, index=True
    )
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)

    score: Mapped[float] = mapped_column(Float, default=0.0)
    outcome: Mapped[str] = mapped_column(String(24))  # approve | review | decline | block_and_review
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)

    transaction: Mapped[EntityTransaction] = relationship()
    hits: Mapped[list["TransactionRuleHit"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )


class TransactionRuleHit(Base):
    __tablename__ = "transaction_rule_hits"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("transaction_decisions.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))  # low | medium | high | critical
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text)  # short, machine-style summary
    explanation: Mapped[str] = mapped_column(Text)  # human-readable narrative for analysts
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    decision: Mapped[TransactionDecision] = relationship(back_populates="hits")


# --------------------------------------------------------------------------- #
# KYB / beneficial-ownership graph (Layer C)
# --------------------------------------------------------------------------- #
class OwnershipLink(Base):
    """A single directed ownership/control edge: ``from_party --relation--> to_party``.

    Example: ``Ivan Petrov --beneficial_owner(35%)--> Blue Horizon Trading LLC``.
    Owners frequently are NOT themselves watchlist entities, so the
    ``*_entity_id`` columns are nullable and the ``*_name`` columns are the
    authoritative key used for re-screening and graph resolution. ``seeded_risk``
    carries a demo/manual-KYB fallback risk used when a live name screen misses.
    """

    __tablename__ = "ownership_links"
    __table_args__ = (
        Index("ix_ownership_links_to_name", "to_name"),
        Index("ix_ownership_links_from_name", "from_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    from_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    from_name: Mapped[str] = mapped_column(Text)
    to_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    to_name: Mapped[str] = mapped_column(Text)

    # owner | beneficial_owner | director | ubo | parent_company | subsidiary | intermediary
    relation_type: Mapped[str] = mapped_column(String(32))
    ownership_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64))  # demo_registry | companies_house_fixture | manual_kyb
    seeded_risk: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"risk": "PEP_MATCH", "source": "...", "confidence": 0.0}

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OwnershipAssessment(Base):
    """Persisted Layer-C result for one beneficiary — the audit record of a trace.

    Mirrors how ``TransactionDecision`` captures a behavioral run, so an analyst
    can defend why a payment was reviewed years later. ``paths`` and ``graph``
    store the full evidence payload returned by the ownership engine.
    """

    __tablename__ = "ownership_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    beneficiary_name: Mapped[str] = mapped_column(Text, index=True)
    verdict: Mapped[str] = mapped_column(String(16))  # MATCH | REVIEW | NO_MATCH
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text)
    related_parties_traced: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int] = mapped_column(default=0)
    paths: Mapped[list] = mapped_column(JSON)
    graph: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

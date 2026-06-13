from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
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

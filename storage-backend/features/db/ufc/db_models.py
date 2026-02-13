"""SQLAlchemy ORM models for the UFC feature package."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base


class Fighter(Base):
    """Represent a UFC fighter record harvested from the legacy service."""

    __tablename__ = "fighters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ufc_url: Mapped[str] = mapped_column("ufcUrl", String(500), nullable=False, unique=True)
    fighter_full_body_img_url: Mapped[str] = mapped_column("fighterFullBodyImgUrl", String(500), nullable=False)
    fighter_headshot_img_url: Mapped[str] = mapped_column("fighterHeadshotImgUrl", String(500), nullable=False)
    weight_class: Mapped[str] = mapped_column("weightClass", String(50), nullable=False, index=True)
    record: Mapped[str] = mapped_column(String(20), nullable=False)
    sherdog_record: Mapped[str] = mapped_column("sherdogRecord", String(20), nullable=False)
    next_fight_date: Mapped[datetime | None] = mapped_column("nextFightDate", DateTime(timezone=True), nullable=True)
    next_fight_opponent: Mapped[str | None] = mapped_column("nextFightOpponent", String(100), nullable=True)
    next_fight_opponent_record: Mapped[str | None] = mapped_column("nextFightOpponentRecord", String(20), nullable=True)
    opponent_headshot_url: Mapped[str | None] = mapped_column("opponentHeadshotUrl", String(500), nullable=True)
    opponent_ufc_url: Mapped[str | None] = mapped_column("opponentUfcUrl", String(500), nullable=True)
    tags: Mapped[str] = mapped_column(
        String(400), nullable=False, default="[]", server_default=text("'[]'")
    )
    tags_dwcs: Mapped[str | None] = mapped_column("tagsDwcs", String(40), nullable=True)
    height: Mapped[str | None] = mapped_column(String(10), nullable=True)
    weight: Mapped[str | None] = mapped_column(String(10), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rumour_next_fight_date: Mapped[datetime | None] = mapped_column("rumourNextFightDate", DateTime(timezone=True), nullable=True)
    rumour_next_fight_opponent: Mapped[str | None] = mapped_column("rumourNextFightOpponent", String(100), nullable=True)
    rumour_next_fight_opponent_record: Mapped[str | None] = mapped_column("rumourNextFightOpponentRecord", String(20), nullable=True)
    rumour_next_fight_opponent_img_url: Mapped[str | None] = mapped_column("rumourNextFightOpponentImgUrl", String(500), nullable=True)
    rumour_opponent_ufc_url: Mapped[str | None] = mapped_column("rumourOpponentUfcUrl", String(500), nullable=True)
    description: Mapped[str | None] = mapped_column("mydesc", Text, nullable=True)
    twitter: Mapped[str | None] = mapped_column(String(500), nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sherdog: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tapology: Mapped[str | None] = mapped_column(String(500), nullable=True)

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription",
        back_populates="fighter",
        cascade="all, delete-orphan",
    )


class Person(Base):
    """Registered UFC automation user."""

    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_name: Mapped[str] = mapped_column("accountName", String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    lang: Mapped[str] = mapped_column(
        String(5), nullable=False, default="en", server_default=text("'en'")
    )
    total_generations: Mapped[int] = mapped_column(
        "totalGenerations", Integer, nullable=False, default=0, server_default=text("'0'")
    )
    photo: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="default_photo.png",
        server_default=text("'default_photo.png'"),
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription",
        back_populates="person",
        cascade="all, delete-orphan",
    )


class Subscription(Base):
    """Association table between :class:`Person` entries and followed fighters."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column("personId", ForeignKey("people.id"), nullable=False, index=True)
    fighter_id: Mapped[int] = mapped_column("fighterId", ForeignKey("fighters.id"), nullable=False, index=True)

    person: Mapped[Person] = relationship("Person", back_populates="subscriptions")
    fighter: Mapped[Fighter] = relationship("Fighter", back_populates="subscriptions")


__all__ = ["Fighter", "Person", "Subscription"]

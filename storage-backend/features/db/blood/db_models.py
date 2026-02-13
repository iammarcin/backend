"""SQLAlchemy ORM models for the Blood domain tables."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base


class TestDefinition(Base):
    """Reference information describing each supported blood test."""

    __tablename__ = "test_definitions"
    __test__ = False  # Prevent pytest from treating this ORM model as a test case

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    test_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    short_explanation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    long_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    blood_tests: Mapped[list["BloodTest"]] = relationship(
        back_populates="test_definition",
        cascade="all, delete-orphan",
    )


class BloodTest(Base):
    """Recorded blood test values linked to ``TestDefinition`` metadata."""

    __tablename__ = "blood_tests"
    __test__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_date: Mapped[date] = mapped_column(Date, nullable=False)
    test_definition_id: Mapped[int] = mapped_column(
        ForeignKey("test_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    result_value: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_range: Mapped[str | None] = mapped_column(String(100), nullable=True)

    test_definition: Mapped[TestDefinition] = relationship(
        back_populates="blood_tests",
        lazy="selectin",
    )


__all__ = ["BloodTest", "TestDefinition"]

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Variant(Base):
    __tablename__ = "variants"

    __table_args__ = (
        UniqueConstraint(
            "experiment_id",
            "name",
            name="uq_variant_experiment_name",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "experiments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    is_control: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    experiment: Mapped["Experiment"] = relationship(
        back_populates="variants",
    )

    observations: Mapped[list["Observation"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Observation(Base):
    __tablename__ = "observations"

    __table_args__ = (
        UniqueConstraint(
            "variant_id",
            "observed_on",
            name="uq_observation_variant_date",
        ),
        CheckConstraint(
            "impressions >= 0",
            name="ck_observation_impressions_non_negative",
        ),
        CheckConstraint(
            "clicks >= 0",
            name="ck_observation_clicks_non_negative",
        ),
        CheckConstraint(
            "clicks <= impressions",
            name="ck_observation_clicks_not_above_impressions",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    variant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "variants.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    observed_on: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    impressions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    clicks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    variant: Mapped["Variant"] = relationship(
        back_populates="observations",
    )

    @property
    def non_clicks(self) -> int:
        return self.impressions - self.clicks

    @property
    def ctr(self) -> float:
        if self.impressions == 0:
            return 0.0

        return self.clicks / self.impressions
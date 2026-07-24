from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bandits import (
    ThompsonSampling,
    VariantAllocation,
    VariantPerformance,
)
from src.config import settings
from src.core.database import get_database_session
from src.core.logging import get_logger
from src.models import Experiment, Observation, Variant


router = APIRouter()
logger = get_logger(__name__)


# -- Response schemas
class VariantAllocationResponse(BaseModel):
    variant_id: str
    name: str
    is_control: bool
    impressions: int
    clicks: int
    ctr: float
    probability_best: float
    allocation: float
    allocation_percentage: float


class AllocationResponse(BaseModel):
    experiment_id: str
    algorithm: str
    allocation_date: date
    variants: list[VariantAllocationResponse]


def _round_percentages_to_total(
    allocations: list[VariantAllocation],
    precision: int,
) -> dict[str, float]:
    """
    Round percentages while preserving an exact total of 100.

    Rounding each value independently can produce totals such as 99.99 for
    three equal variants. This uses the largest-remainder method: first round
    every value down to the requested precision, then distribute the remaining
    units to the variants with the largest discarded fractions.
    """
    if not allocations:
        return {}

    scale = Decimal(10) ** precision
    target_units = int(Decimal(100) * scale)

    exact_units = [
        Decimal(str(item.allocation))
        * Decimal(100)
        * scale
        for item in allocations
    ]

    rounded_units = [
        int(value.to_integral_value(rounding=ROUND_FLOOR))
        for value in exact_units
    ]

    units_to_distribute = (
        target_units - sum(rounded_units)
    )

    remainders = [
        value - Decimal(base)
        for value, base in zip(
            exact_units,
            rounded_units,
            strict=True,
        )
    ]

    # Allocate one smallest display unit at a time to the values that lost the
    # most during flooring. This keeps the final result as close as possible to
    # the original allocation while guaranteeing an exact 100% total.
    ranked_indexes = sorted(
        range(len(allocations)),
        key=lambda index: remainders[index],
        reverse=True,
    )

    for index in ranked_indexes[:units_to_distribute]:
        rounded_units[index] += 1

    return {
        item.variant_id: float(
            Decimal(units) / scale
        )
        for item, units in zip(
            allocations,
            rounded_units,
            strict=True,
        )
    }


@router.get(
    "/{experiment_id}/allocation",
    response_model=AllocationResponse,
    summary="Calculate the next traffic allocation",
)
async def get_allocation(
    experiment_id: str,
    session: AsyncSession = Depends(get_database_session),
) -> AllocationResponse:
    experiment_query = select(Experiment).where(
        Experiment.id == experiment_id
    )

    experiment_result = await session.execute(
        experiment_query
    )

    experiment = experiment_result.scalar_one_or_none()

    if experiment is None:
        logger.warning(
            "Cannot calculate allocation because experiment %s was not found",
            experiment_id,
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found.",
        )

    aggregation_query = (
        select(
            Variant.id.label("variant_id"),
            Variant.name.label("name"),
            Variant.is_control.label("is_control"),
            func.coalesce(
                func.sum(Observation.impressions),
                0,
            ).label("impressions"),
            func.coalesce(
                func.sum(Observation.clicks),
                0,
            ).label("clicks"),
        )
        .outerjoin(
            Observation,
            Observation.variant_id == Variant.id,
        )
        .where(
            Variant.experiment_id == experiment_id
        )
        .group_by(
            Variant.id,
            Variant.name,
            Variant.is_control,
        )
        .order_by(
            Variant.is_control.desc(),
            Variant.created_at.asc(),
        )
    )

    aggregation_result = await session.execute(
        aggregation_query
    )

    rows = aggregation_result.all()

    if not rows:
        logger.warning(
            "Cannot calculate allocation because experiment %s has no variants",
            experiment_id,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The experiment does not have any variants.",
        )

    settings.allocation.validate_for_variant_count(
        len(rows)
    )

    performances = [
        VariantPerformance(
            variant_id=row.variant_id,
            name=row.name,
            impressions=int(row.impressions),
            clicks=int(row.clicks),
        )
        for row in rows
    ]

    logger.info(
        "Calculating allocation for experiment %s using %s variants",
        experiment_id,
        len(performances),
    )

    algorithm = ThompsonSampling(
        simulations=settings.thompson_sampling.simulations,
        minimum_allocation=(
            settings.allocation.minimum_allocation
        ),
        prior_alpha=(
            settings.thompson_sampling.prior_alpha
        ),
        prior_beta=(
            settings.thompson_sampling.prior_beta
        ),
        random_seed=(
            settings.thompson_sampling.random_seed
        ),
    )

    allocations = algorithm.calculate(
        performances
    )

    allocation_by_variant_id = {
        allocation.variant_id: allocation
        for allocation in allocations
    }

    precision = (
        settings.allocation.percentage_precision
    )

    # Display percentages are rounded as a group rather than independently so
    # consumers always receive values that total exactly 100 at the configured
    # precision.
    rounded_percentages = _round_percentages_to_total(
        allocations=allocations,
        precision=precision,
    )

    response_variants: list[
        VariantAllocationResponse
    ] = []

    for row in rows:
        impressions = int(row.impressions)
        clicks = int(row.clicks)

        ctr = (
            clicks / impressions
            if impressions > 0
            else 0.0
        )

        allocation = allocation_by_variant_id[
            row.variant_id
        ]

        response_variants.append(
            VariantAllocationResponse(
                variant_id=row.variant_id,
                name=row.name,
                is_control=row.is_control,
                impressions=impressions,
                clicks=clicks,
                ctr=round(ctr, 6),
                probability_best=round(
                    allocation.probability_best,
                    6,
                ),
                allocation=round(
                    allocation.allocation,
                    6,
                ),
                allocation_percentage=(
                    rounded_percentages[
                        row.variant_id
                    ]
                ),
            )
        )

    allocation_date = (
        date.today() + timedelta(days=1)
    )

    logger.info(
        "Calculated %s allocation for experiment %s for %s: %s",
        algorithm.name,
        experiment_id,
        allocation_date,
        {
            variant.name: variant.allocation_percentage
            for variant in response_variants
        },
    )

    return AllocationResponse(
        experiment_id=experiment_id,
        algorithm=algorithm.name,
        allocation_date=allocation_date,
        variants=response_variants,
    )
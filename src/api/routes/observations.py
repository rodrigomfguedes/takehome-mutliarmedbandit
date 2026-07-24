from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_database_session
from src.core.logging import get_logger
from src.models import Experiment, Observation, Variant


router = APIRouter()
logger = get_logger(__name__)


# -- Request schemas
class VariantObservationInput(BaseModel):
    variant_id: str

    impressions: int = Field(
        ge=0,
    )

    clicks: int = Field(
        ge=0,
    )

    @model_validator(mode="after")
    def validate_clicks(self) -> "VariantObservationInput":
        if self.clicks > self.impressions:
            raise ValueError(
                "Clicks cannot exceed impressions."
            )

        return self


class ObservationBatchInput(BaseModel):
    observed_on: date
    results: list[VariantObservationInput] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_unique_variants(self) -> "ObservationBatchInput":
        variant_ids = [
            result.variant_id
            for result in self.results
        ]

        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError(
                "Each variant can only appear once per request."
            )

        return self


# -- Response schemas
class SavedObservationResponse(BaseModel):
    variant_id: str
    observed_on: date
    impressions: int
    clicks: int
    ctr: float


class ObservationBatchResponse(BaseModel):
    experiment_id: str
    observations: list[SavedObservationResponse]


@router.post(
    "/{experiment_id}/observations",
    response_model=ObservationBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update daily observations",
)
async def create_observations(
    experiment_id: str,
    payload: ObservationBatchInput,
    session: AsyncSession = Depends(get_database_session),
) -> ObservationBatchResponse:
    experiment_query = select(Experiment.id).where(
        Experiment.id == experiment_id
    )

    experiment_result = await session.execute(
        experiment_query
    )

    if experiment_result.scalar_one_or_none() is None:
        logger.warning(
            "Cannot save observations because experiment %s was not found",
            experiment_id,
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found.",
        )

    variants_query = select(Variant.id).where(
        Variant.experiment_id == experiment_id
    )

    variants_result = await session.execute(
        variants_query
    )

    experiment_variant_ids = set(
        variants_result.scalars().all()
    )

    submitted_variant_ids = {
        result.variant_id
        for result in payload.results
    }

    invalid_variant_ids = (
        submitted_variant_ids - experiment_variant_ids
    )

    if invalid_variant_ids:
        logger.warning(
            "Invalid variants submitted for experiment %s: %s",
            experiment_id,
            sorted(invalid_variant_ids),
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": (
                    "One or more variants do not belong "
                    "to this experiment."
                ),
                "invalid_variant_ids": sorted(
                    invalid_variant_ids
                ),
            },
        )

    saved_observations: list[SavedObservationResponse] = []

    for result in payload.results:
        statement = sqlite_insert(Observation).values(
            variant_id=result.variant_id,
            observed_on=payload.observed_on,
            impressions=result.impressions,
            clicks=result.clicks,
        )

        statement = statement.on_conflict_do_update(
            index_elements=[
                Observation.variant_id,
                Observation.observed_on,
            ],
            set_={
                "impressions": result.impressions,
                "clicks": result.clicks,
            },
        )

        await session.execute(statement)

        ctr = (
            result.clicks / result.impressions
            if result.impressions > 0
            else 0.0
        )

        saved_observations.append(
            SavedObservationResponse(
                variant_id=result.variant_id,
                observed_on=payload.observed_on,
                impressions=result.impressions,
                clicks=result.clicks,
                ctr=ctr,
            )
        )

    await session.commit()

    logger.info(
        "Saved %s observations for experiment %s on %s",
        len(saved_observations),
        experiment_id,
        payload.observed_on,
    )

    return ObservationBatchResponse(
        experiment_id=experiment_id,
        observations=saved_observations,
    )
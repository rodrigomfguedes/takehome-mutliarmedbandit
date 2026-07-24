from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_database_session
from src.core.logging import get_logger
from src.models import Experiment, Variant


router = APIRouter()
logger = get_logger(__name__)


# -- Request schemas
class VariantCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )
    is_control: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        # Pydantic's min_length validation runs before strip(), so a value
        # containing only spaces would otherwise pass validation.
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Variant name cannot be empty or contain only whitespace."
            )

        return normalized


class ExperimentCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    variants: list[VariantCreate] = Field(
        min_length=2,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Experiment name cannot be empty or contain only whitespace."
            )

        return normalized

    @model_validator(mode="after")
    def validate_variants(self) -> "ExperimentCreate":
        # Variant names have already been stripped by the field validator.
        # Case-insensitive comparison prevents names such as "Control" and
        # "control" from being created in the same experiment.
        normalized_names = [
            variant.name.casefold()
            for variant in self.variants
        ]

        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError(
                "Variant names must be unique within an experiment."
            )

        control_count = sum(
            variant.is_control
            for variant in self.variants
        )

        if control_count != 1:
            raise ValueError(
                "An experiment must have exactly one control variant."
            )

        return self


# -- Response schemas
class VariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    is_control: bool
    created_at: datetime


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    created_at: datetime
    variants: list[VariantResponse]


@router.post(
    "",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an experiment",
)
async def create_experiment(
    payload: ExperimentCreate,
    session: AsyncSession = Depends(get_database_session),
) -> ExperimentResponse:
    # Names are normalized by the request schemas, so there is no need to
    # strip them again at persistence time.
    experiment = Experiment(
        name=payload.name,
    )

    experiment.variants = [
        Variant(
            name=variant.name,
            is_control=variant.is_control,
        )
        for variant in payload.variants
    ]

    session.add(experiment)

    await session.commit()
    await session.refresh(experiment)

    logger.info(
        "Created experiment %s with %s variants",
        experiment.id,
        len(experiment.variants),
    )

    return ExperimentResponse.model_validate(experiment)


@router.get(
    "",
    response_model=list[ExperimentResponse],
    summary="List experiments",
)
async def list_experiments(
    session: AsyncSession = Depends(get_database_session),
) -> list[ExperimentResponse]:
    query = (
        select(Experiment)
        .options(selectinload(Experiment.variants))
        .order_by(Experiment.created_at.desc())
    )

    result = await session.execute(query)
    experiments = result.scalars().unique().all()

    return [
        ExperimentResponse.model_validate(experiment)
        for experiment in experiments
    ]


@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Get an experiment",
)
async def get_experiment(
    experiment_id: str,
    session: AsyncSession = Depends(get_database_session),
) -> ExperimentResponse:
    query = (
        select(Experiment)
        .options(selectinload(Experiment.variants))
        .where(Experiment.id == experiment_id)
    )

    result = await session.execute(query)
    experiment = result.scalar_one_or_none()

    if experiment is None:
        logger.warning(
            "Experiment %s was not found",
            experiment_id,
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found.",
        )

    return ExperimentResponse.model_validate(experiment)
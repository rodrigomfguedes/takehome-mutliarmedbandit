import pytest

from src.bandits.models import (
    VariantAllocation,
    VariantPerformance,
)


def test_variant_performance_calculates_ctr() -> None:
    # Keep the derived metrics on the domain model so every caller uses the
    # same CTR and non-click calculation instead of duplicating that logic.
    variant = VariantPerformance(
        variant_id="control",
        name="Control",
        impressions=1_000,
        clicks=100,
    )

    assert variant.ctr == pytest.approx(0.10)
    assert variant.non_clicks == 900


def test_variant_performance_returns_zero_ctr_without_impressions() -> None:
    # A variant with no traffic should return a safe numeric value rather than
    # raising a division-by-zero error. This also keeps API responses simple.
    variant = VariantPerformance(
        variant_id="control",
        name="Control",
        impressions=0,
        clicks=0,
    )

    assert variant.ctr == 0
    assert variant.non_clicks == 0


def test_variant_performance_rejects_negative_impressions() -> None:
    # Negative counts are not meaningful experiment data, so they should be
    # rejected at the domain boundary before reaching the bandit algorithm.
    with pytest.raises(
        ValueError,
        match="Impressions cannot be negative",
    ):
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=-1,
            clicks=0,
        )


def test_variant_performance_rejects_negative_clicks() -> None:
    # Keeping this validation in the model protects the algorithm even when
    # VariantPerformance is created outside the HTTP validation layer.
    with pytest.raises(
        ValueError,
        match="Clicks cannot be negative",
    ):
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=100,
            clicks=-1,
        )


def test_variant_performance_rejects_more_clicks_than_impressions() -> None:
    # Every click must correspond to an impression. Accepting a larger click
    # count would produce invalid failures and therefore an invalid Beta model.
    with pytest.raises(
        ValueError,
        match="Clicks cannot exceed impressions",
    ):
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=100,
            clicks=101,
        )


def test_variant_allocation_calculates_percentage() -> None:
    # Allocations are stored as proportions internally because that is easier
    # to compose mathematically. The percentage property is only a display view.
    allocation = VariantAllocation(
        variant_id="control",
        name="Control",
        allocation=0.25,
        probability_best=0.20,
    )

    assert allocation.percentage == pytest.approx(25.0)


@pytest.mark.parametrize(
    "allocation",
    [-0.01, 1.01],
)
def test_variant_allocation_rejects_invalid_values(
    allocation: float,
) -> None:
    # Traffic allocations must remain within the closed interval [0, 1].
    # Testing both sides protects against invalid negative and overflow values.
    with pytest.raises(
        ValueError,
        match="Allocation must be between 0 and 1",
    ):
        VariantAllocation(
            variant_id="control",
            name="Control",
            allocation=allocation,
            probability_best=0.5,
        )
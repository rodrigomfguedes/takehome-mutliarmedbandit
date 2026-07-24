import pytest

from src.bandits.constraints import (
    apply_minimum_allocation,
    normalize_allocations,
)
from src.bandits.models import VariantAllocation


def build_allocation(
    variant_id: str,
    allocation: float,
) -> VariantAllocation:
    """
    Build a lightweight allocation object for tests.

    Using the same value for allocation and probability_best keeps the
    individual test cases focused on the constraint being exercised.
    """
    return VariantAllocation(
        variant_id=variant_id,
        name=variant_id.title(),
        allocation=allocation,
        probability_best=allocation,
    )


def test_normalize_allocations_adds_up_to_one() -> None:
    # The input does not need to add up to one. Normalization should preserve
    # the relative weight of each variant while producing a valid distribution.
    allocations = [
        build_allocation("control", 0.20),
        build_allocation("variant", 0.30),
    ]

    normalized = normalize_allocations(allocations)

    assert sum(
        item.allocation
        for item in normalized
    ) == pytest.approx(1.0)

    assert normalized[0].allocation == pytest.approx(0.4)
    assert normalized[1].allocation == pytest.approx(0.6)


def test_zero_total_creates_equal_allocations() -> None:
    # A zero-total input does not contain enough information to favor any
    # variant, so the safest fallback is an equal traffic split.
    allocations = [
        build_allocation("control", 0),
        build_allocation("variant", 0),
    ]

    normalized = normalize_allocations(allocations)

    assert normalized[0].allocation == pytest.approx(0.5)
    assert normalized[1].allocation == pytest.approx(0.5)


def test_minimum_allocation_is_applied() -> None:
    allocations = [
        VariantAllocation(
            variant_id="control",
            name="Control",
            allocation=0.10,
            probability_best=0.10,
        ),
        VariantAllocation(
            variant_id="variant",
            name="Variant",
            allocation=0.90,
            probability_best=0.90,
        ),
    ]

    constrained = apply_minimum_allocation(
        allocations,
        minimum_allocation=0.05,
    )

    by_id = {
        item.variant_id: item
        for item in constrained
    }

    # Five percent is reserved for each variant. The remaining ninety percent
    # is then distributed according to the raw recommendation, which keeps
    # exploration alive without discarding the model's relative preference.
    assert by_id["control"].allocation == pytest.approx(0.14)
    assert by_id["variant"].allocation == pytest.approx(0.86)

    assert sum(
        item.allocation
        for item in constrained
    ) == pytest.approx(1.0)


def test_probability_best_is_not_changed_by_constraint() -> None:
    allocations = [
        VariantAllocation(
            variant_id="control",
            name="Control",
            allocation=0.01,
            probability_best=0.01,
        ),
        VariantAllocation(
            variant_id="variant",
            name="Variant",
            allocation=0.99,
            probability_best=0.99,
        ),
    ]

    constrained = apply_minimum_allocation(
        allocations,
        minimum_allocation=0.05,
    )

    by_id = {
        item.variant_id: item
        for item in constrained
    }

    # The minimum-allocation rule is a traffic policy, not a statistical
    # recalculation. The raw probability of being best must remain unchanged.
    assert by_id["control"].probability_best == pytest.approx(
        0.01
    )
    assert by_id["variant"].probability_best == pytest.approx(
        0.99
    )


def test_rejects_minimum_that_is_too_high() -> None:
    allocations = [
        build_allocation("a", 0.34),
        build_allocation("b", 0.33),
        build_allocation("c", 0.33),
    ]

    # Reserving forty percent for each of three variants would require more
    # than one hundred percent of the available traffic, so the configuration
    # must be rejected rather than silently adjusted.
    with pytest.raises(
        ValueError,
        match="too high",
    ):
        apply_minimum_allocation(
            allocations,
            minimum_allocation=0.40,
        )
from src.bandits.models import VariantAllocation


def apply_minimum_allocation(
    allocations: list[VariantAllocation],
    minimum_allocation: float,
) -> list[VariantAllocation]:
    """
    Guarantee a minimum traffic share for every variant.

    The minimum allocation is reserved first. The remaining traffic
    is distributed proportionally according to the raw allocation.
    """
    if not allocations:
        return []

    if not 0 <= minimum_allocation < 1:
        raise ValueError(
            "Minimum allocation must be between 0 and 1."
        )

    variant_count = len(allocations)

    if minimum_allocation * variant_count > 1:
        raise ValueError(
            "Minimum allocation is too high for the number "
            "of variants."
        )

    if minimum_allocation == 0:
        return normalize_allocations(allocations)

    reserved_traffic = minimum_allocation * variant_count
    remaining_traffic = 1 - reserved_traffic

    raw_total = sum(
        item.allocation
        for item in allocations
    )

    if raw_total <= 0:
        return create_equal_allocations(allocations)

    constrained = [
        VariantAllocation(
            variant_id=item.variant_id,
            name=item.name,
            allocation=(
                minimum_allocation
                + (item.allocation / raw_total)
                * remaining_traffic
            ),
            probability_best=item.probability_best,
        )
        for item in allocations
    ]

    return normalize_allocations(constrained)


def normalize_allocations(
    allocations: list[VariantAllocation],
) -> list[VariantAllocation]:
    """
    Normalize allocation values so their total equals exactly 1.
    """
    if not allocations:
        return []

    total = sum(
        item.allocation
        for item in allocations
    )

    if total <= 0:
        return create_equal_allocations(allocations)

    normalized = [
        VariantAllocation(
            variant_id=item.variant_id,
            name=item.name,
            allocation=item.allocation / total,
            probability_best=item.probability_best,
        )
        for item in allocations
    ]

    return correct_floating_point_difference(normalized)


def create_equal_allocations(
    allocations: list[VariantAllocation],
) -> list[VariantAllocation]:
    if not allocations:
        return []

    equal_allocation = 1 / len(allocations)

    return [
        VariantAllocation(
            variant_id=item.variant_id,
            name=item.name,
            allocation=equal_allocation,
            probability_best=item.probability_best,
        )
        for item in allocations
    ]


def correct_floating_point_difference(
    allocations: list[VariantAllocation],
) -> list[VariantAllocation]:
    """
    Correct small floating-point differences.

    Example:
        0.333333 + 0.333333 + 0.333333 may not equal exactly 1.
    """
    if not allocations:
        return []

    total = sum(
        item.allocation
        for item in allocations
    )

    difference = 1.0 - total

    if abs(difference) < 1e-12:
        return allocations

    largest_index = max(
        range(len(allocations)),
        key=lambda index: allocations[index].allocation,
    )

    corrected = list(allocations)
    largest = corrected[largest_index]

    corrected[largest_index] = VariantAllocation(
        variant_id=largest.variant_id,
        name=largest.name,
        allocation=largest.allocation + difference,
        probability_best=largest.probability_best,
    )

    return corrected
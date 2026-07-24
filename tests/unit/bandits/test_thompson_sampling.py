import pytest

from src.bandits import (
    ThompsonSampling,
    VariantPerformance,
)


def test_allocations_add_up_to_one() -> None:
    # Final traffic allocations must always form a valid distribution,
    # regardless of the raw probabilities produced by the simulations.
    algorithm = ThompsonSampling(
        simulations=10_000,
        minimum_allocation=0.05,
        random_seed=42,
    )

    variants = [
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=1_000,
            clicks=100,
        ),
        VariantPerformance(
            variant_id="variant",
            name="Variant",
            impressions=1_000,
            clicks=120,
        ),
    ]

    allocations = algorithm.calculate(variants)

    assert sum(
        item.allocation
        for item in allocations
    ) == pytest.approx(1.0)


def test_probabilities_add_up_to_one() -> None:
    # Each simulation produces exactly one winning variant, so the estimated
    # probabilities of being best should add up to one across all variants.
    algorithm = ThompsonSampling(
        simulations=10_000,
        minimum_allocation=0.05,
        random_seed=42,
    )

    variants = [
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=1_000,
            clicks=100,
        ),
        VariantPerformance(
            variant_id="variant",
            name="Variant",
            impressions=1_000,
            clicks=120,
        ),
    ]

    allocations = algorithm.calculate(variants)

    assert sum(
        item.probability_best
        for item in allocations
    ) == pytest.approx(1.0)


def test_better_variant_receives_more_traffic() -> None:
    # With the same number of impressions and a materially higher CTR, the
    # stronger variant should win more simulations and receive more traffic.
    algorithm = ThompsonSampling(
        simulations=10_000,
        minimum_allocation=0.05,
        random_seed=42,
    )

    variants = [
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=10_000,
            clicks=800,
        ),
        VariantPerformance(
            variant_id="variant",
            name="Variant",
            impressions=10_000,
            clicks=1_200,
        ),
    ]

    allocations = algorithm.calculate(variants)

    by_id = {
        item.variant_id: item
        for item in allocations
    }

    assert (
        by_id["variant"].probability_best
        > by_id["control"].probability_best
    )

    assert (
        by_id["variant"].allocation
        > by_id["control"].allocation
    )


def test_minimum_allocation_is_respected() -> None:
    # Even when one variant is clearly weaker, it should still receive the
    # configured exploration share instead of being removed completely.
    minimum = 0.05

    algorithm = ThompsonSampling(
        simulations=10_000,
        minimum_allocation=minimum,
        random_seed=42,
    )

    variants = [
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=100_000,
            clicks=1_000,
        ),
        VariantPerformance(
            variant_id="variant",
            name="Variant",
            impressions=100_000,
            clicks=20_000,
        ),
    ]

    allocations = algorithm.calculate(variants)

    assert all(
        item.allocation >= minimum
        for item in allocations
    )


def test_single_variant_receives_all_traffic() -> None:
    # There is no exploration decision to make when only one option exists,
    # so the algorithm can return immediately without running simulations.
    algorithm = ThompsonSampling(
        simulations=1_000,
        minimum_allocation=0.05,
        random_seed=42,
    )

    variants = [
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=100,
            clicks=10,
        )
    ]

    allocations = algorithm.calculate(variants)

    assert len(allocations) == 1
    assert allocations[0].allocation == 1.0
    assert allocations[0].probability_best == 1.0


def test_rejects_empty_variant_list() -> None:
    # An allocation cannot be calculated without at least one candidate.
    # Failing early also keeps downstream normalization logic simpler.
    algorithm = ThompsonSampling()

    with pytest.raises(
        ValueError,
        match="At least one variant",
    ):
        algorithm.calculate([])


def test_rejects_duplicate_variant_ids() -> None:
    # Variant IDs are used as dictionary keys while counting simulation wins.
    # Duplicates would merge distinct variants and silently corrupt the result.
    algorithm = ThompsonSampling()

    variants = [
        VariantPerformance(
            variant_id="same-id",
            name="Control",
            impressions=100,
            clicks=10,
        ),
        VariantPerformance(
            variant_id="same-id",
            name="Variant",
            impressions=100,
            clicks=12,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="Variant IDs must be unique",
    ):
        algorithm.calculate(variants)


def test_results_are_reproducible_with_fixed_seed() -> None:
    # A fixed seed makes stochastic behavior deterministic, which is useful
    # for tests and for reproducing unexpected allocation results.
    variants = [
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=1_000,
            clicks=100,
        ),
        VariantPerformance(
            variant_id="variant",
            name="Variant",
            impressions=1_000,
            clicks=110,
        ),
    ]

    first_algorithm = ThompsonSampling(
        simulations=5_000,
        minimum_allocation=0.05,
        random_seed=42,
    )

    second_algorithm = ThompsonSampling(
        simulations=5_000,
        minimum_allocation=0.05,
        random_seed=42,
    )

    first_result = first_algorithm.calculate(variants)
    second_result = second_algorithm.calculate(variants)

    assert first_result == second_result


def test_empty_variants_receive_approximately_equal_results() -> None:
    # With no observations, both variants have the same Beta(1, 1) prior.
    # Monte Carlo sampling will not be exactly 50/50, but it should be close.
    algorithm = ThompsonSampling(
        simulations=20_000,
        minimum_allocation=0,
        random_seed=42,
    )

    variants = [
        VariantPerformance(
            variant_id="control",
            name="Control",
            impressions=0,
            clicks=0,
        ),
        VariantPerformance(
            variant_id="variant",
            name="Variant",
            impressions=0,
            clicks=0,
        ),
    ]

    allocations = algorithm.calculate(variants)

    by_id = {
        item.variant_id: item
        for item in allocations
    }

    assert by_id["control"].probability_best == pytest.approx(
        0.5,
        abs=0.02,
    )

    assert by_id["variant"].probability_best == pytest.approx(
        0.5,
        abs=0.02,
    )
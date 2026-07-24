import random

from src.bandits.constraints import (
    apply_minimum_allocation,
    normalize_allocations,
)
from src.bandits.models import (
    VariantAllocation,
    VariantPerformance,
)


class ThompsonSampling:
    name = "thompson_sampling"

    def __init__(
        self,
        simulations: int = 10_000,
        minimum_allocation: float = 0.05,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
        random_seed: int | None = None,
    ) -> None:
        if simulations <= 0:
            raise ValueError(
                "Simulations must be greater than zero."
            )

        if prior_alpha <= 0:
            raise ValueError(
                "Prior alpha must be greater than zero."
            )

        if prior_beta <= 0:
            raise ValueError(
                "Prior beta must be greater than zero."
            )

        if not 0 <= minimum_allocation < 1:
            raise ValueError(
                "Minimum allocation must be between 0 and 1."
            )

        self.simulations = simulations
        self.minimum_allocation = minimum_allocation
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self._random = random.Random(random_seed)

    def calculate(
        self,
        variants: list[VariantPerformance],
    ) -> list[VariantAllocation]:
        self._validate_variants(variants)

        if len(variants) == 1:
            variant = variants[0]

            return [
                VariantAllocation(
                    variant_id=variant.variant_id,
                    name=variant.name,
                    allocation=1.0,
                    probability_best=1.0,
                )
            ]

        wins = {
            variant.variant_id: 0
            for variant in variants
        }

        for _ in range(self.simulations):
            winner_id = self._run_simulation(
                variants
            )

            wins[winner_id] += 1

        raw_allocations = [
            VariantAllocation(
                variant_id=variant.variant_id,
                name=variant.name,
                allocation=(
                    wins[variant.variant_id]
                    / self.simulations
                ),
                probability_best=(
                    wins[variant.variant_id]
                    / self.simulations
                ),
            )
            for variant in variants
        ]

        normalized = normalize_allocations(
            raw_allocations
        )

        return apply_minimum_allocation(
            allocations=normalized,
            minimum_allocation=self.minimum_allocation,
        )

    def _run_simulation(
        self,
        variants: list[VariantPerformance],
    ) -> str:
        sampled_values = {
            variant.variant_id: self._sample_variant(
                variant
            )
            for variant in variants
        }

        return max(
            sampled_values,
            key=sampled_values.get,
        )

    def _sample_variant(
        self,
        variant: VariantPerformance,
    ) -> float:
        alpha = (
            self.prior_alpha
            + variant.clicks
        )

        beta = (
            self.prior_beta
            + variant.non_clicks
        )

        return self._random.betavariate(
            alpha,
            beta,
        )

    def _validate_variants(
        self,
        variants: list[VariantPerformance],
    ) -> None:
        if not variants:
            raise ValueError(
                "At least one variant is required."
            )

        variant_ids = [
            variant.variant_id
            for variant in variants
        ]

        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError(
                "Variant IDs must be unique."
            )

        if (
            self.minimum_allocation
            * len(variants)
            > 1
        ):
            raise ValueError(
                "Minimum allocation is too high for the "
                "number of variants."
            )
from typing import Protocol

from src.bandits.models import (
    VariantAllocation,
    VariantPerformance,
)


class BanditStrategy(Protocol):
    @property
    def name(self) -> str:
        """Return the algorithm name."""
        ...

    def calculate(
        self,
        variants: list[VariantPerformance],
    ) -> list[VariantAllocation]:
        """Calculate recommended traffic allocations."""
        ...
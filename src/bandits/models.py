from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VariantPerformance:
    variant_id: str
    name: str
    impressions: int
    clicks: int

    def __post_init__(self) -> None:
        if not self.variant_id:
            raise ValueError("Variant ID cannot be empty.")

        if not self.name:
            raise ValueError("Variant name cannot be empty.")

        if self.impressions < 0:
            raise ValueError("Impressions cannot be negative.")

        if self.clicks < 0:
            raise ValueError("Clicks cannot be negative.")

        if self.clicks > self.impressions:
            raise ValueError("Clicks cannot exceed impressions.")

    @property
    def non_clicks(self) -> int:
        return self.impressions - self.clicks

    @property
    def ctr(self) -> float:
        if self.impressions == 0:
            return 0.0

        return self.clicks / self.impressions


@dataclass(frozen=True, slots=True)
class VariantAllocation:
    variant_id: str
    name: str
    allocation: float
    probability_best: float

    def __post_init__(self) -> None:
        if not self.variant_id:
            raise ValueError("Variant ID cannot be empty.")

        if not self.name:
            raise ValueError("Variant name cannot be empty.")

        if not 0 <= self.allocation <= 1:
            raise ValueError(
                "Allocation must be between 0 and 1."
            )

        if not 0 <= self.probability_best <= 1:
            raise ValueError(
                "Probability best must be between 0 and 1."
            )

    @property
    def percentage(self) -> float:
        return self.allocation * 100
"""Replaceable interface for image-based meal estimation providers."""

from dataclasses import dataclass
from typing import Protocol


class FoodProviderUnavailable(RuntimeError):
    """The configured provider cannot run; callers must not synthesize estimates."""


class FoodAnalysisError(RuntimeError):
    """An input image or provider output could not be analyzed safely."""


@dataclass(frozen=True)
class FoodAnalysisResult:
    provider: str
    provider_version: str
    model_version: str
    nutrition_source: str
    nutrition_source_version: str | None
    estimation_method: str
    recognition_confidence: float | None
    estimated_portion_grams: float
    nutrients: dict[str, float]
    raw_output: dict[str, float]


class FoodProvider(Protocol):
    def analyze(self, image: bytes) -> FoodAnalysisResult: ...

"""Provider abstraction for synthetic-only structured extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.schemas import ProviderMetadata, ProviderResult, SyntheticEmailRecord


class ModelConfigurationError(RuntimeError):
    """Raised for missing or unsafe provider configuration."""


class ModelExtractor(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        """Return non-secret provider and prompt configuration."""

    @abstractmethod
    def extract(self, record: SyntheticEmailRecord) -> ProviderResult:
        """Extract a validated structured prediction from one synthetic record."""

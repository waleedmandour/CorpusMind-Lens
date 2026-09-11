"""Shared API error types."""
from __future__ import annotations


class ConsentRequiredError(PermissionError):
    """Raised when a consent-gated capability is invoked while opted out."""


class CompanionUnavailableError(ConnectionError):
    """Raised when Companion Mode is off or no companion engine is reachable."""

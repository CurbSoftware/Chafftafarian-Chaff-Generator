"""Domain exception hierarchy for Chaff Generator.

Every error raised intentionally by the application derives from
:class:`ChaffError` so GUI and CLI layers can present a concise message
(and optional details) instead of a raw traceback.
"""

from __future__ import annotations

from typing import Any


class ChaffError(Exception):
    """Base class for all Chaff domain errors."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details: dict[str, Any] = details or {}


class ConfigurationError(ChaffError):
    """Invalid or contradictory job configuration."""


class InsufficientSpaceError(ChaffError):
    """The target filesystem cannot satisfy the requested generation."""


class UnsafePathError(ChaffError):
    """A path violated containment or sanitization rules."""


class TemplateError(ChaffError):
    """A template failed to validate, compile, or render."""


class RendererError(ChaffError):
    """A renderer failed to produce a valid file."""


class ManifestError(ChaffError):
    """A manifest or journal could not be written, read, or trusted."""


class VerificationError(ChaffError):
    """A verification run could not be performed."""


class CleanupSafetyError(ChaffError):
    """A cleanup operation was refused by the safety layer."""


class PackError(ChaffError):
    """A ChaffBank pack is missing, invalid, or untrusted."""

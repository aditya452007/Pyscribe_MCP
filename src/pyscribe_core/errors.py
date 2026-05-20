"""Custom exception hierarchy for PyScribe."""

from __future__ import annotations


class PyScribeError(Exception):
    """Base exception for all PyScribe errors."""

    def __init__(self, message: str, *, recoverable: bool = True) -> None:
        super().__init__(message)
        self.recoverable = recoverable


class ConfigError(PyScribeError):
    """Configuration parsing or validation error."""

    def __init__(self, message: str) -> None:
        super().__init__(message, recoverable=False)


class NetworkError(PyScribeError):
    """HTTP request or network failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RetryExhaustedError(NetworkError):
    """All retry attempts failed."""

    def __init__(self, message: str, *, last_exception: Exception | None = None) -> None:
        super().__init__(message)
        self.last_exception = last_exception


class SkillNotFoundError(PyScribeError):
    """Requested skill does not exist."""

    def __init__(self, skill_name: str, *, source: str | None = None) -> None:
        msg = f"Skill '{skill_name}' not found"
        if source:
            msg += f" in source '{source}'"
        super().__init__(msg, recoverable=False)


class LanguageDetectionError(PyScribeError):
    """Could not auto-detect project language."""

    def __init__(self, message: str) -> None:
        super().__init__(message, recoverable=False)

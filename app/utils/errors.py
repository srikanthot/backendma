"""Custom exception classes and HTTP error helpers.

Provides structured error handling so route handlers can raise meaningful
errors that translate to proper HTTP responses with clean user-facing messages
and detailed backend logs.
"""

import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)


class RetrievalError(Exception):
    """Raised when Azure AI Search retrieval fails."""

    def __init__(self, message: str = "Retrieval failed", detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class GenerationError(Exception):
    """Raised when Azure OpenAI generation fails."""

    def __init__(self, message: str = "Generation failed", detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class InsufficientEvidenceError(Exception):
    """Raised when retrieved evidence does not meet quality thresholds."""

    def __init__(
        self,
        message: str = "Insufficient evidence to answer confidently",
        n_results: int = 0,
        avg_score: float = 0.0,
    ):
        self.message = message
        self.n_results = n_results
        self.avg_score = avg_score
        super().__init__(self.message)


def raise_retrieval_error(exc: Exception) -> None:
    """Log and raise an HTTP 502 for retrieval failures."""
    logger.error("Retrieval error: %s", str(exc), exc_info=True)
    raise HTTPException(
        status_code=502,
        detail="An error occurred while searching the knowledge base. Please try again.",
    ) from exc


def raise_generation_error(exc: Exception) -> None:
    """Log and raise an HTTP 502 for generation failures."""
    logger.error("Generation error: %s", str(exc), exc_info=True)
    raise HTTPException(
        status_code=502,
        detail="An error occurred while generating the answer. Please try again.",
    ) from exc

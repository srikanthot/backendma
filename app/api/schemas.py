"""Pydantic request / response models for the chat API.

These models define the stable contract between this backend and any
future frontend (React, Power Apps, PCF, custom web UIs, mobile, etc.).

The shapes are intentionally simple and frontend-friendly.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat request body.

    Attributes
    ----------
    question:
        The user's question about technical manuals.
    session_id:
        Optional session identifier. Kept in the contract for future
        multi-turn support, but no history is persisted in this version.
    """

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's question about technical manuals.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional session ID. Pass-through only in this version — "
            "echoed back in the response for future multi-turn support. "
            "No conversation state is stored or restored."
        ),
    )


class Citation(BaseModel):
    """A single citation reference with structured metadata.

    Built directly from retrieval results, not from LLM formatting.
    """

    title: str = Field(default="", description="Document title.")
    source: str = Field(default="", description="Source document filename.")
    chunk_id: str = Field(default="", description="Unique chunk identifier.")
    section: str = Field(
        default="", description="Section breadcrumb (e.g., 'Chapter 3 > Safety')."
    )
    page: str = Field(default="", description="Page number if available.")


class ChatResponse(BaseModel):
    """Response from the /chat endpoint.

    Contains the grounded answer, structured citations, and session_id.
    """

    answer: str = Field(
        ..., description="The generated answer grounded in technical manual content."
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Structured citations from retrieved chunks.",
    )
    session_id: str = Field(
        default="",
        description=(
            "Session ID echoed back from the request. Pass-through only — "
            "no conversation state is stored in this version."
        ),
    )

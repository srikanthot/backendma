"""Data models for the retrieval pipeline.

These models define the canonical shapes for retrieval results flowing
through the system — from raw Azure AI Search documents through filtering
and ranking to final context assembly and citation generation.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RetrievalChunk:
    """A single retrieved chunk from Azure AI Search, normalized to a
    canonical schema used throughout the retrieval and context pipelines.

    All optional metadata fields default to empty strings so downstream
    code never needs to handle None for string fields.
    """

    content: str = ""
    title: str = ""
    source: str = ""
    url: str = ""
    chunk_id: str = ""
    page: str = ""
    section1: str = ""
    section2: str = ""
    section3: str = ""
    score: float = 0.0
    reranker_score: Optional[float] = None

    @property
    def effective_score(self) -> float:
        """Return the best available relevance score.

        When semantic reranker is active, reranker_score (0-4 scale) is used.
        Otherwise the base RRF/hybrid score (0.01-0.033 typical range) is used.
        """
        if self.reranker_score is not None:
            return self.reranker_score
        return self.score

    @property
    def section_path(self) -> str:
        """Build a readable section breadcrumb from header_1/2/3 fields."""
        parts = [self.section1, self.section2, self.section3]
        return " > ".join(p for p in parts if p)

    def to_dict(self) -> dict:
        """Convert to a plain dict for serialization."""
        return {
            "content": self.content,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "chunk_id": self.chunk_id,
            "page": self.page,
            "section1": self.section1,
            "section2": self.section2,
            "section3": self.section3,
            "section_path": self.section_path,
            "score": self.score,
            "reranker_score": self.reranker_score,
            "effective_score": self.effective_score,
        }


@dataclass
class RetrievalResult:
    """Container for the full result of a retrieval operation.

    Carries the final filtered chunks plus diagnostic metadata
    useful for logging and debugging retrieval quality.
    """

    chunks: list[RetrievalChunk] = field(default_factory=list)
    query_used: str = ""
    keyword_query_used: str = ""
    total_candidates: int = 0
    after_threshold_filter: int = 0
    after_dedup: int = 0
    after_diversity_filter: int = 0
    after_score_gap_filter: int = 0
    final_count: int = 0
    semantic_reranker_active: bool = False

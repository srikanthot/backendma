"""Post-retrieval ranking, filtering, and deduplication.

This module contains the logic that narrows a wide pool of retrieval
candidates down to a small, high-quality set of evidence chunks.

Improvement over the reference repo:
- Relevance threshold filtering (absolute cutoff before any other filtering)
- Content-based deduplication using Jaccard similarity
- Minimum content-length filter (removes stub/empty chunks)
- TOC / index page detection and removal
- Per-source diversity capping
- Score-gap filtering relative to the top chunk
- Detailed diagnostic logging at every stage

All thresholds are configurable via settings so retrieval quality can be
tuned without code changes.
"""

import logging
import re
from collections import defaultdict

from app.config.settings import (
    DEDUP_SIMILARITY_THRESHOLD,
    MAX_CHUNKS_PER_SOURCE,
    MIN_CHUNK_LENGTH,
    MIN_RERANKER_SCORE,
    MIN_RELEVANCE_SCORE,
    SCORE_GAP_RATIO,
    TRACE_MODE,
    USE_SEMANTIC_RERANKER,
)
from app.models.retrieval_models import RetrievalChunk
from app.utils.helpers import jaccard_similarity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TOC / index page detection
# ---------------------------------------------------------------------------
_TOC_PATTERNS = [
    re.compile(r"Table\s+of\s+Contents", re.IGNORECASE),
    re.compile(r"(\.\s*){5,}"),  # dot leaders: ". . . . . . 2-11"
    re.compile(r"^Index\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"(\.{3,}\s*\d+)", re.MULTILINE),  # "Section Name...........12"
]


def _is_toc_or_index(chunk: RetrievalChunk) -> bool:
    """Return True if this chunk looks like a Table of Contents or index page.

    These chunks rarely contain useful procedural content for technical
    manuals and tend to add noise to LLM context.
    """
    sample = chunk.content[:500]
    return any(p.search(sample) for p in _TOC_PATTERNS)


# ---------------------------------------------------------------------------
# Minimum content-length filter
# ---------------------------------------------------------------------------
def filter_by_content_length(chunks: list[RetrievalChunk]) -> list[RetrievalChunk]:
    """Remove chunks whose content is too short to be useful.

    Very short chunks (stubs, empty pages, metadata-only rows) waste
    context window space and rarely contribute useful evidence.
    """
    if MIN_CHUNK_LENGTH <= 0:
        return chunks

    filtered = [c for c in chunks if len(c.content.strip()) >= MIN_CHUNK_LENGTH]
    removed = len(chunks) - len(filtered)
    if TRACE_MODE and removed:
        logger.info(
            "FILTER | content_length: removed %d chunk(s) shorter than %d chars",
            removed,
            MIN_CHUNK_LENGTH,
        )
    return filtered


# ---------------------------------------------------------------------------
# Relevance threshold filter
# ---------------------------------------------------------------------------
def filter_by_relevance_threshold(
    chunks: list[RetrievalChunk],
) -> list[RetrievalChunk]:
    """Remove chunks below the configured minimum relevance threshold.

    Uses reranker_score when semantic reranker is active, otherwise uses
    the base hybrid/RRF score.

    This is the first quality gate — chunks that don't meet a minimum
    relevance bar are removed before any other filtering.
    """
    filtered = []
    for chunk in chunks:
        if USE_SEMANTIC_RERANKER and chunk.reranker_score is not None:
            if chunk.reranker_score >= MIN_RERANKER_SCORE:
                filtered.append(chunk)
            elif TRACE_MODE:
                logger.debug(
                    "FILTER | dropped chunk_id=%s reranker_score=%.4f < threshold=%.4f",
                    chunk.chunk_id,
                    chunk.reranker_score,
                    MIN_RERANKER_SCORE,
                )
        else:
            if chunk.score >= MIN_RELEVANCE_SCORE:
                filtered.append(chunk)
            elif TRACE_MODE:
                logger.debug(
                    "FILTER | dropped chunk_id=%s score=%.4f < threshold=%.4f",
                    chunk.chunk_id,
                    chunk.score,
                    MIN_RELEVANCE_SCORE,
                )

    if TRACE_MODE:
        logger.info(
            "FILTER | relevance_threshold: %d -> %d chunks",
            len(chunks),
            len(filtered),
        )
    return filtered


# ---------------------------------------------------------------------------
# TOC filter
# ---------------------------------------------------------------------------
def filter_toc_chunks(chunks: list[RetrievalChunk]) -> list[RetrievalChunk]:
    """Remove chunks that appear to be table of contents or index pages."""
    filtered = [c for c in chunks if not _is_toc_or_index(c)]
    removed = len(chunks) - len(filtered)
    if TRACE_MODE and removed:
        logger.info("FILTER | toc_filter: removed %d TOC/index chunk(s)", removed)
    return filtered


# ---------------------------------------------------------------------------
# Content deduplication
# ---------------------------------------------------------------------------
def deduplicate_chunks(chunks: list[RetrievalChunk]) -> list[RetrievalChunk]:
    """Remove near-duplicate chunks based on content similarity.

    Uses Jaccard word-token similarity to detect overlapping chunks that
    would waste context window space without adding new information.

    Chunks are processed in score order (highest first), so when a duplicate
    pair is found, the lower-scored chunk is dropped.
    """
    if DEDUP_SIMILARITY_THRESHOLD <= 0:
        return chunks

    kept: list[RetrievalChunk] = []
    for chunk in chunks:
        is_duplicate = False
        for existing in kept:
            similarity = jaccard_similarity(chunk.content, existing.content)
            if similarity >= DEDUP_SIMILARITY_THRESHOLD:
                is_duplicate = True
                if TRACE_MODE:
                    logger.debug(
                        "DEDUP | dropped chunk_id=%s (sim=%.3f with chunk_id=%s)",
                        chunk.chunk_id,
                        similarity,
                        existing.chunk_id,
                    )
                break
        if not is_duplicate:
            kept.append(chunk)

    if TRACE_MODE:
        logger.info(
            "FILTER | dedup: %d -> %d chunks (threshold=%.2f)",
            len(chunks),
            len(kept),
            DEDUP_SIMILARITY_THRESHOLD,
        )
    return kept


# ---------------------------------------------------------------------------
# Per-source diversity filter
# ---------------------------------------------------------------------------
def filter_by_source_diversity(
    chunks: list[RetrievalChunk],
) -> list[RetrievalChunk]:
    """Cap the number of chunks from any single source document.

    Prevents a single manual from dominating the context when multiple
    manuals might have relevant information. Chunks are already sorted by
    score, so higher-scored chunks from each source are kept.
    """
    counts: defaultdict[str, int] = defaultdict(int)
    filtered: list[RetrievalChunk] = []

    for chunk in chunks:
        source_key = chunk.source or chunk.title or "unknown"
        if counts[source_key] < MAX_CHUNKS_PER_SOURCE:
            filtered.append(chunk)
            counts[source_key] += 1
        elif TRACE_MODE:
            logger.debug(
                "DIVERSITY | capped chunk_id=%s from source=%s (already %d chunks)",
                chunk.chunk_id,
                source_key,
                counts[source_key],
            )

    if TRACE_MODE:
        logger.info(
            "FILTER | diversity: %d -> %d chunks (max_per_source=%d)",
            len(chunks),
            len(filtered),
            MAX_CHUNKS_PER_SOURCE,
        )
    return filtered


# ---------------------------------------------------------------------------
# Score-gap filter
# ---------------------------------------------------------------------------
def filter_by_score_gap(chunks: list[RetrievalChunk]) -> list[RetrievalChunk]:
    """Remove chunks whose effective score falls too far below the top chunk.

    This prevents low-relevance tail chunks from diluting the context.
    The threshold is expressed as a fraction of the top chunk's effective score.
    """
    if not chunks or SCORE_GAP_RATIO <= 0:
        return chunks

    top_score = chunks[0].effective_score
    if top_score <= 0:
        return chunks

    threshold = SCORE_GAP_RATIO * top_score
    filtered = [c for c in chunks if c.effective_score >= threshold]

    removed = len(chunks) - len(filtered)
    if TRACE_MODE and removed:
        logger.info(
            "FILTER | score_gap: removed %d chunk(s) below %.4f (%.0f%% of top %.4f)",
            removed,
            threshold,
            SCORE_GAP_RATIO * 100,
            top_score,
        )
    return filtered


# ---------------------------------------------------------------------------
# Full ranking pipeline
# ---------------------------------------------------------------------------
def rank_and_filter(chunks: list[RetrievalChunk]) -> list[RetrievalChunk]:
    """Execute the full post-retrieval ranking and filtering pipeline.

    Steps:
    1. Sort by effective score (descending)
    2. Filter by minimum content length
    3. Filter by absolute relevance threshold
    4. Remove TOC / index page chunks
    5. Deduplicate near-identical content
    6. Apply per-source diversity cap
    7. Apply score-gap filter

    Parameters
    ----------
    chunks:
        Raw normalized chunks from Azure AI Search, not yet filtered.

    Returns
    -------
    list[RetrievalChunk]
        High-quality, deduplicated, diverse chunks ordered by relevance.
    """
    # 1. Sort by effective score descending
    chunks.sort(key=lambda c: c.effective_score, reverse=True)

    if TRACE_MODE:
        logger.info("RANK | starting with %d candidate chunks", len(chunks))

    # 2. Minimum content length
    chunks = filter_by_content_length(chunks)

    # 3. Absolute relevance threshold
    chunks = filter_by_relevance_threshold(chunks)

    # 4. TOC / index removal
    chunks = filter_toc_chunks(chunks)

    # 5. Content deduplication
    chunks = deduplicate_chunks(chunks)

    # 6. Per-source diversity
    chunks = filter_by_source_diversity(chunks)

    # 7. Score-gap filter
    chunks = filter_by_score_gap(chunks)

    if TRACE_MODE:
        logger.info("RANK | final: %d chunks after all filters", len(chunks))
        for i, c in enumerate(chunks, start=1):
            reranker_str = (
                f" reranker={c.reranker_score:.4f}"
                if c.reranker_score is not None
                else ""
            )
            preview = c.content[:120].replace("\n", " ")
            logger.info(
                "RANK | [%d] chunk_id=%s source=%s score=%.4f%s section=%r | %s",
                i,
                c.chunk_id,
                c.source,
                c.score,
                reranker_str,
                c.section_path,
                preview,
            )

    return chunks

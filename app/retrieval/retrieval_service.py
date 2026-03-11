"""Retrieval service — the main entry point for searching technical manuals.

Orchestrates the full retrieval pipeline:
1. Normalize the query for BM25 keyword search
2. Generate query embedding for vector search
3. Execute hybrid search against Azure AI Search
4. Normalize raw documents to canonical RetrievalChunk schema
5. Run the full ranking/filtering pipeline
6. Trim to configured limits
7. Return structured RetrievalResult with diagnostics

This module is the single point of contact for retrieval — the agent
runtime calls retrieve() and gets back a clean, filtered, scored result.

Improvements over the reference repo:
- Separate query normalization for keyword vs vector search
- Explicit relevance threshold filtering (not just score-gap)
- Content-based deduplication to reduce redundant chunks
- TOC/index page filtering
- Per-source diversity capping
- Detailed diagnostic metadata in the result
- Graceful fallback to keyword-only if embedding fails
"""

import logging

from azure.search.documents.models import VectorizedQuery

from app.config.settings import (
    MAX_CONTEXT_CHUNKS,
    QUERY_LANGUAGE,
    RETRIEVAL_CANDIDATES,
    SEARCH_CHUNK_ID_FIELD,
    SEARCH_CONTENT_FIELD,
    SEARCH_FILENAME_FIELD,
    SEARCH_PAGE_FIELD,
    SEARCH_SECTION1_FIELD,
    SEARCH_SECTION2_FIELD,
    SEARCH_SECTION3_FIELD,
    SEARCH_TITLE_FIELD,
    SEARCH_URL_FIELD,
    SEARCH_VECTOR_FIELD,
    SEMANTIC_CONFIG_NAME,
    TOP_K,
    TRACE_MODE,
    USE_SEMANTIC_RERANKER,
    VECTOR_K,
)
from app.models.retrieval_models import RetrievalChunk, RetrievalResult
from app.retrieval.ranking import rank_and_filter
from app.retrieval.search_client import generate_query_embedding, get_search_client
from app.utils.helpers import normalize_query

logger = logging.getLogger(__name__)


def _select_fields() -> list[str]:
    """Return the list of index fields to retrieve from Azure AI Search.

    Includes all schema fields needed for context building and citations.
    Optional fields (SEARCH_PAGE_FIELD) are included only when configured.
    The vector field is excluded — it is not retrievable.
    """
    fields = [
        SEARCH_CONTENT_FIELD,
        SEARCH_TITLE_FIELD,
        SEARCH_FILENAME_FIELD,
        SEARCH_URL_FIELD,
        SEARCH_CHUNK_ID_FIELD,
        SEARCH_SECTION1_FIELD,
        SEARCH_SECTION2_FIELD,
        SEARCH_SECTION3_FIELD,
    ]
    if SEARCH_PAGE_FIELD:
        fields.append(SEARCH_PAGE_FIELD)
    # Filter out any blank field names from unconfigured optional fields
    return [f for f in fields if f]


def _normalize_document(doc: dict) -> RetrievalChunk:
    """Map a raw Azure AI Search document to the canonical RetrievalChunk.

    Parameters
    ----------
    doc:
        Raw document dict from Azure AI Search results.

    Returns
    -------
    RetrievalChunk
        Normalized chunk with all metadata mapped to canonical field names.
    """
    return RetrievalChunk(
        content=doc.get(SEARCH_CONTENT_FIELD) or "",
        title=doc.get(SEARCH_TITLE_FIELD) or "",
        source=doc.get(SEARCH_FILENAME_FIELD) or "",
        url=doc.get(SEARCH_URL_FIELD) or "",
        chunk_id=doc.get(SEARCH_CHUNK_ID_FIELD) or "",
        section1=doc.get(SEARCH_SECTION1_FIELD) or "",
        section2=doc.get(SEARCH_SECTION2_FIELD) or "",
        section3=doc.get(SEARCH_SECTION3_FIELD) or "",
        page=(
            str(doc.get(SEARCH_PAGE_FIELD) or "") if SEARCH_PAGE_FIELD else ""
        ),
        score=doc.get("@search.score") or 0.0,
        reranker_score=doc.get("@search.reranker_score"),
    )


def retrieve(question: str, top_k: int = TOP_K) -> RetrievalResult:
    """Run a hybrid search and return filtered, ranked retrieval results.

    This is the main entry point for retrieval. Called by the agent runtime.

    Parameters
    ----------
    question:
        The user's question. Used verbatim for vector embedding.
        A normalized version is used for BM25 keyword search.
    top_k:
        Maximum number of chunks to return after all filtering.

    Returns
    -------
    RetrievalResult
        Contains the final chunks plus diagnostic metadata.

    Raises
    ------
    Exception
        Propagated from Azure AI Search or embedding generation if
        the search itself fails (not just low-quality results).
    """
    result = RetrievalResult(query_used=question)

    # ── 1. Normalize query for BM25 keyword search ──────────────────────────
    keyword_query = normalize_query(question)
    result.keyword_query_used = keyword_query
    if TRACE_MODE and keyword_query != question:
        logger.info("RETRIEVE | keyword_query=%r (original=%r)", keyword_query, question)

    # ── 2. Generate query embedding for vector search ───────────────────────
    query_vector: list[float] | None = None
    try:
        query_vector = generate_query_embedding(question)
    except Exception:
        logger.warning(
            "Embedding generation failed — falling back to keyword-only search",
            exc_info=True,
        )

    # ── 3. Build search arguments ───────────────────────────────────────────
    client = get_search_client()
    select = _select_fields()

    search_kwargs: dict = {
        "search_text": keyword_query,
        "top": RETRIEVAL_CANDIDATES,
        "select": select,
    }

    if query_vector:
        search_kwargs["vector_queries"] = [
            VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=VECTOR_K,
                fields=SEARCH_VECTOR_FIELD,
            )
        ]

    # ── 4. Execute search (with optional semantic reranking) ────────────────
    raw_results: list[dict] = []

    if USE_SEMANTIC_RERANKER:
        try:
            from azure.search.documents.models import QueryType

            search_kwargs["query_type"] = QueryType.SEMANTIC
            search_kwargs["semantic_configuration_name"] = SEMANTIC_CONFIG_NAME
            search_kwargs["query_language"] = QUERY_LANGUAGE
            raw_results = list(client.search(**search_kwargs))
            result.semantic_reranker_active = True
            logger.info(
                "RETRIEVE | semantic reranker active — %d raw candidates",
                len(raw_results),
            )
        except Exception:
            logger.warning(
                "Semantic reranking unavailable — falling back to hybrid search",
                exc_info=True,
            )
            search_kwargs.pop("query_type", None)
            search_kwargs.pop("semantic_configuration_name", None)
            search_kwargs.pop("query_language", None)
            raw_results = list(client.search(**search_kwargs))
    else:
        raw_results = list(client.search(**search_kwargs))
        logger.info("RETRIEVE | hybrid search — %d raw candidates", len(raw_results))

    result.total_candidates = len(raw_results)

    # ── 5. Normalize raw documents to RetrievalChunk ────────────────────────
    chunks = [_normalize_document(doc) for doc in raw_results]

    # ── 6. Run full ranking/filtering pipeline ──────────────────────────────
    chunks = rank_and_filter(chunks)

    # ── 7. Trim to final limits ─────────────────────────────────────────────
    final_limit = min(top_k, MAX_CONTEXT_CHUNKS)
    chunks = chunks[:final_limit]

    result.chunks = chunks
    result.final_count = len(chunks)

    if TRACE_MODE:
        logger.info(
            "RETRIEVE | final=%d chunks (limit=%d) from %d candidates",
            result.final_count,
            final_limit,
            result.total_candidates,
        )

    return result

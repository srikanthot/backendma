"""Citation builder — structures retrieval results into frontend-friendly citations.

Citations are built directly from the retrieved chunks, not from the LLM's
formatting. This ensures citations are always present and accurate regardless
of how the model formats its answer text.

Each citation preserves the full metadata trail: title, source document,
section breadcrumb, page number, and chunk ID.
"""

from app.api.schemas import Citation
from app.models.retrieval_models import RetrievalChunk


def build_citations(chunks: list[RetrievalChunk]) -> list[Citation]:
    """Build a deduplicated, ordered citation list from retrieved chunks.

    Parameters
    ----------
    chunks:
        Final filtered RetrievalChunk objects from the retrieval pipeline.
        Assumed to be ordered by relevance (highest first).

    Returns
    -------
    list[Citation]
        One Citation per unique chunk_id (or source fallback), in order of
        first appearance (highest relevance).
    """
    seen: set[str] = set()
    citations: list[Citation] = []

    for chunk in chunks:
        # chunk_id is globally unique per indexed chunk; fallback to source
        key = chunk.chunk_id or f"{chunk.source}|{chunk.url}"
        if key in seen:
            continue
        seen.add(key)

        citations.append(
            Citation(
                title=chunk.title,
                source=chunk.source,
                chunk_id=chunk.chunk_id,
                section=chunk.section_path,
                page=chunk.page,
            )
        )

    return citations

"""Application settings loaded from environment variables.

All configuration is driven by .env so the same codebase works across
dev / staging / production without code changes.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Azure OpenAI
# ---------------------------------------------------------------------------
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
AZURE_OPENAI_CHAT_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
# Agent Framework SDK reads AZURE_OPENAI_CHAT_DEPLOYMENT_NAME; fallback to legacy var
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: str = os.getenv(
    "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
)
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: str = os.getenv(
    "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", ""
)

# ---------------------------------------------------------------------------
# Azure AI Search
# ---------------------------------------------------------------------------
AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "")

# ---------------------------------------------------------------------------
# Index field mappings — must match the actual index schema exactly.
# ---------------------------------------------------------------------------
SEARCH_CONTENT_FIELD: str = os.getenv("SEARCH_CONTENT_FIELD", "chunk")
SEARCH_VECTOR_FIELD: str = os.getenv("SEARCH_VECTOR_FIELD", "text_vector")
SEARCH_TITLE_FIELD: str = os.getenv("SEARCH_TITLE_FIELD", "title")
SEARCH_FILENAME_FIELD: str = os.getenv("SEARCH_FILENAME_FIELD", "source_file")
SEARCH_URL_FIELD: str = os.getenv("SEARCH_URL_FIELD", "source_url")
SEARCH_CHUNK_ID_FIELD: str = os.getenv("SEARCH_CHUNK_ID_FIELD", "chunk_id")
SEARCH_PAGE_FIELD: str = os.getenv("SEARCH_PAGE_FIELD", "")
SEARCH_SECTION1_FIELD: str = os.getenv("SEARCH_SECTION1_FIELD", "header_1")
SEARCH_SECTION2_FIELD: str = os.getenv("SEARCH_SECTION2_FIELD", "header_2")
SEARCH_SECTION3_FIELD: str = os.getenv("SEARCH_SECTION3_FIELD", "header_3")

# ---------------------------------------------------------------------------
# Retrieval tuning — these settings most affect answer quality
# ---------------------------------------------------------------------------
# TOP_K: number of final chunks to pass to the LLM after all filtering
TOP_K: int = int(os.getenv("TOP_K", "5"))
# VECTOR_K: number of nearest neighbors for vector search component
VECTOR_K: int = int(os.getenv("VECTOR_K", "50"))
# MAX_CONTEXT_CHUNKS: hard cap on chunks assembled into the prompt context
MAX_CONTEXT_CHUNKS: int = int(os.getenv("MAX_CONTEXT_CHUNKS", "5"))
# How many candidates to fetch before post-retrieval filtering trims to TOP_K
RETRIEVAL_CANDIDATES: int = int(os.getenv("RETRIEVAL_CANDIDATES", "20"))

# ---------------------------------------------------------------------------
# Retrieval quality thresholds
# ---------------------------------------------------------------------------
# Minimum relevance score (base hybrid/RRF score) for a chunk to be considered
MIN_RELEVANCE_SCORE: float = float(os.getenv("MIN_RELEVANCE_SCORE", "0.01"))
# Minimum reranker score (0.0-4.0 scale) when semantic reranker is active
MIN_RERANKER_SCORE: float = float(os.getenv("MIN_RERANKER_SCORE", "0.5"))
# Whether to use Azure AI Search semantic reranker
USE_SEMANTIC_RERANKER: bool = (
    os.getenv("USE_SEMANTIC_RERANKER", "true").lower() == "true"
)
SEMANTIC_CONFIG_NAME: str = os.getenv(
    "SEMANTIC_CONFIG_NAME", "manual-semantic-config"
)
QUERY_LANGUAGE: str = os.getenv("QUERY_LANGUAGE", "en-us")

# ---------------------------------------------------------------------------
# Post-retrieval filtering
# ---------------------------------------------------------------------------
# Maximum chunks from any single source document
MAX_CHUNKS_PER_SOURCE: int = int(os.getenv("MAX_CHUNKS_PER_SOURCE", "3"))
# Score gap ratio: discard chunks scoring below this fraction of the top score
SCORE_GAP_RATIO: float = float(os.getenv("SCORE_GAP_RATIO", "0.40"))
# Overlap similarity threshold for deduplication (0.0-1.0, higher = stricter)
DEDUP_SIMILARITY_THRESHOLD: float = float(
    os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.85")
)
# Minimum content length (chars) for a chunk to be useful — filters out stubs
MIN_CHUNK_LENGTH: int = int(os.getenv("MIN_CHUNK_LENGTH", "50"))

# ---------------------------------------------------------------------------
# CORS — comma-separated origins
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS: str = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
)

# ---------------------------------------------------------------------------
# Logging / diagnostics
# ---------------------------------------------------------------------------
TRACE_MODE: bool = os.getenv("TRACE_MODE", "true").lower() == "true"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

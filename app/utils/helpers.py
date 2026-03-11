"""General-purpose helper utilities.

Small, reusable functions that don't belong to any specific domain module.
"""

import re
import hashlib


# ---------------------------------------------------------------------------
# Query normalization
# ---------------------------------------------------------------------------

# Conversational filler words that hurt BM25 keyword precision
_FILLER_RE = re.compile(
    r"\b(right now|currently|at this (moment|time)|i am|i'm|i need to|i want to|"
    r"can you|what should( i)?|how do i|what are the|please|tell me|help me|"
    r"so |just |i was told|could you|would you|i have to|what do i|"
    r"explain|describe|show me|give me|walk me through)\b",
    re.IGNORECASE,
)


def normalize_query(question: str) -> str:
    """Strip conversational filler to improve BM25 keyword search precision.

    The original question is still used for vector embedding (semantic search).
    This cleaned version is used only for the keyword (BM25) component.

    Parameters
    ----------
    question:
        The raw user question.

    Returns
    -------
    str
        A cleaned query string. Falls back to the original if cleaning
        produces something too short to be useful.
    """
    cleaned = _FILLER_RE.sub(" ", question)
    cleaned = re.sub(r"[,\s]+", " ", cleaned).strip()
    # Fall back to original if distillation was too aggressive
    return cleaned if len(cleaned) >= 10 else question


# ---------------------------------------------------------------------------
# Text similarity for deduplication
# ---------------------------------------------------------------------------

def compute_text_fingerprint(text: str) -> str:
    """Compute a simple hash fingerprint of normalized text.

    Used for fast deduplication checks before falling back to
    more expensive similarity measures.
    """
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity between two texts based on word tokens.

    Parameters
    ----------
    text_a, text_b:
        The two text strings to compare.

    Returns
    -------
    float
        Similarity score between 0.0 and 1.0.
    """
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a and not words_b:
        return 1.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0

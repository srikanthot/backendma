"""Dependency-free RAG-triad proxy metrics.

These are lexical proxies so the harness runs anywhere with no API keys. They
correlate with, but do not replace, LLM-judged RAGAS metrics — wire an LLM judge
into `score_case` for production (see README). Each metric returns 0..1.
"""
from __future__ import annotations
import re
from collections import Counter

_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("a an the of to and or is are was were be been in on at for with "
            "that this it as by from your you we our".split())


def _tokens(text: str) -> set:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def _overlap(a: str, b: str) -> float:
    """Fraction of content tokens in `a` that also appear in `b`."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)


def context_recall(ground_truth: str, contexts: list[str]) -> float:
    """How much of the reference answer is actually present in retrieved context."""
    ctx = " ".join(contexts)
    return _overlap(ground_truth, ctx)


def faithfulness(answer: str, contexts: list[str]) -> float:
    """How much of the generated answer is supported by retrieved context."""
    ctx = " ".join(contexts)
    return _overlap(answer, ctx)


def answer_relevance(answer: str, question: str, ground_truth: str) -> float:
    """How well the answer addresses the question / expected answer."""
    return _overlap(answer, f"{question} {ground_truth}")


def score_case(case: dict) -> dict:
    ctx = case.get("contexts", [])
    return {
        "faithfulness": round(faithfulness(case.get("answer", ""), ctx), 3),
        "context_recall": round(context_recall(case.get("ground_truth", ""), ctx), 3),
        "answer_relevance": round(
            answer_relevance(case.get("answer", ""), case.get("question", ""),
                             case.get("ground_truth", "")), 3),
    }

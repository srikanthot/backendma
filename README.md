# RAG Evaluation Harness (Python)

> A reusable **evaluation harness** for RAG systems: score the RAG triad (faithfulness/groundedness, answer relevance, context precision/recall) on a versioned golden dataset, with LLM-as-judge and a CI gate that blocks regressions.

![status](https://img.shields.io/badge/status-active%20build-orange) ![focus](https://img.shields.io/badge/focus-evaluation-brightgreen) ![python](https://img.shields.io/badge/python-3.11-blue) ![license](https://img.shields.io/badge/license-MIT-lightgrey)


---

## Why this exists

Most RAG demos have no numbers. Hiring teams look for exactly the opposite: a repeatable way to prove retrieval quality and catch regressions. This harness plugs into any RAG service (or your own) and produces a real scorecard.

## What it measures

| metric | question it answers |
|--------|---------------------|
| Faithfulness / groundedness | is the answer supported by retrieved sources? |
| Answer relevance | does it address the question? |
| Context precision / recall | did retrieval surface the right chunks? |
| Gate precision/recall | does the system abstain when it should? |

## Status
- **Implemented:** a reference frontend-agnostic RAG API (managed identity, hybrid retrieval) to evaluate against.
- **Focus (this repo):** the eval harness — RAGAS + DeepEval, a versioned `golden.jsonl`, LLM-as-judge scoring, an HTML scorecard, and a **GitHub Actions gate** that fails the build when faithfulness/recall drop below thresholds.

## Quickstart
```bash
pip install -r requirements.txt
python -m eval.run --dataset eval/golden.jsonl --target http://localhost:8000
# → prints triad scores + writes eval/report.html
```

## Roadmap
- Online eval on sampled traffic; drift alerts.
- Pluggable adapters for Azure / AWS / local targets.

---

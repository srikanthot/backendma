"""Run the RAG evaluation suite over a golden dataset and gate on thresholds.

    python -m eval.run --dataset eval/golden.jsonl

Exit code is non-zero if any mean metric falls below its threshold — so this
doubles as a CI quality gate (see .github/workflows/eval.yml).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from statistics import mean
from eval.metrics import score_case

THRESHOLDS = {"faithfulness": 0.60, "context_recall": 0.55, "answer_relevance": 0.50}


def load(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/golden.jsonl")
    ap.add_argument("--report", default="eval/report.md")
    args = ap.parse_args()

    cases = load(args.dataset)
    rows = [(c.get("question", "")[:50], score_case(c)) for c in cases]
    means = {m: round(mean(r[1][m] for r in rows), 3) for m in THRESHOLDS}

    lines = ["# RAG Evaluation Report", "", f"Cases: {len(rows)}", "",
             "| metric | mean | threshold | pass |", "|---|---|---|---|"]
    ok = True
    for m, thr in THRESHOLDS.items():
        p = means[m] >= thr
        ok = ok and p
        lines.append(f"| {m} | {means[m]} | {thr} | {'✅' if p else '❌'} |")
    lines += ["", "## Per-case", "", "| question | faithfulness | context_recall | answer_relevance |",
              "|---|---|---|---|"]
    for q, s in rows:
        lines.append(f"| {q} | {s['faithfulness']} | {s['context_recall']} | {s['answer_relevance']} |")
    report = "\n".join(lines) + "\n"
    Path(args.report).write_text(report, encoding="utf-8")
    print(report)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

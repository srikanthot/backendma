# RAG Evaluation Report

Cases: 4

| metric | mean | threshold | pass |
|---|---|---|---|
| faithfulness | 0.874 | 0.6 | ✅ |
| context_recall | 0.947 | 0.55 | ✅ |
| answer_relevance | 0.74 | 0.5 | ✅ |

## Per-case

| question | faithfulness | context_recall | answer_relevance |
|---|---|---|---|
| What happens when retrieval confidence is low? | 0.833 | 0.889 | 0.833 |
| How does hybrid search work? | 1.0 | 1.0 | 0.769 |
| Where do citations come from? | 0.818 | 0.9 | 0.818 |
| How often is the index refreshed? | 0.846 | 1.0 | 0.538 |

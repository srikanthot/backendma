"""RagContextProvider — official Agent Framework ContextProvider for RAG.

Implements the Agent Framework BaseContextProvider hook pattern.

Before each LLM call (before_run):
  - Reads pre-retrieved Azure AI Search results from session.state
    (placed there by the runtime before calling agent.run).
  - Formats them into numbered evidence blocks via build_context_blocks.
  - Injects the formatted context as additional instructions via
    context.extend_instructions(), which the framework appends to the
    agent's system prompt before the model call.

After each LLM call (after_run):
  - No-op for this version. Audit logging or persistence can be added here.

This is the ONLY context provider in this no-history version. No history
or memory provider is wired — each request is a standalone single-turn
interaction with fresh context from Azure AI Search.

This is what makes the repo a true Agent Framework implementation:
RAG context injection is a first-class ContextProvider, not ad-hoc
string formatting inside the orchestrator.
"""

import logging
from typing import Any

from agent_framework import AgentSession, BaseContextProvider, SessionContext

from app.config.settings import TRACE_MODE
from app.llm.prompt_builder import build_context_blocks
from app.models.retrieval_models import RetrievalChunk

logger = logging.getLogger(__name__)

# Key in session.state used to pass pre-retrieved results from the runtime
# to this provider without double-querying Azure AI Search.
_PENDING_RESULTS_KEY = "_rag_pending_results"


class RagContextProvider(BaseContextProvider):
    """Injects pre-retrieved search chunks as grounded context for each turn.

    This provider is wired into the Agent via agent_factory.py and is
    called automatically by the Agent Framework before each LLM invocation.
    """

    def __init__(self) -> None:
        super().__init__("rag")

    def store_results(
        self, session: AgentSession, chunks: list[RetrievalChunk]
    ) -> None:
        """Called by the runtime before agent.run() to pass retrieved chunks.

        Storing in session.state makes the data visible to before_run()
        via the session parameter.
        """
        session.state[_PENDING_RESULTS_KEY] = chunks

    async def before_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """Inject retrieved chunks as system-level context before model call.

        The Agent Framework calls this hook before every LLM invocation.
        We read the chunks from session.state, format them into numbered
        evidence blocks, and inject them via context.extend_instructions().
        """
        chunks: list[RetrievalChunk] = session.state.pop(
            _PENDING_RESULTS_KEY, []
        )
        if not chunks:
            return

        context_blocks = build_context_blocks(chunks)
        context.extend_instructions(
            self.source_id,
            (
                "Context (retrieved from technical manuals):\n\n"
                f"{context_blocks}\n\n"
                "Answer the question using ONLY the context above. "
                "When the context covers the topic - even partially - provide a "
                "complete answer from the available information. "
                "Reference each source by its [N] label inline. "
                'Include a "Sources:" section at the end.'
            ),
        )

        if TRACE_MODE:
            chunk_summary = "  |  ".join(
                "[{i}] {src} score={s:.4f}{r}".format(
                    i=i + 1,
                    src=c.source,
                    s=c.score,
                    r=(
                        f" reranker={c.reranker_score:.4f}"
                        if c.reranker_score is not None
                        else ""
                    ),
                )
                for i, c in enumerate(chunks)
            )
            logger.info("CONTEXT | injected: %s", chunk_summary)
            for i, c in enumerate(chunks, start=1):
                logger.info(
                    "CONTEXT | block[%d] (%s | %s):\n%s",
                    i,
                    c.source,
                    c.section_path or "no section",
                    c.content[:600],
                )

    async def after_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """No-op for this version. Audit/persistence can be wired here later."""

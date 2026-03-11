"""Agent runtime — orchestrates the full retrieve-gate-generate-cite pipeline.

This is the central orchestration layer. It:
1. Receives the user question
2. Calls the retrieval service to get evidence chunks
3. Applies a confidence gate (insufficient evidence check)
4. Hands chunks to the Agent Framework via the RagContextProvider
5. Runs the Agent Framework agent to generate a grounded answer
6. Builds structured citations from the retrieved chunks
7. Returns a clean ChatResponse

The route handler calls this runtime — it does NOT call raw search
or prompt logic directly. This keeps routes thin and the orchestration
testable and swappable.

Uses Microsoft Agent Framework SDK:
- af_agent.create_session() for per-request session state (no history carried over)
- af_agent.run() for LLM invocation through the framework
- RagContextProvider.before_run() for automatic context injection

NO-HISTORY DESIGN:
  Each request creates a fresh AgentSession. session_id is passed through
  from request to response for future-friendliness only — it does NOT
  restore or carry over any conversation state in this version.
"""

import asyncio
import logging

from app.agent_runtime.agent_factory import af_agent, rag_provider
from app.api.schemas import ChatResponse, Citation
from app.config.settings import TRACE_MODE, TOP_K
from app.models.retrieval_models import RetrievalChunk
from app.retrieval.citations import build_citations
from app.retrieval.retrieval_service import retrieve
from app.utils.errors import (
    GenerationError,
    InsufficientEvidenceError,
    RetrievalError,
)

logger = logging.getLogger(__name__)

# Minimum number of chunks required to proceed with answer generation
_MIN_EVIDENCE_CHUNKS = 1


class AgentRuntime:
    """Orchestrates the full retrieve -> gate -> generate -> cite pipeline.

    Uses the Microsoft Agent Framework SDK for LLM invocation and context
    injection (RagContextProvider).

    This class is stateless and safe for concurrent requests.
    """

    async def run(
        self,
        question: str,
        session_id: str | None = None,
        top_k: int = TOP_K,
    ) -> ChatResponse:
        """Execute the full pipeline and return a structured ChatResponse.

        Parameters
        ----------
        question:
            The user's question.
        session_id:
            Pass-through session identifier. Echoed back in the response
            for future multi-turn support. No state is stored or restored.
        top_k:
            Maximum chunks to retrieve (after filtering).

        Returns
        -------
        ChatResponse
            The generated answer with structured citations.

        Raises
        ------
        RetrievalError
            If Azure AI Search retrieval fails.
        InsufficientEvidenceError
            If retrieved evidence doesn't meet quality thresholds.
        GenerationError
            If Azure OpenAI generation fails.
        """
        logger.info(
            "AgentRuntime.run | session=%s | question=%s",
            session_id or "none",
            question,
        )

        # ── 1. RETRIEVE — hybrid Azure AI Search ───────────────────────────
        try:
            retrieval_result = await asyncio.to_thread(
                retrieve, question, top_k=top_k
            )
        except Exception as exc:
            raise RetrievalError(
                message="Failed to search the knowledge base",
                detail=str(exc),
            ) from exc

        chunks = retrieval_result.chunks

        # ── 2. GATE — confidence check ─────────────────────────────────────
        if len(chunks) < _MIN_EVIDENCE_CHUNKS:
            logger.info(
                "GATE | insufficient evidence: %d chunks (min=%d)",
                len(chunks),
                _MIN_EVIDENCE_CHUNKS,
            )
            raise InsufficientEvidenceError(
                message=(
                    "I don't have enough evidence from the technical manuals "
                    "to answer your question confidently. Could you provide "
                    "more detail - for example, the equipment name, model "
                    "number, or the specific procedure you are looking for?"
                ),
                n_results=len(chunks),
                avg_score=(
                    sum(c.effective_score for c in chunks) / len(chunks)
                    if chunks
                    else 0.0
                ),
            )

        if TRACE_MODE:
            avg_score = sum(c.effective_score for c in chunks) / len(chunks)
            logger.info(
                "GATE | passed: %d chunks, avg_effective_score=%.4f",
                len(chunks),
                avg_score,
            )

        # ── 3. Create Agent Framework session ──────────────────────────────
        af_session = af_agent.create_session()

        # ── 4. Hand retrieved chunks to RagContextProvider ─────────────────
        rag_provider.store_results(af_session, chunks)

        # ── 5. GENERATE — run via Agent Framework agent ────────────────────
        answer_text = ""
        try:
            # Run agent without streaming — collect the full response
            response = await af_agent.run(question, session=af_session)
            if response and response.text:
                answer_text = response.text
        except Exception as exc:
            raise GenerationError(
                message="Failed to generate an answer",
                detail=str(exc),
            ) from exc

        if not answer_text:
            raise GenerationError(
                message="The model returned an empty response. Please try again."
            )

        # ── 6. CITE — build structured citations from retrieved chunks ─────
        citations: list[Citation] = build_citations(chunks)

        if TRACE_MODE:
            logger.info(
                "GENERATE | answer_length=%d citations=%d",
                len(answer_text),
                len(citations),
            )

        return ChatResponse(
            answer=answer_text,
            citations=citations,
            session_id=session_id or "",
        )

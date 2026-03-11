"""FastAPI routes — intentionally thin per the agent framework pattern.

Each route does exactly three things:
  1. Validate the incoming request (Pydantic does this automatically).
  2. Delegate to the AgentRuntime.
  3. Return the structured response or a meaningful error.

No business logic lives here. The route layer is purely transport.
All orchestration happens in agent_runtime/runtime.py.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.agent_runtime.runtime import AgentRuntime
from app.api.schemas import ChatRequest, ChatResponse
from app.utils.errors import (
    GenerationError,
    InsufficientEvidenceError,
    RetrievalError,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Single shared runtime instance — stateless, safe for concurrent requests
_runtime = AgentRuntime()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a question about technical manuals",
    description=(
        "Submit a question and receive a grounded answer with structured "
        "citations from technical manual content."
    ),
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Primary chat endpoint — returns a grounded answer with citations.

    Request body: {"question": "...", "session_id": "optional-id"}

    Response: {"answer": "...", "citations": [...], "session_id": "..."}
    """
    logger.info(
        "POST /chat | session=%s | question=%s",
        request.session_id or "none",
        request.question[:100],
    )

    try:
        response = await _runtime.run(
            question=request.question,
            session_id=request.session_id,
        )
        return response

    except InsufficientEvidenceError as exc:
        # Return the "not enough evidence" message as a normal response
        # with empty citations, not as an HTTP error — this is a valid
        # outcome, not a backend failure.
        logger.info("Insufficient evidence for question: %s", request.question[:100])
        return ChatResponse(
            answer=exc.message,
            citations=[],
            session_id=request.session_id or "",
        )

    except RetrievalError as exc:
        logger.error("Retrieval failed: %s", exc.detail, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="An error occurred while searching the knowledge base. Please try again.",
        ) from exc

    except GenerationError as exc:
        logger.error("Generation failed: %s", exc.detail, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="An error occurred while generating the answer. Please try again.",
        ) from exc

    except Exception as exc:
        logger.error("Unexpected error in /chat: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again.",
        ) from exc

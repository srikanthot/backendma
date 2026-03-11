"""Prompt and context assembly for the technical manuals chatbot.

Provides:
- SYSTEM_PROMPT: the agent's system-level instructions
- build_context_blocks(): formats retrieved chunks into numbered evidence blocks
- build_user_message(): assembles the final user message with embedded context

Design principles:
- Clearly separates system instructions from retrieved context
- Tells the model to answer only from grounded manual content
- Tells the model not to invent unsupported procedures
- Encourages source-grounded answers with inline citations
- Works well with technical manuals (step-by-step, safety, procedures)
- Stays concise and clean to maximize effective context window usage
"""

from app.models.retrieval_models import RetrievalChunk


# ---------------------------------------------------------------------------
# System prompt — defines the agent's behavior and grounding rules
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Technical Manual Assistant that helps engineers, \
technicians, and field personnel find accurate information from official \
technical manuals and documentation.

GROUNDING RULES:
- Base your answer ONLY on the numbered context blocks provided. Do not use \
prior knowledge or general industry practices.
- Reference factual claims with their [N] citation number inline \
(e.g., "The torque setting is 25 ft-lbs [1]").
- When the context covers the topic — even partially — provide the best \
answer you can from the available information. Do not refuse when evidence \
exists.
- If multiple context blocks contain related information, synthesize them \
into a coherent answer while citing each source.
- NEVER invent procedures, safety warnings, PPE requirements, or steps \
not explicitly present in the context blocks.

WHEN TO DECLINE:
- Only state you cannot answer if the context is genuinely unrelated to the \
question. In that case say so briefly and suggest what the user could \
clarify (e.g., equipment model, procedure name, manual title).

FORMATTING:
- Keep answers concise and actionable — technicians need clear guidance \
they can follow in the field.
- Preserve original structure from the manual where possible: numbered \
steps, warnings, cautions, and notes.
- At the end include a "Sources:" section listing cited sources:
     Sources:
     - [1] <document title>, Section: <section if available>
     - [2] <document title>
- Use a natural structure that best fits the question — do not force \
every answer into the same rigid template."""


def build_context_blocks(chunks: list[RetrievalChunk]) -> str:
    """Format retrieved chunks into numbered, labeled evidence blocks.

    Each block carries a header with source metadata followed by the raw
    chunk content. The LLM prompt instructs the model to answer only from
    these blocks and to reference them by their [N] label.

    Parameters
    ----------
    chunks:
        Final filtered RetrievalChunk objects from the retrieval pipeline.

    Returns
    -------
    str
        A single string with one evidence block per chunk, separated by
        horizontal rules for clear visual separation.
    """
    blocks: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        lines = [f"[{i}]"]
        if chunk.title:
            lines.append(f"Title: {chunk.title}")
        if chunk.source:
            lines.append(f"Source: {chunk.source}")
        section = chunk.section_path
        if section:
            lines.append(f"Section: {section}")
        if chunk.page:
            lines.append(f"Page: {chunk.page}")
        if chunk.chunk_id:
            lines.append(f"Chunk ID: {chunk.chunk_id}")
        lines.append("Content:")
        lines.append(chunk.content)
        blocks.append("\n".join(lines))

    return "\n\n---\n\n".join(blocks)


def build_user_message(question: str, chunks: list[RetrievalChunk]) -> str:
    """Assemble the user message with the question and embedded context.

    This is used when injecting context directly into the user message
    (as opposed to using the Agent Framework's context_providers hook).

    Parameters
    ----------
    question:
        The user's original question.
    chunks:
        Final filtered chunks from the retrieval pipeline.

    Returns
    -------
    str
        The formatted user message ready for the LLM.
    """
    context_blocks = build_context_blocks(chunks)
    return (
        f"Question:\n{question}\n\n"
        f"Context (retrieved from technical manuals):\n\n"
        f"{context_blocks}\n\n"
        f"Answer the question using ONLY the context above.\n"
        f"Reference each source by its [N] label inline.\n"
        f'Include a "Sources:" section at the end.'
    )

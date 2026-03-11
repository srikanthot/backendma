# Technical Manuals Chatbot API

A **backend-only** chatbot API for technical manuals, built with **Microsoft Agent Framework SDK** for orchestration, **Azure AI Search** for retrieval, and **Azure OpenAI** for generation.

This backend is **frontend-agnostic** — it exposes stable JSON endpoints suitable for any future frontend: React, Power Apps, PCF, custom web UIs, mobile apps, or any enterprise internal UI.

## Authentication

This version uses **managed identity / Microsoft Entra ID** authentication for all Azure services. **No API keys are used.**

| Environment | Credential Used |
|-------------|----------------|
| **Local development** | Your signed-in Azure developer identity (`az login` or VS Code Azure sign-in) |
| **Azure App Service** | System-assigned managed identity |

The code uses `DefaultAzureCredential` from the `azure-identity` package, which automatically selects the best available credential for the current environment. The credential is passed directly to the Azure SDKs — no manual token fetching, no `AZURE_OPENAI_API_KEY` environment variable, and token refresh is handled automatically by the SDKs via `get_bearer_token_provider()`.

## Architecture

    POST /chat
         |
         v
    routes.py            (thin: validate -> delegate to runtime)
         |
         v
    AgentRuntime.run()   (orchestration layer)
      1. retrieve()      (hybrid Azure AI Search: keyword + vector)
      2. GATE            (insufficient evidence check)
      3. rag_provider    (store chunks in Agent Framework session state)
      4. af_agent.run()  (Agent Framework ChatAgent -> AzureOpenAIChatClient)
           |              - RagContextProvider.before_run() injects context
           |              - LLM generates grounded answer
      5. citations       (structured citations from retrieval results)
         |
         v
    ChatResponse JSON    (answer + citations + session_id)

### Key Design Principles

- **FastAPI** is only the HTTP/API transport layer
- **Microsoft Agent Framework SDK** handles all LLM orchestration
- **Retrieval** is a separate, tunable module
- **Prompt/context preparation** is a separate module
- **Route handlers** stay thin — they only validate and delegate
- **No API keys** — uses managed identity / Entra ID for all Azure services
- **No frontend code** — purely backend
- **No Docker** — deploys directly to Azure App Service
- **No streaming** — returns normal JSON responses
- **No persistent history** — each request is a standalone single-turn interaction
- **No in-memory history** — no InMemoryHistoryProvider or similar abstraction
- **session_id** is a pass-through field only — echoed from request to response for future multi-turn support, but no conversation state is stored or restored in this version

## Endpoints

| Method | Path      | Description                                    |
|--------|-----------|------------------------------------------------|
| GET    | `/health` | Health check for deployment verification       |
| POST   | `/chat`   | Primary endpoint — returns grounded answer + citations |
| GET    | `/docs`   | Swagger/OpenAPI interactive documentation      |
| GET    | `/redoc`  | ReDoc API documentation                        |

### POST /chat — Request

```json
{
  "question": "What safety steps should be followed before servicing the unit?",
  "session_id": "abc123"
}
```

- `question` (required): The user’s question about technical manuals.
- `session_id` (optional): Pass-through identifier. Echoed back in the response. No state is stored or restored.

### POST /chat — Response

```json
{
  "answer": "According to the service manual...",
  "citations": [
    {
      "title": "Service Manual XYZ",
      "source": "service_manual_xyz.pdf",
      "chunk_id": "chunk_042",
      "section": "Safety Procedures > Pre-Service Checklist",
      "page": "12"
    }
  ],
  "session_id": "abc123"
}
```

## Azure RBAC Requirements

Both your **local developer identity** and the **App Service managed identity** need the following RBAC role assignments on the respective Azure resources.

### Azure OpenAI

| Role | Scope | Purpose |
|------|-------|---------|
| **Cognitive Services OpenAI User** | Your Azure OpenAI resource | Allows chat completions and embeddings inference |

Assign this role to:
1. **Your Azure AD user account** (for local development)
2. **The App Service system-assigned managed identity** (for production)

How to assign (Azure CLI):

```bash
# For your local developer identity
az role assignment create \
  --assignee "<your-azure-ad-user-object-id>" \
  --role "Cognitive Services OpenAI User" \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<openai-resource>"

# For the App Service managed identity
az role assignment create \
  --assignee "<app-service-managed-identity-principal-id>" \
  --role "Cognitive Services OpenAI User" \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<openai-resource>"
```

### Azure AI Search

| Role | Scope | Purpose |
|------|-------|---------|
| **Search Index Data Reader** | Your Azure AI Search resource | Allows querying the search index |

Assign this role to:
1. **Your Azure AD user account** (for local development)
2. **The App Service system-assigned managed identity** (for production)

How to assign (Azure CLI):

```bash
# For your local developer identity
az role assignment create \
  --assignee "<your-azure-ad-user-object-id>" \
  --role "Search Index Data Reader" \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-resource>"

# For the App Service managed identity
az role assignment create \
  --assignee "<app-service-managed-identity-principal-id>" \
  --role "Search Index Data Reader" \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-resource>"
```

> **Important:** RBAC role assignments can take a few minutes to propagate. If you get 403 errors immediately after assigning roles, wait 5-10 minutes and try again.

## Local Setup

### Prerequisites

- Python 3.10+
- Azure CLI installed and signed in (`az login`)
- Azure OpenAI resource with chat and embeddings deployments
- Azure AI Search resource with a configured index
- RBAC roles assigned to your Azure AD identity (see above)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd technical-manuals-chatbot

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Azure resource URLs and index configuration
# NOTE: No API keys needed — authentication uses your Azure identity
```

### Environment Variables

All configuration is driven by environment variables. See `.env.example` for the complete list.

**Azure OpenAI (no API key needed):**
- `AZURE_OPENAI_ENDPOINT` — Azure OpenAI resource URL
- `AZURE_OPENAI_API_VERSION` — API version (e.g., `2024-06-01`)
- `AZURE_OPENAI_CHAT_DEPLOYMENT` — Chat model deployment name
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` — Embeddings model deployment name

**Azure AI Search (no API key needed):**
- `AZURE_SEARCH_ENDPOINT` — Search service URL
- `AZURE_SEARCH_INDEX` — Index name

**Index Field Mappings:**
- `SEARCH_CONTENT_FIELD` — Main content field (default: `chunk`)
- `SEARCH_VECTOR_FIELD` — Vector field name (default: `text_vector`)
- `SEARCH_TITLE_FIELD` — Document title field (default: `title`)
- `SEARCH_FILENAME_FIELD` — Source filename field (default: `source_file`)
- `SEARCH_URL_FIELD` — Source URL field (default: `source_url`)
- `SEARCH_CHUNK_ID_FIELD` — Chunk ID field (default: `chunk_id`)
- `SEARCH_PAGE_FIELD` — Page number field (leave blank if not available)
- `SEARCH_SECTION1_FIELD` — Section header level 1 (default: `header_1`)
- `SEARCH_SECTION2_FIELD` — Section header level 2 (default: `header_2`)
- `SEARCH_SECTION3_FIELD` — Section header level 3 (default: `header_3`)

**Retrieval Tuning (most important for answer quality):**
- `TOP_K` — Number of final chunks after filtering (default: `5`)
- `VECTOR_K` — Vector search nearest neighbors (default: `50`)
- `MAX_CONTEXT_CHUNKS` — Hard cap on prompt context chunks (default: `5`)
- `RETRIEVAL_CANDIDATES` — Candidates to fetch before filtering (default: `20`)

**Retrieval Quality Thresholds:**
- `MIN_RELEVANCE_SCORE` — Minimum base hybrid score (default: `0.01`)
- `MIN_RERANKER_SCORE` — Minimum reranker score when active (default: `0.5`)
- `USE_SEMANTIC_RERANKER` — Enable semantic reranker (default: `true`)
- `SEMANTIC_CONFIG_NAME` — Semantic configuration name
- `SCORE_GAP_RATIO` — Drop chunks below this fraction of top score (default: `0.40`)
- `MAX_CHUNKS_PER_SOURCE` — Max chunks from one source (default: `3`)
- `DEDUP_SIMILARITY_THRESHOLD` — Jaccard similarity for dedup (default: `0.85`)
- `MIN_CHUNK_LENGTH` — Minimum content length in chars to keep a chunk (default: `50`)

**CORS:**
- `ALLOWED_ORIGINS` — Comma-separated allowed origins

**Diagnostics:**
- `TRACE_MODE` — Enable detailed retrieval logging (default: `true`)
- `LOG_LEVEL` — Logging level (default: `INFO`)

### Run Locally

```bash
# Make sure you are signed in to Azure
az login

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Test Locally

1. Open Swagger UI: http://localhost:8000/docs
2. Test health check: `GET /health`
3. Test chat: `POST /chat` with body:
```json
{
  "question": "What safety steps should be followed before servicing the unit?",
  "session_id": "test-session"
}
```

## Azure App Service Deployment

### Startup Command

```
gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
```

### Deployment Steps

1. Create an Azure App Service (Python 3.10+ Linux)
2. **Enable system-assigned managed identity** on the App Service:
   - Go to App Service > Identity > System assigned > Status: **On**
3. **Assign RBAC roles** to the managed identity (see Azure RBAC Requirements above)
4. Set environment variables from `.env.example` in App Service Configuration
   - Do **NOT** set any API key variables — authentication is handled by managed identity
5. Deploy from VS Code using the Azure App Service extension
6. Set the startup command in App Service Configuration > General Settings
7. Verify deployment: `GET https://<your-app>.azurewebsites.net/health`

## Project Structure

    technical-manuals-chatbot/
    +-- app/
    |   +-- __init__.py
    |   +-- main.py                        # FastAPI app factory, CORS, health check
    |   +-- api/
    |   |   +-- routes.py                  # Thin route handlers (POST /chat)
    |   |   +-- schemas.py                 # Request/response Pydantic models
    |   +-- config/
    |   |   +-- settings.py                # All configuration from env vars
    |   |   +-- logging_config.py          # Logging setup
    |   +-- agent_runtime/
    |   |   +-- agent_factory.py           # Agent Framework SDK + Entra ID auth
    |   |   +-- runtime.py                 # Full orchestration pipeline
    |   |   +-- context_provider.py        # Agent Framework BaseContextProvider (RAG only)
    |   +-- retrieval/
    |   |   +-- search_client.py           # Azure AI Search + embeddings (Entra ID auth)
    |   |   +-- retrieval_service.py       # Main retrieval entry point
    |   |   +-- ranking.py                 # Post-retrieval filtering (7-stage pipeline)
    |   |   +-- citations.py               # Citation builder
    |   +-- llm/
    |   |   +-- prompt_builder.py          # System prompt + context assembly
    |   +-- models/
    |   |   +-- retrieval_models.py        # RetrievalChunk, RetrievalResult
    |   +-- utils/
    |       +-- errors.py                  # Custom exceptions + HTTP error helpers
    |       +-- helpers.py                 # Query normalization, text similarity
    +-- requirements.txt                   # All dependencies (includes azure-identity)
    +-- .env.example                       # Environment variable template (no API keys)
    +-- .gitignore
    +-- README.md

## Where Retrieval Is Implemented

| File | Purpose |
|------|---------|
| `app/retrieval/retrieval_service.py` | Main entry point — orchestrates the full retrieval pipeline |
| `app/retrieval/ranking.py` | Post-retrieval filtering: content-length, thresholds, TOC, dedup, diversity, score-gap |
| `app/retrieval/search_client.py` | Azure AI Search client (Entra ID auth) and embedding generation |
| `app/retrieval/citations.py` | Builds structured citations from retrieval results |
| `app/models/retrieval_models.py` | RetrievalChunk and RetrievalResult data models |
| `app/utils/helpers.py` | Query normalization and text similarity utilities |

## Settings That Most Affect Retrieval Quality

1. **`MIN_RELEVANCE_SCORE`** / **`MIN_RERANKER_SCORE`** — Absolute quality floor.
2. **`SCORE_GAP_RATIO`** — Relative quality filter.
3. **`TOP_K`** / **`MAX_CONTEXT_CHUNKS`** — How many chunks reach the LLM.
4. **`RETRIEVAL_CANDIDATES`** — How wide to cast the initial net.
5. **`MAX_CHUNKS_PER_SOURCE`** — Prevents one manual from dominating.
6. **`DEDUP_SIMILARITY_THRESHOLD`** — Controls duplicate removal.
7. **`MIN_CHUNK_LENGTH`** — Minimum content length to keep a chunk.
8. **`USE_SEMANTIC_RERANKER`** — Enables Azure neural reranker.
9. **`VECTOR_K`** — Vector search breadth.

## Where Future Tuning Can Happen

- **Retrieval thresholds:** `app/config/settings.py` (all configurable via env vars)
- **Ranking pipeline:** `app/retrieval/ranking.py` (add/remove/reorder filter stages)
- **Query normalization:** `app/utils/helpers.py` (improve keyword distillation)
- **Prompt engineering:** `app/llm/prompt_builder.py` (adjust system prompt and context format)
- **Context injection:** `app/agent_runtime/context_provider.py` (modify how context reaches the LLM)
- **Citation format:** `app/retrieval/citations.py` (adjust citation structure)

## Microsoft Agent Framework SDK

This backend uses the **self-hosted Microsoft Agent Framework SDK** pattern:

- `agent-framework-core` package in `requirements.txt`
- `AzureOpenAIChatClient` from `agent_framework.azure` manages the Azure OpenAI connection
- `DefaultAzureCredential` is passed directly to `AzureOpenAIChatClient(credential=...)` — the SDK internally uses `get_bearer_token_provider()` for automatic token caching and refresh
- `BaseContextProvider` is implemented as `RagContextProvider` for RAG context injection
- Agent is created via `.as_agent()` with RagContextProvider as the only context provider
- The agent runtime calls `af_agent.run()` — all LLM interaction goes through the framework
- **No history provider** is wired in this version — each request is a standalone single-turn interaction
- **No API keys** — no `AZURE_OPENAI_API_KEY` environment variable is set or read at runtime

This is NOT a plain FastAPI chat wrapper — the Agent Framework SDK is the actual orchestration layer.

## No-History Design (This Version)

This version is intentionally **stateless per-request**:

- No `InMemoryHistoryProvider` — removed from the orchestration path
- No persistent history (no Cosmos DB, no database, no file storage)
- No multi-turn conversation continuity
- `session_id` exists only as a **pass-through** field in the request/response contract
- Each `/chat` request creates a fresh `AgentSession` with no prior state
- The agent receives only the current question + retrieved context from Azure AI Search

To add multi-turn support in a future version, wire a history/memory provider in `agent_factory.py` alongside the existing `RagContextProvider`.

"""Microsoft Agent Framework singleton -- AzureOpenAIChatClient + Agent.

Reads configuration from environment variables (loaded by settings.py at
import time via python-dotenv):

  AZURE_OPENAI_ENDPOINT             - Azure OpenAI resource URL
  AZURE_OPENAI_API_VERSION          - e.g. 2024-06-01
  AZURE_OPENAI_CHAT_DEPLOYMENT      - chat model deployment name

AUTHENTICATION:
  Uses DefaultAzureCredential from azure-identity, which is passed
  directly to AzureOpenAIChatClient via its ``credential`` parameter.
  The SDK internally converts the credential into a token provider using
  ``get_bearer_token_provider()``, which handles token caching and
  automatic refresh — no manual token management is needed.

  - Locally: your signed-in Azure developer identity (az login / VS Code)
  - Azure App Service: the system-assigned managed identity

  No API keys are used. No AZURE_OPENAI_API_KEY environment variable is
  set or read at runtime.

The module exposes two singletons used by the agent runtime:
  af_agent     - the configured Agent instance
  rag_provider - the RagContextProvider instance (shared so the runtime
                 can pre-load results before each agent.run() call)

This is the file that PROVES Microsoft Agent Framework SDK usage:
- Imports from agent_framework
- Creates AzureOpenAIChatClient with credential=DefaultAzureCredential()
- Creates an Agent via .as_agent()
- Wires RagContextProvider as a context_provider

NO-HISTORY DESIGN:
  This version intentionally does NOT include InMemoryHistoryProvider or
  any other history/memory provider. Each /chat request is a standalone
  single-turn interaction. The agent receives only the current question
  plus retrieved context -- no conversation history is carried over.
  History/memory can be added in a future version by wiring a provider here.
"""

import logging

from azure.identity import DefaultAzureCredential
from agent_framework.azure import AzureOpenAIChatClient

from app.agent_runtime.context_provider import RagContextProvider
from app.config.settings import (
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_CHAT_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
)
from app.llm.prompt_builder import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Shared provider instance -- the runtime calls rag_provider.store_results()
# before agent.run() so the provider can inject the pre-fetched chunks.
rag_provider = RagContextProvider()

# ---------------------------------------------------------------------------
# Azure AD credential -- works locally (developer identity) and in
# Azure App Service (system-assigned managed identity).
#
# DefaultAzureCredential is passed directly to AzureOpenAIChatClient.
# The SDK internally uses get_bearer_token_provider() which handles:
#   - Token caching (avoids redundant token requests)
#   - Automatic refresh before expiry
#   - Scoping to https://cognitiveservices.azure.com/.default
# No manual token fetch, no AZURE_OPENAI_API_KEY env var needed.
# ---------------------------------------------------------------------------
_credential = DefaultAzureCredential()

logger.info("Creating AzureOpenAIChatClient with managed identity / Entra ID credential")

_client = AzureOpenAIChatClient(
    endpoint=AZURE_OPENAI_ENDPOINT,
    deployment_name=AZURE_OPENAI_CHAT_DEPLOYMENT,
    api_version=AZURE_OPENAI_API_VERSION,
    credential=_credential,
)

af_agent = _client.as_agent(
    name="TechnicalManualAgent",
    instructions=SYSTEM_PROMPT,
    context_providers=[
        # RagContextProvider injects the pre-retrieved Azure AI Search chunks
        # as additional instructions before every LLM call.
        # This is the ONLY context provider for this no-history version.
        # To add multi-turn memory later, wire a history/memory provider
        # here alongside the rag_provider.
        rag_provider,
    ],
)

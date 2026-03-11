"""Azure AI Search client wrapper.

Provides a configured SearchClient instance and query embedding generation.
Isolates all Azure SDK authentication and client construction so the rest
of the retrieval layer works with clean abstractions.

AUTHENTICATION:
  Uses DefaultAzureCredential from azure-identity, which automatically
  selects the best available credential:
  - Locally: your signed-in Azure developer identity (az login / VS Code)
  - Azure App Service: the system-assigned managed identity

  For Azure AI Search: DefaultAzureCredential is passed directly to the
  SearchClient, which handles token acquisition and refresh internally.

  For Azure OpenAI embeddings: get_bearer_token_provider() wraps the
  credential into a callable that the OpenAI SDK uses for automatic
  token caching and refresh. No manual token fetch is needed.

  No API keys are used in this version.
"""

import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from app.config.settings import (
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
)

logger = logging.getLogger(__name__)

# Shared credential instance -- DefaultAzureCredential handles both
# local developer identity and App Service managed identity automatically.
_credential = DefaultAzureCredential()

# Token provider for Azure OpenAI — wraps DefaultAzureCredential with
# automatic token caching and refresh. The provider is a callable that
# returns a fresh bearer token string each time it is invoked.
_openai_token_provider = get_bearer_token_provider(
    _credential, "https://cognitiveservices.azure.com/.default"
)


def get_search_client() -> SearchClient:
    """Return a configured Azure AI Search client.

    Uses DefaultAzureCredential for authentication (managed identity in
    Azure App Service, developer identity locally).
    """
    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=_credential,
    )


def generate_query_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given query text.

    Uses the Azure OpenAI embeddings deployment configured in settings.
    Authentication is via a token provider backed by DefaultAzureCredential,
    which handles token caching and automatic refresh.

    Parameters
    ----------
    text:
        The query string to embed. Typically the user's original question
        (not the distilled keyword version).

    Returns
    -------
    list[float]
        Embedding vector from the configured embeddings deployment.

    Raises
    ------
    openai.OpenAIError
        Propagated to the caller for handling.
    """
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=_openai_token_provider,
        api_version=AZURE_OPENAI_API_VERSION,
    )

    response = client.embeddings.create(
        model=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        input=text,
    )

    return response.data[0].embedding

"""
Knowledge retrieval using Azure AI Search with agent-framework.

Diagram:

 Input ──▶ Agent ──────────────────▶ LLM ──▶ Response
             │                        ▲
             │  search with input     │ relevant knowledge
             ▼                        │
         ┌────────────┐               │
         │ Knowledge  │───────────────┘
         │   store    │
         │ (Azure AI  │
         │  Search)   │
         └────────────┘

This example uses the built-in AzureAISearchContextProvider in agentic
mode, which handles the entire retrieval pipeline — no custom
ContextProvider subclass needed. Agentic mode uses Knowledge Bases
for multi-hop reasoning across documents, providing accurate results
through intelligent query planning.

Requires:
  - An Azure AI Search service with a Knowledge Base
  - An OpenAI-compatible model endpoint (Azure OpenAI or OpenAI)

Environment variables:
  - AZURE_SEARCH_ENDPOINT: Your Azure AI Search endpoint
  - AZURE_SEARCH_KNOWLEDGE_BASE_NAME: Your Knowledge Base name
  - Plus the standard API_HOST / model config (see other examples)

See also:
  - agent_knowledge_sqlite.py for keyword-only search with SQLite
  - agent_knowledge_postgres.py for hybrid search with PostgreSQL + pgvector
"""

import asyncio
import logging
import os
import sys

from agent_framework import Agent
from agent_framework.azure import AzureAISearchContextProvider
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich import print
from rich.logging import RichHandler

# ── Logging ──────────────────────────────────────────────────────────
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Configuration ────────────────────────────────────────────────────
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
KNOWLEDGE_BASE_NAME = os.environ["AZURE_SEARCH_KNOWLEDGE_BASE_NAME"]

# ── OpenAI client ────────────────────────────────────────────────────

async_credential = None
if API_HOST == "azure":
    async_credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
else:
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )

# ── Azure AI Search context provider ─────────────────────────────────

search_credential = DefaultAzureCredential()

search_provider = AzureAISearchContextProvider(
    endpoint=SEARCH_ENDPOINT,
    credential=search_credential,
    knowledge_base_name=KNOWLEDGE_BASE_NAME,
    mode="agentic",
)

# ── Agent ────────────────────────────────────────────────────────────

agent = Agent(
    client=client,
    name="search-agent",
    instructions=(
        "You are a helpful home improvement shopping assistant. "
        "Answer customer questions using the product information provided in the context. "
        "If no relevant products are found, say you don't have information about that item. "
    ),
    context_providers=[search_provider],
)


async def main() -> None:
    """Demonstrate Azure AI Search RAG in a multi-turn conversation."""
    async with search_provider:
        print("\n[bold]=== Knowledge Retrieval with Azure AI Search (agentic mode) ===[/bold]")
        print(f"[dim]Knowledge Base: {KNOWLEDGE_BASE_NAME}[/dim]\n")

        session = agent.create_session()

        # Turn 1
        user_msg = "What kind of interior paint do you have for a living room?"
        print(f"[blue]User:[/blue] {user_msg}")
        response = await agent.run(user_msg, session=session)
        print(f"[green]Agent:[/green] {response.text}\n")

        # Turn 2 — follow-up referencing the previous answer
        user_msg = "What supplies do I need to apply it?"
        print(f"[blue]User:[/blue] {user_msg}")
        response = await agent.run(user_msg, session=session)
        print(f"[green]Agent:[/green] {response.text}\n")

    if async_credential:
        await async_credential.close()
    await search_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())

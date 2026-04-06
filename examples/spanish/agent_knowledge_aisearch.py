"""Recuperación de conocimiento usando Azure AI Search con agent-framework.

Diagrama:

 Entrada ──▶ Agente ──────────────────▶ LLM ──▶ Respuesta
                            │                        ▲
                            │  buscar con entrada    │ conocimiento relevante
                            ▼                        │
                 ┌────────────┐                │
                 │   Base de   │────────────────┘
                 │ conocimiento│
                 │ (Azure AI   │
                 │  Search)    │
                 └────────────┘

Este ejemplo usa el AzureAISearchContextProvider incorporado en modo
agentic, que maneja toda la canalización de recuperación: no necesitas
crear una subclase de ContextProvider. El modo agentic usa Knowledge
Bases para razonamiento multi-hop entre documentos, dando resultados más
precisos mediante planeación inteligente de consultas.

Requiere:
    - Un servicio de Azure AI Search con una base de conocimiento (Knowledge Base)
    - Un endpoint compatible con OpenAI (Azure OpenAI u OpenAI)

Variables de entorno:
    - AZURE_SEARCH_ENDPOINT: Tu endpoint de Azure AI Search
    - AZURE_SEARCH_KNOWLEDGE_BASE_NAME: Nombre de tu base de conocimiento (Knowledge Base)
    - Además de la configuración estándar de API_HOST / modelo (ver otros ejemplos)

Ver también:
    - agent_knowledge_sqlite.py para búsqueda solo por palabras clave con SQLite
    - agent_knowledge_postgres.py para búsqueda híbrida con PostgreSQL + pgvector
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

# ── Configuración ───────────────────────────────────────────────────
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
KNOWLEDGE_BASE_NAME = os.environ["AZURE_SEARCH_KNOWLEDGE_BASE_NAME"]

# ── Cliente OpenAI ──────────────────────────────────────────────────

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

# ── Proveedor de contexto de Azure AI Search ────────────────────────

search_credential = DefaultAzureCredential()

search_provider = AzureAISearchContextProvider(
    endpoint=SEARCH_ENDPOINT,
    credential=search_credential,
    knowledge_base_name=KNOWLEDGE_BASE_NAME,
    mode="agentic",
)

# ── Agente ──────────────────────────────────────────────────────────

agent = Agent(
    client=client,
    name="search-agent",
    instructions=(
        "Eres un asistente útil de compras para mejoras del hogar. "
        "Responde preguntas del cliente usando la información de producto que venga en el contexto. "
        "Si no se encuentran productos relevantes, di que no tienes información sobre ese artículo. "
    ),
    context_providers=[search_provider],
)


async def main() -> None:
    """Demuestra RAG con Azure AI Search en una conversación multi-turno."""
    async with search_provider:
        print("\n[bold]=== Recuperación de conocimiento con Azure AI Search (modo agentic) ===[/bold]")
        print(f"[dim]Base de conocimiento: {KNOWLEDGE_BASE_NAME}[/dim]\n")

        session = agent.create_session()

        # Turno 1
        user_msg = "¿Qué tipo de pintura interior tienen para una sala?"
        print(f"[blue]Usuario:[/blue] {user_msg}")
        response = await agent.run(user_msg, session=session)
        print(f"[green]Agente:[/green] {response.text}\n")

        # Turno 2 — seguimiento basado en la respuesta anterior
        user_msg = "¿Qué materiales necesito para aplicarla?"
        print(f"[blue]Usuario:[/blue] {user_msg}")
        response = await agent.run(user_msg, session=session)
        print(f"[green]Agente:[/green] {response.text}\n")

    if async_credential:
        await async_credential.close()
    await search_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())

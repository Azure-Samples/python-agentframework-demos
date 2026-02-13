import asyncio
import logging
import os
import random
import uuid
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.mem0 import Mem0ContextProvider
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from mem0 import AsyncMemory
from pydantic import Field
from rich import print
from rich.logging import RichHandler

# Setup logging
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure OpenAI client based on environment
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")

async_credential = None
if API_HOST == "azure":
    async_credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model_id=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
elif API_HOST == "github":
    client = OpenAIChatClient(
        base_url="https://models.github.ai/inference",
        api_key=os.environ["GITHUB_TOKEN"],
        model_id=os.getenv("GITHUB_MODEL", "openai/gpt-5-mini"),
    )
else:
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model_id=os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    )


# NOTE: approval_mode="never_require" is for sample brevity.
# Use "always_require" in production.
@tool
def get_weather(
    city: Annotated[str, Field(description="The city to get the weather for.")],
) -> str:
    """Returns weather data for a given city."""
    logger.info(f"Getting weather for {city}")
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {city} is {conditions[random.randint(0, 3)]} with a high of {random.randint(10, 30)}°C."


async def main() -> None:
    """Demonstrate an agent with Mem0 OSS for long-term memory.

    Unlike RedisContextProvider (which stores raw messages), Mem0 uses an LLM to
    extract and store distilled facts from conversations. When the agent
    starts a new session, Mem0 injects relevant memories as context.

    Mem0 OSS needs an LLM and embedder for memory extraction. This example
    uses Azure OpenAI when API_HOST=azure, otherwise falls back to OPENAI_API_KEY.
    """
    print("\n[bold]=== Agent with Mem0 OSS Memory ===[/bold]")

    # Each user gets a unique ID so memories are scoped per user
    user_id = str(uuid.uuid4())

    # Configure Mem0 OSS to use Azure OpenAI or OpenAI for its LLM and embedder
    if API_HOST == "azure":
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        chat_deployment = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
        embedding_deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
        embedding_dims = 3072 if "large" in embedding_deployment else 1536
        mem0_config = {
            "llm": {
                "provider": "azure_openai",
                "config": {
                    "model": chat_deployment,
                    "azure_kwargs": {
                        "azure_deployment": chat_deployment,
                        "azure_endpoint": azure_endpoint,
                        "api_version": "2024-12-01-preview",
                    },
                },
            },
            "embedder": {
                "provider": "azure_openai",
                "config": {
                    "model": embedding_deployment,
                    "embedding_dims": embedding_dims,
                    "azure_kwargs": {
                        "azure_deployment": embedding_deployment,
                        "azure_endpoint": azure_endpoint,
                        "api_version": "2024-12-01-preview",
                    },
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "embedding_model_dims": embedding_dims,
                },
            },
        }
    elif os.getenv("OPENAI_API_KEY"):
        mem0_config = {}  # Mem0 defaults to OpenAI via OPENAI_API_KEY
    else:
        print("[red]Mem0 OSS requires an LLM for memory extraction.[/red]")
        print("[red]Set API_HOST=azure (with Azure OpenAI) or set OPENAI_API_KEY.[/red]")
        return

    mem0_client = await AsyncMemory.from_config(mem0_config)

    provider = Mem0ContextProvider(source_id="mem0_memory", user_id=user_id, mem0_client=mem0_client)

    agent = Agent(
        client=client,
        instructions=(
            "You are a helpful weather assistant. Personalize replies using provided context. "
            "Before answering, always check for stored context."
        ),
        tools=[get_weather],
        context_providers=[provider],
    )

    # Step 1: Teach the agent user preferences
    print("\n[dim]--- Step 1: Teaching preferences ---[/dim]")
    print("[blue]User:[/blue] Remember that my favorite city is Tokyo and I prefer Celsius.")
    response = await agent.run("Remember that my favorite city is Tokyo and I prefer Celsius.")
    print(f"[green]Agent:[/green] {response.text}")

    # Step 2: Start a new session — Mem0 should inject remembered facts
    print("\n[dim]--- Step 2: New session — recalling preferences ---[/dim]")
    print("[blue]User:[/blue] What's my favorite city?")
    response = await agent.run("What's my favorite city?")
    print(f"[green]Agent:[/green] {response.text}")
    print("[dim]Note: Mem0 extracted and stored facts, then injected them into the new session.[/dim]")

    # Step 3: Use a tool, demonstrating memory with tool outputs
    print("\n[dim]--- Step 3: Tool use with memory ---[/dim]")
    print("[blue]User:[/blue] What's the weather in my favorite city?")
    response = await agent.run("What's the weather in my favorite city?")
    print(f"[green]Agent:[/green] {response.text}")
    print("[dim]Note: The agent used Mem0 memory to know which city to check.[/dim]")

    # Show what Mem0 has stored
    print("\n[dim]--- Extracted memories ---[/dim]")
    memories = await mem0_client.get_all(user_id=user_id)
    for mem in memories.get("results", []):
        print(f"  [cyan]•[/cyan] {mem.get('memory', '')}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

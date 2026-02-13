import asyncio
import logging
import os
import random
import uuid
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework.redis import RedisContextProvider
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
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
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

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


async def example_agent_with_memory() -> None:
    """Demonstrate an agent with Redis-backed long-term memory via RedisContextProvider.

    The RedisContextProvider stores conversational context in Redis and retrieves it
    using full-text search (BM25), or hybrid search (BM25 + vector similarity)
    when an embedding model is configured.

    Requires Redis Stack (with RediSearch module) — see docker-compose.yaml.
    """
    print("\n[bold]=== Agent with Redis Memory (RedisProvider) ===[/bold]")

    user_id = str(uuid.uuid4())

    # RedisContextProvider supports hybrid search (full-text + vector) when a vectorizer is configured.
    # However, there is currently a version mismatch between agent-framework-redis and redisvl
    # (the HybridQuery API changed), so this example uses text-only search for now.
    memory_provider = RedisContextProvider(
        source_id="redis_memory",
        redis_url=REDIS_URL,
        index_name="agent_memory_demo",
        prefix="memory_demo",
        application_id="weather_app",
        agent_id="weather_agent",
        user_id=user_id,
        overwrite_index=True,
    )

    agent = Agent(
        client=client,
        instructions=(
            "You are a helpful weather assistant. Personalize replies using provided context. "
            "Before answering, always check for stored context."
        ),
        tools=[get_weather],
        context_providers=[memory_provider],
    )

    # Step 1: Teach the agent a user preference
    print("\n[dim]--- Step 1: Teaching a preference ---[/dim]")
    print("[blue]User:[/blue] Remember that my favorite city is Tokyo.")
    response = await agent.run("Remember that my favorite city is Tokyo.")
    print(f"[green]Agent:[/green] {response.text}")

    # Step 2: Ask the agent to recall the preference from memory
    print("\n[dim]--- Step 2: Recalling a preference ---[/dim]")
    print("[blue]User:[/blue] What's my favorite city?")
    response = await agent.run("What's my favorite city?")
    print(f"[green]Agent:[/green] {response.text}")

    # Step 3: Use a tool, then verify the agent remembers tool output details
    print("\n[dim]--- Step 3: Tool use with memory ---[/dim]")
    print("[blue]User:[/blue] What's the weather in Paris?")
    response = await agent.run("What's the weather in Paris?")
    print(f"[green]Agent:[/green] {response.text}")

    print("\n[blue]User:[/blue] What city did I just ask about and what was the weather?")
    response = await agent.run("What city did I just ask about and what was the weather?")
    print(f"[green]Agent:[/green] {response.text}")


async def main() -> None:
    """Run the Redis memory example."""
    # Verify Redis has RediSearch module
    import redis as redis_client

    r = redis_client.from_url(REDIS_URL)
    try:
        r.execute_command("FT._LIST")
    except Exception:
        print(f"[red]Redis at {REDIS_URL} does not have the RediSearch module.[/red]")
        return
    finally:
        r.close()

    print("[dim]Redis Stack with RediSearch verified.[/dim]")

    await example_agent_with_memory()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

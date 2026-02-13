import asyncio
import logging
import os
import random
import uuid
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework.redis import RedisHistoryProvider
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


@tool
def get_weather(
    city: Annotated[str, Field(description="The city to get the weather for.")],
) -> str:
    """Returns weather data for a given city."""
    logger.info(f"Getting weather for {city}")
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {city} is {conditions[random.randint(0, 3)]} with a high of {random.randint(10, 30)}°C."


async def example_persistent_session() -> None:
    """A Redis-backed session persists conversation history across application restarts."""
    print("\n[bold]=== Persistent Redis Session ===[/bold]")

    session_id = str(uuid.uuid4())

    # Phase 1: Start a conversation with a Redis-backed history provider
    print("[dim]--- Phase 1: Starting conversation ---[/dim]")
    redis_provider = RedisHistoryProvider(source_id="redis_chat", redis_url=REDIS_URL)

    agent = Agent(
        client=client,
        instructions="You are a helpful weather agent.",
        tools=[get_weather],
        context_providers=[redis_provider],
    )

    session = agent.create_session(session_id=session_id)

    print("[blue]User:[/blue] What's the weather like in Tokyo?")
    response = await agent.run("What's the weather like in Tokyo?", session=session)
    print(f"[green]Agent:[/green] {response.text}")

    print("\n[blue]User:[/blue] How about Paris?")
    response = await agent.run("How about Paris?", session=session)
    print(f"[green]Agent:[/green] {response.text}")

    # Phase 2: Simulate an application restart — reconnect using the same session ID in Redis
    print("\n[dim]--- Phase 2: Resuming after 'restart' ---[/dim]")
    redis_provider2 = RedisHistoryProvider(source_id="redis_chat", redis_url=REDIS_URL)

    agent2 = Agent(
        client=client,
        instructions="You are a helpful weather agent.",
        tools=[get_weather],
        context_providers=[redis_provider2],
    )

    session2 = agent2.create_session(session_id=session_id)

    print("[blue]User:[/blue] Which of the cities I asked about had better weather?")
    response = await agent2.run("Which of the cities I asked about had better weather?", session=session2)
    print(f"[green]Agent:[/green] {response.text}")
    print("[dim]Note: The agent remembered the conversation from Phase 1 via Redis persistence.[/dim]")


async def main() -> None:
    """Run all Redis session examples to demonstrate persistent storage patterns."""
    # Verify Redis connectivity
    import redis as redis_client

    r = redis_client.from_url(REDIS_URL)
    try:
        r.ping()
    except Exception as e:
        print(f"[red]Cannot connect to Redis at {REDIS_URL}: {e}[/red]")
        print(
            "[red]Ensure Redis is running (e.g. via the dev container"
            " or 'docker run -p 6379:6379 redis:7-alpine').[/red]"
        )
        return
    finally:
        r.close()

    print("[dim]Redis connection verified.[/dim]")

    await example_persistent_session()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

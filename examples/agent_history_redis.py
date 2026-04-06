# Note: Do not add tools= to agents using history providers — causes duplicate item errors
# with the Responses API. See https://github.com/microsoft/agent-framework/issues/3295
import asyncio
import logging
import os
import uuid

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework.redis import RedisHistoryProvider
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich import print
from rich.logging import RichHandler

# Setup logging
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure OpenAI client based on environment
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

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


async def example_persistent_session() -> None:
    """A Redis-backed session persists conversation history across application restarts."""
    print("\n[bold]=== Persistent Redis Session ===[/bold]")

    session_id = str(uuid.uuid4())

    # Phase 1: Start a conversation with a Redis-backed history provider
    print("[bold]--- Phase 1: Starting conversation ---[/bold]")
    redis_provider = RedisHistoryProvider(source_id="redis_chat", redis_url=REDIS_URL)

    agent = Agent(
        client=client,
        instructions="You are a helpful assistant that remembers our conversation.",
        context_providers=[redis_provider],
    )

    session = agent.create_session(session_id=session_id)

    print("[blue]User:[/blue] Hello! My name is Alice and I love hiking.")
    response = await agent.run("Hello! My name is Alice and I love hiking.", session=session)
    print(f"[green]Agent:[/green] {response.text}")

    print("\n[blue]User:[/blue] What are some good trails in Colorado?")
    response = await agent.run("What are some good trails in Colorado?", session=session)
    print(f"[green]Agent:[/green] {response.text}")

    # Phase 2: Simulate an application restart — reconnect using the same session ID in Redis
    print("\n[bold]--- Phase 2: Resuming after 'restart' ---[/bold]")
    redis_provider2 = RedisHistoryProvider(source_id="redis_chat", redis_url=REDIS_URL)

    agent2 = Agent(
        client=client,
        instructions="You are a helpful assistant that remembers our conversation.",
        context_providers=[redis_provider2],
    )

    session2 = agent2.create_session(session_id=session_id)

    print("[blue]User:[/blue] What do you remember about me?")
    response = await agent2.run("What do you remember about me?", session=session2)
    print(f"[green]Agent:[/green] {response.text}")


async def main() -> None:
    """Run all Redis session examples to demonstrate persistent storage patterns."""
    # Verify Redis connectivity
    import redis as redis_client

    r = redis_client.from_url(REDIS_URL)
    try:
        r.ping()
    except Exception as e:
        logger.error(f"Cannot connect to Redis at {REDIS_URL}: {e}")
        logger.error(
            "Ensure Redis is running (e.g. via the dev container" " or 'docker run -p 6379:6379 redis:7-alpine')."
        )
        return
    finally:
        r.close()

    await example_persistent_session()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

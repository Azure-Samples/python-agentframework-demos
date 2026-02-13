import asyncio
import logging
import os
import random
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
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
    client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model_id=os.environ.get("OPENAI_MODEL", "gpt-5-mini"))


@tool
def get_weather(
    city: Annotated[str, Field(description="The city to get the weather for.")],
) -> str:
    """Returns weather data for a given city."""
    logger.info(f"Getting weather for {city}")
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {city} is {conditions[random.randint(0, 3)]} with a high of {random.randint(10, 30)}°C."


agent = Agent(
    client=client,
    instructions="You are a helpful weather agent.",
    tools=[get_weather],
)


async def example_without_session() -> None:
    """Without a session, each call is independent — the agent has no memory of prior messages."""
    print("\n[bold]=== Without Session (No Memory) ===[/bold]")

    response = await agent.run("What's the weather like in Seattle?")
    print(f"[blue]User:[/blue] What's the weather like in Seattle?")
    print(f"[green]Agent:[/green] {response.text}")

    response = await agent.run("What was the last city I asked about?")
    print(f"\n[blue]User:[/blue] What was the last city I asked about?")
    print(f"[green]Agent:[/green] {response.text}")
    print("[dim]Note: Each call creates a separate session, so the agent doesn't remember previous context.[/dim]")


async def example_with_session() -> None:
    """With a session, the agent maintains context across multiple messages."""
    print("\n[bold]=== With Session (Persistent Memory) ===[/bold]")

    session = agent.create_session()

    print(f"[blue]User:[/blue] What's the weather like in Tokyo?")
    response = await agent.run("What's the weather like in Tokyo?", session=session)
    print(f"[green]Agent:[/green] {response.text}")

    print(f"\n[blue]User:[/blue] How about London?")
    response = await agent.run("How about London?", session=session)
    print(f"[green]Agent:[/green] {response.text}")

    print(f"\n[blue]User:[/blue] Which of those cities has better weather?")
    response = await agent.run("Which of those cities has better weather?", session=session)
    print(f"[green]Agent:[/green] {response.text}")
    print("[dim]Note: The agent remembers context from previous messages in the same session.[/dim]")


async def example_session_across_agents() -> None:
    """A session can be shared across different agent instances."""
    print("\n[bold]=== Session Across Agent Instances ===[/bold]")

    session = agent.create_session()

    print(f"[blue]User:[/blue] What's the weather in Paris?")
    response = await agent.run("What's the weather in Paris?", session=session)
    print(f"[green]Agent 1:[/green] {response.text}")

    # Create a second agent and continue with the same session
    agent2 = Agent(
        client=client,
        instructions="You are a helpful weather agent.",
        tools=[get_weather],
    )

    print(f"\n[blue]User:[/blue] What was the last city I asked about?")
    response = await agent2.run("What was the last city I asked about?", session=session)
    print(f"[green]Agent 2:[/green] {response.text}")
    print("[dim]Note: The second agent continues the conversation using the session's message history.[/dim]")


async def main() -> None:
    """Run all session examples to demonstrate different persistence patterns."""
    await example_without_session()
    await example_with_session()
    await example_session_across_agents()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
Middleware flow diagram:

 agent.run("user message")
 │
 ▼
 ┌─────────────────────────────────────────────┐
 │         Agent Middleware                    │
 │  (timing, blocking, logging)                │
 │                                             │
 │  ┌───────────────────────────────────────┐  │
 │  │       Chat Middleware                 │  │
 │  │  (logging, message counting)          │  │
 │  │                                       │  │
 │  │        ┌──────────────┐               │  │
 │  │        │   AI Model   │               │  │
 │  │        └──────┬───────┘               │  │
 │  │               │ tool calls            │  │
 │  │               ▼                       │  │
 │  │  ┌──────────────────────────────────┐ │  │
 │  │  │     Function Middleware          │ │  │
 │  │  │  (logging, timing)               │ │  │
 │  │  │                                  │ │  │
 │  │  │  get_weather(), get_date(), ...  │ │  │
 │  │  └──────────────────────────────────┘ │  │
 │  │               │                       │  │
 │  │               ▼                       │  │
 │  │        ┌──────────────┐               │  │
 │  │        │   AI Model   │               │  │
 │  │        │  (final ans) │               │  │
 │  │        └──────────────┘               │  │
 │  └───────────────────────────────────────┘  │
 └─────────────────────────────────────────────┘
 │
 ▼
 response
"""

import asyncio
import logging
import os
import random
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated

from agent_framework import (
    AgentMiddleware,
    AgentRunContext,
    AgentRunResponse,
    ChatAgent,
    ChatContext,
    ChatMessage,
    ChatMiddleware,
    FunctionInvocationContext,
    FunctionMiddleware,
    Role,
)
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
        model_id=os.getenv("GITHUB_MODEL", "openai/gpt-4o"),
    )
else:
    client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model_id=os.environ.get("OPENAI_MODEL", "gpt-4o"))


# ---- Tools ----


def get_weather(
    city: Annotated[str, Field(description="The city to get the weather for.")],
) -> dict:
    """Return weather data for a given city, a dictionary with temperature and description."""
    logger.info(f"Getting weather for {city}")
    if random.random() < 0.05:
        return {"temperature": 72, "description": "Sunny"}
    else:
        return {"temperature": 60, "description": "Rainy"}


def get_current_date() -> str:
    """Get the current date from the system and return as a string in format YYYY-MM-DD."""
    logger.info("Getting current date")
    return datetime.now().strftime("%Y-%m-%d")


# ---- Function-based middleware ----


async def timing_agent_middleware(
    context: AgentRunContext,
    next: Callable[[AgentRunContext], Awaitable[None]],
) -> None:
    """Agent middleware that logs execution timing."""
    start = time.perf_counter()
    logger.info("[⏲️ Timing][ Agent Middleware] Starting agent execution")

    await next(context)

    elapsed = time.perf_counter() - start
    logger.info(f"[⏲️ Timing][ Agent Middleware] Execution completed in {elapsed:.2f}s")


async def logging_function_middleware(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]],
) -> None:
    """Function middleware that logs function calls and results."""
    logger.info(f"[🪵 Logging][ Function Middleware] Calling {context.function.name} with args: {context.arguments}")

    await next(context)

    logger.info(f"[🪵 Logging][ Function Middleware] {context.function.name} returned: {context.result}")


async def logging_chat_middleware(
    context: ChatContext,
    next: Callable[[ChatContext], Awaitable[None]],
) -> None:
    """Chat middleware that logs AI interactions."""
    logger.info(f"[💬 Logging][ Chat Middleware] Sending {len(context.messages)} messages to AI")

    await next(context)

    logger.info("[💬 Logging][ Chat Middleware] AI response received")


# ---- Class-based middleware ----


class BlockingAgentMiddleware(AgentMiddleware):
    """Agent middleware that blocks requests containing forbidden words."""

    def __init__(self, blocked_words: list[str]) -> None:
        """Initialize with a list of words that should be blocked."""
        self.blocked_words = blocked_words

    async def process(
        self,
        context: AgentRunContext,
        next: Callable[[AgentRunContext], Awaitable[None]],
    ) -> None:
        """Check messages for blocked content and terminate if found."""
        last_message = context.messages[-1] if context.messages else None
        if last_message and last_message.text:
            for word in self.blocked_words:
                if word.lower() in last_message.text.lower():
                    logger.warning(f"[❌ Blocking][ Agent Middleware] Request blocked: contains '{word}'")
                    context.terminate = True
                    context.result = AgentRunResponse(
                        messages=[
                            ChatMessage(role=Role.ASSISTANT, text=f"Sorry, I can't process requests about '{word}'.")
                        ]
                    )
                    return

        await next(context)


class TimingFunctionMiddleware(FunctionMiddleware):
    """Function middleware that tracks execution time of each function call."""

    async def process(
        self,
        context: FunctionInvocationContext,
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        """Time the function execution and log the duration."""
        start = time.perf_counter()
        logger.info(f"[⌚️ Timing][ Function Middleware] Starting {context.function.name}")

        await next(context)

        elapsed = time.perf_counter() - start
        logger.info(f"[⌚️ Timing][ Function Middleware] {context.function.name} took {elapsed:.4f}s")


class MessageCountChatMiddleware(ChatMiddleware):
    """Chat middleware that tracks the total number of messages sent to the AI."""

    def __init__(self) -> None:
        """Initialize the message counter."""
        self.total_messages = 0

    async def process(
        self,
        context: ChatContext,
        next: Callable[[ChatContext], Awaitable[None]],
    ) -> None:
        """Count messages and log the running total."""
        self.total_messages += len(context.messages)
        logger.info(
            "[🔢 Message Count][ Chat Middleware] Messages in this request: %s, total so far: %s",
            len(context.messages),
            self.total_messages,
        )

        await next(context)

        logger.info("[🔢 Message Count][ Chat Middleware] Chat response received")


# ---- Agent setup ----

# Instantiate class-based middleware
blocking_middleware = BlockingAgentMiddleware(blocked_words=["nuclear", "classified"])
timing_function_middleware = TimingFunctionMiddleware()
message_count_middleware = MessageCountChatMiddleware()

agent = ChatAgent(
    name="middleware-demo",
    chat_client=client,
    instructions="You help users plan their weekends. Use the available tools to check the weather and date.",
    tools=[get_weather, get_current_date],
    middleware=[
        # Agent-level middleware applied to ALL runs
        timing_agent_middleware,
        blocking_middleware,
        logging_function_middleware,
        timing_function_middleware,
        logging_chat_middleware,
        message_count_middleware,
    ],
)


async def main() -> None:
    """Run the agent with different inputs to demonstrate middleware behavior."""
    # Normal request - all middleware fires
    logger.info("=== Normal Request ===")
    response = await agent.run("What's the weather like this weekend in San Francisco?")
    print(response.text)

    # Blocked request - blocking middleware terminates early
    logger.info("\n=== Blocked Request ===")
    response = await agent.run("Tell me about nuclear physics.")
    print(response.text)

    # Another normal request with run-level middleware
    logger.info("\n=== Request with Run-Level Middleware ===")

    async def extra_agent_middleware(
        context: AgentRunContext,
        next: Callable[[AgentRunContext], Awaitable[None]],
    ) -> None:
        """Run-level middleware that only applies to this specific run."""
        logger.info("[🏃🏽‍♀️ Run-Level Middleware] This middleware only applies to this run")
        await next(context)
        logger.info("[🏃🏽‍♀️ Run-Level Middleware] Run completed")

    response = await agent.run(
        "What's the weather like in Portland?",
        middleware=[extra_agent_middleware],
    )
    print(response.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())

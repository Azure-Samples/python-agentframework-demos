"""
Context compaction via summarization middleware.

When a conversation grows long, the accumulated messages can exceed the
model's context window or become expensive. This middleware monitors
cumulative token usage and, once a threshold is crossed, asks the LLM to
summarize the conversation so far. The summary replaces the old messages,
freeing up context space for future turns.

Diagram:

 agent.run("user message")
 │
 ▼
 ┌──────────────────────────────────────────────────┐
 │       SummarizationMiddleware (Agent-level)      │
 │                                                  │
 │  1. Check cumulative token usage                 │
 │  2. If over threshold → summarize old messages   │
 │     via LLM and replace them with summary        │
 │  3. call_next() → normal agent execution         │
 │  4. Track new token usage from response          │
 └──────────────────────────────────────────────────┘
 │
 ▼
 response

This uses agent-level middleware because summarization should happen
*before* the agent's normal processing (tool calls, chat, etc.) and
needs access to the full message history.
"""

import asyncio
import logging
import os
import random
import sys
from collections.abc import Awaitable, Callable
from typing import Annotated

from agent_framework import (
    Agent,
    AgentContext,
    AgentMiddleware,
    AgentResponse,
    InMemoryHistoryProvider,
    Message,
    tool,
)
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
from rich import print
from rich.logging import RichHandler

# ── Logging ──────────────────────────────────────────────────────────
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── OpenAI client ────────────────────────────────────────────────────
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

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
    client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4"))


# ── Tools ────────────────────────────────────────────────────────────


@tool
def get_weather(
    city: Annotated[str, Field(description="The city to get the weather for.")],
) -> str:
    """Return weather data for a given city."""
    conditions = ["sunny", "cloudy", "rainy", "snowy"]
    temp = random.randint(30, 90)
    return f"The weather in {city} is {random.choice(conditions)} with a high of {temp}°F."


@tool
def get_activities(
    city: Annotated[str, Field(description="The city to find activities in.")],
) -> str:
    """Return popular weekend activities for a given city."""
    all_activities = [
        "Visit the farmer's market",
        "Hike at the local state park",
        "Check out a food truck festival",
        "Go to the art museum",
        "Take a walking tour of downtown",
        "Visit the botanical garden",
        "Catch a live music show",
        "Try a new brunch spot",
    ]
    picked = random.sample(all_activities, k=3)
    return f"Popular activities in {city}: {', '.join(picked)}."


# ── Summarization Middleware ─────────────────────────────────────────

SUMMARIZE_PROMPT = (
    "You are a summarization assistant. Condense the following conversation "
    "into a concise summary that preserves all key facts, decisions, and context "
    "needed to continue the conversation. Write the summary in third person. "
    "Be concise but don't lose important details like specific cities, "
    "weather conditions, or recommendations that were discussed."
)


class SummarizationMiddleware(AgentMiddleware):
    """Agent middleware that summarizes conversation history when token usage exceeds a threshold.

    This implements the "context compaction" pattern: once cumulative token
    usage crosses a configurable threshold, the middleware asks the LLM to
    produce a summary of the conversation so far and replaces the old
    messages with that summary. This keeps the context window manageable
    for long-running conversations.

    The middleware accesses session history via ``session.state`` (where the
    built-in ``InMemoryHistoryProvider`` stores messages) and replaces it
    with a single summary message before the agent processes the next turn.
    """

    def __init__(
        self,
        client: OpenAIChatClient,
        token_threshold: int = 1000,
    ) -> None:
        """Initialize the summarization middleware.

        Args:
            client: The LLM client to use for generating summaries.
            token_threshold: Summarize when cumulative tokens exceed this value.
        """
        self.client = client
        self.token_threshold = token_threshold
        self.context_tokens = 0

    def _format_messages_for_summary(self, messages: list[Message]) -> str:
        """Format conversation messages into a text block for the summarizer."""
        lines: list[str] = []
        for msg in messages:
            if msg.text:
                lines.append(f"{msg.role}: {msg.text}")
        return "\n".join(lines)

    async def _summarize(self, messages: list[Message]) -> str:
        """Call the LLM to summarize the conversation messages."""
        conversation_text = self._format_messages_for_summary(messages)
        summary_messages = [
            Message(role="system", contents=[SUMMARIZE_PROMPT]),
            Message(role="user", contents=[f"Summarize this conversation:\n\n{conversation_text}"]),
        ]
        response = await self.client.get_response(summary_messages)
        return response.text or "No summary available."

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Check token usage and summarize if over threshold, then continue execution."""
        session = context.session

        # Before the agent runs: check if we should compact the history
        if session and self.context_tokens > self.token_threshold:
            history = session.state.get(InMemoryHistoryProvider.DEFAULT_SOURCE_ID, {}).get("messages", [])
            if len(history) > 2:
                logger.info(
                    "[📝 Summarization] Token usage (%d) exceeds threshold (%d). " "Summarizing %d history messages...",
                    self.context_tokens,
                    self.token_threshold,
                    len(history),
                )

                # Summarize the full history
                summary_text = await self._summarize(history)
                logger.info(
                    "[📝 Summarization] Summary: %s",
                    summary_text[:200] + "..." if len(summary_text) > 200 else summary_text,
                )

                # Replace session history with a single summary message
                session.state[InMemoryHistoryProvider.DEFAULT_SOURCE_ID]["messages"] = [
                    Message(role="assistant", contents=[f"[Summary of earlier conversation]\n{summary_text}"]),
                ]

                # Reset token counter after summarization
                self.context_tokens = 0
                logger.info("[📝 Summarization] History compacted to 1 summary message")
        else:
            logger.info(
                "[📝 Summarization] Token usage: %d / %d threshold. No summarization needed.",
                self.context_tokens,
                self.token_threshold,
            )

        # Execute the agent (loads history from session, calls LLM, saves response)
        await call_next()

        # After the agent runs: track token usage from the response
        if context.result and isinstance(context.result, AgentResponse) and context.result.usage_details:
            new_tokens = context.result.usage_details.get("total_token_count", 0) or 0
            self.context_tokens += new_tokens
            logger.info(
                "[📝 Summarization] This turn used %d tokens. Context: %d",
                new_tokens,
                self.context_tokens,
            )


# ── Agent setup ──────────────────────────────────────────────────────

# Use a low threshold for demo purposes so summarization triggers quickly
summarization_middleware = SummarizationMiddleware(client=client, token_threshold=500)

agent = Agent(
    name="weekend-planner",
    client=client,
    instructions=(
        "You are a helpful weekend-planning assistant. Help users plan "
        "their weekends by checking weather and suggesting activities. "
        "Be friendly and provide detailed recommendations."
    ),
    tools=[get_weather, get_activities],
    middleware=[summarization_middleware],
)


async def main() -> None:
    """Run a multi-turn conversation that triggers summarization."""
    print("\n[bold]=== Context Compaction with Summarization ===[/bold]")
    print(f"[dim]Token threshold: {summarization_middleware.token_threshold}[/dim]")
    print("[dim]The middleware will summarize the conversation once token usage exceeds the threshold.[/dim]\n")

    session = agent.create_session()

    # Turn 1
    user_msg = "What's the weather like in San Francisco this weekend?"
    print(f"[blue]User:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agent:[/green] {response.text}\n")

    # Turn 2
    user_msg = "How about Portland? What's the weather and what activities can I do there?"
    print(f"[blue]User:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agent:[/green] {response.text}\n")

    # Turn 3 — by now we should be approaching or past the threshold
    user_msg = "What about Seattle? Give me the full picture — weather and things to do."
    print(f"[blue]User:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agent:[/green] {response.text}\n")

    # Turn 4 — this should trigger summarization
    user_msg = "Of all the cities we discussed, which one has the best combination of weather and activities?"
    print(f"[blue]User:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agent:[/green] {response.text}\n")

    # Turn 5 — after summarization, the agent should still have context
    user_msg = "Great, let's go with that city. What should I pack?"
    print(f"[blue]User:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agent:[/green] {response.text}\n")

    print(f"[dim]Final context token count: {summarization_middleware.context_tokens}[/dim]")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())

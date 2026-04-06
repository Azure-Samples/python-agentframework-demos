"""MagenticOne orchestration example with OpenAIChatClient setup used in this repo.

This sample demonstrates a Magentic manager coordinating three specialists to
produce a travel plan, with streaming output and orchestration ledger events.

Run:
    uv run examples/workflow_magenticone.py
    uv run examples/workflow_magenticone.py --devui
"""

import asyncio
import json
import os
import sys
from typing import cast

from agent_framework import Agent, AgentResponseUpdate, Message, WorkflowEvent
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import MagenticBuilder, MagenticProgressLedger
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# Configure OpenAI client based on environment
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
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )

console = Console()


local_agent = Agent(
    client=client,
    instructions=(
        "You suggest authentic and interesting local activities or places to visit, "
        "using any context provided by the user or other agents."
    ),
    name="local_agent",
    description="Specialist in local activities and places.",
)

language_agent = Agent(
    client=client,
    instructions=(
        "You review travel plans and provide practical tips for language and communication "
        "challenges at the destination. If coverage is already good, acknowledge that with rationale."
    ),
    name="language_agent",
    description="Specialist in language and communication advice.",
)

travel_summary_agent = Agent(
    client=client,
    instructions=(
        "You synthesize suggestions and advice from other agents into a complete travel plan. "
        "Make reasonable assumptions when details are missing. "
        "Do not ask the user follow-up questions. "
        "Do not ask for confirmations or permissions. "
        "YOUR FINAL RESPONSE MUST BE THE COMPLETE PLAN."
    ),
    name="travel_summary_agent",
    description="Specialist in travel-plan synthesis.",
)

manager_agent = Agent(
    client=client,
    name="manager_agent",
    description="Magentic manager that coordinates specialists.",
    instructions=(
        "You coordinate specialists to solve complex tasks efficiently. "
        "The user is not available for follow-up questions. "
        "If information is missing, choose sensible assumptions and continue. "
        "Ensure the workflow ends with a complete final plan."
    ),
)

magentic_workflow = MagenticBuilder(
    participants=[local_agent, language_agent, travel_summary_agent],
    manager_agent=manager_agent,
    max_round_count=10,
    max_stall_count=1,
    max_reset_count=1,
).build()


def handle_stream_event(event: WorkflowEvent, last_message_id: str | None) -> str | None:
    """Render a workflow stream event and return the updated message id."""
    # Streaming token from an agent (may not fire for all orchestrators)
    if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
        message_id = event.data.message_id
        if message_id != last_message_id:
            if last_message_id is not None:
                console.print()
            console.print(f"🤖 {event.executor_id}:", end=" ")
            last_message_id = message_id
        console.print(event.data, end="")
        return last_message_id

    # A participant finished — show its output
    if event.type == "executor_completed" and isinstance(event.data, list) and event.data:
        # The data is a list of AgentResponseUpdate tokens — concatenate them
        parts = [msg.text for msg in event.data if isinstance(msg, AgentResponseUpdate) and msg.text]
        if parts:
            full_text = "".join(parts)
            console.print(
                Panel(
                    Markdown(full_text),
                    title=f"🤖 {event.executor_id}",
                    border_style="cyan",
                    padding=(1, 2),
                )
            )
        return last_message_id

    # Orchestrator events (plan, progress ledger)
    if event.type == "magentic_orchestrator":
        console.print()
        emoji = "✅" if event.data.event_type.name == "PROGRESS_LEDGER_UPDATED" else "🧭"

        if isinstance(event.data.content, MagenticProgressLedger):
            rendered_content = json.dumps(event.data.content.to_dict(), indent=2)
            console.print(
                Panel(
                    rendered_content,
                    title=f"{emoji} Orchestrator: {event.data.event_type.name}",
                    border_style="bold yellow",
                    padding=(1, 2),
                )
            )
        elif hasattr(event.data.content, "text"):
            console.print(
                Panel(
                    Markdown(event.data.content.text),
                    title=f"{emoji} Orchestrator: {event.data.event_type.name}",
                    border_style="bold green",
                    padding=(1, 2),
                )
            )
        else:
            console.print(
                Panel(
                    Markdown(str(event.data.content)),
                    title=f"{emoji} Orchestrator: {event.data.event_type.name}",
                    border_style="bold green",
                    padding=(1, 2),
                )
            )

    return last_message_id


def print_final_result(output_event: WorkflowEvent | None) -> None:
    """Print the final plan from the workflow output event."""
    if output_event is None:
        return

    output_messages = cast(list[Message], output_event.data)
    console.print(
        Panel(
            Markdown(output_messages[-1].text),
            title="🌍 Final Travel Plan",
            border_style="bold green",
            padding=(1, 2),
        )
    )


async def main() -> None:
    """Run the Magentic workflow with streaming output."""
    task = (
        "Plan a half-day trip in Costa Rica for a family with two children ages 6 and 9, "
        "staying in San José, with a mid-range budget. "
        "Provide a complete itinerary with timing, transport assumptions, estimated costs, "
        "food recommendation, and practical language tips."
    )
    console.print(f"[bold]Task:[/bold] {task}\n")

    last_message_id: str | None = None
    output_event: WorkflowEvent | None = None

    async for event in magentic_workflow.run(task, stream=True):
        last_message_id = handle_stream_event(event, last_message_id)
        if event.type == "output" and not isinstance(event.data, AgentResponseUpdate):
            output_event = event

    print_final_result(output_event)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[magentic_workflow], auto_open=True)
    else:
        asyncio.run(main())

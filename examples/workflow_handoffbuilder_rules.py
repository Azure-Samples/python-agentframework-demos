"""Handoff orchestration with explicit routing rules (customer support).

Demonstrates: HandoffBuilder with .add_handoff() rules that enforce
business logic — e.g. triage cannot route directly to the refund agent;
only return_agent can escalate to refunds.

Routing rules:
    triage_agent  -> order_agent, return_agent   (NOT refund_agent)
    order_agent   -> triage_agent
    return_agent  -> triage_agent, refund_agent  (only path to refunds)
    refund_agent  -> triage_agent

Reference:
    https://learn.microsoft.com/agent-framework/workflows/orchestrations/handoff?pivots=programming-language-python#configure-handoff-rules-1

Run:
    uv run examples/workflow_handoffbuilder_rules.py
    uv run examples/workflow_handoffbuilder_rules.py --devui
"""

import asyncio
import logging
import os
import sys

from agent_framework import Agent, AgentResponseUpdate, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import HandoffBuilder
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
from rich.console import Console

logging.basicConfig(level=logging.WARNING)
console = Console()

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

# Configure the chat client based on the API host
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


# ── Tools ──────────────────────────────────────────────────────────────────


@tool
def initiate_return(
    order_id: str = Field(description="The order ID to return"),
    reason: str = Field(description="Reason for the return"),
) -> str:
    """Initiate a product return and generate a prepaid shipping label."""
    return (
        f"Return initiated for order {order_id} (reason: {reason}). "
        f"Return label RL-{order_id}-2026 has been emailed to the customer. "
        "Please drop off at any carrier location within 14 days."
    )


@tool
def process_refund(
    order_id: str = Field(description="The order ID to refund"),
    amount: str = Field(description="Refund amount in USD"),
) -> str:
    """Process a refund to the customer's original payment method."""
    return (
        f"Refund of ${amount} for order {order_id} has been processed. "
        "It will appear on the original payment method within 5-10 business days. "
        f"Refund confirmation number: RF-{order_id}-2026."
    )


# ── Agents ─────────────────────────────────────────────────────────────────

triage_agent = Agent(
    client=client,
    name="triage_agent",
    instructions=(
        "You are a customer-support triage agent. Briefly acknowledge the customer's issue "
        "and immediately hand off to the right specialist: order_agent for order inquiries, "
        "return_agent for returns. You cannot handle refunds directly. "
        "Do NOT ask the customer for additional details — the specialist will handle it. "
        "When the conversation is fully resolved (all agents have completed their tasks), say 'Goodbye!' to end the session."
    ),
)

order_agent = Agent(
    client=client,
    name="order_agent",
    instructions=(
        "You handle order status inquiries. Look up the customer's order and provide a brief update. "
        "When done, hand off back to triage_agent."
    ),
)

return_agent = Agent(
    client=client,
    name="return_agent",
    instructions=(
        "You handle product returns. Use the initiate_return tool with the information provided "
        "to create the return — do NOT ask the customer for extra details. "
        "If they also want a refund, hand off to refund_agent after initiating the return. "
        "Otherwise, hand off back to triage_agent when done."
    ),
    tools=[initiate_return],
)

refund_agent = Agent(
    client=client,
    name="refund_agent",
    instructions=(
        "You process refunds for returned items. Use the process_refund tool to issue the refund "
        "using the information already provided — do NOT ask the customer for extra details. "
        "If the exact amount is unknown, use a reasonable estimate based on context. "
        "Confirm the result and hand off to triage_agent when done."
    ),
    tools=[process_refund],
)

# ── Build the handoff workflow with explicit routing rules ─────────────────

workflow = (
    HandoffBuilder(
        name="customer_support_handoff",
        participants=[triage_agent, order_agent, return_agent, refund_agent],
        termination_condition=lambda conversation: (
            len(conversation) > 0 and "goodbye" in conversation[-1].text.lower()
        ),
    )
    .with_start_agent(triage_agent)
    # Triage cannot route directly to refund_agent
    .add_handoff(triage_agent, [order_agent, return_agent])
    # Only return_agent can escalate to refund_agent
    .add_handoff(return_agent, [refund_agent, triage_agent])
    # All specialists can hand back to triage
    .add_handoff(order_agent, [triage_agent])
    .add_handoff(refund_agent, [triage_agent])
    .with_autonomous_mode()
    .build()
)


async def main() -> None:
    """Run a customer support handoff workflow with explicit routing rules."""
    request = (
        "I want to return a jacket I bought last week and get a refund. "
        "Order #12345, it's a blue waterproof hiking jacket, size M, and it arrived with a torn zipper. "
        "I paid $89.99 and I'd like the refund back to my credit card."
    )
    console.print(f"[bold]Request:[/bold] {request}\n")

    current_agent = None

    async for event in workflow.run(request, stream=True):
        if event.type == "handoff_sent":
            console.print(f"\n🔀 [bold yellow]Handoff:[/bold yellow] {event.data.source} → {event.data.target}\n")

        elif event.type == "output" and isinstance(event.data, AgentResponseUpdate):
            if event.executor_id != current_agent:
                current_agent = event.executor_id
                console.print(f"\n🤖 [bold cyan]{current_agent}[/bold cyan]")
            console.print(event.data.text, end="")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8098, auto_open=True)
    else:
        asyncio.run(main())

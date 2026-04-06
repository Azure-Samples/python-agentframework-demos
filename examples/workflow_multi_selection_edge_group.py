"""LLM-powered multi-selection routing with one-or-many targets.

Demonstrates: WorkflowBuilder.add_multi_selection_edge_group where a single
source message can activate one or multiple downstream executors.  The
parse-ticket step uses an LLM call with structured outputs (response_format)
so classification is semantic rather than keyword-based.

Run:
    uv run examples/workflow_multi_selection_edge_group.py
    uv run examples/workflow_multi_selection_edge_group.py --devui  (opens DevUI at http://localhost:8099)
"""

import asyncio
import os
import sys

from agent_framework import Executor, Message, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing_extensions import Never

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
    client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4"))


class Ticket(BaseModel):
    """Structured representation of a support ticket, produced by the LLM."""

    text: str = Field(description="The original ticket text.")
    is_bug: bool = Field(description="True if the ticket describes a bug, error, or crash.")
    is_billing: bool = Field(description="True if the ticket relates to billing, invoices, or charges.")
    is_urgent: bool = Field(description="True if the ticket conveys urgency.")


class ParseTicketExecutor(Executor):
    """Parse incoming text into typed routing metadata using an LLM."""

    def __init__(self, *, client: OpenAIChatClient, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._client = client

    @handler
    async def parse(self, text: str, ctx: WorkflowContext[Ticket]) -> None:
        """Call the LLM with structured outputs to classify the ticket."""
        messages = [
            Message(
                role="system",
                contents=[
                    (
                        "You are a support ticket classifier. Given a customer message, "
                        "determine whether it describes a bug, relates to billing, and whether it is urgent. "
                        "Return the classification as structured JSON."
                    )
                ],
            ),
            Message(role="user", contents=[text]),
        ]
        response = await self._client.get_response(messages, options={"response_format": Ticket})
        ticket: Ticket = response.value
        await ctx.send_message(ticket)


class SupportExecutor(Executor):
    """Default customer support handler."""

    @handler
    async def handle(self, ticket: Ticket, ctx: WorkflowContext[Never, str]) -> None:
        """Emit support handling output."""
        urgency = "high" if ticket.is_urgent else "normal"
        await ctx.yield_output(f"[Support] Opened {urgency} priority support case for: {ticket.text}")


class EngineeringExecutor(Executor):
    """Engineering triage handler for bug-related tickets."""

    @handler
    async def handle(self, ticket: Ticket, ctx: WorkflowContext[Never, str]) -> None:
        """Emit engineering handling output."""
        await ctx.yield_output(f"[Engineering] Routed bug triage: {ticket.text}")


class BillingExecutor(Executor):
    """Billing operations handler for charge/invoice issues."""

    @handler
    async def handle(self, ticket: Ticket, ctx: WorkflowContext[Never, str]) -> None:
        """Emit billing handling output."""
        await ctx.yield_output(f"[Billing] Routed billing review: {ticket.text}")


def select_targets(ticket: Ticket, target_ids: list[str]) -> list[str]:
    """Select one or many downstream targets based on ticket metadata.

    Expected order for ``target_ids``:
    [support_id, engineering_id, billing_id]
    """
    support_id, engineering_id, billing_id = target_ids

    selected = [support_id]
    if ticket.is_bug:
        selected.append(engineering_id)
    if ticket.is_billing:
        selected.append(billing_id)
    return selected


parse_ticket = ParseTicketExecutor(client=client, id="parse_ticket")
support = SupportExecutor(id="support")
engineering = EngineeringExecutor(id="engineering")
billing = BillingExecutor(id="billing")

workflow = (
    WorkflowBuilder(
        name="MultiSelectionEdgeGroup",
        description="One input can route to one-or-many targets via a selection function.",
        start_executor=parse_ticket,
    )
    .add_multi_selection_edge_group(
        parse_ticket,
        [support, engineering, billing],
        selection_func=select_targets,
    )
    .build()
)


async def main() -> None:
    """Run three deterministic routing examples."""
    samples = [
        "Urgent: app crashes on login with error 500.",
        "Question about billing charge on my invoice.",
        "Feature request: add dark mode.",
    ]

    for sample in samples:
        print(f"\nTicket: {sample}")
        events = await workflow.run(sample)
        for output in events.get_outputs():
            print(f"  {output}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8099, auto_open=True)
    else:
        asyncio.run(main())

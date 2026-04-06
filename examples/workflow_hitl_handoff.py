"""Interactive handoff workflow with human-in-the-loop user input.

Demonstrates: HandoffBuilder without autonomous mode — the workflow pauses
for user input between agent turns via HandoffAgentUserRequest events.

A triage agent routes customer issues to specialist agents (order tracking,
returns). Without .with_autonomous_mode(), the framework pauses after each
agent response and waits for the human to provide the next message.

Run:
    uv run examples/workflow_hitl_handoff.py
"""

import asyncio
import os
import sys
from typing import Annotated, Any

from agent_framework import Agent, AgentResponse, AgentResponseUpdate, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

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


# --- Tools ---


@tool
def process_return(
    order_number: Annotated[str, "The 3-digit order number"],
    return_type: Annotated[str, "Either 'refund' or 'replacement'"],
) -> str:
    """Process a product return for the given order."""
    print(f"\n🔧 [Tool called: process_return(order_number={order_number}, return_type={return_type})]")
    return f"Return processed for order {order_number}: {return_type} approved. Confirmation email sent."


# --- Agents ---

triage_agent = Agent(
    client=client,
    name="triage_agent",
    instructions=(
        "You are a customer-support triage agent. Greet the customer, understand their issue, "
        "and hand off to the right specialist: order_agent for order inquiries, "
        "return_agent for returns. You cannot handle specific issues yourself — always hand off. "
        "If a specialist has just finished helping, ask the customer if there is anything else "
        "they need help with — do NOT re-route to the same specialist. "
        "Order numbers are only 3 digits long."
        "Do NOT ask for contact information, email, or phone number. "
        "Do NOT say 'Goodbye' until the customer explicitly confirms they have no more questions."
    ),
)

order_agent = Agent(
    client=client,
    name="order_agent",
    instructions=(
        "You are the order tracking specialist. Help the customer check status of pending orders. "
        "If the customer needs to return an order, hand off to return_agent. "
        "When done, hand off back to triage_agent."
    ),
)

return_agent = Agent(
    client=client,
    name="return_agent",
    instructions=(
        "You are the returns specialist. Help the customer initiate a return. "
        "The only details you need are the order number (3 digits) and whether they want a refund or replacement. "
        "Keep it simple and fast. Once the customer confirms, call process_return to complete the return. "
        "After the return is processed, hand off back to triage_agent."
    ),
    tools=[process_return],
)


# --- Workflow ---
workflow = (
    HandoffBuilder(
        name="customer_support",
        participants=[triage_agent, order_agent, return_agent],
        termination_condition=lambda conversation: (
            len(conversation) > 0 and "goodbye" in conversation[-1].text.lower()
        ),
    )
    .with_start_agent(triage_agent)
    .build()
)


async def main() -> None:
    """Run an interactive handoff workflow with user input."""
    initial_message = "Hi, I need help with an order."
    print(f"👤 You: {initial_message}\n")

    stream = workflow.run(initial_message, stream=True)

    while True:
        pending: list = []
        async for event in stream:
            if event.type == "request_info":
                pending.append(event)
            elif event.type == "handoff_sent":
                print(f"\n🔀 [Handoff: {event.data.source} → {event.data.target}]")
            elif event.type == "output" and isinstance(event.data, AgentResponse):
                for msg in event.data.messages:
                    if msg.text:
                        print(f"🤖 {msg.author_name or msg.role}: {msg.text}")
            elif event.type == "output" and not isinstance(event.data, (AgentResponseUpdate, AgentResponse)):
                if isinstance(event.data, list) and event.data:
                    last_msg = event.data[-1]
                    print(f"\n🤖 {last_msg.author_name or last_msg.role}: {last_msg.text}")
                print("\n✅ Conversation ended.")

        if not pending:
            break

        responses: dict[str, Any] = {}
        for request_event in pending:
            if isinstance(request_event.data, HandoffAgentUserRequest):
                # Show agent's response
                agent_response = request_event.data.agent_response
                for msg in agent_response.messages:
                    if msg.text:
                        print(f"🤖 {msg.author_name}: {msg.text}")

                # Get user input
                user_input = input("\n👤 You: ").strip()
                if user_input.lower() in ("exit", "quit"):
                    responses[request_event.request_id] = HandoffAgentUserRequest.terminate()
                else:
                    responses[request_event.request_id] = HandoffAgentUserRequest.create_response(user_input)

        stream = workflow.run(responses=responses, stream=True)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8098, auto_open=True)
    else:
        asyncio.run(main())

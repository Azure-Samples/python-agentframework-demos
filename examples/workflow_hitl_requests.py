"""Simple chat workflow with human-in-the-loop — "always ask" pattern.

Demonstrates: ctx.request_info(), @response_handler, and the HITL event loop
in the simplest possible form. No structured outputs, no routing logic.

A chat agent responds to the user, then the executor always pauses to ask
for the next message. The human can type "done" to finish the conversation.
This is the minimal HITL pattern — every agent response triggers a human turn.

Run:
    uv run examples/workflow_hitl_requests.py
"""

import asyncio
import os
from dataclasses import dataclass

from agent_framework import (
    Agent,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponseUpdate,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")

# Configure the chat client based on the API host
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


# --- HITL request dataclass ---


@dataclass
class UserPrompt:
    """Request sent to the human after every agent response."""

    message: str


# --- Executor that always asks the human ---


class ChatCoordinator(Executor):
    """After every agent response, pauses and asks the human for input."""

    def __init__(self, agent_id: str, id: str = "chat_coordinator"):
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def start(self, request: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Send the user's first message to the agent."""
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", text=request)], should_respond=True),
            target_id=self._agent_id,
        )

    @handler
    async def on_agent_response(self, result: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        """Always pause and ask the human for the next message."""
        await ctx.request_info(
            request_data=UserPrompt(message=result.agent_response.text),
            response_type=str,
        )

    @response_handler
    async def on_human_reply(
        self,
        original_request: UserPrompt,
        reply: str,
        ctx: WorkflowContext[AgentExecutorRequest, str],
    ) -> None:
        """Forward the human's reply to the agent, or end the conversation."""
        if reply.strip().lower() == "done":
            await ctx.yield_output("Conversation ended.")
            return
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", text=reply)], should_respond=True),
            target_id=self._agent_id,
        )


# --- Main ---


async def main() -> None:
    """Run the simple chat HITL workflow."""
    chat_agent = Agent(
        name="ChatAgent",
        instructions="You are a friendly, helpful assistant. Keep responses concise (2-3 sentences).",
        client=client,
    )

    coordinator = ChatCoordinator(agent_id="ChatAgent")

    workflow = (
        WorkflowBuilder(start_executor=coordinator)
        .add_edge(coordinator, chat_agent)
        .add_edge(chat_agent, coordinator)
        .build()
    )

    first_message = "What are some fun things to do in Seattle?"
    print(f"▶️  Starting chat with: \"{first_message}\"")

    stream = workflow.run(first_message, stream=True)

    while True:
        pending: dict[str, str] = {}
        async for event in stream:
            if event.type == "request_info":
                pending[event.request_id] = event.data
            elif event.type == "output" and not isinstance(event.data, AgentResponseUpdate):
                print(f"\n{event.data}")

        if not pending:
            break

        for request_id, request in pending.items():
            print(f"\n🤖 Agent: {request.message}")
            reply = input("💬 You (or 'done'): ")
            pending[request_id] = reply

        stream = workflow.run(stream=True, responses=pending)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

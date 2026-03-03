"""Trip planner workflow with human-in-the-loop via requests and responses.

Demonstrates: ctx.request_info(), @response_handler, structured agent output,
and driving the HITL loop from application code.

The user starts with a vague travel request like "I want to go somewhere warm."
The trip planner agent asks clarifying questions one at a time (destination,
budget, interests, dates). After each question, the workflow pauses and waits
for the human's answer. Once the agent has enough information, it produces a
final itinerary.

Run:
    uv run examples/workflow_hitl_requests_structured.py
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Literal

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
from pydantic import BaseModel

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


# --- Structured output models ---


class PlannerOutput(BaseModel):
    """Structured output from the trip planner agent."""

    status: Literal["need_info", "complete"]
    question: str | None = None
    itinerary: str | None = None


# --- HITL request dataclass ---


@dataclass
class UserPrompt:
    """Request sent to the human when the agent needs more information."""

    message: str


# --- Executor that coordinates agent ↔ human turns ---


class TripCoordinator(Executor):
    """Coordinates turns between the trip planner agent and the human.

    - After each agent reply, checks if more info is needed.
    - If so, requests human input via ctx.request_info().
    - If the agent has enough info, yields the final itinerary.
    """

    def __init__(self, agent_id: str, id: str = "trip_coordinator"):
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def start(self, request: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Kick off the first agent turn with the user's vague request."""
        user_msg = Message("user", text=request)
        await ctx.send_message(
            AgentExecutorRequest(messages=[user_msg], should_respond=True),
            target_id=self._agent_id,
        )

    @handler
    async def on_agent_response(self, result: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        """Handle the agent's structured response."""
        # Parse structured output from text (AgentResponse.value may be None
        # in streaming workflows due to response_format not propagating).
        output = PlannerOutput.model_validate_json(result.agent_response.text)

        if output.status == "need_info" and output.question:
            # Pause and ask the human
            await ctx.request_info(
                request_data=UserPrompt(message=output.question),
                response_type=str,
            )
        else:
            await ctx.yield_output(output.itinerary or "No itinerary generated.")

    @response_handler
    async def on_human_answer(
        self,
        original_request: UserPrompt,
        answer: str,
        ctx: WorkflowContext[AgentExecutorRequest, str],
    ) -> None:
        """Forward the human's answer back to the agent."""
        user_msg = Message("user", text=answer)
        await ctx.send_message(
            AgentExecutorRequest(messages=[user_msg], should_respond=True),
            target_id=self._agent_id,
        )


# --- Main ---


async def main() -> None:
    """Run the trip planner HITL workflow."""
    planner_agent = Agent(
        name="TripPlanner",
        instructions=(
            "You are a helpful trip planner. The user has a vague travel idea and you need to "
            "gather enough details to create a personalized itinerary.\n"
            "Ask clarifying questions ONE AT A TIME about: destination preferences, travel dates, "
            "budget, interests/activities, and group size.\n"
            "Once you have enough information (at least destination, dates, and budget), "
            'produce a final itinerary.\n\n'
            "You MUST return ONLY a JSON object matching this schema:\n"
            '  {"status": "need_info", "question": "your question here"}\n'
            "  OR\n"
            '  {"status": "complete", "itinerary": "your full itinerary here"}\n'
            "No explanations or additional text outside the JSON."
        ),
        client=client,
        default_options={"response_format": PlannerOutput},
    )

    coordinator = TripCoordinator(agent_id="TripPlanner")

    workflow = (
        WorkflowBuilder(start_executor=coordinator)
        .add_edge(coordinator, planner_agent)
        .add_edge(planner_agent, coordinator)
        .build()
    )

    user_request = "I want to go somewhere warm next month"
    print(f"▶️  Starting trip planner with: \"{user_request}\"\n")

    stream = workflow.run(user_request, stream=True)

    while True:
        pending: dict[str, str] = {}
        async for event in stream:
            if event.type == "request_info":
                pending[event.request_id] = event.data
            elif event.type == "output" and not isinstance(event.data, AgentResponseUpdate):
                print(f"\n📍 Itinerary:\n{event.data}")

        if not pending:
            break

        for request_id, request in pending.items():
            print(f"\n⏸️  Agent asks: {request.message}")
            answer = input("💬 Your answer: ")
            pending[request_id] = answer

        stream = workflow.run(stream=True, responses=pending)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

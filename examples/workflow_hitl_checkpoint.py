"""Content review workflow with checkpoints and human-in-the-loop resume.

Demonstrates: FileCheckpointStorage, on_checkpoint_save/restore,
workflow.run(checkpoint_id=...), and pause/resume across process restarts.

A brief is turned into a prompt for an AI copywriter. The copywriter drafts
release notes, and a review gateway requests human approval. If rejected,
the human provides revision guidance and the loop repeats. Checkpoints are
saved at every superstep so the workflow survives process restarts.

Run:
    uv run examples/workflow_hitl_checkpoint.py
"""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponseUpdate,
    Executor,
    FileCheckpointStorage,
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

# Directory for checkpoint files (easy to inspect and delete)
CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


# --- Executors ---


class BriefPreparer(Executor):
    """Normalizes the user brief and sends an AgentExecutorRequest to the writer."""

    def __init__(self, id: str, agent_id: str) -> None:
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def prepare(self, brief: str, ctx: WorkflowContext[AgentExecutorRequest, str]) -> None:
        normalized = " ".join(brief.split()).strip()
        if not normalized.endswith("."):
            normalized += "."
        ctx.set_state("brief", normalized)
        prompt = (
            "You are drafting product release notes. Summarise the brief below in two sentences. "
            "Keep it positive and end with a call to action.\n\n"
            f"BRIEF: {normalized}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._agent_id,
        )


@dataclass
class HumanApprovalRequest:
    """Sent to the human reviewer for approval."""

    prompt: str = ""
    draft: str = ""
    iteration: int = 0


class ReviewGateway(Executor):
    """Routes agent drafts to humans and optionally back for revisions."""

    def __init__(self, id: str, writer_id: str) -> None:
        super().__init__(id=id)
        self._writer_id = writer_id
        self._iteration = 0

    @handler
    async def on_agent_response(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        self._iteration += 1
        await ctx.request_info(
            request_data=HumanApprovalRequest(
                prompt="Review the draft. Reply 'approve' or provide edit instructions.",
                draft=response.agent_response.text,
                iteration=self._iteration,
            ),
            response_type=str,
        )

    @response_handler
    async def on_human_feedback(
        self,
        original_request: HumanApprovalRequest,
        feedback: str,
        ctx: WorkflowContext[AgentExecutorRequest | str, str],
    ) -> None:
        reply = feedback.strip()
        if len(reply) == 0 or reply.lower() == "approve":
            await ctx.yield_output(original_request.draft)
            return
        # Loop back to the writer with revision guidance
        prompt = (
            "Revise the launch note. Respond with the new copy only.\n\n"
            f"Previous draft:\n{original_request.draft}\n\n"
            f"Human guidance: {reply}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._writer_id,
        )

    async def on_checkpoint_save(self) -> dict[str, Any]:
        return {"iteration": self._iteration}

    async def on_checkpoint_restore(self, state: dict[str, Any]) -> None:
        self._iteration = state.get("iteration", 0)


# --- Main ---


async def main() -> None:
    """Run the checkpoint HITL workflow."""
    storage = FileCheckpointStorage(storage_path=CHECKPOINT_DIR)

    writer_agent = Agent(
        name="writer",
        instructions="Write concise, warm release notes that sound human and helpful.",
        client=client,
    )
    writer = AgentExecutor(writer_agent)
    review_gateway = ReviewGateway(id="review_gateway", writer_id="writer")
    prepare_brief = BriefPreparer(id="prepare_brief", agent_id="writer")

    workflow = (
        WorkflowBuilder(
            name="content_review",
            max_iterations=6,
            start_executor=prepare_brief,
            checkpoint_storage=storage,
        )
        .add_edge(prepare_brief, writer)
        .add_edge(writer, review_gateway)
        .add_edge(review_gateway, writer)  # revisions loop
        .build()
    )

    # Check if there are existing checkpoints to resume from
    checkpoint = await storage.get_latest(workflow_name=workflow.name)
    if checkpoint:
        print(f"📂 Found checkpoint. Resuming from latest: {checkpoint.checkpoint_id}")
        stream = workflow.run(checkpoint_id=checkpoint.checkpoint_id, stream=True)
    else:
        brief = (
            "Introduce our new compact air fryer with a 5-quart basket. Mention the $89 price, "
            "highlight the rapid air technology that crisps food with 95% less oil, "
            "and invite customers to pre-order."
        )
        print(f"▶️  Starting workflow with brief: {brief}\n")
        stream = workflow.run(brief, stream=True)

    while True:
        pending: dict[str, HumanApprovalRequest] = {}
        async for event in stream:
            if event.type == "request_info" and isinstance(event.data, HumanApprovalRequest):
                pending[event.request_id] = event.data
            elif event.type == "output" and not isinstance(event.data, AgentResponseUpdate):
                print(f"\n✅ Workflow completed:\n{event.data}")

        if not pending:
            break

        responses: dict[str, str] = {}
        for request_id, request in pending.items():
            print("\n" + "=" * 60)
            print(f"💬 Human approval needed (iteration {request.iteration})")
            print(request.prompt)
            print(f"\nDraft:\n---\n{request.draft}\n---")
            response = input("Type 'approve' or enter revision guidance: ").strip()
            responses[request_id] = response

        stream = workflow.run(stream=True, responses=responses)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

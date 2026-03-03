"""Content review workflow with PostgreSQL-backed checkpoint storage.

Demonstrates how to implement a custom CheckpointStorage backend
using PostgreSQL. Same workflow as workflow_hitl_checkpoint.py but
with durable database persistence instead of local files.

Run:
    uv run examples/workflow_hitl_checkpoint_pg.py
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from agent_framework import (
    Agent,
    AgentExecutor,
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
from agent_framework import WorkflowCheckpoint

# Private import — no public API for checkpoint encoding yet.
# See: https://github.com/microsoft/agent-framework/issues/4428
from agent_framework._workflows._checkpoint_encoding import decode_checkpoint_value, encode_checkpoint_value
from agent_framework.exceptions import WorkflowCheckpointException
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv(override=True)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://admin:LocalPasswordOnly@db:5432/postgres")


# --- PostgreSQL Checkpoint Storage ---


class PostgresCheckpointStorage:
    """PostgreSQL-backed checkpoint storage.

    Stores checkpoints in a single table with columns for ID, workflow name,
    timestamp, and the encoded JSON data. SQL handles indexing and filtering.
    """

    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo
        self._ensure_table()

    def _ensure_table(self) -> None:
        with psycopg.connect(self._conninfo) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                    id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data JSONB NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_workflow
                ON workflow_checkpoints (workflow_name, timestamp)
            """)

    async def save(self, checkpoint: WorkflowCheckpoint) -> str:
        """Save a checkpoint to PostgreSQL."""
        encoded = encode_checkpoint_value(checkpoint.to_dict())
        async with await psycopg.AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute(
                """INSERT INTO workflow_checkpoints (id, workflow_name, timestamp, data)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data""",
                (checkpoint.checkpoint_id, checkpoint.workflow_name,
                 checkpoint.timestamp, Jsonb(encoded)),
            )
        return checkpoint.checkpoint_id

    async def load(self, checkpoint_id: str) -> WorkflowCheckpoint:
        """Load a checkpoint by ID."""
        async with await psycopg.AsyncConnection.connect(self._conninfo, row_factory=dict_row) as conn:
            row = await (await conn.execute(
                "SELECT data FROM workflow_checkpoints WHERE id = %s", (checkpoint_id,)
            )).fetchone()
        if row is None:
            raise WorkflowCheckpointException(f"No checkpoint found with ID {checkpoint_id}")
        decoded = decode_checkpoint_value(row["data"])
        return WorkflowCheckpoint.from_dict(decoded)

    async def list_checkpoints(self, *, workflow_name: str) -> list[WorkflowCheckpoint]:
        """List all checkpoints for a workflow, ordered by timestamp."""
        async with await psycopg.AsyncConnection.connect(self._conninfo, row_factory=dict_row) as conn:
            rows = await (await conn.execute(
                "SELECT data FROM workflow_checkpoints WHERE workflow_name = %s ORDER BY timestamp",
                (workflow_name,),
            )).fetchall()
        return [WorkflowCheckpoint.from_dict(decode_checkpoint_value(r["data"])) for r in rows]

    async def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by ID."""
        async with await psycopg.AsyncConnection.connect(self._conninfo) as conn:
            result = await conn.execute(
                "DELETE FROM workflow_checkpoints WHERE id = %s", (checkpoint_id,)
            )
        return result.rowcount > 0

    async def get_latest(self, *, workflow_name: str) -> WorkflowCheckpoint | None:
        """Get the most recent checkpoint for a workflow."""
        async with await psycopg.AsyncConnection.connect(self._conninfo, row_factory=dict_row) as conn:
            row = await (await conn.execute(
                """SELECT data FROM workflow_checkpoints
                   WHERE workflow_name = %s ORDER BY timestamp DESC LIMIT 1""",
                (workflow_name,),
            )).fetchone()
        if row is None:
            return None
        return WorkflowCheckpoint.from_dict(decode_checkpoint_value(row["data"]))

    async def list_checkpoint_ids(self, *, workflow_name: str) -> list[str]:
        """List checkpoint IDs for a workflow."""
        async with await psycopg.AsyncConnection.connect(self._conninfo, row_factory=dict_row) as conn:
            rows = await (await conn.execute(
                "SELECT id FROM workflow_checkpoints WHERE workflow_name = %s ORDER BY timestamp",
                (workflow_name,),
            )).fetchall()
        return [r["id"] for r in rows]


# --- Client configuration ---

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
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model_id=os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    )


# --- Executors (same as workflow_hitl_checkpoint.py) ---


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
            AgentExecutorRequest(messages=[Message("user", text=prompt)], should_respond=True),
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
        prompt = (
            "Revise the launch note. Respond with the new copy only.\n\n"
            f"Previous draft:\n{original_request.draft}\n\n"
            f"Human guidance: {reply}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", text=prompt)], should_respond=True),
            target_id=self._writer_id,
        )

    async def on_checkpoint_save(self) -> dict[str, Any]:
        return {"iteration": self._iteration}

    async def on_checkpoint_restore(self, state: dict[str, Any]) -> None:
        self._iteration = state.get("iteration", 0)


# --- Main ---


async def main() -> None:
    """Run the checkpoint HITL workflow with PostgreSQL storage."""
    # Drop-in replacement: PostgresCheckpointStorage instead of FileCheckpointStorage
    storage = PostgresCheckpointStorage(conninfo=POSTGRES_URL)

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
        .add_edge(review_gateway, writer)
        .build()
    )

    # Check if there are existing checkpoints to resume from
    checkpoints = await storage.list_checkpoints(workflow_name=workflow.name)
    if checkpoints:
        latest = checkpoints[-1]  # already sorted by timestamp
        print(f"📂 Found {len(checkpoints)} checkpoint(s) in PostgreSQL. Resuming from latest.")
        stream = workflow.run(checkpoint_id=latest.checkpoint_id, stream=True)
    else:
        brief = (
            "Introduce our new compact air fryer with a 5-quart basket. Mention the $89 price, "
            "highlight the rapid air technology that crisps food with 95% less oil, "
            "and invite customers to pre-order."
        )
        print(f"▶️ Starting workflow with brief: {brief}\n")
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

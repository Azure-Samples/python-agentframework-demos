"""Writer → Reviewer workflow using structured outputs with conditional edges.

Demonstrates: response_format for typed reviewer decisions, conditional edges,
and a terminal @executor publisher node.

This is a direct contrast with workflow_conditional.py:
- Same branching shape via add_edge(..., condition=...)
- Different decision mechanism (typed JSON instead of sentinel string matching)

Routing:
    - decision == APPROVED        → publisher (terminal @executor)
    - decision == REVISION_NEEDED → editor (terminal Agent)

Run:
    uv run examples/workflow_conditional_structured.py  (opens DevUI at http://localhost:8096)
"""

import asyncio
import os
import sys
from typing import Any, Literal

from agent_framework import Agent, AgentExecutorResponse, WorkflowBuilder, WorkflowContext, executor
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel
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


class ReviewDecision(BaseModel):
    """Structured reviewer decision used for conditional routing."""

    decision: Literal["APPROVED", "REVISION_NEEDED"]
    feedback: str
    post_text: str | None = None


# Parse helper so condition functions remain small and explicit.
def parse_review_decision(message: Any) -> ReviewDecision | None:
    """Parse structured reviewer output from AgentExecutorResponse."""
    if not isinstance(message, AgentExecutorResponse):
        return None

    return ReviewDecision.model_validate_json(message.agent_response.text)


def is_approved(message: Any) -> bool:
    """Route to publisher when structured decision is APPROVED."""
    result = parse_review_decision(message)
    return result is not None and result.decision == "APPROVED"


def needs_revision(message: Any) -> bool:
    """Route to editor when structured decision is REVISION_NEEDED."""
    result = parse_review_decision(message)
    return result is not None and result.decision == "REVISION_NEEDED"


writer = Agent(
    client=client,
    name="Writer",
    instructions=(
        "You are a concise content writer. "
        "Write a clear, engaging short article (2-3 paragraphs) based on the user's topic."
    ),
)

reviewer = Agent(
    client=client,
    name="Reviewer",
    instructions=(
        "You are a strict content reviewer. Evaluate the writer's draft. "
        "If the draft is ready, set decision=APPROVED and include the publishable post in post_text. "
        "If it needs changes, set decision=REVISION_NEEDED and provide actionable feedback."
    ),
    default_options={"response_format": ReviewDecision},
)

editor = Agent(
    client=client,
    name="Editor",
    instructions=(
        "You are a skilled editor. "
        "You receive a writer's draft followed by the reviewer's feedback. "
        "Rewrite the draft to address all issues raised in the feedback. "
        "Output only the improved post."
    ),
)


@executor(id="publisher")
async def publisher(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    """Publish content from structured reviewer output."""
    result = parse_review_decision(response)
    if result is None:
        await ctx.yield_output("✅ Published:\n\n(Unable to parse structured reviewer output.)")
        return

    content = (result.post_text or "").strip()
    if not content:
        content = "(Reviewer approved but did not provide post_text.)"

    await ctx.yield_output(f"✅ Published:\n\n{content}")


workflow = (
    WorkflowBuilder(start_executor=writer)
    .add_edge(writer, reviewer)
    .add_edge(reviewer, publisher, condition=is_approved)
    .add_edge(reviewer, editor, condition=needs_revision)
    .build()
)


async def main():
    prompt = "Write a LinkedIn post predicting the 5 jobs AI agents will replace by December 2026."
    print(f"Prompt: {prompt}\n")
    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print("Output:")
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8096, auto_open=True)
    else:
        asyncio.run(main())

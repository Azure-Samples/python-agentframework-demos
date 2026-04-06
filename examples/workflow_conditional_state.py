"""Writer → Reviewer workflow with conditional edges plus workflow state.

Demonstrates: structured reviewer decisions, conditional edges, iterative
review loops, and explicit state management with WorkflowContext.set_state/get_state.

Routing:
    - decision == APPROVED        → publisher (terminal @executor)
    - decision == REVISION_NEEDED → editor → reviewer (iterative loop)

A small max_iterations cap is used to avoid unbounded cycles in demos.

Run:
    uv run examples/workflow_conditional_state.py  (opens DevUI at http://localhost:8094)
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


def parse_review_decision(message: Any) -> ReviewDecision | None:
    """Parse structured reviewer output from AgentExecutorResponse."""
    if not isinstance(message, AgentExecutorResponse):
        return None

    return ReviewDecision.model_validate_json(message.agent_response.text)


# Condition functions — receive the message from the previous executor.
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
        "You are a strict content reviewer. Evaluate the writer's draft.\n"
        "Check that the post is engaging and a good fit for the target platform.\n"
        "Make sure that it does not sound overly LLM-generated.\n"
        "Accessibility/style constraints: do not use em dashes (—) and do not use fancy Unicode text.\n"
        "Return a structured decision using this schema: decision and feedback.\n"
        "Set decision=APPROVED if the draft is clear, accurate, and well-structured.\n"
        "Set decision=REVISION_NEEDED if it requires improvement.\n"
        "In feedback, explain your reasoning briefly and provide actionable edits when needed."
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
        "Ensure the length of the final post is appropriate for the target platform."
    ),
)


# State pass-through executor: stores the latest post text produced by Writer/Editor.
# Docs: https://learn.microsoft.com/agent-framework/workflows/state?pivots=programming-language-python
@executor(id="store_post_text")
async def store_post_text(response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorResponse]) -> None:
    """Persist latest post text in workflow state and pass message downstream."""
    ctx.set_state("post_text", response.agent_response.text.strip())
    await ctx.send_message(response)


# Terminal executor: receives the reviewer's structured decision and publishes from state.
# Using @executor for a standalone function instead of an Executor subclass —
# both are valid ways to define a workflow node.
@executor(id="publisher")
async def publisher(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    """Publish the latest approved post text from workflow state."""
    content = str(ctx.get_state("post_text", "")).strip()
    await ctx.yield_output(f"✅ Published:\n\n{content}")


# Build the workflow with two conditional outgoing edges from the reviewer.
# add_edge(reviewer, publisher, condition=is_approved) fires when is_approved() returns True.
# add_edge(reviewer, editor, condition=needs_revision) fires when needs_revision() returns True.
# add_edge(editor, reviewer) creates a bounded revise-review loop.
workflow = (
    WorkflowBuilder(start_executor=writer, max_iterations=20)
    .add_edge(writer, store_post_text)
    .add_edge(store_post_text, reviewer)
    .add_edge(reviewer, publisher, condition=is_approved)
    .add_edge(reviewer, editor, condition=needs_revision)
    .add_edge(editor, store_post_text)
    .build()
)


async def main():
    prompt = "Write a LinkedIn post predicting the 5 jobs AI agents will replace by December 2026."
    print(f"Prompt: {prompt}\n")
    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8094, auto_open=True)
    else:
        asyncio.run(main())

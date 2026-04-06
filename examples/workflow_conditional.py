"""Writer → Reviewer workflow with conditional edges based on a sentinel token.

Demonstrates: conditional edges, condition functions that inspect
AgentExecutorResponse, and a terminal @executor node.

The Reviewer is instructed to begin its response with exactly "APPROVED"
or "REVISION NEEDED". Two outgoing edges route the flow accordingly:
    - APPROVED        → publisher (terminal @executor)
    - REVISION NEEDED → editor (terminal Agent)

This is the minimal branching version focused only on conditional edges.
For a more robust pattern that uses workflow state and iterative revisions,
see workflow_conditional_state.py.

Run:
    uv run examples/workflow_conditional.py  (opens DevUI at http://localhost:8094)
"""

import asyncio
import os
import sys
from typing import Any

from agent_framework import Agent, AgentExecutorResponse, WorkflowBuilder, WorkflowContext, executor
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
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


# Condition functions — receive the message from the previous executor.
# Both guard with isinstance() since conditions can receive any message type.
def is_approved(message: Any) -> bool:
    """Route to publisher if the reviewer started their response with APPROVED."""
    if not isinstance(message, AgentExecutorResponse):
        return False
    return message.agent_response.text.upper().startswith("APPROVED")


def needs_revision(message: Any) -> bool:
    """Route to editor if the reviewer requested changes."""
    if not isinstance(message, AgentExecutorResponse):
        return False
    return message.agent_response.text.upper().startswith("REVISION NEEDED")


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
        "IMPORTANT: Your response MUST begin with exactly one of these two tokens:\n"
        "  APPROVED   — if the draft is clear, accurate, and well-structured.\n"
        "  REVISION NEEDED — if it requires improvement.\n"
        "If you choose APPROVED, include the final publishable post immediately after the token.\n"
        "If you choose REVISION NEEDED, provide a brief explanation of what to fix."
    ),
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


# Terminal executor: receives the reviewer's APPROVED response and publishes it.
# Using @executor for a standalone function instead of an Executor subclass —
# both are valid ways to define a workflow node.
@executor(id="publisher")
async def publisher(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    """Strip the APPROVED prefix and yield the final published content."""
    text = response.agent_response.text
    content = text[len("APPROVED") :].lstrip(":").strip()

    await ctx.yield_output(f"✅ Published:\n\n{content}")


# Build the workflow with two conditional outgoing edges from the reviewer.
# add_edge(reviewer, publisher, condition=is_approved) fires when is_approved() returns True.
# add_edge(reviewer, editor, condition=needs_revision) fires when needs_revision() returns True.
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
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8094, auto_open=True)
    else:
        asyncio.run(main())

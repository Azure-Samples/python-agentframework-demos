"""Customer message router using structured outputs and switch-case edges.

Demonstrates: response_format= for reliable structured output, @executor
for a converter node, and add_switch_case_edge_group for multi-way routing.

A Classifier agent uses a Pydantic model as its response_format so the
category is always a valid, typed value — no fragile string matching.
A converter executor extracts the structured result, then switch-case edges
route to a specialized handler for each category.

Pipeline:
    Classifier → extract_category → [Case: Question   → handle_question ]
                                  → [Case: Complaint  → handle_complaint]
                                  → [Default          → handle_feedback ]

Contrast with workflow_conditional.py: structured outputs make branching
logic explicit, typed, and easy to extend.

Run:
    uv run examples/workflow_switch_case.py  (opens DevUI at http://localhost:8095)
"""

import asyncio
import os
import sys
from typing import Any, Literal

from agent_framework import Agent, AgentExecutorResponse, Case, Default, WorkflowBuilder, WorkflowContext, executor
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


# Pydantic model used as response_format — the LLM must return valid JSON
# matching this schema, guaranteeing category is always one of the three literals.
class ClassifyResult(BaseModel):
    """Structured classification result from the Classifier agent."""

    category: Literal["Question", "Complaint", "Feedback"]
    original_message: str
    reasoning: str


# The classifier agent uses response_format= to enforce structured output.
# This is more reliable than asking the model to start with a sentinel token.
classifier = Agent(
    client=client,
    name="Classifier",
    instructions=(
        "You are a customer message classifier. "
        "Classify the incoming customer message into exactly one category: "
        "Question, Complaint, or Feedback. "
        "Return a JSON object with category, original_message, and reasoning."
    ),
    default_options={"response_format": ClassifyResult},
)


# Converter executor: parse the agent's JSON response into a typed ClassifyResult
# and forward it. Switch-case conditions will inspect this typed object.
@executor(id="extract_category")
async def extract_category(response: AgentExecutorResponse, ctx: WorkflowContext[ClassifyResult]) -> None:
    """Parse the classifier's structured JSON output and send it downstream."""
    result = ClassifyResult.model_validate_json(response.agent_response.text)
    print(f"→ Classified as: {result.category} — {result.reasoning}")
    await ctx.send_message(result)


# Condition functions for switch-case routing.
# Each receives the ClassifyResult sent by extract_category.
def is_question(msg: Any) -> bool:
    return isinstance(msg, ClassifyResult) and msg.category == "Question"


def is_complaint(msg: Any) -> bool:
    return isinstance(msg, ClassifyResult) and msg.category == "Complaint"


# Terminal handler executors — one per branch.
# Each receives the ClassifyResult and yields a formatted response string.
@executor(id="handle_question")
async def handle_question(result: ClassifyResult, ctx: WorkflowContext[Never, str]) -> None:
    """Route a question to the Q&A team."""
    await ctx.yield_output(
        f"❓ Question routed to Q&A team\n\n" f"Message: {result.original_message}\n" f"Reason: {result.reasoning}"
    )


@executor(id="handle_complaint")
async def handle_complaint(result: ClassifyResult, ctx: WorkflowContext[Never, str]) -> None:
    """Escalate a complaint to the support team."""
    await ctx.yield_output(
        f"⚠️  Complaint escalated to support team\n\n"
        f"Message: {result.original_message}\n"
        f"Reason: {result.reasoning}"
    )


@executor(id="handle_feedback")
async def handle_feedback(result: ClassifyResult, ctx: WorkflowContext[Never, str]) -> None:
    """Forward feedback to the product team."""
    await ctx.yield_output(
        f"💬 Feedback forwarded to product team\n\n"
        f"Message: {result.original_message}\n"
        f"Reason: {result.reasoning}"
    )


# Build the workflow.
# add_switch_case_edge_group evaluates cases in order and takes the first match.
# Default catches everything not matched by an explicit Case.
workflow = (
    WorkflowBuilder(start_executor=classifier)
    .add_edge(classifier, extract_category)
    .add_switch_case_edge_group(
        extract_category,
        [
            Case(condition=is_question, target=handle_question),
            Case(condition=is_complaint, target=handle_complaint),
            Default(target=handle_feedback),
        ],
    )
    .build()
)


async def main():
    message = "How do I reset my password?"
    print(f"Customer message: {message}\n")
    events = await workflow.run(message)
    for output in events.get_outputs():
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8095, auto_open=True)
    else:
        asyncio.run(main())

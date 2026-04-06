"""Writer → Reviewer workflow with branch-and-converge routing.

Demonstrates: Agent executors, conditional edges, and a converging graph shape:
Reviewer routes either directly to Publisher (approved) or through Editor,
and both paths converge before the final Summarizer output.

Run:
    uv run examples/workflow_converge.py
    uv run examples/workflow_converge.py --devui  (opens DevUI at http://localhost:8093)
"""

import asyncio
import os
import sys
from typing import Any

from agent_framework import Agent, AgentExecutorResponse, Message, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel

# Configure OpenAI client based on environment
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

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


class ReviewResult(BaseModel):
    """Review evaluation with scores and feedback."""

    score: int  # Overall quality score (0-100)
    feedback: str  # Concise, actionable feedback
    clarity: int  # Clarity score (0-100)
    completeness: int  # Completeness score (0-100)
    accuracy: int  # Accuracy score (0-100)
    structure: int  # Structure score (0-100)


def parse_review_result(message: Any) -> ReviewResult | None:
    """Parse structured reviewer output from AgentExecutorResponse."""
    if not isinstance(message, AgentExecutorResponse):
        return None

    return ReviewResult.model_validate_json(message.agent_response.text)


def is_approved(message: Any) -> bool:
    """Check if content is approved (high quality)."""
    result = parse_review_result(message)
    return result is not None and result.score >= 80


def needs_editing(message: Any) -> bool:
    """Route to editor when content quality is below threshold."""
    result = parse_review_result(message)
    return result is not None and result.score < 80


writer = Agent(
    client=client,
    name="Writer",
    instructions=(
        "You are an excellent content writer. "
        "Create clear, engaging content based on the user's request. "
        "Focus on clarity, accuracy, and proper structure."
    ),
)


reviewer = Agent(
    client=client,
    name="Reviewer",
    instructions=(
        "You are an expert content reviewer. "
        "Evaluate the writer's content based on:\n"
        "1. Clarity - Is it easy to understand?\n"
        "2. Completeness - Does it fully address the topic?\n"
        "3. Accuracy - Is the information correct?\n"
        "4. Structure - Is it well-organized?\n\n"
        "Return a JSON object with:\n"
        "- score: overall quality (0-100)\n"
        "- feedback: concise, actionable feedback\n"
        "- clarity, completeness, accuracy, structure: individual scores (0-100)"
    ),
    default_options={"response_format": ReviewResult},
)


editor = Agent(
    client=client,
    name="Editor",
    instructions=(
        "You are a skilled editor. "
        "You will receive content along with review feedback. "
        "Improve the content by addressing all the issues mentioned in the feedback. "
        "Maintain the original intent while enhancing clarity, completeness, accuracy, and structure."
    ),
)


publisher = Agent(
    client=client,
    name="Publisher",
    instructions=(
        "You are a publishing agent. "
        "You receive either approved content or edited content. "
        "Format it for publication with proper headings and structure."
    ),
)

summarizer = Agent(
    client=client,
    name="Summarizer",
    instructions=(
        "You are a summarizer agent. "
        "Create a final publication report that includes:\n"
        "1. A brief summary of the published content\n"
        "2. The workflow path taken (direct approval or edited)\n"
        "3. Key highlights and takeaways\n"
        "Keep it concise and professional."
    ),
)


workflow = (
    WorkflowBuilder(
        name="ContentConverge",
        start_executor=writer,
        description="Branch from reviewer, then converge before final summary output.",
    )
    .add_edge(writer, reviewer)
    .add_edge(reviewer, publisher, condition=is_approved)
    .add_edge(reviewer, editor, condition=needs_editing)
    .add_edge(editor, publisher)
    .add_edge(publisher, summarizer)
    .build()
)


async def main():
    prompt = 'Write a one-paragraph LinkedIn post: "The AI workflow mistake almost every team makes."'
    print(f"Prompt: {prompt}\n")

    events = await workflow.run(prompt)
    outputs = events.get_outputs()

    for output in outputs:
        if not isinstance(output, AgentExecutorResponse):
            print(output)
            continue

        final_message = Message(role="assistant", contents=[output.agent_response.text])
        print(f"[{output.executor_id}]\n{final_message.text}\n")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8093, auto_open=True)
    else:
        asyncio.run(main())

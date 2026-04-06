"""Writer → Reviewer workflow with streaming events.

Demonstrates: run(stream=True) to consume workflow events in real-time,
including executor_invoked, executor_completed, and streaming output tokens.

Event types observed:
  "started"             — workflow execution begins
  "executor_invoked"   — an executor (agent) starts processing
  "output"             — a streaming text chunk (AgentResponseUpdate)
  "executor_completed" — an executor finishes
  "executor_failed"    — an executor encounters an error
  "error"              — workflow encounters an error
  "warning"            — workflow encountered a warning

Contrast with workflow_agents.py, which uses run() and prints final output only.

Reference:
    https://learn.microsoft.com/en-us/agent-framework/workflows/events?pivots=programming-language-python

Run:
    uv run examples/workflow_agents_streaming.py
"""

import asyncio
import os

from agent_framework import Agent, AgentResponseUpdate, WorkflowBuilder
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

writer = Agent(
    client=client,
    name="Writer",
    instructions=(
        "You are a concise content writer. "
        "Write a clear, engaging short article (2-3 paragraphs) based on the user's topic. "
        "Focus on accuracy and readability."
    ),
)

reviewer = Agent(
    client=client,
    name="Reviewer",
    instructions=(
        "You are a thoughtful content reviewer. "
        "Read the writer's draft and provide specific, constructive feedback. "
        "Comment on clarity, accuracy, and structure. Keep your review concise."
    ),
)

workflow = WorkflowBuilder(name="WriterReviewer", start_executor=writer).add_edge(writer, reviewer).build()


async def main():
    prompt = 'Write a short LinkedIn post: "4 jobs AI agents are quietly reshaping this year."'
    print(f"💬 Prompt: {prompt}\n")

    async for event in workflow.run(prompt, stream=True):
        if event.type == "started":
            print(f"📡 Event started | workflow={workflow.name}")
        elif event.type == "executor_invoked":
            print(f"\n📡 Event executor_invoked | executor={event.executor_id}")
        elif event.type == "output" and isinstance(event.data, AgentResponseUpdate):
            print(event.data.text, end="", flush=True)
        elif event.type == "executor_completed":
            print(f"\n\n📡 Event executor_completed | executor={event.executor_id}")
        elif event.type == "executor_failed":
            print(f"\n📡 Event executor_failed | executor={event.executor_id} | details={event.data}")
        elif event.type == "error":
            print(f"\n📡 Event error | details={event.data}")
        elif event.type == "warning":
            print(f"\n📡 Event warning | details={event.data}")

    print()
    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

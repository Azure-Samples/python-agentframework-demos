"""Writer → Reviewer workflow using AI agents as executors.

Demonstrates: Agent as a WorkflowBuilder executor, direct edges,
and collecting output with workflow.run() + get_outputs().

This example uses the same WorkflowBuilder + add_edge pattern as
workflow_rag_ingest.py, but with AI agents instead of Python functions.

Run:
    uv run examples/workflow_agents.py
    uv run examples/workflow_agents.py --devui  (opens DevUI at http://localhost:8092)
"""

import asyncio
import os
import sys

from agent_framework import Agent, WorkflowBuilder
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

# Create AI agents — these are passed directly as executors to WorkflowBuilder,
# exactly like the Python Executor subclasses in workflow_rag_ingest.py.
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

# Build the workflow: Writer → Reviewer
# The same WorkflowBuilder.add_edge pattern works for both Python executors
# and AI agents — the graph structure is identical.
workflow = WorkflowBuilder(start_executor=writer).add_edge(writer, reviewer).build()


async def main():
    prompt = 'Write a 2-sentence LinkedIn post: "Why your AI pilot looks good but fails in production."'
    print(f"Prompt: {prompt}\n")
    events = await workflow.run(prompt)

    for output in events.get_outputs():
        print("===== Output =====")
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8092, auto_open=True)
    else:
        asyncio.run(main())

"""Writer → Reviewer workflow using SequentialBuilder orchestration.

Demonstrates: SequentialBuilder(participants=[...]) with AI agents and
collecting the final conversation from workflow.run() + get_outputs().

Each participant receives the full conversation history generated so far.

Reference:
    https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/sequential?pivots=programming-language-python

Run:
    uv run examples/workflow_agents_sequential.py
    uv run examples/workflow_agents_sequential.py --devui  (opens DevUI at http://localhost:8096)
"""

import asyncio
import logging
import os
import sys

from agent_framework import Agent, Message
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import SequentialBuilder
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.logging import RichHandler

log_handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[log_handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

# Build the sequential workflow: Writer → Reviewer
workflow = SequentialBuilder(participants=[writer, reviewer]).build()


async def main():
    prompt = 'Write a one-paragraph LinkedIn post: "The AI workflow mistake almost every team makes."'
    logger.info("Prompt: %s", prompt)
    events = await workflow.run(prompt)
    outputs = events.get_outputs()

    for conversation in outputs:
        logger.info("===== Final Conversation =====")
        messages: list[Message] = conversation
        for index, message in enumerate(messages, start=1):
            author = message.author_name or ("assistant" if message.role == "assistant" else "user")
            logger.info("%02d [%s]\n%s", index, author, message.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8096, auto_open=True)
    else:
        asyncio.run(main())

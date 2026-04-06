"""Concurrent multi-expert analysis using ConcurrentBuilder orchestration.

Demonstrates: ConcurrentBuilder(participants=[...]) to run 3 specialist agents
in parallel on the same user prompt, then collect the default aggregated output
(combined message list).

Each participant receives the original prompt independently and runs concurrently.
The default aggregator merges all agent conversations into a single message list.

Contrast with workflow_agents_sequential.py, where agents run one after another
and each sees the full conversation so far.

Reference:
    https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/concurrent?pivots=programming-language-python

Run:
    uv run examples/workflow_agents_concurrent.py
    uv run examples/workflow_agents_concurrent.py --devui  (opens DevUI at http://localhost:8105)
"""

import asyncio
import logging
import os
import sys

from agent_framework import Agent, Message
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import ConcurrentBuilder
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

# Three specialist agents — each brings a different perspective to the same prompt
researcher = Agent(
    client=client,
    name="Researcher",
    instructions=(
        "You are an expert market and product researcher. "
        "Given a prompt, provide concise, factual insights, opportunities, and risks. "
        "Keep your analysis to one paragraph."
    ),
)

marketer = Agent(
    client=client,
    name="Marketer",
    instructions=(
        "You are a creative marketing strategist. "
        "Craft a compelling value proposition and target messaging aligned to the prompt. "
        "Keep your response to one paragraph."
    ),
)

legal = Agent(
    client=client,
    name="Legal",
    instructions=(
        "You are a cautious legal and compliance reviewer. "
        "Highlight constraints, disclaimers, and policy concerns based on the prompt. "
        "Keep your response to one paragraph."
    ),
)

# Build the concurrent workflow — all three agents run in parallel
workflow = ConcurrentBuilder(participants=[researcher, marketer, legal]).build()


async def main():
    prompt = "We are launching a new budget-friendly electric bike for urban commuters."
    logger.info("Prompt: %s", prompt)
    result = await workflow.run(prompt)
    outputs = result.get_outputs()

    for conversation in outputs:
        logger.info("===== Aggregated Conversation =====")
        messages: list[Message] = conversation
        for index, message in enumerate(messages, start=1):
            author = message.author_name or ("assistant" if message.role == "assistant" else "user")
            logger.info("%02d [%s]\n%s", index, author, message.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8105, auto_open=True)
    else:
        asyncio.run(main())

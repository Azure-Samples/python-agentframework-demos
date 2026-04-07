"""Durable Task hosted agent.

Demonstrates hosting an agent via the Durable Task Scheduler (DTS), which
provides automatic state persistence and a distributed worker-client
architecture. Conversation state survives worker restarts with zero custom
checkpoint code -- DTS handles it all.

This example runs both the worker and client in a single process for
simplicity. In production you would run them separately, potentially on
different machines.

Prerequisites:
    The DTS emulator runs automatically in the dev container at
    http://dts-emulator:8080. Outside the dev container, start it manually:

    docker run -d --name dts-emulator -p 8080:8080 -p 8082:8082 \
        mcr.microsoft.com/dts/dts-emulator:latest

    DTS dashboard: http://localhost:8082 (or http://dts-emulator:8082 in dev container)

Run:
    uv run python examples/agent_durabletask.py

For more DTS patterns (multi-agent, orchestrations, HITL, streaming),
see: https://github.com/microsoft/agent-framework/tree/main/python/samples/04-hosting/durabletask
"""

import os

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_durabletask import DurableAIAgentClient, DurableAIAgentWorker
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from durabletask.azuremanaged.client import DurableTaskSchedulerClient
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
from rich import print

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

DTS_ENDPOINT = os.getenv("DTS_ENDPOINT", "http://dts-emulator:8080")
DTS_TASKHUB = os.getenv("DTS_TASKHUB", "default")

# --- Chat client (same pattern as all other examples) ---
if API_HOST == "azure":
    async_credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
    chat_client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
else:
    chat_client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
    )

# --- Agent ---
agent = Agent(
    name="Joker",
    instructions="You tell short, clever jokes. Keep responses under 3 sentences.",
    client=chat_client,
)

# --- Worker (hosts the agent as a durable entity in DTS) ---
dts_worker = DurableTaskSchedulerWorker(
    host_address=DTS_ENDPOINT,
    secure_channel=not DTS_ENDPOINT.startswith("http://"),
    taskhub=DTS_TASKHUB,
)
agent_worker = DurableAIAgentWorker(dts_worker)
agent_worker.add_agent(agent)

# --- Client (sends requests to the agent via DTS) ---
dts_client = DurableTaskSchedulerClient(
    host_address=DTS_ENDPOINT,
    secure_channel=not DTS_ENDPOINT.startswith("http://"),
    taskhub=DTS_TASKHUB,
)
agent_client = DurableAIAgentClient(dts_client)

# --- Interactive chat loop ---
print("[bold]Durable Task agent (type 'exit' to quit)[/bold]\n")

with dts_worker:
    dts_worker.start()

    joker = agent_client.get_agent("Joker")
    session = joker.create_session()
    print(f"[dim]Session: {session.session_id}[/dim]\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input or user_input.lower() == "exit":
            break
        response = joker.run(user_input, session=session)
        print(f"\n[bold green]Joker:[/bold green] {response.text}\n")

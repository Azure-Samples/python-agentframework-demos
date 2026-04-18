"""Durable Task persistence demo — IT support scenario.

Demonstrates: DurableTaskSchedulerWorker, DurableAIAgentClient,
DurableAgentSession.to_dict/from_dict, and automatic state persistence.

An IT support agent begins troubleshooting a Wi-Fi issue, the worker is
stopped (simulating the user leaving to restart their laptop), and a new
worker picks up the same conversation seamlessly — proving DTS preserves
state with no custom checkpoint code.

Note: You may see noisy warnings ("Invalid or missing created_at value",
"StatusCode.CANCELLED") — these are harmless and tracked upstream:
https://github.com/microsoft/agent-framework/issues/5347

Run:
    uv run python examples/agent_durabletask.py
"""

import asyncio
import os

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_durabletask import DurableAIAgentClient, DurableAIAgentWorker, DurableAgentSession
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from durabletask.azuremanaged.client import DurableTaskSchedulerClient
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
from rich import print

# Configure OpenAI client based on environment
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

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
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )

# DTS configuration
DTS_ENDPOINT = os.getenv("DTS_ENDPOINT", "http://dts-emulator:8080")
DTS_TASKHUB = os.getenv("DTS_TASKHUB", "default")

PLAN_PROMPT = (
    "My laptop won't connect to Wi-Fi. "
    "I've already tried toggling the Wi-Fi switch and forgetting the network."
)
FOLLOWUP_PROMPT = (
    "OK I restarted, and Wi-Fi is working now but it's very slow. "
    "Pages take 10+ seconds to load. What should I try next?"
)

agent = Agent(
    name="ITSupport",
    instructions=(
        "You are a friendly IT support agent. "
        "Reply in 1-2 short sentences — never bullet lists or numbered steps. "
        "Suggest ONE thing to try at a time. If the fix requires leaving "
        "(e.g. restart), tell the user to come back after."
    ),
    client=client,
)


def create_runtime() -> tuple[DurableTaskSchedulerWorker, DurableAIAgentClient]:
    """Create a DTS worker/client pair for the demo."""
    is_emulator = DTS_ENDPOINT.startswith("http://")
    credential = None if is_emulator else SyncDefaultAzureCredential()

    dts_worker = DurableTaskSchedulerWorker(
        host_address=DTS_ENDPOINT,
        secure_channel=not is_emulator,
        taskhub=DTS_TASKHUB,
        token_credential=credential,
    )
    agent_worker = DurableAIAgentWorker(dts_worker)
    agent_worker.add_agent(agent)

    dts_client = DurableTaskSchedulerClient(
        host_address=DTS_ENDPOINT,
        secure_channel=not is_emulator,
        taskhub=DTS_TASKHUB,
        token_credential=credential,
    )

    return dts_worker, DurableAIAgentClient(dts_client)


def run_demo() -> bool:
    """Run a support-ticket demo that proves state survives a worker restart."""
    print("[bold]Durable Task persistence demo — IT Support[/bold]\n")

    worker, agent_client = create_runtime()
    with worker:
        print("[cyan]1.[/cyan] Starting the first worker and creating a durable session...")
        worker.start()

        support = agent_client.get_agent(agent.name)
        session = support.create_session()
        print(f"   [dim]Session: {session.session_id}[/dim]")
        print(f"   [dim]Durable session: {session.durable_session_id}[/dim]")

        print("\n[cyan]2.[/cyan] User reports a Wi-Fi issue...")
        plan_response = support.run(PLAN_PROMPT, session=session)
        print(f"   [green]Agent:[/green] {plan_response.text}")

        saved_session = session.to_dict()

    print("\n[cyan]3.[/cyan] [bold red]Worker stopped.[/bold red] (User goes away to restart their laptop...)")
    print("   Restoring the same session after worker restart...")
    restored_session = DurableAgentSession.from_dict(saved_session)

    worker, agent_client = create_runtime()
    with worker:
        worker.start()
        support = agent_client.get_agent(agent.name)

        print("\n[cyan]4.[/cyan] User comes back after restarting — agent must remember the context...")
        followup_response = support.run(FOLLOWUP_PROMPT, session=restored_session)
        print(f"   [green]Agent:[/green] {followup_response.text}")

    keywords = ["wi-fi", "wifi", "network", "dns", "connection", "slow"]
    passed = any(kw in followup_response.text.lower() for kw in keywords)
    if passed:
        print("\n[bold green]PASS[/bold green] DTS preserved the support conversation across the worker restart.")
    else:
        print("\n[bold red]FAIL[/bold red] The agent did not recall the support context after the worker restart.")

    return passed


async def main() -> None:
    """Run the DTS persistence demo."""
    run_demo()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

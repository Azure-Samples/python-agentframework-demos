"""Handoff orchestration in autonomous mode using HandoffBuilder.

Demonstrates: HandoffBuilder with .with_autonomous_mode() where agents
transfer control to each other without any human-in-the-loop interaction.
A triage agent decides which specialist to involve first, then agents
hand off freely — researcher gathers facts, writer drafts content,
and editor reviews (handing back to the writer if revisions are needed).

By default every participant can hand off to every other participant;
no explicit routing rules are needed.

Reference:
    https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff?pivots=programming-language-python#autonomous-mode

Run:
    uv run examples/workflow_handoffbuilder.py
"""

import asyncio
import logging
import os

from agent_framework import Agent, AgentResponseUpdate, MCPStreamableHTTPTool
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import HandoffBuilder
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.console import Console

logging.basicConfig(level=logging.WARNING)
console = Console()

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
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )


async def main() -> None:
    # ── MCP tool for the researcher ────────────────────────────────────────
    async with MCPStreamableHTTPTool(
        name="Microsoft Learn MCP",
        url="https://learn.microsoft.com/api/mcp",
    ) as mcp_server:
        # ── Agents ─────────────────────────────────────────────────────────

        triage = Agent(
            client=client,
            name="triage",
            instructions=(
                "You are a triage coordinator for a content creation team. "
                "Analyze the user's request and hand off to the most appropriate agent: "
                "'researcher' for fact-gathering (preferred first step for most requests), "
                "'writer' for drafting, or 'editor' for review. "
                "Do NOT produce content yourself — just decide who should start and hand off."
            ),
        )

        researcher = Agent(
            client=client,
            name="researcher",
            instructions=(
                "You are a researcher. Use the Microsoft Learn search tool to find "
                "relevant, up-to-date documentation on the given topic. "
                "The Microsoft Agent Framework Python package is documented at "
                "learn.microsoft.com/agent-framework — search for terms like "
                "'agent framework workflow', 'agent framework orchestrations', etc. "
                "Do NOT confuse it with Microsoft Bot Framework — they are different products. "
                "Produce 3-5 concise bullet points summarizing your findings. "
                "When done, hand off to the writer."
            ),
            tools=[mcp_server],
        )

        writer = Agent(
            client=client,
            name="writer",
            instructions=(
                "You are a social media writer specializing in LinkedIn. "
                "Take the researcher's bullet points and write a punchy LinkedIn post "
                "(80-120 words). Use a hook opening, short paragraphs, and a clear CTA. "
                "Include 2-3 relevant hashtags at the end. When done, hand off to the editor."
            ),
        )

        editor = Agent(
            client=client,
            name="editor",
            instructions=(
                "You are a LinkedIn editor. Review the writer's draft for clarity, tone, and engagement. "
                "If you see issues (weak hook, filler, vague CTA, poor formatting), "
                "give 2-3 specific critiques and hand off to the writer for revision. "
                "If the draft is solid or has already been revised, output the polished version "
                "prefixed with 'FINAL:' on the first line. "
                "Each response must EITHER hand off OR output FINAL — never both."
            ),
        )

        # ── Build the handoff workflow (autonomous — no user interaction) ──

        workflow = (
            HandoffBuilder(
                name="content_pipeline",
                participants=[triage, researcher, writer, editor],
                termination_condition=lambda conversation: (
                    len(conversation) > 0 and conversation[-1].text.strip().startswith("FINAL:")
                ),
            )
            .with_start_agent(triage)
            .with_autonomous_mode()
            .build()
        )

        # ── Run ───────────────────────────────────────────────────────────

        prompt = "Write a LinkedIn post about deploying Python agents on Azure Container Apps."
        console.print(f"[bold]Prompt:[/bold] {prompt}\n")

        current_agent = None

        async for event in workflow.run(prompt, stream=True):
            if event.type == "handoff_sent":
                console.print(f"\n🔀 [bold yellow]Handoff:[/bold yellow] {event.data.source} → {event.data.target}\n")

            elif event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                if event.executor_id != current_agent:
                    current_agent = event.executor_id
                    console.print(f"\n🤖 [bold cyan]{current_agent}[/bold cyan]")
                console.print(event.data.text, end="")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

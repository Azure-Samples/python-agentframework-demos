"""
Context bloat without sub-agents.

When an agent uses tools that return large outputs (file contents, search
results, database rows), all that raw data accumulates in the agent's
context window. Over multiple tool calls, this bloats the context,
increasing cost and potentially degrading performance.

This example demonstrates the problem: a single agent reads and searches
source files directly. Every line of source code flows into the agent's
context window alongside the conversation.

Diagram:

 agent.run("user question")
 │
 ▼
 ┌──────────────────────────────────────────────────┐
 │              Code Research Agent                 │
 │                                                  │
 │  1. Calls list_project_files() → full listing    │
 │  2. Calls read_project_file() → entire file      │
 │     contents added to context (repeated N times) │
 │  3. Calls search_project_files() → all matching  │
 │     lines added to context                       │
 │  4. Generates answer from bloated context        │
 └──────────────────────────────────────────────────┘
 │
 ▼
 response (agent saw ALL raw file contents)

Compare with agent_with_subagent.py to see how sub-agents solve this.
"""

import asyncio
import glob
import logging
import os
import sys
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
from rich import print
from rich.logging import RichHandler

# ── Logging ──────────────────────────────────────────────────────────
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── OpenAI client ────────────────────────────────────────────────────
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
    client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4"))

# ── Project root for file tools ──────────────────────────────────────
PROJECT_DIR = os.path.join(os.path.dirname(__file__))


# ── Tools ────────────────────────────────────────────────────────────


@tool
def list_project_files(
    directory: Annotated[
        str, Field(description="Relative directory path within the examples folder, e.g. '.' or 'spanish'.")
    ],
) -> str:
    """List all files in the given directory under the examples folder."""
    logger.info("[📂 Tool] list_project_files('%s')", directory)
    target = os.path.join(PROJECT_DIR, directory)
    if not os.path.isdir(target):
        return f"Error: directory '{directory}' not found."
    entries = sorted(os.listdir(target))
    return "\n".join(entries)


@tool
def read_project_file(
    filepath: Annotated[
        str, Field(description="Relative file path within the examples folder, e.g. 'agent_middleware.py'.")
    ],
) -> str:
    """Read and return the full contents of a file in the examples folder."""
    logger.info("[📄 Tool] read_project_file('%s')", filepath)
    target = os.path.join(PROJECT_DIR, filepath)
    if not os.path.isfile(target):
        return f"Error: file '{filepath}' not found."
    with open(target) as f:
        return f.read()


@tool
def search_project_files(
    query: Annotated[
        str, Field(description="Text to search for (case-insensitive) across all .py files in the examples folder.")
    ],
) -> str:
    """Search all .py files in the examples folder for lines containing the query string."""
    logger.info("[🔍 Tool] search_project_files('%s')", query)
    query_lower = query.lower()
    results: list[str] = []
    for fpath in sorted(glob.glob(os.path.join(PROJECT_DIR, "*.py"))):
        relpath = os.path.relpath(fpath, PROJECT_DIR)
        with open(fpath) as f:
            for lineno, line in enumerate(f, 1):
                if query_lower in line.lower():
                    results.append(f"{relpath}:{lineno}: {line.rstrip()}")
    if not results:
        return f"No matches found for '{query}'."
    if len(results) > 50:
        return "\n".join(results[:50]) + f"\n... ({len(results) - 50} more matches truncated)"
    return "\n".join(results)


# ── Agent ────────────────────────────────────────────────────────────

agent = Agent(
    name="coding-assistant",
    client=client,
    instructions=(
        "You are a helpful coding assistant. You answer questions about "
        "codebases, explain patterns, and help developers understand code. "
        "Use the available tools to list, read, and search Python source "
        "files in the project, then provide a clear, well-organized answer."
    ),
    tools=[list_project_files, read_project_file, search_project_files],
)

# ── Query ────────────────────────────────────────────────────────────

USER_QUERY = "What different middleware patterns are used across this project? Read the relevant files to find out."


async def main() -> None:
    """Run a single query and log token usage."""
    print("\n[bold]=== Code Research WITHOUT Sub-Agents ===[/bold]")
    print("[dim]All file contents flow directly into the agent's context window.[/dim]\n")

    print(f"[blue]User:[/blue] {USER_QUERY}")
    response = await agent.run(USER_QUERY)
    print(f"[green]Assistant:[/green] {response.text}\n")

    # Token usage
    usage = response.usage_details or {}
    input_t = usage.get("input_token_count", 0) or 0
    output_t = usage.get("output_token_count", 0) or 0
    total_t = usage.get("total_token_count", 0) or 0

    print("[bold]── Token Usage ──[/bold]")
    print(f"[yellow]  Assistant tokens:[/yellow]  input={input_t:,}  output={output_t:,}  total={total_t:,}")
    print()
    print("[dim]All raw file contents were in the agent's context window.[/dim]")
    print("[dim]Compare with agent_with_subagent.py to see context isolation in action.[/dim]\n")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())

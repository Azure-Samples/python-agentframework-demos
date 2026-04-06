"""Fan-out/fan-in workflow with explicit edge groups.

Demonstrates: WorkflowBuilder.add_fan_out_edges + add_fan_in_edges.
A dispatcher sends one prompt to three expert agents in parallel, then an
aggregator receives all branch results as a list and consolidates them
into one structured report.

Run:
    uv run examples/workflow_fan_out_fan_in_edges.py
    uv run examples/workflow_fan_out_fan_in_edges.py --devui  (opens DevUI at http://localhost:8097)
"""

import asyncio
import os
import sys
from dataclasses import dataclass

from agent_framework import Agent, AgentExecutorResponse, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
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


class DispatchPrompt(Executor):
    """Emit the same prompt downstream so fan-out edges can broadcast it."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        """Send one prompt message to all downstream expert branches."""
        await ctx.send_message(prompt)


@dataclass
class AggregatedInsights:
    """Typed container for consolidated expert perspectives."""

    research: str
    marketing: str
    legal: str


class AggregateInsights(Executor):
    """Join fan-in branch outputs and emit one consolidated report."""

    @handler
    async def aggregate(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, str],
    ) -> None:
        """Reduce a list of expert responses to one structured summary."""
        expert_outputs: dict[str, str] = {"research": "", "marketing": "", "legal": ""}
        # Process result.executor_id and result.agent_response.text
        for result in results:
            executor_id = result.executor_id.lower()
            text = result.agent_response.text
            if "research" in executor_id:
                expert_outputs["research"] = text
            elif "market" in executor_id:
                expert_outputs["marketing"] = text
            elif "legal" in executor_id:
                expert_outputs["legal"] = text

        aggregated = AggregatedInsights(
            research=expert_outputs["research"],
            marketing=expert_outputs["marketing"],
            legal=expert_outputs["legal"],
        )

        consolidated = (
            "=== Consolidated Launch Brief ===\n\n"
            f"Research Findings:\n{aggregated.research}\n\n"
            f"Marketing Angle:\n{aggregated.marketing}\n\n"
            f"Legal/Compliance Notes:\n{aggregated.legal}\n"
        )
        await ctx.yield_output(consolidated)


dispatcher = DispatchPrompt(id="dispatcher")

researcher = Agent(
    client=client,
    name="Researcher",
    instructions=(
        "You are an expert market researcher. "
        "Given the prompt, provide concise factual insights, opportunities, and risks. "
        "Use short bullet points."
    ),
)

marketer = Agent(
    client=client,
    name="Marketer",
    instructions=(
        "You are a marketing strategist. "
        "Given the prompt, propose clear value proposition and audience messaging. "
        "Use short bullet points."
    ),
)

legal = Agent(
    client=client,
    name="Legal",
    instructions=(
        "You are a legal and compliance reviewer. "
        "Given the prompt, list constraints, disclaimers, and policy concerns. "
        "Use short bullet points."
    ),
)

aggregator = AggregateInsights(id="aggregator")

workflow = (
    WorkflowBuilder(
        name="FanOutFanInEdges",
        description="Explicit fan-out/fan-in using edge groups.",
        start_executor=dispatcher,
        output_executors=[aggregator],
    )
    .add_fan_out_edges(dispatcher, [researcher, marketer, legal])
    .add_fan_in_edges([researcher, marketer, legal], aggregator)
    .build()
)


async def main() -> None:
    """Run the sample with one prompt and print the aggregated output."""
    prompt = "We are launching a budget-friendly electric bike for urban commuters."
    print(f"Prompt: {prompt}\n")

    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8097, auto_open=True)
    else:
        asyncio.run(main())

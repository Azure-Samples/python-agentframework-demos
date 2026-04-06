"""Fan-out/fan-in with LLM summarization aggregation.

Same 3 expert branches as workflow_fan_out_fan_in_edges.py, but instead
of a hand-coded template, a summarizer Agent synthesizes all branch
outputs into a concise executive brief.

Aggregation technique: LLM synthesis (Agent as post-processor).

Run:
    uv run examples/workflow_aggregator_summary.py
    uv run examples/workflow_aggregator_summary.py --devui  (opens DevUI at http://localhost:8101)
"""

import asyncio
import os
import sys

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
        await ctx.send_message(prompt)


class SummarizerExecutor(Executor):
    """Fan-in aggregator that synthesizes expert outputs via a wrapped Agent."""

    agent: Agent

    def __init__(self, client: OpenAIChatClient, id: str = "Summarizer"):
        super().__init__(id=id)
        self.agent = Agent(
            client=client,
            name=id,
            instructions=(
                "You receive analysis from three domain experts (researcher, marketer, legal). "
                "Synthesize their combined insights into a concise 3-sentence executive brief "
                "that a CEO could read in 30 seconds. Do not repeat the raw analysis."
            ),
        )

    @handler
    async def run(self, results: list[AgentExecutorResponse], ctx: WorkflowContext[Never, str]) -> None:
        """Format branch outputs and feed them to the summarizer Agent."""
        sections = []
        for result in results:
            sections.append(f"[{result.executor_id}]\n{result.agent_response.text}")
        combined = "\n\n---\n\n".join(sections)
        response = await self.agent.run(combined)
        await ctx.yield_output(response.text)


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

# The summarizer Executor wraps an Agent that formats the collected
# expert outputs and synthesizes them into a concise executive brief.
summarizer = SummarizerExecutor(client=client)

workflow = (
    WorkflowBuilder(
        name="FanOutFanInLLMSummary",
        description="Fan-out/fan-in with LLM summarization aggregation.",
        start_executor=dispatcher,
        output_executors=[summarizer],
    )
    .add_fan_out_edges(dispatcher, [researcher, marketer, legal])
    .add_fan_in_edges([researcher, marketer, legal], summarizer)
    .build()
)


async def main() -> None:
    """Run the sample and print the LLM-synthesized brief."""
    prompt = "We are launching a budget-friendly electric bike for urban commuters."
    print(f"Prompt: {prompt}\n")

    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print("=== Executive Brief (LLM-synthesized) ===")
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8101, auto_open=True)
    else:
        asyncio.run(main())

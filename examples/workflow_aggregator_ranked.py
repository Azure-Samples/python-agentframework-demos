"""Fan-out/fan-in with LLM-as-judge ranking aggregation.

Three creative agents with different personas (bold, minimalist,
emotional) each propose a marketing slogan.  A ranker Executor collects
the candidates, formats them, and uses an internal judge Agent to score
and rank them — letting the LLM evaluate creativity, memorability, and
brand fit.

Aggregation technique: LLM-as-judge (generate N candidates, rank the best).

Run:
    uv run examples/workflow_aggregator_ranked.py
    uv run examples/workflow_aggregator_ranked.py --devui  (opens DevUI at http://localhost:8104)
"""

import asyncio
import os
import sys

from agent_framework import Agent, AgentExecutorResponse, Executor, Message, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel, Field
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


class RankedSlogan(BaseModel):
    """A single ranked slogan entry."""

    rank: int = Field(description="Rank position, 1 = best.")
    agent_name: str = Field(description="Name of the agent that produced the slogan.")
    slogan: str = Field(description="The marketing slogan text.")
    score: int = Field(description="Score from 1 to 10.")
    justification: str = Field(description="One-sentence justification for the score.")


class RankedSlogans(BaseModel):
    """Typed output: a ranked list of slogans."""

    rankings: list[RankedSlogan] = Field(description="Slogans ranked from best to worst.")


class DispatchPrompt(Executor):
    """Emit the product brief downstream for fan-out broadcast."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(prompt)


class RankerExecutor(Executor):
    """Fan-in aggregator that formats candidate slogans and ranks them via the LLM client directly."""

    def __init__(self, *, client: OpenAIChatClient, id: str = "Ranker") -> None:
        super().__init__(id=id)
        self._client = client

    @handler
    async def run(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, RankedSlogans],
    ) -> None:
        """Collect slogans, format them, and ask the LLM to rank them."""
        lines = []
        for result in results:
            slogan = result.agent_response.text.strip().strip("\"'").split("\n")[0].strip().strip("\"'")
            lines.append(f'- [{result.executor_id}]: "{slogan}"')

        messages = [
            Message(
                role="system",
                contents=[
                    (
                        "You are a senior creative director judging marketing slogans. "
                        "Given a list of candidate slogans, rank them from best to worst. "
                        "For each slogan, give a 1-10 score and a one-sentence justification "
                        "evaluating creativity, memorability, clarity, and brand fit."
                    )
                ],
            ),
            Message(role="user", contents=["Candidate slogans:\n" + "\n".join(lines)]),
        ]
        response = await self._client.get_response(messages, options={"response_format": RankedSlogans})
        await ctx.yield_output(response.value)


dispatcher = DispatchPrompt(id="dispatcher")

bold_writer = Agent(
    client=client,
    name="BoldWriter",
    instructions=(
        "You are a bold, dramatic copywriter. "
        "Given the product brief, propose ONE punchy marketing slogan (max 10 words). "
        "Make it attention-grabbing and confident. Reply with ONLY the slogan."
    ),
)

minimalist_writer = Agent(
    client=client,
    name="MinimalistWriter",
    instructions=(
        "You are a minimalist copywriter who values brevity above all. "
        "Given the product brief, propose ONE ultra-short marketing slogan (max 6 words). "
        "Less is more. Reply with ONLY the slogan."
    ),
)

emotional_writer = Agent(
    client=client,
    name="EmotionalWriter",
    instructions=(
        "You are an empathy-driven copywriter. "
        "Given the product brief, propose ONE marketing slogan (max 10 words) "
        "that connects emotionally with the audience. Reply with ONLY the slogan."
    ),
)

# The ranker Executor calls the LLM client directly to handle fan-in —
# it formats the collected slogans and has the LLM rank them.
ranker = RankerExecutor(client=client)

workflow = (
    WorkflowBuilder(
        name="FanOutFanInRanked",
        description="Generate slogans in parallel, then LLM-judge ranks them.",
        start_executor=dispatcher,
        output_executors=[ranker],
    )
    .add_fan_out_edges(dispatcher, [bold_writer, minimalist_writer, emotional_writer])
    .add_fan_in_edges([bold_writer, minimalist_writer, emotional_writer], ranker)
    .build()
)


async def main() -> None:
    """Run the slogan pipeline and print the ranked results."""
    prompt = "Budget-friendly electric bike for urban commuters. Reliable, affordable, green."
    print(f"Product brief: {prompt}\n")

    events = await workflow.run(prompt)
    for output in events.get_outputs():
        for entry in output.rankings:
            print(f'#{entry.rank} (score {entry.score}) [{entry.agent_name}]: "{entry.slogan}"')
            print(f"   {entry.justification}\n")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8104, auto_open=True)
    else:
        asyncio.run(main())

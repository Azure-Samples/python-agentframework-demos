"""Fan-out/fan-in with structured extraction aggregation.

Three interviewer agents (technical, behavioral, culture-fit) each assess
a job candidate.  The fan-in Executor collects their assessments, calls
the LLM with response_format=CandidateReview, and yields a typed Pydantic
model — ready for downstream code, not prose.

Aggregation technique: LLM structured extraction into a typed model.

Run:
    uv run examples/workflow_aggregator_structured.py
    uv run examples/workflow_aggregator_structured.py --devui  (opens DevUI at http://localhost:8102)
"""

import asyncio
import os
import sys
from typing import Literal

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


class CandidateReview(BaseModel):
    """Typed output produced by the reviewer — suitable for APIs, databases, or scoring engines."""

    technical_score: int = Field(description="Technical skills score from 1 to 10.")
    technical_reason: str = Field(description="Justification for the technical score.")
    behavioral_score: int = Field(description="Behavioral skills score from 1 to 10.")
    behavioral_reason: str = Field(description="Justification for the behavioral score.")
    recommendation: Literal["strong hire", "hire with reservations", "no hire"] = Field(
        description="Final hiring recommendation."
    )


class DispatchPrompt(Executor):
    """Emit the candidate description downstream for fan-out broadcast."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(prompt)


class ExtractReview(Executor):
    """Fan-in aggregator that calls the LLM with response_format to produce a typed CandidateReview."""

    def __init__(self, *, client: OpenAIChatClient, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._client = client

    @handler
    async def extract(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, CandidateReview],
    ) -> None:
        """Collect interviewer assessments and ask the LLM for a structured review."""
        sections = []
        for result in results:
            label = result.executor_id.replace("_", " ").title()
            sections.append(f"[{label}]\n{result.agent_response.text}")
        combined = "\n\n".join(sections)

        messages = [
            Message(
                role="system",
                contents=[
                    (
                        "You are a hiring committee reviewer. "
                        "Based on the following interviewer assessments, produce a structured candidate review."
                    )
                ],
            ),
            Message(role="user", contents=[combined]),
        ]
        response = await self._client.get_response(messages, options={"response_format": CandidateReview})
        review: CandidateReview = response.value
        await ctx.yield_output(review)


dispatcher = DispatchPrompt(id="dispatcher")

technical_interviewer = Agent(
    client=client,
    name="TechnicalInterviewer",
    instructions=(
        "You are a senior engineer conducting a technical interview. "
        "Assess the candidate's technical skills, architecture knowledge, and coding ability. "
        "Be specific about strengths and gaps. Use short bullet points."
    ),
)

behavioral_interviewer = Agent(
    client=client,
    name="BehavioralInterviewer",
    instructions=(
        "You are an HR specialist conducting a behavioral interview. "
        "Assess the candidate's communication, teamwork, conflict resolution, and leadership. "
        "Be specific about strengths and gaps. Use short bullet points."
    ),
)

cultural_interviewer = Agent(
    client=client,
    name="CulturalInterviewer",
    instructions=(
        "You are a team lead assessing culture fit. "
        "Evaluate whether the candidate aligns with a collaborative, fast-paced startup culture. "
        "Be specific about strengths and gaps. Use short bullet points."
    ),
)

extractor = ExtractReview(client=client, id="extractor")

workflow = (
    WorkflowBuilder(
        name="FanOutFanInStructured",
        description="Fan-out/fan-in with Pydantic structured extraction.",
        start_executor=dispatcher,
        output_executors=[extractor],
    )
    .add_fan_out_edges(dispatcher, [technical_interviewer, behavioral_interviewer, cultural_interviewer])
    .add_fan_in_edges([technical_interviewer, behavioral_interviewer, cultural_interviewer], extractor)
    .build()
)


async def main() -> None:
    """Run the interview pipeline and print the typed review."""
    prompt = (
        "Candidate applying for Senior Software Engineer. "
        "5 years experience in Python and distributed systems. "
        "Strong communicator but limited cloud experience."
    )
    print(f"Candidate brief: {prompt}\n")

    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print(f"Recommendation: {output.recommendation}\n")
        print(f"Technical: {output.technical_score}/10 — {output.technical_reason}\n")
        print(f"Behavioral: {output.behavioral_score}/10 — {output.behavioral_reason}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8102, auto_open=True)
    else:
        asyncio.run(main())

"""Fan-out/fan-in with majority-vote aggregation.

Three classifier agents use different reasoning strategies (keyword,
sentiment, intent) to independently categorize a support ticket.  The
fan-in aggregator tallies votes and picks the majority label.

Aggregation technique: majority vote (pure logic, no LLM in aggregator).

Note: In production, using different models per branch would strengthen
the ensemble.  Here we simulate diversity via different prompting
strategies on the same model.

Run:
    uv run examples/workflow_aggregator_voting.py
    uv run examples/workflow_aggregator_voting.py --devui  (opens DevUI at http://localhost:8103)
"""

import asyncio
import os
import sys
from collections import Counter
from enum import Enum

from agent_framework import Agent, AgentExecutorResponse, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel
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


class Category(str, Enum):
    BUG = "bug"
    BILLING = "billing"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"


class Classification(BaseModel):
    """Structured output for each classifier agent."""

    category: Category


class DispatchPrompt(Executor):
    """Emit the ticket text downstream for fan-out broadcast."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(prompt)


class TallyVotes(Executor):
    """Fan-in aggregator that counts votes and picks the majority label."""

    @handler
    async def tally(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, str],
    ) -> None:
        """Count classifier votes and yield the winning category."""
        votes: list[tuple[str, str]] = []
        for result in results:
            classification = Classification.model_validate_json(result.agent_response.text)
            votes.append((result.executor_id, classification.category.value))

        labels = [label for _, label in votes]
        counter = Counter(labels)
        winner, count = counter.most_common(1)[0]

        report = f"  Result: {winner} ({count}/{len(votes)} votes)\n"
        for agent_id, label in votes:
            report += f"    {agent_id}: {label}\n"
        await ctx.yield_output(report)


dispatcher = DispatchPrompt(id="dispatcher")

keyword_classifier = Agent(
    client=client,
    name="KeywordClassifier",
    instructions=(
        "Classify the support ticket into exactly one category: bug, billing, feature_request, or general.\n"
        "Rules:\n"
        "- If the message mentions error, crash, bug, broken, or fail → bug\n"
        "- If the message mentions invoice, charge, payment, refund, or subscription → billing\n"
        "- If the message mentions add, wish, suggest, request, or would be nice → feature_request\n"
        "- Otherwise → general"
    ),
    default_options={"response_format": Classification},
)

sentiment_classifier = Agent(
    client=client,
    name="SentimentClassifier",
    instructions=(
        "Classify the support ticket into exactly one category: bug, billing, feature_request, or general.\n"
        "Analyze the emotional tone:\n"
        "- Frustrated or angry about something not working → bug\n"
        "- Confused or upset about money/charges → billing\n"
        "- Enthusiastic or hopeful about new capabilities → feature_request\n"
        "- Neutral informational inquiry → general"
    ),
    default_options={"response_format": Classification},
)

intent_classifier = Agent(
    client=client,
    name="IntentClassifier",
    instructions=(
        "Classify the support ticket into exactly one category: bug, billing, feature_request, or general.\n"
        "Focus on what the user wants to accomplish:\n"
        "- Wants something fixed or repaired → bug\n"
        "- Wants a refund, explanation of charges, or account adjustment → billing\n"
        "- Wants a new feature or improvement → feature_request\n"
        "- Wants general information or has a question → general"
    ),
    default_options={"response_format": Classification},
)

tally = TallyVotes(id="tally")

workflow = (
    WorkflowBuilder(
        name="FanOutFanInVoting",
        description="Ensemble classification with majority-vote aggregation.",
        start_executor=dispatcher,
        output_executors=[tally],
    )
    .add_fan_out_edges(dispatcher, [keyword_classifier, sentiment_classifier, intent_classifier])
    .add_fan_in_edges([keyword_classifier, sentiment_classifier, intent_classifier], tally)
    .build()
)


async def main() -> None:
    """Run several sample tickets and show vote breakdowns."""
    samples = [
        # Clear-cut: all three should agree
        "The app crashes every time I try to upload a photo. Error code 500.",
        # Keyword → feature_request (add, wish), Sentiment → bug (angry), Intent → bug (fix broken)
        "I wish the export button actually worked. Please add a fix — I'm losing data daily!",
        # Keyword → bug (error, fail), Sentiment → feature_request (hopeful), Intent → feature_request (new ability)
        "The current search fails on long queries — it would be amazing if you could add fuzzy matching.",
    ]

    for sample in samples:
        print(f"Ticket: {sample}")
        events = await workflow.run(sample)
        for output in events.get_outputs():
            print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8103, auto_open=True)
    else:
        asyncio.run(main())

"""Email agent workflow with tool approval for sensitive operations.

Demonstrates: @tool(approval_mode="always_require"), Content type checking
with data.type == "function_approval_request", to_function_approval_response(),
and an event loop that handles approval requests via get_request_info_events().

An email-writing agent processes incoming emails and uses tools to look up
context and send replies. Tools like send_email and read_historical_email_data
require human approval before execution, while tools like get_current_date
run automatically.

Run:
    uv run examples/workflow_hitl_tool_approval.py
"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Annotated

from agent_framework import (
    AgentExecutorResponse,
    Content,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    handler,
    tool,
)
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from typing_extensions import Never

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")

# Configure the chat client based on the API host
async_credential = None
if API_HOST == "azure":
    async_credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model_id=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
elif API_HOST == "github":
    client = OpenAIChatClient(
        base_url="https://models.github.ai/inference",
        api_key=os.environ["GITHUB_TOKEN"],
        model_id=os.getenv("GITHUB_MODEL", "openai/gpt-5-mini"),
    )
else:
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model_id=os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    )


# --- Tools ---
# Tools with approval_mode="always_require" will pause the workflow for human approval.
# Tools with approval_mode="never_require" execute automatically.


@tool(approval_mode="never_require")
def get_current_date() -> str:
    """Get the current date in YYYY-MM-DD format."""
    return "2026-03-05"


@tool(approval_mode="never_require")
def get_team_members_email_addresses() -> list[dict[str, str]]:
    """Get the email addresses of team members."""
    return [
        {"name": "Alice", "email": "alice@contoso.com", "position": "Software Engineer"},
        {"name": "Bob", "email": "bob@contoso.com", "position": "Product Manager"},
        {"name": "Charlie", "email": "charlie@contoso.com", "position": "Senior Software Engineer"},
    ]


@tool(approval_mode="always_require")
async def read_historical_email_data(
    email_address: Annotated[str, "The email address to read historical data from"],
    start_date: Annotated[str, "The start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "The end date in YYYY-MM-DD format"],
) -> list[dict[str, str]]:
    """Read historical email data for a given email address and date range."""
    historical_data = {
        "alice@contoso.com": [
            {
                "from": "alice@contoso.com",
                "to": "john@contoso.com",
                "date": "2026-03-03",
                "subject": "Bug Bash Results",
                "body": "We just completed the bug bash and found a few issues that need immediate attention.",
            },
        ],
        "bob@contoso.com": [
            {
                "from": "bob@contoso.com",
                "to": "john@contoso.com",
                "date": "2026-03-04",
                "subject": "Team Outing",
                "body": "Don't forget about the team outing this Friday!",
            },
        ],
    }
    emails = historical_data.get(email_address, [])
    return [email for email in emails if start_date <= email["date"] <= end_date]


@tool(approval_mode="always_require")
async def send_email(
    to: Annotated[str, "The recipient email address"],
    subject: Annotated[str, "The email subject"],
    body: Annotated[str, "The email body"],
) -> str:
    """Send an email."""
    await asyncio.sleep(0.5)  # Simulate sending
    return "Email successfully sent."


# --- Data model ---


@dataclass
class Email:
    sender: str
    subject: str
    body: str


# --- Executors ---


class EmailPreprocessor(Executor):
    def __init__(self, priority_senders: set[str]) -> None:
        super().__init__(id="email_preprocessor")
        self.priority_senders = priority_senders

    @handler
    async def preprocess(self, email: Email, ctx: WorkflowContext[str]) -> None:
        """Add priority context if the sender is important."""
        email_payload = f"Incoming email:\nFrom: {email.sender}\nSubject: {email.subject}\nBody: {email.body}"
        message = email_payload
        if email.sender in self.priority_senders:
            note = (
                "Priority sender context: this message is business-critical. "
                "If additional context is needed, use available tools to retrieve "
                "relevant prior communication."
            )
            message = f"{note}\n\n{email_payload}"
        await ctx.send_message(message)


@executor(id="conclude_workflow")
async def conclude_workflow(
    email_response: AgentExecutorResponse,
    ctx: WorkflowContext[Never, str],
) -> None:
    """Yield the final email response as output."""
    await ctx.yield_output(email_response.agent_response.text)


# --- Main ---


async def main() -> None:
    """Run the email agent workflow with tool approval."""
    email_writer_agent = client.as_agent(
        name="EmailWriter",
        instructions="You are an excellent email assistant. You respond to incoming emails.",
        tools=[
            read_historical_email_data,
            send_email,
            get_current_date,
            get_team_members_email_addresses,
        ],
    )

    email_processor = EmailPreprocessor(priority_senders={"mike@contoso.com"})

    workflow = (
        WorkflowBuilder(start_executor=email_processor, output_executors=[conclude_workflow])
        .add_edge(email_processor, email_writer_agent)
        .add_edge(email_writer_agent, conclude_workflow)
        .build()
    )

    incoming_email = Email(
        sender="mike@contoso.com",
        subject="Important: Project Update",
        body="Please provide your team's status update on the project since last week.",
    )

    print(f"📧 Incoming email from {incoming_email.sender}: {incoming_email.subject}\n")

    events = await workflow.run(incoming_email)
    request_info_events = events.get_request_info_events()

    while request_info_events:
        responses: dict[str, Content] = {}
        for request_info_event in request_info_events:
            data = request_info_event.data
            if not isinstance(data, Content) or data.type != "function_approval_request":
                raise ValueError(f"Unexpected request info content type: {type(data)}")
            if data.function_call is None:
                raise ValueError("Function call information is missing in the approval request.")

            arguments = json.dumps(data.function_call.parse_arguments(), indent=2)
            print(f"🔒 Approval requested for: {data.function_call.name}")
            print(f"   Arguments:\n{arguments}")

            approval = input("   Approve? (y/n): ").strip().lower()
            approved = approval == "y"
            print(f"   {'✅ Approved' if approved else '❌ Rejected'}\n")
            responses[request_info_event.request_id] = data.to_function_approval_response(approved=approved)

        events = await workflow.run(responses=responses)
        request_info_events = events.get_request_info_events()

    print("📨 Final email response:")
    print(events.get_outputs()[0])

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

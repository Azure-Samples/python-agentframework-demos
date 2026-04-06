"""Standalone agent with tool approval — no workflow required.

Demonstrates: @tool(approval_mode="always_require") with a plain Agent,
handling user_input_requests, and re-running the agent with approval context.

An expense reporting agent can look up receipts automatically but must get
human approval before submitting an expense report. This shows the simplest
HITL pattern: tool approval on a standalone agent without any workflow.

Run:
    uv run examples/agent_tool_approval.py
"""

import asyncio
import os
from typing import Annotated, Any

from agent_framework import Agent, Message, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

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


# --- Tools ---

submitted_reports: list[dict[str, str]] = []

receipts_db: dict[str, dict[str, str]] = {
    "R-001": {"vendor": "Office Depot", "amount": "$142.50", "category": "Office Supplies", "date": "2026-03-01"},
    "R-002": {"vendor": "Delta Airlines", "amount": "$489.00", "category": "Travel", "date": "2026-02-28"},
    "R-003": {"vendor": "Uber Eats", "amount": "$32.75", "category": "Meals", "date": "2026-03-03"},
}


@tool(approval_mode="never_require")
def lookup_receipt(
    receipt_id: Annotated[str, "The receipt ID to look up"],
) -> dict[str, str]:
    """Look up a receipt by ID and return its details."""
    return receipts_db.get(receipt_id, {"error": f"Receipt {receipt_id} not found"})


@tool(approval_mode="always_require")
def submit_expense_report(
    description: Annotated[str, "Description of the expense report"],
    total_amount: Annotated[str, "Total amount to reimburse"],
    receipt_ids: Annotated[str, "Comma-separated receipt IDs included"],
) -> str:
    """Submit an expense report for reimbursement. Requires manager approval."""
    report = {"description": description, "total_amount": total_amount, "receipt_ids": receipt_ids}
    submitted_reports.append(report)
    return f"Expense report submitted: {description} for {total_amount} (receipts: {receipt_ids})"


# --- Main ---


agent = Agent(
    client=client,
    name="ExpenseAgent",
    instructions=(
        "You are an expense reporting assistant. Help users look up receipts and submit expense reports. "
        "Always look up the receipt details before including them in an expense report."
    ),
    tools=[lookup_receipt, submit_expense_report],
)


async def main() -> None:
    query = "Look up receipts R-001 and R-002, then submit an expense report for both."
    print(f"👤 User: {query}\n")

    result = await agent.run(query)

    # Loop while there are pending approval requests
    while len(result.user_input_requests) > 0:
        new_inputs: list[Any] = [query]

        for request in result.user_input_requests:
            func_call = request.function_call
            print(f"🔒 Approval requested: {func_call.name}")
            print(f"   Arguments: {func_call.arguments}")

            # Add the assistant message containing the approval request
            new_inputs.append(Message("assistant", [request]))

            approval = input("   Approve? (y/n): ").strip().lower()
            approved = approval == "y"
            print(f"   {'✅ Approved' if approved else '❌ Rejected'}\n")

            # Add the user's approval response
            new_inputs.append(Message("user", [request.to_function_approval_response(approved)]))

        # Re-run with approval context
        result = await agent.run(new_inputs)

    print(f"🤖 {agent.name}: {result.text}")

    if submitted_reports:
        print(f"\n📋 {len(submitted_reports)} report(s) submitted:")
        for report in submitted_reports:
            print(f"   - {report['description']} | {report['total_amount']} | receipts: {report['receipt_ids']}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

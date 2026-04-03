"""Batch evaluation of agent responses using Azure AI Evaluation's evaluate() function.

Reads evaluation data from a JSONL file (produced by agent_evaluation_generate.py) and runs
all evaluators in a single batch call. Optionally logs results to Azure AI Foundry
if AZURE_AI_PROJECT is set.

Usage:
    python agent_evaluation_batch.py                          # uses eval_data.jsonl
    AZURE_AI_PROJECT=<url> python agent_evaluation_batch.py   # logs to Azure AI Foundry
"""

import logging
import os
from pathlib import Path

import rich
from azure.ai.evaluation import (
    AzureOpenAIModelConfiguration,
    IntentResolutionEvaluator,
    OpenAIModelConfiguration,
    ResponseCompletenessEvaluator,
    TaskAdherenceEvaluator,
    ToolCallAccuracyEvaluator,
    evaluate,
)
from dotenv import load_dotenv
from rich.logging import RichHandler
from rich.table import Table

handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")

if API_HOST == "azure":
    model_config = AzureOpenAIModelConfiguration(
        type="azure_openai",
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
elif API_HOST == "github":
    model_config = OpenAIModelConfiguration(
        type="openai",
        base_url="https://models.github.ai/inference",
        api_key=os.environ["GITHUB_TOKEN"],
        model="openai/gpt-4.1-mini",
    )
else:
    model_config = OpenAIModelConfiguration(
        type="openai",
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
    )

# Optional: Set AZURE_AI_PROJECT in .env to log results to Azure AI Foundry.
# Example: https://your-account.services.ai.azure.com/api/projects/your-project
AZURE_AI_PROJECT = os.getenv("AZURE_AI_PROJECT")


def display_evaluation_results(eval_result: dict) -> None:
    """Display batch evaluation results in a formatted table using rich."""
    result_keys = {
        "IntentResolution": "intent_resolution",
        "ResponseCompleteness": "response_completeness",
        "TaskAdherence": "task_adherence",
        "ToolCallAccuracy": "tool_call_accuracy",
    }

    rows = eval_result.get("rows", [])

    for i, row in enumerate(rows):
        table = Table(title=f"Evaluation Results - Row {i + 1}", show_lines=True)
        table.add_column("Evaluator", style="cyan", width=28)
        table.add_column("Score", style="bold", justify="center", width=8)
        table.add_column("Result", justify="center", width=8)
        table.add_column("Reason", style="dim", width=70)

        for display_name, key in result_keys.items():
            score = str(row.get(f"outputs.{key}.{key}", "N/A"))
            pass_fail = row.get(f"outputs.{key}.{key}_result", "N/A")
            reason = row.get(f"outputs.{key}.{key}_reason", "N/A")

            if pass_fail == "pass":
                result_str = "[green]pass[/green]"
            elif pass_fail == "fail":
                result_str = "[red]fail[/red]"
            else:
                result_str = str(pass_fail)

            table.add_row(display_name, score, result_str, reason)

        rich.print()
        rich.print(table)


def main() -> None:
    """Run batch evaluation on a JSONL data file."""
    eval_data_file = Path(__file__).parent / "eval_data.jsonl"

    if not eval_data_file.exists():
        logger.error(f"Data file not found: {eval_data_file}")
        logger.error("Run agent_evaluation_generate.py first to generate evaluation data.")
        return

    logger.info(f"Running batch evaluation on {eval_data_file}...")

    optional_kwargs: dict = {}
    if AZURE_AI_PROJECT:
        logger.info(f"Logging results to Azure AI project: {AZURE_AI_PROJECT}")
        optional_kwargs["azure_ai_project"] = AZURE_AI_PROJECT
    else:
        optional_kwargs["output_path"] = str(Path(__file__).parent / "eval_results.json")

    eval_result = evaluate(
        data=eval_data_file,
        evaluators={
            "intent_resolution": IntentResolutionEvaluator(model_config, is_reasoning_model=True),
            "response_completeness": ResponseCompletenessEvaluator(model_config, is_reasoning_model=True),
            "task_adherence": TaskAdherenceEvaluator(model_config, is_reasoning_model=True),
            "tool_call_accuracy": ToolCallAccuracyEvaluator(model_config, is_reasoning_model=True),
        },
        # ResponseCompletenessEvaluator expects a plain text response, not a message list,
        # so we override its column mapping to use response_text and ground_truth.
        # Other evaluators auto-map correctly since data keys match param names.
        evaluator_config={
            "response_completeness": {
                "column_mapping": {
                    "response": "${data.response_text}",
                    "ground_truth": "${data.ground_truth}",
                }
            },
        },
        **optional_kwargs,
    )

    display_evaluation_results(eval_result)

    if AZURE_AI_PROJECT:
        studio_url = eval_result.get("studio_url")
        if studio_url:
            print(f"\nView results in Azure AI Foundry:\n{studio_url}")
    else:
        logger.info("Results saved to eval_results.json")


if __name__ == "__main__":
    main()

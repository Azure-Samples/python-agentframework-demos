"""Generate evaluation data for the travel planner agent.

Runs the agent on multiple test queries and saves the results to a JSONL file
that can be used with agent_evaluation_batch.py.

Usage:
    python agent_evaluation_generate.py
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
from rich import print
from rich.logging import RichHandler
from rich.panel import Panel

handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )


@tool
def get_weather(
    city: Annotated[str, Field(description="The city to get the weather forecast for.")],
    date_range: Annotated[str, Field(description="Date range in format 'YYYY-MM-DD to YYYY-MM-DD'.")],
) -> dict:
    """Returns a weather forecast for a city over a date range, including temperature and conditions."""
    logger.info(f"Getting weather for {city} ({date_range})")
    return {
        "city": city,
        "date_range": date_range,
        "forecast": [
            {"date": "Day 1", "high_f": 65, "low_f": 52, "conditions": "Partly cloudy"},
            {"date": "Day 2", "high_f": 70, "low_f": 55, "conditions": "Sunny"},
            {"date": "Day 3", "high_f": 62, "low_f": 50, "conditions": "Light rain"},
        ],
    }


@tool
def search_flights(
    origin: Annotated[str, Field(description="Departure city or airport code.")],
    destination: Annotated[str, Field(description="Arrival city or airport code.")],
    departure_date: Annotated[str, Field(description="Departure date in YYYY-MM-DD format.")],
    return_date: Annotated[str, Field(description="Return date in YYYY-MM-DD format.")],
) -> list[dict]:
    """Searches for round-trip flights and returns options with prices."""
    logger.info(f"Searching flights {origin} -> {destination} ({departure_date} to {return_date})")
    return [
        {"airline": "SkyAir", "price_usd": 850, "duration": "14h 20m", "stops": 1},
        {"airline": "OceanWings", "price_usd": 720, "duration": "16h 45m", "stops": 2},
        {"airline": "DirectJet", "price_usd": 1100, "duration": "12h 30m", "stops": 0},
    ]


@tool
def search_hotels(
    city: Annotated[str, Field(description="The city to search hotels in.")],
    checkin: Annotated[str, Field(description="Check-in date in YYYY-MM-DD format.")],
    checkout: Annotated[str, Field(description="Check-out date in YYYY-MM-DD format.")],
    max_price_per_night: Annotated[int, Field(description="Maximum price per night in USD.")],
) -> list[dict]:
    """Searches for hotels within a nightly budget and returns options with ratings."""
    logger.info(f"Searching hotels in {city} ({checkin} to {checkout}, max ${max_price_per_night}/night)")
    return [
        {"name": "Budget Inn Tokyo", "price_per_night_usd": 80, "rating": 3.8, "neighborhood": "Asakusa"},
        {"name": "Sakura Hotel", "price_per_night_usd": 120, "rating": 4.2, "neighborhood": "Shinjuku"},
        {"name": "Tokyo Garden Suites", "price_per_night_usd": 200, "rating": 4.6, "neighborhood": "Ginza"},
    ]


@tool
def get_activities(
    city: Annotated[str, Field(description="The city to find activities in.")],
    interests: Annotated[list[str], Field(description="List of interests, e.g. ['hiking', 'museums'].")],
) -> list[dict]:
    """Returns activity suggestions for a city based on user interests."""
    logger.info(f"Getting activities in {city} for interests: {interests}")
    activities = []
    if "hiking" in [i.lower() for i in interests]:
        activities.extend(
            [
                {"name": "Mt. Takao Day Hike", "cost_usd": 15, "duration": "4-5 hours"},
                {"name": "Kamakura Trail Walk", "cost_usd": 25, "duration": "3 hours"},
            ]
        )
    if "museums" in [i.lower() for i in interests]:
        activities.extend(
            [
                {"name": "Tokyo National Museum", "cost_usd": 10, "duration": "2-3 hours"},
                {"name": "teamLab Borderless", "cost_usd": 30, "duration": "2 hours"},
            ]
        )
    if not activities:
        activities = [{"name": "City walking tour", "cost_usd": 0, "duration": "3 hours"}]
    return activities


@tool
def estimate_budget(
    total_budget: Annotated[int, Field(description="Total trip budget in USD.")],
    num_days: Annotated[int, Field(description="Number of days for the trip.")],
) -> dict:
    """Provides a recommended budget breakdown for flights, hotels, activities, and food."""
    logger.info(f"Estimating budget: ${total_budget} for {num_days} days")
    flight_pct = 0.40
    hotel_pct = 0.30
    activities_pct = 0.15
    food_pct = 0.15
    return {
        "total_budget_usd": total_budget,
        "flights_usd": int(total_budget * flight_pct),
        "hotels_usd": int(total_budget * hotel_pct),
        "hotels_per_night_usd": int(total_budget * hotel_pct / num_days),
        "activities_usd": int(total_budget * activities_pct),
        "food_usd": int(total_budget * food_pct),
        "food_per_day_usd": int(total_budget * food_pct / num_days),
    }


tools = [get_weather, search_flights, search_hotels, get_activities, estimate_budget]

tool_definitions = [t.to_json_schema_spec()["function"] for t in tools]

AGENT_INSTRUCTIONS = (
    "You are a travel planning assistant. Help users plan trips by checking weather, "
    "finding flights and hotels within budget, and suggesting activities based on their interests. "
    "Always provide a complete itinerary with costs for each component and ensure the total stays "
    "within the user's budget. Include weather information to help with packing."
)

agent = Agent(
    client=client,
    instructions=AGENT_INSTRUCTIONS,
    tools=tools,
)

# Test queries and their expected ground truth responses
TEST_CASES = [
    {
        "query": "Plan a 3-day trip from New York (JFK) to Tokyo, departing March 15 and returning March 18, 2026. My budget is $2000 total. I like hiking and museums. Please search for flights, hotels under $150/night, check the weather, and suggest activities.",
        "ground_truth": (
            "A complete 3-day Tokyo trip itinerary from New York including: round-trip flight options with prices, "
            "hotel recommendations within nightly budget, hiking activities (e.g. Mt. Takao), museum visits "
            "(e.g. Tokyo National Museum, teamLab Borderless), weather forecast for the travel dates, "
            "a full cost breakdown showing total under $2000, and packing suggestions based on weather."
        ),
    },
    {
        "query": "Plan a 5-day trip from San Francisco (SFO) to Tokyo, departing April 1 and returning April 6, 2026. My budget is $3000 total and I love museums. Please search for flights, hotels under $200/night, check the weather, and suggest museum activities.",
        "ground_truth": (
            "A complete 5-day Tokyo trip itinerary from San Francisco including: round-trip flight options with "
            "prices, hotel recommendations within nightly budget, museum activity suggestions "
            "(e.g. Tokyo National Museum, teamLab Borderless), weather forecast for the travel dates, "
            "a full cost breakdown showing total under $3000, and packing suggestions based on weather."
        ),
    },
    {
        "query": "Plan a weekend trip from Los Angeles (LAX) to Tokyo, departing Friday March 20 and returning Sunday March 22, 2026. My budget is $1500 total. I enjoy hiking. Please search for flights, hotels under $100/night, check the weather, and suggest hiking activities.",
        "ground_truth": (
            "A complete 2-day Tokyo trip itinerary from Los Angeles including: round-trip flight options with "
            "prices, hotel recommendations within nightly budget, hiking activity suggestions "
            "(e.g. Mt. Takao, Kamakura Trail Walk), weather forecast for the travel dates, "
            "a full cost breakdown showing total under $1500, and packing suggestions based on weather."
        ),
    },
]


def convert_to_evaluator_messages(messages) -> list[dict]:
    """Convert agent framework ChatMessages to the Azure AI Evaluation message schema."""
    evaluator_messages = []
    for msg in messages:
        role = str(msg.role.value) if hasattr(msg.role, "value") else str(msg.role)
        content_items = []
        for c in msg.contents:
            if c.type == "function_call":
                content_items.append(
                    {
                        "type": "tool_call",
                        "tool_call_id": c.call_id,
                        "name": c.name,
                        "arguments": json.loads(c.arguments) if isinstance(c.arguments, str) else c.arguments,
                    }
                )
            elif c.type == "function_result":
                if c.call_id:
                    if content_items:
                        evaluator_messages.append({"role": role, "content": content_items})
                        content_items = []
                    evaluator_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": c.call_id,
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_result": c.result,
                                }
                            ],
                        }
                    )
                    continue
                content_items.append(
                    {
                        "type": "tool_result",
                        "tool_result": c.result,
                    }
                )
            elif c.type == "text" and c.text:
                content_items.append({"type": "text", "text": c.text})
        if content_items:
            evaluator_messages.append({"role": role, "content": content_items})
    return evaluator_messages


async def main():
    output_file = Path(__file__).parent / "eval_data.jsonl"

    logger.info(f"Generating evaluation data for {len(TEST_CASES)} test cases...")

    with open(output_file, "w", encoding="utf-8") as f:
        for i, test_case in enumerate(TEST_CASES):
            query = test_case["query"]
            logger.info(f"[{i + 1}/{len(TEST_CASES)}] Running agent: {query[:60]}...")

            response = await agent.run(query)
            print(Panel(response.text, title=f"Response {i + 1}", border_style="blue"))

            eval_query = [
                {"role": "system", "content": AGENT_INSTRUCTIONS},
                {"role": "user", "content": [{"type": "text", "text": query}]},
            ]

            eval_data_row = {
                "query": eval_query,
                "response": convert_to_evaluator_messages(response.messages),
                "response_text": response.text,
                "ground_truth": test_case["ground_truth"],
                "tool_definitions": tool_definitions,
            }
            f.write(json.dumps(eval_data_row) + "\n")

    logger.info(f"Evaluation data saved to {output_file}")
    logger.info(f"Run batch evaluation with: python agent_evaluation_batch.py {output_file}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

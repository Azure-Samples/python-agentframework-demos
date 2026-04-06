import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.observability import create_resource, enable_instrumentation
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from azure.monitor.opentelemetry import configure_azure_monitor
from dotenv import load_dotenv
from pydantic import Field
from rich import print
from rich.logging import RichHandler

# Setup logging
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure OpenTelemetry export to Azure Application Insights
load_dotenv(override=True)
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    resource=create_resource(),
    enable_live_metrics=True,
)
enable_instrumentation(enable_sensitive_data=True)
logger.info("Azure Application Insights export enabled")

# Configure OpenAI client based on environment
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
    city: Annotated[str, Field(description="City name, spelled out fully")],
) -> dict:
    """Returns weather data for a given city, a dictionary with temperature and description."""
    logger.info(f"Getting weather for {city}")
    weather_options = [
        {"temperature": 72, "description": "Sunny"},
        {"temperature": 60, "description": "Rainy"},
        {"temperature": 55, "description": "Cloudy"},
        {"temperature": 45, "description": "Windy"},
    ]
    return random.choice(weather_options)


@tool
def get_current_time(
    timezone_name: Annotated[str, Field(description="Timezone name, e.g. 'US/Eastern', 'Asia/Tokyo', 'UTC'")],
) -> str:
    """Returns the current date and time in UTC (timezone_name is for display context only)."""
    logger.info(f"Getting current time for {timezone_name}")
    now = datetime.now(timezone.utc)
    return f"The current time in {timezone_name} is approximately {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"


agent = Agent(
    name="weather-time-agent",
    client=client,
    instructions="You are a helpful assistant that can look up weather and time information.",
    tools=[get_weather, get_current_time],
)


async def main():
    response = await agent.run("What's the weather in Seattle and what time is it in Tokyo?")
    print(response.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

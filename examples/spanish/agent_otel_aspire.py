import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.observability import configure_otel_providers
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
from rich import print
from rich.logging import RichHandler

# Configura logging
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configura OpenTelemetry (lee OTEL_EXPORTER_OTLP_* y ENABLE_CONSOLE_EXPORTERS del entorno)
configure_otel_providers(enable_sensitive_data=True)

# Configura el cliente para usar Azure OpenAI u OpenAI
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
    city: Annotated[str, Field(description="City name, spelled out fully")],
) -> dict:
    """Devuelve datos meteorológicos para una ciudad: temperatura y descripción."""
    logger.info(f"Obteniendo el clima para {city}")
    weather_options = [
        {"temperature": 22, "description": "Soleado"},
        {"temperature": 15, "description": "Lluvioso"},
        {"temperature": 13, "description": "Nublado"},
        {"temperature": 7, "description": "Ventoso"},
    ]
    return random.choice(weather_options)


@tool
def get_current_time(
    timezone_name: Annotated[str, Field(description="Timezone name, e.g. 'US/Eastern', 'America/Mexico_City', 'UTC'")],
) -> str:
    """Devuelve la fecha y hora actual en UTC (timezone_name es solo para contexto de visualización)."""
    logger.info(f"Obteniendo la hora actual para {timezone_name}")
    now = datetime.now(timezone.utc)
    return f"La hora actual en {timezone_name} es aproximadamente {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"


agent = Agent(
    name="weather-time-agent",
    client=client,
    instructions="Eres un asistente útil que puede consultar información del clima y la hora.",
    tools=[get_weather, get_current_time],
)


async def main():
    response = await agent.run("¿Cómo está el clima en Ciudad de México y qué hora es en Buenos Aires?")
    print(response.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

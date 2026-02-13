import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from typing import Annotated

from agent_framework import ChatAgent
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

# Configura la exportación de OpenTelemetry al Aspire Dashboard (si el endpoint está configurado)
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    os.environ.setdefault("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    os.environ.setdefault("OTEL_SERVICE_NAME", "agent-framework-demo")
    configure_otel_providers(enable_sensitive_data=True)
    logger.info(f"Exportación OpenTelemetry habilitada — enviando a {otlp_endpoint}")
else:
    logger.info(
        "Configura OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 en .env"
        " para exportar telemetría al Aspire Dashboard"
    )

# Configura el cliente para usar Azure OpenAI, GitHub Models u OpenAI
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")

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


def get_current_time(
    timezone_name: Annotated[
        str, Field(description="Timezone name, e.g. 'US/Eastern', 'America/Mexico_City', 'UTC'")
    ],
) -> str:
    """Devuelve la fecha y hora actual en UTC (timezone_name es solo para contexto de visualización)."""
    logger.info(f"Obteniendo la hora actual para {timezone_name}")
    now = datetime.now(timezone.utc)
    return f"La hora actual en {timezone_name} es aproximadamente {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"


agent = ChatAgent(
    name="weather-time-agent",
    chat_client=client,
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

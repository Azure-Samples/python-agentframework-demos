import asyncio
import logging
import os
import random
import uuid
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework.redis import RedisContextProvider
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
from rich import print
from rich.logging import RichHandler

# Configurar logging
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configurar cliente de OpenAI según el entorno
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

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


# NOTA: approval_mode="never_require" es para que la muestra sea más corta.
# Usa "always_require" en producción.
@tool
def get_weather(
    city: Annotated[str, Field(description="The city to get the weather for.")],
) -> str:
    """Devuelve datos del clima para una ciudad."""
    logger.info(f"Obteniendo el clima para {city}")
    conditions = ["soleado", "nublado", "lluvioso", "tormentoso"]
    return f"El clima en {city} está {conditions[random.randint(0, 3)]} con una máxima de {random.randint(10, 30)}°C."


async def example_agent_with_memory() -> None:
    """Demuestra un agente con memoria de largo plazo en Redis usando RedisContextProvider.

    RedisContextProvider guarda contexto conversacional en Redis y lo recupera
    usando búsqueda de texto completo (BM25) o búsqueda híbrida (BM25 + similitud
    vectorial) cuando se configura un modelo de embeddings.

    Requiere Redis Stack (con el módulo RediSearch): revisa docker-compose.yaml.
    """
    print("\n[bold]=== Agente con memoria en Redis (RedisContextProvider) ===[/bold]")

    user_id = str(uuid.uuid4())

    # RedisContextProvider soporta búsqueda híbrida (texto completo + vector) cuando hay un vectorizador.
    # Sin embargo, ahora hay un mismatch de versiones entre agent-framework-redis y redisvl
    # (cambió el API de HybridQuery), así que por el momento este ejemplo usa solo búsqueda por texto.
    memory_provider = RedisContextProvider(
        source_id="redis_memory",
        redis_url=REDIS_URL,
        index_name="agent_memory_demo",
        prefix="memory_demo",
        application_id="weather_app",
        agent_id="weather_agent",
        user_id=user_id,
        overwrite_index=True,
    )

    agent = Agent(
        client=client,
        instructions=(
            "Eres un asistente de clima útil. Personaliza tus respuestas usando el contexto proporcionado. "
            "Antes de responder, siempre revisa el contexto guardado."
        ),
        tools=[get_weather],
        context_providers=[memory_provider],
    )

    # Paso 1: Enseñarle una preferencia al agente
    print("\n[bold]--- Paso 1: Enseñando una preferencia ---[/bold]")
    print("[blue]Usuario:[/blue] Recuerda que mi ciudad favorita es Tokio.")
    response = await agent.run("Recuerda que mi ciudad favorita es Tokio.")
    print(f"[green]Agente:[/green] {response.text}")

    # Paso 2: Pedirle al agente que recuerde la preferencia
    print("\n[bold]--- Paso 2: Recordando una preferencia ---[/bold]")
    print("[blue]Usuario:[/blue] ¿Cuál es mi ciudad favorita?")
    response = await agent.run("¿Cuál es mi ciudad favorita?")
    print(f"[green]Agente:[/green] {response.text}")

    # Paso 3: Usar una herramienta y verificar que recuerde detalles del resultado
    print("\n[bold]--- Paso 3: Uso de herramientas con memoria ---[/bold]")
    print("[blue]Usuario:[/blue] ¿Cómo está el clima en París?")
    response = await agent.run("¿Cómo está el clima en París?")
    print(f"[green]Agente:[/green] {response.text}")

    print("\n[blue]Usuario:[/blue] ¿Por qué ciudad acabo de preguntar y cómo estuvo el clima?")
    response = await agent.run("¿Por qué ciudad acabo de preguntar y cómo estuvo el clima?")
    print(f"[green]Agente:[/green] {response.text}")


async def main() -> None:
    await example_agent_with_memory()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import os
import random
import uuid
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.mem0 import Mem0ContextProvider
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from mem0 import AsyncMemory
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


async def main() -> None:
    """Demuestra un agente con Mem0 OSS para memoria de largo plazo.

    A diferencia de RedisContextProvider (que guarda mensajes crudos), Mem0 usa
    un LLM para extraer y guardar hechos destilados de las conversaciones.
    Cuando el agente inicia una nueva sesión, Mem0 inyecta recuerdos relevantes
    como contexto.

    Mem0 OSS necesita un LLM y un embedder para extraer memoria. Este ejemplo
    usa Azure OpenAI cuando API_HOST=azure; si no, usa OPENAI_API_KEY.
    """
    print("\n[bold]=== Agente con memoria Mem0 OSS ===[/bold]")

    # Cada usuario tiene un ID único para aislar memorias por usuario
    user_id = str(uuid.uuid4())

    # Configurar Mem0 OSS para usar Azure OpenAI u OpenAI como LLM y embedder
    if API_HOST == "azure":
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        chat_deployment = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
        embedding_deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
        embedding_dims = 3072 if "large" in embedding_deployment else 1536
        mem0_config = {
            "llm": {
                "provider": "azure_openai",
                "config": {
                    "model": chat_deployment,
                    "azure_kwargs": {
                        "azure_deployment": chat_deployment,
                        "azure_endpoint": azure_endpoint,
                        "api_version": "2024-12-01-preview",
                    },
                },
            },
            "embedder": {
                "provider": "azure_openai",
                "config": {
                    "model": embedding_deployment,
                    "embedding_dims": embedding_dims,
                    "azure_kwargs": {
                        "azure_deployment": embedding_deployment,
                        "azure_endpoint": azure_endpoint,
                        "api_version": "2024-12-01-preview",
                    },
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "embedding_model_dims": embedding_dims,
                },
            },
        }
    elif os.getenv("OPENAI_API_KEY"):
        mem0_config = {}  # Mem0 usa OpenAI por defecto vía OPENAI_API_KEY
    else:
        logger.error("Mem0 OSS requiere un LLM para extraer memoria.")
        logger.error("Configura API_HOST=azure (con Azure OpenAI) o define OPENAI_API_KEY.")
        return

    mem0_client = await AsyncMemory.from_config(mem0_config)

    provider = Mem0ContextProvider(source_id="mem0_memory", user_id=user_id, mem0_client=mem0_client)

    agent = Agent(
        client=client,
        instructions=(
            "Eres un asistente de clima útil. Personaliza tus respuestas usando el contexto proporcionado. "
            "Antes de responder, siempre revisa el contexto guardado."
        ),
        tools=[get_weather],
        context_providers=[provider],
    )

    # Paso 1: Enseñarle preferencias al agente
    print("\n[bold]--- Paso 1: Enseñando preferencias ---[/bold]")
    print("[blue]Usuario:[/blue] Recuerda que mi ciudad favorita es Tokio y prefiero Celsius.")
    response = await agent.run("Recuerda que mi ciudad favorita es Tokio y prefiero Celsius.")
    print(f"[green]Agente:[/green] {response.text}")

    # Paso 2: Empezar una nueva sesión: Mem0 debería inyectar hechos recordados
    print("\n[bold]--- Paso 2: Nueva sesión — recordando preferencias ---[/bold]")
    print("[blue]Usuario:[/blue] ¿Cuál es mi ciudad favorita?")
    response = await agent.run("¿Cuál es mi ciudad favorita?")
    print(f"[green]Agente:[/green] {response.text}")

    # Paso 3: Usar una herramienta, demostrando memoria con salidas de herramientas
    print("\n[bold]--- Paso 3: Uso de herramientas con memoria ---[/bold]")
    print("[blue]Usuario:[/blue] ¿Cómo está el clima en mi ciudad favorita?")
    response = await agent.run("¿Cómo está el clima en mi ciudad favorita?")
    print(f"[green]Agente:[/green] {response.text}")

    # Mostrar qué ha guardado Mem0
    print("\n[bold]--- Memorias extraídas ---[/bold]")
    memories = await mem0_client.get_all(user_id=user_id)
    for mem in memories.get("results", []):
        print(f"  [cyan]•[/cyan] {mem.get('memory', '')}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

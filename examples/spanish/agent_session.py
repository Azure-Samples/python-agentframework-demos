import asyncio
import logging
import os
import random
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
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
    city: Annotated[str, Field(description="The city to get the weather for.")],
) -> str:
    """Devuelve datos del clima para una ciudad."""
    logger.info(f"Obteniendo el clima para {city}")
    conditions = ["soleado", "nublado", "lluvioso", "tormentoso"]
    return f"El clima en {city} está {conditions[random.randint(0, 3)]} con una máxima de {random.randint(10, 30)}°C."


agent = Agent(
    client=client,
    instructions="Eres un agente de clima útil.",
    tools=[get_weather],
)


async def example_without_session() -> None:
    """Sin una sesión, cada llamada es independiente: el agente no recuerda mensajes previos."""
    print("\n[bold]=== Sin sesión (sin memoria) ===[/bold]")

    print("[blue]Usuario:[/blue] ¿Cómo está el clima en Seattle?")
    response = await agent.run("¿Cómo está el clima en Seattle?")
    print(f"[green]Agente:[/green] {response.text}")

    print("\n[blue]Usuario:[/blue] ¿Cuál fue la última ciudad por la que pregunté?")
    response = await agent.run("¿Cuál fue la última ciudad por la que pregunté?")
    print(f"[green]Agente:[/green] {response.text}")


async def example_with_session() -> None:
    """Con una sesión, el agente mantiene el contexto a través de varios mensajes."""
    print("\n[bold]=== Con sesión (memoria persistente) ===[/bold]")

    session = agent.create_session()

    print("[blue]Usuario:[/blue] ¿Cómo está el clima en Tokio?")
    response = await agent.run("¿Cómo está el clima en Tokio?", session=session)
    print(f"[green]Agente:[/green] {response.text}")

    print("\n[blue]Usuario:[/blue] ¿Y Londres?")
    response = await agent.run("¿Y Londres?", session=session)
    print(f"[green]Agente:[/green] {response.text}")

    print("\n[blue]Usuario:[/blue] ¿Cuál de esas ciudades tiene mejor clima?")
    response = await agent.run("¿Cuál de esas ciudades tiene mejor clima?", session=session)
    print(f"[green]Agente:[/green] {response.text}")


async def example_session_across_agents() -> None:
    """Una sesión se puede compartir entre distintas instancias de agente."""
    print("\n[bold]=== Sesión compartida entre instancias ===[/bold]")

    session = agent.create_session()

    print("[blue]Usuario:[/blue] ¿Cómo está el clima en París?")
    response = await agent.run("¿Cómo está el clima en París?", session=session)
    print(f"[green]Agente 1:[/green] {response.text}")

    # Crear un segundo agente y continuar con la misma sesión
    agent2 = Agent(
        client=client,
        instructions="Eres un agente de clima útil.",
        tools=[get_weather],
    )

    print("\n[blue]Usuario:[/blue] ¿Cuál fue la última ciudad por la que pregunté?")
    response = await agent2.run("¿Cuál fue la última ciudad por la que pregunté?", session=session)
    print(f"[green]Agente 2:[/green] {response.text}")


async def main() -> None:
    """Ejecuta todos los ejemplos de sesión para demostrar distintos patrones de persistencia."""
    await example_without_session()
    await example_with_session()
    await example_session_across_agents()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

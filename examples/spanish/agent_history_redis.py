# Nota: No agregar tools= a agentes con proveedores de historial — causa errores de ítems duplicados
# con la Responses API. Ver https://github.com/microsoft/agent-framework/issues/3295
import asyncio
import logging
import os
import uuid

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework.redis import RedisHistoryProvider
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
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


async def example_persistent_session() -> None:
    """Una sesión con Redis persiste el historial de conversación incluso tras reinicios."""
    print("\n[bold]=== Sesión persistente en Redis ===[/bold]")

    session_id = str(uuid.uuid4())

    # Fase 1: Iniciar una conversación con un proveedor de historial en Redis
    print("[bold]--- Fase 1: Iniciando conversación ---[/bold]")
    redis_provider = RedisHistoryProvider(source_id="redis_chat", redis_url=REDIS_URL)

    agent = Agent(
        client=client,
        instructions="Eres un asistente útil que recuerda nuestra conversación.",
        context_providers=[redis_provider],
    )

    session = agent.create_session(session_id=session_id)

    print("[blue]Usuario:[/blue] ¡Hola! Me llamo Alicia y me encanta el senderismo.")
    response = await agent.run("¡Hola! Me llamo Alicia y me encanta el senderismo.", session=session)
    print(f"[green]Agente:[/green] {response.text}")

    print("\n[blue]Usuario:[/blue] ¿Qué senderos buenos hay en Colorado?")
    response = await agent.run("¿Qué senderos buenos hay en Colorado?", session=session)
    print(f"[green]Agente:[/green] {response.text}")

    # Fase 2: Simular un reinicio de la app — reconectar usando el mismo session_id en Redis
    print("\n[bold]--- Fase 2: Reanudando después del 'reinicio' ---[/bold]")
    redis_provider2 = RedisHistoryProvider(source_id="redis_chat", redis_url=REDIS_URL)

    agent2 = Agent(
        client=client,
        instructions="Eres un asistente útil que recuerda nuestra conversación.",
        context_providers=[redis_provider2],
    )

    session2 = agent2.create_session(session_id=session_id)

    print("[blue]Usuario:[/blue] ¿Qué recuerdas de mí?")
    response = await agent2.run("¿Qué recuerdas de mí?", session=session2)
    print(f"[green]Agente:[/green] {response.text}")


async def main() -> None:
    """Ejecuta los ejemplos de Redis para demostrar patrones de almacenamiento persistente."""
    # Verificar conectividad con Redis
    import redis as redis_client

    r = redis_client.from_url(REDIS_URL)
    try:
        r.ping()
    except Exception as e:
        logger.error(f"No se puede conectar a Redis en {REDIS_URL}: {e}")
        logger.error(
            "Asegúrate de que Redis esté corriendo (por ejemplo, con el dev container"
            " o con 'docker run -p 6379:6379 redis:7-alpine')."
        )
        return
    finally:
        r.close()

    await example_persistent_session()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

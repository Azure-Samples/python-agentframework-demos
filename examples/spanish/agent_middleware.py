"""
Diagrama de flujo del middleware:

 agent.run("mensaje del usuario")
 │
 ▼
 ┌─────────────────────────────────────────────┐
 │         Agent Middleware                    │
 │  (temporización, bloqueo, registro)         │
 │                                             │
 │  ┌───────────────────────────────────────┐  │
 │  │       Chat Middleware                 │  │
 │  │  (registro, conteo de mensajes)       │  │
 │  │                                       │  │
 │  │        ┌──────────────┐               │  │
 │  │        │  Modelo IA   │               │  │
 │  │        └──────┬───────┘               │  │
 │  │               │ llamadas a funciones  │  │
 │  │               ▼                       │  │
 │  │  ┌──────────────────────────────────┐ │  │
 │  │  │   Function Middleware           │ │  │
 │  │  │  (registro, temporización)       │ │  │
 │  │  │                                  │ │  │
 │  │  │  get_weather(), get_date(), ...  │ │  │
 │  │  └──────────────────────────────────┘ │  │
 │  │               │                       │  │
 │  │               ▼                       │  │
 │  │        ┌──────────────┐               │  │
 │  │        │  Modelo IA   │               │  │
 │  │        │ (resp final) │               │  │
 │  │        └──────────────┘               │  │
 │  └───────────────────────────────────────┘  │
 └─────────────────────────────────────────────┘
 │
 ▼
 respuesta
"""

import asyncio
import logging
import os
import random
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated

from agent_framework import (
    Agent,
    AgentContext,
    AgentMiddleware,
    AgentResponse,
    ChatContext,
    ChatMiddleware,
    FunctionInvocationContext,
    FunctionMiddleware,
    Message,
    tool,
)
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
    client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4"))


# ---- Herramientas ----


@tool
def get_weather(
    city: Annotated[str, Field(description="The city to get the weather for.")],
) -> dict:
    """Devuelve datos del clima para una ciudad dada, con temperatura y descripción."""
    logger.info(f"Obteniendo clima para {city}")
    if random.random() < 0.05:
        return {"temperature": 22, "description": "Soleado"}
    else:
        return {"temperature": 15, "description": "Lluvioso"}


@tool
def get_current_date() -> str:
    """Obtiene la fecha actual del sistema en texto con formato YYYY-MM-DD."""
    logger.info("Obteniendo fecha actual")
    return datetime.now().strftime("%Y-%m-%d")


# ---- Middleware basado en funciones ----


async def timing_agent_middleware(
    context: AgentContext,
    call_next: Callable[[], Awaitable[None]],
) -> None:
    """Middleware de agente que registra el tiempo de ejecución."""
    start = time.perf_counter()
    logger.info("[⏲️ Temporización][ Agent Middleware] Iniciando ejecución del agente")

    await call_next()

    elapsed = time.perf_counter() - start
    logger.info(f"[⏲️ Temporización][ Agent Middleware] Ejecución completada en {elapsed:.2f}s")


async def logging_function_middleware(
    context: FunctionInvocationContext,
    call_next: Callable[[], Awaitable[None]],
) -> None:
    """Middleware de función que registra llamadas y resultados."""
    logger.info(f"[🪵 Registro][ Function Middleware] Llamando a {context.function.name} con args: {context.arguments}")

    await call_next()

    logger.info(f"[🪵 Registro][ Function Middleware] {context.function.name} devolvió: {context.result}")


async def logging_chat_middleware(
    context: ChatContext,
    call_next: Callable[[], Awaitable[None]],
) -> None:
    """Middleware de chat que registra interacciones con la IA."""
    logger.info(f"[💬 Registro][ Chat Middleware] Enviando {len(context.messages)} mensajes a la IA")

    await call_next()

    logger.info("[💬 Registro][ Chat Middleware] Respuesta de la IA recibida")


# ---- Middleware basado en clases ----


class BlockingAgentMiddleware(AgentMiddleware):
    """Middleware de agente que bloquea solicitudes con palabras prohibidas."""

    def __init__(self, blocked_words: list[str]) -> None:
        """Inicializa con una lista de palabras que deben ser bloqueadas."""
        self.blocked_words = blocked_words

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Verifica mensajes con contenido bloqueado y termina si lo encuentra."""
        last_message = context.messages[-1] if context.messages else None
        if last_message and last_message.text:
            for word in self.blocked_words:
                if word.lower() in last_message.text.lower():
                    logger.warning(f"[❌ Bloqueo][ Agent Middleware] Solicitud bloqueada: contiene '{word}'")
                    context.terminate = True
                    context.result = AgentResponse(
                        messages=[
                            Message(
                                role="assistant", contents=[f"Lo siento, no puedo procesar solicitudes sobre '{word}'."]
                            )
                        ]
                    )
                    return

        await call_next()


class TimingFunctionMiddleware(FunctionMiddleware):
    """Middleware de función que mide el tiempo de ejecución de cada llamada."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Mide el tiempo de ejecución de la función y registra la duración."""
        start = time.perf_counter()
        logger.info(f"[⌚️ Temporización][ Function Middleware] Iniciando {context.function.name}")

        await call_next()

        elapsed = time.perf_counter() - start
        logger.info(f"[⌚️ Temporización][ Function Middleware] {context.function.name} tardó {elapsed:.4f}s")


class MessageCountChatMiddleware(ChatMiddleware):
    """Middleware de chat que cuenta el total de mensajes enviados a la IA."""

    def __init__(self) -> None:
        """Inicializa el contador de mensajes."""
        self.total_messages = 0

    async def process(
        self,
        context: ChatContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Cuenta los mensajes y registra el total acumulado."""
        self.total_messages += len(context.messages)
        logger.info(
            "[🔢 Conteo][ Chat Middleware] Mensajes en esta solicitud: %s, total hasta ahora: %s",
            len(context.messages),
            self.total_messages,
        )

        await call_next()

        logger.info("[🔢 Conteo][ Chat Middleware] Respuesta de chat recibida")


# ---- Configuración del agente ----

# Instanciar middleware basado en clases
blocking_middleware = BlockingAgentMiddleware(blocked_words=["nuclear", "clasificado"])
timing_function_middleware = TimingFunctionMiddleware()
message_count_middleware = MessageCountChatMiddleware()

agent = Agent(
    name="middleware-demo",
    client=client,
    instructions=(
        "Ayudas a la gente a planificar su fin de semana. "
        "Usa las herramientas disponibles para consultar el clima y la fecha. "
    ),
    tools=[get_weather, get_current_date],
    middleware=[
        # Middleware a nivel de agente aplicado a TODAS las ejecuciones
        timing_agent_middleware,
        blocking_middleware,
        logging_function_middleware,
        timing_function_middleware,
        logging_chat_middleware,
        message_count_middleware,
    ],
)


async def main() -> None:
    """Ejecuta el agente con diferentes entradas para demostrar el comportamiento del middleware."""
    # Solicitud normal - todo el middleware se ejecuta
    logger.info("=== Solicitud Normal ===")
    response = await agent.run("¿Cómo estará el clima este fin de semana en Madrid?")
    print(response.text)

    # Solicitud bloqueada - el middleware de bloqueo termina anticipadamente
    logger.info("\n=== Solicitud Bloqueada ===")
    response = await agent.run("Cuéntame sobre la física nuclear.")
    print(response.text)

    # Otra solicitud normal con middleware a nivel de ejecución
    logger.info("\n=== Solicitud con Middleware a Nivel de Ejecución ===")

    async def extra_agent_middleware(
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Middleware de ejecución que solo aplica a esta ejecución específica."""
        logger.info("[🏃🏽‍♀️ Middleware de ejecución] Este middleware solo aplica a esta ejecución")
        await call_next()
        logger.info("[🏃🏽‍♀️ Middleware de ejecución] Ejecución completada")

    response = await agent.run(
        "¿Cómo estará el clima en Barcelona?",
        middleware=[extra_agent_middleware],
    )
    print(response.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())

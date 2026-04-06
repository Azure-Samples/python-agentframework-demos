"""Análisis concurrente multi-experto usando orquestación ConcurrentBuilder.

Demuestra: ConcurrentBuilder(participants=[...]) para ejecutar 3 agentes
especialistas en paralelo sobre el mismo prompt del usuario, y luego recopilar
la salida agregada por defecto (lista combinada de mensajes).

Cada participante recibe el prompt original de forma independiente y se ejecuta
concurrentemente. El agregador por defecto fusiona todas las conversaciones de
los agentes en una sola lista de mensajes.

Contraste con workflow_agents_sequential.py, donde los agentes se ejecutan uno
tras otro y cada uno ve la conversación completa hasta ese punto.

Referencia:
    https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/concurrent?pivots=programming-language-python

Ejecutar:
    uv run examples/spanish/workflow_agents_concurrent.py
    uv run examples/spanish/workflow_agents_concurrent.py --devui  (abre DevUI en http://localhost:8105)
"""

import asyncio
import logging
import os
import sys

from agent_framework import Agent, Message
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import ConcurrentBuilder
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.logging import RichHandler

log_handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[log_handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

# Configura el cliente de chat según el proveedor de API
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

# Tres agentes especialistas — cada uno aporta una perspectiva diferente al mismo prompt
researcher = Agent(
    client=client,
    name="Investigador",
    instructions=(
        "Eres un experto en investigación de mercado y productos. "
        "Dado un prompt, proporciona información concisa, factual, oportunidades y riesgos. "
        "Limita tu análisis a un párrafo."
    ),
)

marketer = Agent(
    client=client,
    name="Mercadólogo",
    instructions=(
        "Eres un estratega creativo de marketing. "
        "Elabora una propuesta de valor atractiva y mensajes dirigidos alineados con el prompt. "
        "Limita tu respuesta a un párrafo."
    ),
)

legal = Agent(
    client=client,
    name="Legal",
    instructions=(
        "Eres un revisor cauteloso de asuntos legales y cumplimiento normativo. "
        "Destaca restricciones, advertencias y preocupaciones de política basadas en el prompt. "
        "Limita tu respuesta a un párrafo."
    ),
)

# Construye el workflow concurrente — los tres agentes se ejecutan en paralelo
workflow = ConcurrentBuilder(participants=[researcher, marketer, legal]).build()


async def main():
    prompt = "Estamos lanzando una nueva bicicleta eléctrica económica para viajeros urbanos."
    logger.info("Prompt: %s", prompt)
    result = await workflow.run(prompt)
    outputs = result.get_outputs()

    for conversation in outputs:
        logger.info("===== Conversación agregada =====")
        messages: list[Message] = conversation
        for index, message in enumerate(messages, start=1):
            author = message.author_name or ("assistant" if message.role == "assistant" else "user")
            logger.info("%02d [%s]\n%s", index, author, message.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8105, auto_open=True)
    else:
        asyncio.run(main())

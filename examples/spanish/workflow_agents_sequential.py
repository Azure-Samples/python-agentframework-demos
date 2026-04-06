"""Workflow Escritor → Revisor usando orquestación SequentialBuilder.

Demuestra: SequentialBuilder(participants=[...]) con agentes de IA
y recopilación de la conversación final con workflow.run() + get_outputs().

Cada participante recibe el historial completo de mensajes generado hasta ese punto.

Referencia:
    https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/sequential?pivots=programming-language-python

Ejecutar:
    uv run examples/spanish/workflow_agents_sequential.py
    uv run examples/spanish/workflow_agents_sequential.py --devui  (abre DevUI en http://localhost:8096)
"""

import asyncio
import logging
import os
import sys

from agent_framework import Agent, Message
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import SequentialBuilder
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

writer = Agent(
    client=client,
    name="Escritor",
    instructions=(
        "Eres un escritor de contenido conciso. "
        "Escribe un artículo corto (2-3 párrafos) claro y atractivo sobre el tema del usuario. "
        "Prioriza la precisión y la legibilidad."
    ),
)

reviewer = Agent(
    client=client,
    name="Revisor",
    instructions=(
        "Eres un revisor de contenido reflexivo. "
        "Lee el borrador del escritor y ofrece retroalimentación específica y constructiva. "
        "Comenta sobre la claridad, la precisión y la estructura. Mantén tu revisión concisa."
    ),
)

# Construye el workflow secuencial: Escritor → Revisor
workflow = SequentialBuilder(participants=[writer, reviewer]).build()


async def main():
    prompt = 'Escribe una publicación de LinkedIn de un párrafo: "El error de workflow de IA que casi todos los equipos cometen."'
    logger.info("Prompt: %s", prompt)
    events = await workflow.run(prompt)
    outputs = events.get_outputs()

    for conversation in outputs:
        logger.info("===== Conversación final =====")
        messages: list[Message] = conversation
        for index, message in enumerate(messages, start=1):
            author = message.author_name or ("assistant" if message.role == "assistant" else "user")
            logger.info("%02d [%s]\n%s", index, author, message.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8096, auto_open=True)
    else:
        asyncio.run(main())

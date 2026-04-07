"""Agente hospedado con Durable Task.

Demuestra cómo hospedar un agente usando el Durable Task Scheduler (DTS),
que proporciona persistencia automática de estado y una arquitectura
distribuida worker-client. El estado de la conversación sobrevive reinicios
del worker sin necesidad de código personalizado para checkpoints -- DTS se
encarga de todo.

Este ejemplo ejecuta tanto el worker como el client en un solo proceso
por simplicidad. En producción se ejecutarían por separado, potencialmente
en máquinas diferentes.

Requisitos:
    El emulador DTS se ejecuta automáticamente en el dev container en
    http://dts-emulator:8080. Fuera del dev container, inícialo manualmente:

    docker run -d --name dts-emulator -p 8080:8080 -p 8082:8082 \
        mcr.microsoft.com/dts/dts-emulator:latest

    Dashboard de DTS: http://localhost:8082 (o http://dts-emulator:8082 en dev container)

Ejecución:
    uv run python examples/spanish/agent_durabletask.py

Para más patrones DTS (multi-agente, orquestaciones, HITL, streaming),
ver: https://github.com/microsoft/agent-framework/tree/main/python/samples/04-hosting/durabletask
"""

import os

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_durabletask import DurableAIAgentClient, DurableAIAgentWorker
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from durabletask.azuremanaged.client import DurableTaskSchedulerClient
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
from rich import print

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

DTS_ENDPOINT = os.getenv("DTS_ENDPOINT", "http://dts-emulator:8080")
DTS_TASKHUB = os.getenv("DTS_TASKHUB", "default")

# --- Cliente de chat (mismo patrón que todos los demás ejemplos) ---
if API_HOST == "azure":
    async_credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
    chat_client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
else:
    chat_client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
    )

# --- Agente ---
agent = Agent(
    name="Joker",
    instructions="Cuentas chistes cortos e ingeniosos. Mantén las respuestas en 3 oraciones o menos.",
    client=chat_client,
)

# --- Worker (hospeda el agente como entidad durable en DTS) ---
dts_worker = DurableTaskSchedulerWorker(
    host_address=DTS_ENDPOINT,
    secure_channel=not DTS_ENDPOINT.startswith("http://"),
    taskhub=DTS_TASKHUB,
    token_credential=None,
)
agent_worker = DurableAIAgentWorker(dts_worker)
agent_worker.add_agent(agent)

# --- Client (envía solicitudes al agente a través de DTS) ---
dts_client = DurableTaskSchedulerClient(
    host_address=DTS_ENDPOINT,
    secure_channel=not DTS_ENDPOINT.startswith("http://"),
    taskhub=DTS_TASKHUB,
    token_credential=None,
)
agent_client = DurableAIAgentClient(dts_client)

# --- Bucle de chat interactivo ---
print("[bold]Agente con Durable Task (escribe 'exit' o 'salir' para salir)[/bold]\n")

with dts_worker:
    dts_worker.start()

    joker = agent_client.get_agent("Joker")
    session = joker.create_session()
    print(f"[dim]Sesión: {session.session_id}[/dim]\n")

    while True:
        user_input = input("Tú: ").strip()
        if not user_input or user_input.lower() in ("exit", "salir"):
            break
        response = joker.run(user_input, session=session)
        print(f"\n[bold green]Joker:[/bold green] {response.text}\n")

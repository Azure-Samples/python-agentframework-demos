"""Demo de persistencia con Durable Task — escenario de soporte técnico.

Demuestra: DurableTaskSchedulerWorker, DurableAIAgentClient,
DurableAgentSession.to_dict/from_dict, y persistencia automática de estado.

Un agente de soporte técnico comienza a resolver un problema de Wi-Fi, el
worker se detiene (simulando que el usuario se va a reiniciar su laptop), y
un nuevo worker retoma la misma conversación sin problema — probando que DTS
conserva el estado sin código personalizado para checkpoints.

Ejecución:
    uv run python examples/spanish/agent_durabletask.py
"""

import asyncio
import os

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_durabletask import DurableAIAgentClient, DurableAIAgentWorker, DurableAgentSession
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from durabletask.azuremanaged.client import DurableTaskSchedulerClient
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
from rich import print

# Configurar cliente OpenAI según el entorno
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

# Configuración de DTS
DTS_ENDPOINT = os.getenv("DTS_ENDPOINT", "http://dts-emulator:8080")
DTS_TASKHUB = os.getenv("DTS_TASKHUB", "default")

PLAN_PROMPT = (
    "Mi laptop no se conecta al Wi-Fi. "
    "Ya intenté desactivar y activar el Wi-Fi y olvidar la red."
)
FOLLOWUP_PROMPT = (
    "OK reinicié, y el Wi-Fi ya funciona pero está muy lento. "
    "Las páginas tardan más de 10 segundos en cargar. ¿Qué más puedo intentar?"
)

agent = Agent(
    name="ITSupport",
    instructions=(
        "Eres un agente de soporte técnico amigable. "
        "Responde en 1-2 oraciones cortas — nunca listas ni pasos numerados. "
        "Sugiere UNA sola cosa a la vez. Si la solución requiere irse "
        "(ej. reiniciar), dile al usuario que regrese después."
    ),
    client=client,
)


def create_runtime() -> tuple[DurableTaskSchedulerWorker, DurableAIAgentClient]:
    """Crea un par worker/client de DTS para el demo."""
    is_emulator = DTS_ENDPOINT.startswith("http://")
    credential = None if is_emulator else SyncDefaultAzureCredential()

    dts_worker = DurableTaskSchedulerWorker(
        host_address=DTS_ENDPOINT,
        secure_channel=not is_emulator,
        taskhub=DTS_TASKHUB,
        token_credential=credential,
    )
    agent_worker = DurableAIAgentWorker(dts_worker)
    agent_worker.add_agent(agent)

    dts_client = DurableTaskSchedulerClient(
        host_address=DTS_ENDPOINT,
        secure_channel=not is_emulator,
        taskhub=DTS_TASKHUB,
        token_credential=credential,
    )

    return dts_worker, DurableAIAgentClient(dts_client)


def run_demo() -> bool:
    """Ejecuta un demo de soporte técnico que prueba que el estado sobrevive un reinicio del worker."""
    print("[bold]Demo de persistencia con Durable Task — Soporte Técnico[/bold]\n")

    worker, agent_client = create_runtime()
    with worker:
        print("[cyan]1.[/cyan] Iniciando el primer worker y creando una sesión durable...")
        worker.start()

        support = agent_client.get_agent(agent.name)
        session = support.create_session()
        print(f"   [dim]Sesión: {session.session_id}[/dim]")
        print(f"   [dim]Sesión durable: {session.durable_session_id}[/dim]")

        print("\n[cyan]2.[/cyan] El usuario reporta un problema de Wi-Fi...")
        plan_response = support.run(PLAN_PROMPT, session=session)
        print(f"   [green]Agente:[/green] {plan_response.text}")

        saved_session = session.to_dict()

    print("\n[cyan]3.[/cyan] [bold red]Worker detenido.[/bold red] (El usuario se va a reiniciar su laptop...)")
    print("   Restaurando la misma sesión después del reinicio del worker...")
    restored_session = DurableAgentSession.from_dict(saved_session)

    worker, agent_client = create_runtime()
    with worker:
        worker.start()
        support = agent_client.get_agent(agent.name)

        print("\n[cyan]4.[/cyan] El usuario regresa después de reiniciar — el agente debe recordar el contexto...")
        followup_response = support.run(FOLLOWUP_PROMPT, session=restored_session)
        print(f"   [green]Agente:[/green] {followup_response.text}")

    keywords = ["wi-fi", "wifi", "red", "dns", "conexión", "lento", "lenta"]
    passed = any(kw in followup_response.text.lower() for kw in keywords)
    if passed:
        print("\n[bold green]PASS[/bold green] DTS conservó la conversación de soporte después del reinicio del worker.")
    else:
        print("\n[bold red]FAIL[/bold red] El agente no recordó el contexto de soporte después del reinicio del worker.")

    return passed


async def main() -> None:
    """Ejecuta el demo de persistencia con DTS."""
    run_demo()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

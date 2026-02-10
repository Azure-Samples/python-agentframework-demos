"""Ejemplo de MagenticOne con Agent Framework - Planificación de viaje con múltiples agentes."""
import asyncio
import os
import sys
from typing import cast

from agent_framework import (
    AgentRunUpdateEvent,
    ChatAgent,
    ChatMessage,
    MagenticBuilder,
    MagenticOrchestratorEvent,
    MagenticProgressLedger,
    WorkflowOutputEvent,
)
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

# Configura el cliente de OpenAI según el entorno
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


# Inicializa la consola rich
console = Console()

# Crea los agentes
local_agent = ChatAgent(
    chat_client=client,
    instructions=(
        "Eres un asistente útil: puedes sugerir actividades locales auténticas e interesantes "
        "o lugares para visitar, y puedes usar cualquier información de contexto que te compartan."
    ),
    name="local_agent",
    description="A local assistant who can suggest local activities or places to visit.",
)

language_agent = ChatAgent(
    chat_client=client,
    instructions=(
        "Eres un asistente útil: puedes revisar planes de viaje y dar feedback con tips importantes/críticos "
        "para manejar mejor desafíos de idioma o comunicación en el destino. "
        "Si el plan ya incluye tips de idioma, puedes decir que está bien y explicar por qué."
    ),
    name="language_agent",
    description="A helpful assistant that can provide language tips for a given destination.",
)

travel_summary_agent = ChatAgent(
    chat_client=client,
    instructions=(
        "Eres un asistente útil: puedes tomar todas las sugerencias y consejos de los otros agentes "
        "y armar un plan de viaje final detallado. Asegúrate de que el plan quede integrado y completo. "
        "TU RESPUESTA FINAL DEBE SER EL PLAN COMPLETO. Da un resumen completo cuando ya integraste "
        "todas las perspectivas de los otros agentes."
    ),
    name="travel_summary_agent",
    description="A helpful assistant that can summarize the travel plan.",
)

# Crea un agente manager para la orquestación
manager_agent = ChatAgent(
    chat_client=client,
    instructions="Coordinas un equipo para completar tareas de planificación de viaje de forma eficiente.",
    name="magentic_manager",
    description="Orchestrator that coordinates the travel-planning workflow",
)

# Construye el workflow de Magentic
magentic_orchestrator = (
    MagenticBuilder()
    .participants([local_agent, language_agent, travel_summary_agent])
    .with_manager(
        agent=manager_agent,
        max_round_count=20,
        max_stall_count=3,
        max_reset_count=2,
    )
    .build()
)


async def main():
    # Lleva registro del último mensaje para formatear la salida en modo streaming
    last_message_id: str | None = None
    output_event: WorkflowOutputEvent | None = None

    async for event in magentic_orchestrator.run_stream("Planifica un viaje de medio día a Costa Rica"):
        if isinstance(event, AgentRunUpdateEvent):
            message_id = event.data.message_id
            if message_id != last_message_id:
                if last_message_id is not None:
                    console.print()  # Agregar espacio después del mensaje anterior
                console.print(Rule(f"🤖 {event.executor_id}", style="bold blue"))
                last_message_id = message_id
            console.print(event.data, end="")

        elif isinstance(event, MagenticOrchestratorEvent):
            console.print()  # Asegura que el panel empiece en una nueva línea
            if isinstance(event.data, ChatMessage):
                # Mostrar la creación del plan en un panel
                console.print(
                    Panel(
                        Markdown(event.data.text),
                        title=f"📋 Orquestador: {event.event_type.name}",
                        border_style="bold green",
                        padding=(1, 2),
                    )
                )
            elif isinstance(event.data, MagenticProgressLedger):
                # Mostrar un resumen compacto del progreso en un panel
                ledger = event.data
                satisfied = "✅" if ledger.is_request_satisfied.answer else "⏳ Pasos pendientes"
                progress = "✅" if ledger.is_progress_being_made.answer else "❌ Progreso estancado"
                loop = "⚠️ Bucle detectado" if ledger.is_in_loop.answer else ""
                next_agent = ledger.next_speaker.answer
                instruction = ledger.instruction_or_question.answer

                status_text = (
                    f"¿Plan satisfecho? {satisfied} | ¿Hay progreso? {progress} {loop}\n\n"
                    f"➡️  Siguiente paso: [bold]{next_agent}[/bold]\n"
                    f"{instruction}"
                )
                console.print(
                    Panel(
                        status_text,
                        title=f"📊 Orquestador: {event.event_type.name}",
                        border_style="bold yellow",
                        padding=(1, 2),
                    )
                )

        elif isinstance(event, WorkflowOutputEvent):
            output_event = event

    if output_event:
        console.print()  # Agregar espacio
        # La salida del workflow de Magentic es una lista de ChatMessages con un solo mensaje final
        output_messages = cast(list[ChatMessage], output_event.data)
        if output_messages:
            console.print(
                Panel(
                    Markdown(output_messages[-1].text),
                    title="🌎 Plan de Viaje Final",
                    border_style="bold green",
                    padding=(1, 2),
                )
            )

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[magentic_orchestrator], auto_open=True)
    else:
        asyncio.run(main())

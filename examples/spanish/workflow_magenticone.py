"""Ejemplo de orquestación MagenticOne con el setup de OpenAIChatClient de este repo.

Este ejemplo muestra cómo un manager Magentic coordina tres especialistas para
crear un plan de viaje, con salida en streaming y eventos del ledger de orquestación.

Ejecutar:
    uv run examples/spanish/workflow_magenticone.py
    uv run examples/spanish/workflow_magenticone.py --devui
"""

import asyncio
import json
import os
import sys
from typing import cast

from agent_framework import Agent, AgentResponseUpdate, Message, WorkflowEvent
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import MagenticBuilder, MagenticProgressLedger
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# Configura el cliente OpenAI según el entorno
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

console = Console()


local_agent = Agent(
    client=client,
    instructions=(
        "Sugieres actividades locales auténticas e interesantes o lugares para visitar, "
        "usando cualquier contexto que provea la persona usuaria u otros agentes."
    ),
    name="agente_local",
    description="Specialist in local activities and places.",
)

language_agent = Agent(
    client=client,
    instructions=(
        "Revisas planes de viaje y das recomendaciones prácticas para retos de idioma "
        "y comunicación en el destino. Si ya está bien cubierto, menciónalo con una razón clara."
    ),
    name="agente_idioma",
    description="Specialist in language and communication advice.",
)

travel_summary_agent = Agent(
    client=client,
    instructions=(
        "Sintetizas las sugerencias y recomendaciones de los demás agentes en un plan completo. "
        "Haz suposiciones razonables si faltan detalles. "
        "No hagas preguntas de seguimiento a la persona usuaria. "
        "No pidas confirmaciones ni permisos. "
        "YOUR FINAL RESPONSE MUST BE THE COMPLETE PLAN."
    ),
    name="agente_resumen_viaje",
    description="Specialist in travel-plan synthesis.",
)

manager_agent = Agent(
    client=client,
    name="agente_coordinador",
    description="Magentic manager that coordinates specialists.",
    instructions=(
        "Coordinas especialistas para resolver tareas complejas de forma eficiente. "
        "La persona usuaria no está disponible para preguntas de seguimiento. "
        "Si falta información, elige suposiciones sensatas y continúa. "
        "Asegúrate de terminar con un plan final completo."
    ),
)

magentic_workflow = MagenticBuilder(
    participants=[local_agent, language_agent, travel_summary_agent],
    manager_agent=manager_agent,
    max_round_count=10,
    max_stall_count=1,
    max_reset_count=1,
).build()


def handle_stream_event(event: WorkflowEvent, last_message_id: str | None) -> str | None:
    """Renderiza un evento del stream y regresa el último message id actualizado."""
    if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
        message_id = event.data.message_id
        if message_id != last_message_id:
            if last_message_id is not None:
                console.print()
            console.print(f"🤖 {event.executor_id}:", end=" ")
            last_message_id = message_id
        console.print(event.data, end="")
        return last_message_id

    # Un participante terminó — muestra su salida
    if event.type == "executor_completed" and isinstance(event.data, list) and event.data:
        parts = [msg.text for msg in event.data if isinstance(msg, AgentResponseUpdate) and msg.text]
        if parts:
            full_text = "".join(parts)
            console.print(
                Panel(
                    Markdown(full_text),
                    title=f"🤖 {event.executor_id}",
                    border_style="cyan",
                    padding=(1, 2),
                )
            )
        return last_message_id

    if event.type == "magentic_orchestrator":
        console.print()
        emoji = "✅" if event.data.event_type.name == "PROGRESS_LEDGER_UPDATED" else "🧭"

        if isinstance(event.data.content, MagenticProgressLedger):
            rendered_content = json.dumps(event.data.content.to_dict(), indent=2)
            console.print(
                Panel(
                    rendered_content,
                    title=f"{emoji} Orchestrator: {event.data.event_type.name}",
                    border_style="bold yellow",
                    padding=(1, 2),
                )
            )
        elif hasattr(event.data.content, "text"):
            console.print(
                Panel(
                    Markdown(event.data.content.text),
                    title=f"{emoji} Orchestrator: {event.data.event_type.name}",
                    border_style="bold green",
                    padding=(1, 2),
                )
            )
        else:
            console.print(
                Panel(
                    Markdown(str(event.data.content)),
                    title=f"{emoji} Orchestrator: {event.data.event_type.name}",
                    border_style="bold green",
                    padding=(1, 2),
                )
            )

    return last_message_id


def print_final_result(output_event: WorkflowEvent | None) -> None:
    """Imprime el plan final a partir del evento de salida del workflow."""
    if output_event is None:
        return

    output_messages = cast(list[Message], output_event.data)
    console.print(
        Panel(
            Markdown(output_messages[-1].text),
            title="🌍 Plan de viaje final",
            border_style="bold green",
            padding=(1, 2),
        )
    )


async def main() -> None:
    """Ejecuta el workflow Magentic con salida en streaming."""
    task = (
        "Planea un viaje de medio día en Costa Rica para una familia con dos hijos de 6 y 9 años, "
        "hospedada en San José, con presupuesto medio. "
        "Entrega un itinerario completo con horarios, supuestos de transporte, costos estimados, "
        "recomendación de comida y consejos prácticos de idioma."
    )
    console.print(f"[bold]Tarea:[/bold] {task}\n")

    last_message_id: str | None = None
    output_event: WorkflowEvent | None = None

    async for event in magentic_workflow.run(task, stream=True):
        last_message_id = handle_stream_event(event, last_message_id)
        if event.type == "output" and not isinstance(event.data, AgentResponseUpdate):
            output_event = event

    print_final_result(output_event)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[magentic_workflow], auto_open=True)
    else:
        asyncio.run(main())

"""Orquestación de handoff con reglas explícitas de ruteo (soporte al cliente).

Demuestra: HandoffBuilder con reglas .add_handoff() que aplican lógica de
negocio — por ejemplo, triage no puede rutear directo al agente de reembolsos;
solo return_agent puede escalar a refunds.

Reglas de ruteo:
    triage_agent  -> order_agent, return_agent   (NO refund_agent)
    order_agent   -> triage_agent
    return_agent  -> triage_agent, refund_agent  (único camino a refunds)
    refund_agent  -> triage_agent

Referencia:
    https://learn.microsoft.com/agent-framework/workflows/orchestrations/handoff?pivots=programming-language-python#configure-handoff-rules-1

Ejecutar:
    uv run examples/spanish/workflow_handoffbuilder_rules.py
    uv run examples/spanish/workflow_handoffbuilder_rules.py --devui
"""

import asyncio
import logging
import os
import sys

from agent_framework import Agent, AgentResponseUpdate, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import HandoffBuilder
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
from rich.console import Console

logging.basicConfig(level=logging.WARNING)
console = Console()

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
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )


# ── Herramientas ────────────────────────────────────────────────────────────


@tool
def initiate_return(
    order_id: str = Field(description="The order ID to return"),
    reason: str = Field(description="Reason for the return"),
) -> str:
    """Inicia una devolución de producto y genera una etiqueta de envío prepagada."""
    return (
        f"Devolución iniciada para el pedido {order_id} (motivo: {reason}). "
        f"La etiqueta de devolución RL-{order_id}-2026 fue enviada por correo al cliente. "
        "Por favor, deja el paquete en cualquier punto de envío dentro de 14 días."
    )


@tool
def process_refund(
    order_id: str = Field(description="The order ID to refund"),
    amount: str = Field(description="Refund amount in USD"),
) -> str:
    """Procesa un reembolso al método de pago original del cliente."""
    return (
        f"Reembolso de ${amount} para el pedido {order_id} procesado. "
        "Aparecerá en el método de pago original en 5-10 días hábiles. "
        f"Número de confirmación: RF-{order_id}-2026."
    )


# ── Agentes ───────────────────────────────────────────────────────────────

triage_agent = Agent(
    client=client,
    name="agente_triaje",
    instructions=(
        "Eres un agente de triage de soporte al cliente. Reconoce brevemente el problema del cliente "
        "y haz handoff de inmediato al especialista correcto: agente_pedidos para temas de pedidos, "
        "agente_devoluciones para devoluciones. No puedes gestionar reembolsos directamente. "
        "NO pidas detalles adicionales al cliente — el especialista se encargará. "
        "Cuando el caso esté resuelto, di '¡Adiós!' para terminar la sesión."
    ),
)

order_agent = Agent(
    client=client,
    name="agente_pedidos",
    instructions=(
        "Atiendes consultas sobre el estado del pedido. Busca el pedido del cliente y da una actualización breve. "
        "Al terminar, haz handoff de vuelta a agente_triaje."
    ),
)

return_agent = Agent(
    client=client,
    name="agente_devoluciones",
    instructions=(
        "Atiendes devoluciones de productos. Usa la herramienta initiate_return con la información proporcionada "
        "para crear la devolución — NO pidas detalles adicionales al cliente. "
        "Si también quiere un reembolso, haz handoff a agente_reembolsos después de iniciar la devolución. "
        "De lo contrario, haz handoff de vuelta a agente_triaje al terminar."
    ),
    tools=[initiate_return],
)

refund_agent = Agent(
    client=client,
    name="agente_reembolsos",
    instructions=(
        "Procesas reembolsos por artículos devueltos. Usa la herramienta process_refund para emitir el reembolso "
        "con la información ya proporcionada — NO pidas detalles adicionales al cliente. "
        "Si el monto exacto no se conoce, usa una estimación razonable basada en el contexto. "
        "Confirma el resultado y haz handoff a agente_triaje al terminar."
    ),
    tools=[process_refund],
)

# ── Construye el workflow de handoff con reglas explícitas ─────────────────

workflow = (
    HandoffBuilder(
        name="handoff_soporte_cliente",
        participants=[triage_agent, order_agent, return_agent, refund_agent],
        termination_condition=lambda conversation: (len(conversation) > 0 and "adiós" in conversation[-1].text.lower()),
    )
    .with_start_agent(triage_agent)
    # triage_agent no puede rutear directamente a refund_agent
    .add_handoff(triage_agent, [order_agent, return_agent])
    # Solo return_agent puede escalar a refund_agent
    .add_handoff(return_agent, [refund_agent, triage_agent])
    # Todos los especialistas pueden regresar a triage
    .add_handoff(order_agent, [triage_agent])
    .add_handoff(refund_agent, [triage_agent])
    .with_autonomous_mode()
    .build()
)


async def main() -> None:
    """Ejecuta un workflow de soporte con handoff y reglas explícitas de ruteo."""
    request = (
        "Quiero devolver una chamarra que compré la semana pasada y recibir un reembolso. "
        "Pedido #12345, es una chamarra azul impermeable de senderismo, talla M, llegó con el cierre roto. "
        "Pagué $89.99 y quiero el reembolso a mi tarjeta de crédito."
    )
    console.print(f"[bold]Solicitud:[/bold] {request}\n")

    current_agent = None

    async for event in workflow.run(request, stream=True):
        if event.type == "handoff_sent":
            console.print(f"\n🔀 [bold yellow]Handoff:[/bold yellow] {event.data.source} → {event.data.target}\n")

        elif event.type == "output" and isinstance(event.data, AgentResponseUpdate):
            if event.executor_id != current_agent:
                current_agent = event.executor_id
                console.print(f"\n🤖 [bold cyan]{current_agent}[/bold cyan]")
            console.print(event.data.text, end="")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8098, auto_open=True)
    else:
        asyncio.run(main())

"""Ruteo multi-selección impulsado por LLM con uno-o-muchos destinos.

Demuestra: WorkflowBuilder.add_multi_selection_edge_group donde un solo
mensaje de origen puede activar uno o múltiples ejecutores downstream. El
paso parse-ticket usa una llamada al LLM con salidas estructuradas
(response_format) para que la clasificación sea semántica, no basada en
palabras clave.

Ejecutar:
    uv run examples/spanish/workflow_multi_selection_edge_group.py
    uv run examples/spanish/workflow_multi_selection_edge_group.py --devui  (abre DevUI en http://localhost:8099)
"""

import asyncio
import os
import sys

from agent_framework import Executor, Message, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing_extensions import Never

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


class Ticket(BaseModel):
    """Representación estructurada de un ticket de soporte, producida por el LLM."""

    text: str = Field(description="The original ticket text.")
    is_bug: bool = Field(description="True if the ticket describes a bug, error, or crash.")
    is_billing: bool = Field(description="True if the ticket relates to billing, invoices, or charges.")
    is_urgent: bool = Field(description="True if the ticket conveys urgency.")


class ParseTicketExecutor(Executor):
    """Parsea texto entrante a metadata de ruteo tipada usando un LLM."""

    def __init__(self, *, client: OpenAIChatClient, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._client = client

    @handler
    async def parse(self, text: str, ctx: WorkflowContext[Ticket]) -> None:
        """Llama al LLM con salidas estructuradas para clasificar el ticket."""
        messages = [
            Message(
                role="system",
                contents=[
                    (
                        "Eres un clasificador de tickets de soporte. Dado un mensaje de un cliente, "
                        "determina si describe un bug, si se relaciona con billing y si es urgente. "
                        "Devuelve la clasificación como JSON estructurado."
                    )
                ],
            ),
            Message(role="user", contents=[text]),
        ]
        response = await self._client.get_response(messages, options={"response_format": Ticket})
        ticket: Ticket = response.value
        await ctx.send_message(ticket)


class SupportExecutor(Executor):
    """Handler por defecto de soporte al cliente."""

    @handler
    async def handle(self, ticket: Ticket, ctx: WorkflowContext[Never, str]) -> None:
        """Emite salida de manejo de soporte."""
        urgency = "alta" if ticket.is_urgent else "normal"
        await ctx.yield_output(f"[Soporte] Abrí un caso de prioridad {urgency} para: {ticket.text}")


class EngineeringExecutor(Executor):
    """Handler de triage de ingeniería para tickets relacionados a bugs."""

    @handler
    async def handle(self, ticket: Ticket, ctx: WorkflowContext[Never, str]) -> None:
        """Emite salida de manejo de ingeniería."""
        await ctx.yield_output(f"[Ingeniería] Enviado a triage de bugs: {ticket.text}")


class BillingExecutor(Executor):
    """Handler de operaciones de facturación para temas de cargos/invoices."""

    @handler
    async def handle(self, ticket: Ticket, ctx: WorkflowContext[Never, str]) -> None:
        """Emite salida de manejo de facturación."""
        await ctx.yield_output(f"[Facturación] Enviado a revisión de cargos: {ticket.text}")


def select_targets(ticket: Ticket, target_ids: list[str]) -> list[str]:
    """Selecciona uno o varios destinos downstream según la metadata del ticket.

    Orden esperado para ``target_ids``:
    [support_id, engineering_id, billing_id]
    """
    support_id, engineering_id, billing_id = target_ids

    selected = [support_id]
    if ticket.is_bug:
        selected.append(engineering_id)
    if ticket.is_billing:
        selected.append(billing_id)
    return selected


parse_ticket = ParseTicketExecutor(client=client, id="parse_ticket")
support = SupportExecutor(id="support")
engineering = EngineeringExecutor(id="engineering")
billing = BillingExecutor(id="billing")

workflow = (
    WorkflowBuilder(
        name="SeleccionMultiple",
        description="One input can route to one-or-many targets via a selection function.",
        start_executor=parse_ticket,
    )
    .add_multi_selection_edge_group(
        parse_ticket,
        [support, engineering, billing],
        selection_func=select_targets,
    )
    .build()
)


async def main() -> None:
    """Ejecuta tres ejemplos deterministas de ruteo."""
    samples = [
        "Urgente: la app se crashea al iniciar sesión con error 500.",
        "Pregunta sobre un cargo de facturación en mi invoice.",
        "Solicitud de feature: agrega modo oscuro.",
    ]

    for sample in samples:
        print(f"\nTicket: {sample}")
        events = await workflow.run(sample)
        for output in events.get_outputs():
            print(f"  {output}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8099, auto_open=True)
    else:
        asyncio.run(main())

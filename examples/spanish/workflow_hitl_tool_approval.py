"""Workflow de agente de correo con aprobación de herramientas para operaciones sensibles.

Demuestra: @tool(approval_mode="always_require"), verificación de tipo Content
con data.type == "function_approval_request", to_function_approval_response(),
y un bucle de eventos que maneja solicitudes de aprobación via get_request_info_events().

Un agente de redacción de correos procesa correos entrantes y usa herramientas para
buscar contexto y enviar respuestas. Herramientas como send_email y read_historical_email_data
requieren aprobación humana antes de ejecutarse, mientras que herramientas como get_current_date
se ejecutan automáticamente.

Ejecutar:
    uv run examples/spanish/workflow_hitl_tool_approval.py
"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Annotated

from agent_framework import (
    AgentExecutorResponse,
    Content,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    handler,
    tool,
)
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from typing_extensions import Never

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

# Configura el cliente según el host de la API
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


# --- Herramientas ---
# Las herramientas con approval_mode="always_require" pausarán el workflow para aprobación humana.
# Las herramientas con approval_mode="never_require" se ejecutan automáticamente.


@tool(approval_mode="never_require")
def get_current_date() -> str:
    """Obtiene la fecha actual en formato YYYY-MM-DD."""
    return "2026-03-05"


@tool(approval_mode="never_require")
def get_team_members_email_addresses() -> list[dict[str, str]]:
    """Obtiene las direcciones de correo de los miembros del equipo."""
    return [
        {"name": "Alice", "email": "alice@contoso.com", "position": "Ingeniera de Software"},
        {"name": "Bob", "email": "bob@contoso.com", "position": "Gerente de Producto"},
        {"name": "Charlie", "email": "charlie@contoso.com", "position": "Ingeniero de Software Senior"},
    ]


@tool(approval_mode="always_require")
async def read_historical_email_data(
    email_address: Annotated[str, "The email address to read historical data from"],
    start_date: Annotated[str, "The start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "The end date in YYYY-MM-DD format"],
) -> list[dict[str, str]]:
    """Lee datos históricos de correo para una dirección y rango de fechas."""
    historical_data = {
        "alice@contoso.com": [
            {
                "from": "alice@contoso.com",
                "to": "john@contoso.com",
                "date": "2026-03-03",
                "subject": "Resultados del Bug Bash",
                "body": (
                    "Acabamos de completar el bug bash y encontramos algunos"
                    " problemas que necesitan atención inmediata."
                ),
            },
        ],
        "bob@contoso.com": [
            {
                "from": "bob@contoso.com",
                "to": "john@contoso.com",
                "date": "2026-03-04",
                "subject": "Salida del equipo",
                "body": "¡No olvides la salida del equipo este viernes!",
            },
        ],
    }
    emails = historical_data.get(email_address, [])
    return [email for email in emails if start_date <= email["date"] <= end_date]


@tool(approval_mode="always_require")
async def send_email(
    to: Annotated[str, "The recipient email address"],
    subject: Annotated[str, "The email subject"],
    body: Annotated[str, "The email body"],
) -> str:
    """Envía un correo electrónico."""
    await asyncio.sleep(0.5)  # Simula el envío
    return "Correo enviado exitosamente."


# --- Modelo de datos ---


@dataclass
class Email:
    sender: str
    subject: str
    body: str


# --- Executors ---


class EmailPreprocessor(Executor):
    def __init__(self, priority_senders: set[str]) -> None:
        super().__init__(id="email_preprocessor")
        self.priority_senders = priority_senders

    @handler
    async def preprocess(self, email: Email, ctx: WorkflowContext[str]) -> None:
        """Agrega contexto de prioridad si el remitente es importante."""
        email_payload = f"Correo entrante:\nDe: {email.sender}\nAsunto: {email.subject}\nCuerpo: {email.body}"
        message = email_payload
        if email.sender in self.priority_senders:
            note = (
                "Contexto de remitente prioritario: este mensaje es crítico para el negocio. "
                "Si se necesita contexto adicional, usa las herramientas disponibles para recuperar "
                "comunicaciones previas relevantes."
            )
            message = f"{note}\n\n{email_payload}"
        await ctx.send_message(message)


@executor(id="conclude_workflow")
async def conclude_workflow(
    email_response: AgentExecutorResponse,
    ctx: WorkflowContext[Never, str],
) -> None:
    """Emite la respuesta final del correo como salida."""
    await ctx.yield_output(email_response.agent_response.text)


# --- Principal ---


async def main() -> None:
    """Ejecuta el workflow del agente de correo con aprobación de herramientas."""
    email_writer_agent = client.as_agent(
        name="EmailWriter",
        instructions="Eres un excelente asistente de correo electrónico. Respondes a correos entrantes.",
        tools=[
            read_historical_email_data,
            send_email,
            get_current_date,
            get_team_members_email_addresses,
        ],
    )

    email_processor = EmailPreprocessor(priority_senders={"mike@contoso.com"})

    workflow = (
        WorkflowBuilder(start_executor=email_processor, output_executors=[conclude_workflow])
        .add_edge(email_processor, email_writer_agent)
        .add_edge(email_writer_agent, conclude_workflow)
        .build()
    )

    incoming_email = Email(
        sender="mike@contoso.com",
        subject="Importante: Actualización del Proyecto",
        body="Por favor proporciona la actualización de estado de tu equipo sobre el proyecto desde la semana pasada.",
    )

    print(f"📧 Correo entrante de {incoming_email.sender}: {incoming_email.subject}\n")

    events = await workflow.run(incoming_email)
    request_info_events = events.get_request_info_events()

    while request_info_events:
        responses: dict[str, Content] = {}
        for request_info_event in request_info_events:
            data = request_info_event.data
            if not isinstance(data, Content) or data.type != "function_approval_request":
                raise ValueError(f"Tipo de contenido inesperado en request info: {type(data)}")
            if data.function_call is None:
                raise ValueError("Falta la información de llamada a función en la solicitud de aprobación.")

            arguments = json.dumps(data.function_call.parse_arguments(), indent=2)
            print(f"🔒 Aprobación solicitada para: {data.function_call.name}")
            print(f"   Argumentos:\n{arguments}")

            approval = input("   ¿Aprobar/Approve? (s/y): ").strip().lower()
            approved = approval in ("s", "y")
            print(f"   {'✅ Aprobado' if approved else '❌ Rechazado'}\n")
            responses[request_info_event.request_id] = data.to_function_approval_response(approved=approved)

        events = await workflow.run(responses=responses)
        request_info_events = events.get_request_info_events()

    print("📨 Respuesta final del correo:")
    print(events.get_outputs()[0])

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

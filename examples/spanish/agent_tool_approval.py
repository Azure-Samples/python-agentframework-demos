"""Agente independiente con aprobación de herramientas — no se requiere workflow.

Demuestra: @tool(approval_mode="always_require") con un Agent simple,
manejo de user_input_requests, y re-ejecución del agente con contexto de aprobación.

Un agente de reportes de gastos puede buscar recibos automáticamente pero debe obtener
aprobación humana antes de enviar un reporte de gastos. Esto muestra el patrón HITL
más simple: aprobación de herramientas en un agente independiente sin ningún workflow.

Ejecutar:
    uv run examples/spanish/agent_tool_approval.py
"""

import asyncio
import os
from typing import Annotated, Any

from agent_framework import Agent, Message, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")

# Configura el cliente según el host de la API
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
        model_id=os.getenv("GITHUB_MODEL", "openai/gpt-4.1-mini"),
    )
else:
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model_id=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    )


# --- Herramientas ---

submitted_reports: list[dict[str, str]] = []

receipts_db: dict[str, dict[str, str]] = {
    "R-001": {
        "vendor": "Librería Nacional", "amount": "$142.50", "category": "Útiles de Oficina", "date": "2026-03-01",
    },
    "R-002": {"vendor": "LATAM Airlines", "amount": "$489.00", "category": "Viajes", "date": "2026-02-28"},
    "R-003": {"vendor": "Rappi", "amount": "$32.75", "category": "Comidas", "date": "2026-03-03"},
}


@tool(approval_mode="never_require")
def lookup_receipt(
    receipt_id: Annotated[str, "The receipt ID to look up"],
) -> dict[str, str]:
    """Busca un recibo por ID y devuelve sus detalles."""
    return receipts_db.get(receipt_id, {"error": f"Recibo {receipt_id} no encontrado"})


@tool(approval_mode="always_require")
def submit_expense_report(
    description: Annotated[str, "Description of the expense report"],
    total_amount: Annotated[str, "Total amount to reimburse"],
    receipt_ids: Annotated[str, "Comma-separated receipt IDs included"],
) -> str:
    """Envía un reporte de gastos para reembolso. Requiere aprobación del gerente."""
    report = {"description": description, "total_amount": total_amount, "receipt_ids": receipt_ids}
    submitted_reports.append(report)
    return f"Reporte de gastos enviado: {description} por {total_amount} (recibos: {receipt_ids})"


# --- Principal ---


agent = Agent(
    client=client,
    name="ExpenseAgent",
    instructions=(
        "Eres un asistente de reportes de gastos. Ayuda a los usuarios a buscar recibos y enviar reportes de gastos. "
        "Siempre busca los detalles del recibo antes de incluirlos en un reporte de gastos."
    ),
    tools=[lookup_receipt, submit_expense_report],
)


async def main() -> None:
    query = "Busca los recibos R-001 y R-002, luego envía un reporte de gastos por ambos."
    print(f"👤 Usuario: {query}\n")

    result = await agent.run(query)

    # Bucle mientras haya solicitudes de aprobación pendientes
    while len(result.user_input_requests) > 0:
        new_inputs: list[Any] = [query]

        for request in result.user_input_requests:
            func_call = request.function_call
            print(f"🔒 Aprobación solicitada: {func_call.name}")
            print(f"   Argumentos: {func_call.arguments}")

            # Agrega el mensaje del asistente que contiene la solicitud de aprobación
            new_inputs.append(Message("assistant", [request]))

            approval = input("   ¿Aprobar/Approve? (s/n): ").strip().lower()
            approved = approval == "s"
            print(f"   {'✅ Aprobado' if approved else '❌ Rechazado'}\n")

            # Agrega la respuesta de aprobación del usuario
            new_inputs.append(Message("user", [request.to_function_approval_response(approved)]))

        # Re-ejecuta con contexto de aprobación
        result = await agent.run(new_inputs)

    print(f"🤖 {agent.name}: {result.text}")

    if submitted_reports:
        print(f"\n📋 {len(submitted_reports)} reporte(s) enviado(s):")
        for report in submitted_reports:
            print(f"   - {report['description']} | {report['total_amount']} | recibos: {report['receipt_ids']}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

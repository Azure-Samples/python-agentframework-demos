"""Workflow Escritor → Revisor usando agentes de IA como ejecutores.

Demuestra: Agent como ejecutor de WorkflowBuilder, aristas directas
y recopilación de salida con workflow.run() + get_outputs().

Este ejemplo usa el mismo patrón WorkflowBuilder + add_edge que
workflow_rag_ingest.py, pero con agentes de IA en lugar de funciones Python.

Ejecutar:
    uv run examples/spanish/workflow_agents.py
    uv run examples/spanish/workflow_agents.py --devui  (abre DevUI en http://localhost:8092)
"""

import asyncio
import os
import sys

from agent_framework import Agent, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

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

# Crea los agentes de IA — se pasan directamente como ejecutores al WorkflowBuilder,
# igual que las subclases de Executor en workflow_rag_ingest.py.
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

# Construye el workflow: Escritor → Revisor
# El mismo patrón WorkflowBuilder.add_edge funciona tanto para ejecutores Python
# como para agentes de IA — la estructura del grafo es idéntica.
workflow = WorkflowBuilder(start_executor=writer).add_edge(writer, reviewer).build()


async def main():
    prompt = 'Escribe una publicación de LinkedIn de 2 frases: "Por qué tu piloto de IA se ve bien, pero falla en producción."'
    print(f"Prompt: {prompt}\n")
    events = await workflow.run(prompt)

    for output in events.get_outputs():
        print("===== Salida =====")
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8092, auto_open=True)
    else:
        asyncio.run(main())

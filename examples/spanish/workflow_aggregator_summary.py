"""Fan-out/fan-in con agregación por resumido del LLM.

Las mismas 3 ramas expertas que workflow_fan_out_fan_in_edges.py, pero en
vez de una plantilla codificada a mano, un agente resumidor sintetiza las
salidas de todas las ramas en un brief ejecutivo conciso.

Técnica de agregación: síntesis por LLM (Agent como post-procesador).

Ejecutar:
    uv run examples/spanish/workflow_aggregator_summary.py
    uv run examples/spanish/workflow_aggregator_summary.py --devui  (abre DevUI en http://localhost:8101)
"""

import asyncio
import os
import sys

from agent_framework import Agent, AgentExecutorResponse, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
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


class DispatchPrompt(Executor):
    """Emite el mismo prompt hacia abajo para que las aristas fan-out lo transmitan."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(prompt)


class SummarizerExecutor(Executor):
    """Agregador fan-in que sintetiza las salidas expertas mediante un Agent envuelto."""

    agent: Agent

    def __init__(self, client: OpenAIChatClient, id: str = "Summarizer"):
        super().__init__(id=id)
        self.agent = Agent(
            client=client,
            name=id,
            instructions=(
                "Recibes análisis de tres expertos de dominio (investigador, marketer, legal). "
                "Sintetiza sus insights combinados en un brief ejecutivo conciso de 3 oraciones "
                "que un CEO pueda leer en 30 segundos. No repitas el análisis en bruto."
            ),
        )

    @handler
    async def run(self, results: list[AgentExecutorResponse], ctx: WorkflowContext[Never, str]) -> None:
        """Formatea las salidas de las ramas y se las pasa al Agent resumidor."""
        sections = []
        for result in results:
            sections.append(f"[{result.executor_id}]\n{result.agent_response.text}")
        combined = "\n\n---\n\n".join(sections)
        response = await self.agent.run(combined)
        await ctx.yield_output(response.text)


dispatcher = DispatchPrompt(id="dispatcher")

researcher = Agent(
    client=client,
    name="Investigador",
    instructions=(
        "Eres un investigador de mercado experto. "
        "Dado el prompt, proporciona insights factuales concisos, oportunidades y riesgos. "
        "Usa viñetas cortas."
    ),
)

marketer = Agent(
    client=client,
    name="Estratega",
    instructions=(
        "Eres un estratega de marketing. "
        "Dado el prompt, propone una propuesta de valor clara y mensajes para la audiencia. "
        "Usa viñetas cortas."
    ),
)

legal = Agent(
    client=client,
    name="Legal",
    instructions=(
        "Eres un revisor legal y de compliance. "
        "Dado el prompt, lista restricciones, disclaimers y preocupaciones de políticas. "
        "Usa viñetas cortas."
    ),
)

# El ejecutor resumidor envuelve un Agent que formatea las salidas
# expertas recopiladas y las sintetiza en un brief ejecutivo conciso.
summarizer = SummarizerExecutor(client=client)

workflow = (
    WorkflowBuilder(
        name="ResumenLLMFanOutFanIn",
        description="Fan-out/fan-in with LLM summarization aggregation.",
        start_executor=dispatcher,
        output_executors=[summarizer],
    )
    .add_fan_out_edges(dispatcher, [researcher, marketer, legal])
    .add_fan_in_edges([researcher, marketer, legal], summarizer)
    .build()
)


async def main() -> None:
    """Ejecuta el ejemplo e imprime el brief sintetizado por LLM."""
    prompt = "Vamos a lanzar una bicicleta eléctrica económica para commuters urbanos."
    print(f"Prompt: {prompt}\n")

    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print("=== Brief Ejecutivo (sintetizado por LLM) ===")
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8101, auto_open=True)
    else:
        asyncio.run(main())

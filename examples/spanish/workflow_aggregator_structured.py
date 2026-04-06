"""Fan-out/fan-in con agregación usando extracción estructurada.

Tres agentes entrevistadores (técnico, conductual, cultura) evalúan a un
candidato. El ejecutor fan-in recopila sus evaluaciones, llama al LLM con
response_format=CandidateReview y produce un modelo tipado de Pydantic —
listo para código downstream, no prosa.

Técnica de agregación: extracción estructurada del LLM hacia un modelo tipado.

Ejecutar:
    uv run examples/spanish/workflow_aggregator_structured.py
    uv run examples/spanish/workflow_aggregator_structured.py --devui  (abre DevUI en http://localhost:8102)
"""

import asyncio
import os
import sys
from typing import Literal

from agent_framework import Agent, AgentExecutorResponse, Executor, Message, WorkflowBuilder, WorkflowContext, handler
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


class CandidateReview(BaseModel):
    """Salida tipada producida por el revisor — útil para APIs, bases de datos o motores de scoring."""

    technical_score: int = Field(description="Technical skills score from 1 to 10.")
    technical_reason: str = Field(description="Justification for the technical score.")
    behavioral_score: int = Field(description="Behavioral skills score from 1 to 10.")
    behavioral_reason: str = Field(description="Justification for the behavioral score.")
    recommendation: Literal["strong hire", "hire with reservations", "no hire"] = Field(
        description="Final hiring recommendation."
    )


class DispatchPrompt(Executor):
    """Emite la descripción del candidato hacia abajo para el broadcast de fan-out."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(prompt)


class ExtractReview(Executor):
    """Agregador fan-in que llama al LLM con response_format para producir un CandidateReview tipado."""

    def __init__(self, *, client: OpenAIChatClient, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._client = client

    @handler
    async def extract(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, CandidateReview],
    ) -> None:
        """Recopila evaluaciones de entrevistadores y le pide al LLM una revisión estructurada."""
        sections = []
        for result in results:
            label = result.executor_id.replace("_", " ").title()
            sections.append(f"[{label}]\n{result.agent_response.text}")
        combined = "\n\n".join(sections)

        messages = [
            Message(
                role="system",
                contents=[
                    (
                        "Eres un revisor de un comité de contratación. "
                        "Con base en las siguientes evaluaciones de entrevistadores, "
                        "produce una revisión estructurada del candidato."
                    )
                ],
            ),
            Message(role="user", contents=[combined]),
        ]
        response = await self._client.get_response(messages, options={"response_format": CandidateReview})
        review: CandidateReview = response.value
        await ctx.yield_output(review)


dispatcher = DispatchPrompt(id="dispatcher")

technical_interviewer = Agent(
    client=client,
    name="EntrevistadorTecnico",
    instructions=(
        "Eres un ingeniero senior haciendo una entrevista técnica. "
        "Evalúa las habilidades técnicas del candidato, su conocimiento de arquitectura y su capacidad de programar. "
        "Sé específico sobre fortalezas y brechas. Usa viñetas cortas."
    ),
)

behavioral_interviewer = Agent(
    client=client,
    name="EntrevistadorConductual",
    instructions=(
        "Eres un especialista de RR.HH. haciendo una entrevista conductual. "
        "Evalúa comunicación, trabajo en equipo, resolución de conflictos y liderazgo. "
        "Sé específico sobre fortalezas y brechas. Usa viñetas cortas."
    ),
)

cultural_interviewer = Agent(
    client=client,
    name="EntrevistadorCultural",
    instructions=(
        "Eres un líder de equipo evaluando encaje cultural. "
        "Evalúa si el candidato se alinea con una cultura startup colaborativa y de ritmo rápido. "
        "Sé específico sobre fortalezas y brechas. Usa viñetas cortas."
    ),
)

extractor = ExtractReview(client=client, id="extractor")

workflow = (
    WorkflowBuilder(
        name="ExtraccionEstructurada",
        description="Fan-out/fan-in with Pydantic structured extraction.",
        start_executor=dispatcher,
        output_executors=[extractor],
    )
    .add_fan_out_edges(dispatcher, [technical_interviewer, behavioral_interviewer, cultural_interviewer])
    .add_fan_in_edges([technical_interviewer, behavioral_interviewer, cultural_interviewer], extractor)
    .build()
)


async def main() -> None:
    """Ejecuta el pipeline de entrevistas e imprime la revisión tipada."""
    prompt = (
        "Candidato aplicando a Senior Software Engineer. "
        "5 años de experiencia en Python y sistemas distribuidos. "
        "Gran comunicador pero con experiencia limitada en cloud."
    )
    print(f"Brief del candidato: {prompt}\n")

    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print(f"Recomendación: {output.recommendation}\n")
        print(f"Técnico: {output.technical_score}/10 — {output.technical_reason}\n")
        print(f"Conductual: {output.behavioral_score}/10 — {output.behavioral_reason}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8102, auto_open=True)
    else:
        asyncio.run(main())

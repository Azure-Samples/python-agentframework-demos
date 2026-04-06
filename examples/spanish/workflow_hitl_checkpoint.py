"""Workflow de revisión de contenido con checkpoints y reanudación human-in-the-loop.

Demuestra: FileCheckpointStorage, on_checkpoint_save/restore,
workflow.run(checkpoint_id=...), y pausa/reanudación entre reinicios de proceso.

Un brief se convierte en un prompt para un redactor IA. El redactor elabora
notas de lanzamiento, y un gateway de revisión solicita aprobación humana. Si se rechaza,
el humano proporciona guía de revisión y el ciclo se repite. Los checkpoints se
guardan en cada superstep para que el workflow sobreviva reinicios de proceso.

Ejecutar:
    uv run examples/spanish/workflow_hitl_checkpoint.py
"""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponseUpdate,
    Executor,
    FileCheckpointStorage,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

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

# Directorio para archivos de checkpoint (fácil de inspeccionar y eliminar)
CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


# --- Executors ---


class BriefPreparer(Executor):
    """Normaliza el brief del usuario y envía un AgentExecutorRequest al redactor."""

    def __init__(self, id: str, agent_id: str) -> None:
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def prepare(self, brief: str, ctx: WorkflowContext[AgentExecutorRequest, str]) -> None:
        normalized = " ".join(brief.split()).strip()
        if not normalized.endswith("."):
            normalized += "."
        ctx.set_state("brief", normalized)
        prompt = (
            "Estás redactando notas de lanzamiento de producto. Resume el brief a continuación en dos oraciones. "
            "Mantenlo positivo y termina con un llamado a la acción.\n\n"
            f"BRIEF: {normalized}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._agent_id,
        )


@dataclass
class HumanApprovalRequest:
    """Enviado al revisor humano para aprobación."""

    prompt: str = ""
    draft: str = ""
    iteration: int = 0


class ReviewGateway(Executor):
    """Enruta los borradores del agente a humanos y opcionalmente de vuelta para revisiones."""

    def __init__(self, id: str, writer_id: str) -> None:
        super().__init__(id=id)
        self._writer_id = writer_id
        self._iteration = 0

    @handler
    async def on_agent_response(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        self._iteration += 1
        await ctx.request_info(
            request_data=HumanApprovalRequest(
                prompt="Revisa el borrador. Escribe 'approve/aprobar' o proporciona instrucciones de edición.",
                draft=response.agent_response.text,
                iteration=self._iteration,
            ),
            response_type=str,
        )

    @response_handler
    async def on_human_feedback(
        self,
        original_request: HumanApprovalRequest,
        feedback: str,
        ctx: WorkflowContext[AgentExecutorRequest | str, str],
    ) -> None:
        reply = feedback.strip()
        if len(reply) == 0 or reply.lower() in ("approve", "aprobar"):
            await ctx.yield_output(original_request.draft)
            return
        # Regresa al redactor con guía de revisión
        prompt = (
            "Revisa la nota de lanzamiento. Responde solo con la nueva copia.\n\n"
            f"Borrador anterior:\n{original_request.draft}\n\n"
            f"Guía del humano: {reply}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._writer_id,
        )

    async def on_checkpoint_save(self) -> dict[str, Any]:
        return {"iteration": self._iteration}

    async def on_checkpoint_restore(self, state: dict[str, Any]) -> None:
        self._iteration = state.get("iteration", 0)


# --- Principal ---


async def main() -> None:
    """Ejecuta el workflow HITL con checkpoints."""
    storage = FileCheckpointStorage(storage_path=CHECKPOINT_DIR)

    writer_agent = Agent(
        name="writer",
        instructions="Escribe notas de lanzamiento concisas y cálidas que suenen humanas y útiles.",
        client=client,
    )
    writer = AgentExecutor(writer_agent)
    review_gateway = ReviewGateway(id="review_gateway", writer_id="writer")
    prepare_brief = BriefPreparer(id="prepare_brief", agent_id="writer")

    workflow = (
        WorkflowBuilder(
            name="content_review",
            max_iterations=6,
            start_executor=prepare_brief,
            checkpoint_storage=storage,
        )
        .add_edge(prepare_brief, writer)
        .add_edge(writer, review_gateway)
        .add_edge(review_gateway, writer)  # ciclo de revisiones
        .build()
    )

    # Verifica si hay checkpoints existentes para reanudar
    checkpoint = await storage.get_latest(workflow_name=workflow.name)
    if checkpoint:
        print(f"📂 Se encontró un checkpoint. Reanudando desde el más reciente: {checkpoint.checkpoint_id}")
        stream = workflow.run(checkpoint_id=checkpoint.checkpoint_id, stream=True)
    else:
        brief = (
            "Presenta nuestra nueva freidora de aire compacta con canasta de 5 cuartos. Menciona el precio de $89, "
            "destaca la tecnología de aire rápido que hace los alimentos crujientes con 95% menos aceite, "
            "e invita a los clientes a hacer su pedido anticipado."
        )
        print(f"▶️  Iniciando workflow con brief: {brief}\n")
        stream = workflow.run(brief, stream=True)

    while True:
        pending: dict[str, HumanApprovalRequest] = {}
        async for event in stream:
            if event.type == "request_info" and isinstance(event.data, HumanApprovalRequest):
                pending[event.request_id] = event.data
            elif event.type == "output" and not isinstance(event.data, AgentResponseUpdate):
                print(f"\n✅ Workflow completado:\n{event.data}")

        if not pending:
            break

        responses: dict[str, str] = {}
        for request_id, request in pending.items():
            print("\n" + "=" * 60)
            print(f"💬 Aprobación humana necesaria (iteración {request.iteration})")
            print(request.prompt)
            print(f"\nBorrador:\n---\n{request.draft}\n---")
            response = input("Escribe 'approve/aprobar' o ingresa guía de revisión: ").strip()
            responses[request_id] = response

        stream = workflow.run(stream=True, responses=responses)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())

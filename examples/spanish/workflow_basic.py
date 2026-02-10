# pip install agent-framework-devui==1.0.0b251016
import os
from typing import Any

from agent_framework import AgentExecutorResponse, ChatAgent, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel

# Configura el cliente de OpenAI según el entorno
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")

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


# Define la salida estructurada para los resultados de revisión
class ResultadoRevision(BaseModel):
    """Evaluación de revisión con puntajes y retroalimentación."""

    puntaje: int  # Puntaje general de calidad (0-100)
    retroalimentacion: str  # Retroalimentación concisa y accionable
    claridad: int  # Puntaje de claridad (0-100)
    completitud: int  # Puntaje de completitud (0-100)
    precision: int  # Puntaje de precisión (0-100)
    estructura: int  # Puntaje de estructura (0-100)


# Función de condición: envía al editor si puntaje < 80
def necesita_edicion(message: Any) -> bool:
    """Verifica si el contenido necesita edición según el puntaje de revisión."""
    if not isinstance(message, AgentExecutorResponse):
        return False
    try:
        revision = ResultadoRevision.model_validate_json(message.agent_run_response.text)
        return revision.puntaje < 80
    except Exception:
        return False


# Función de condición: el contenido está aprobado (puntaje >= 80)
def esta_aprobado(message: Any) -> bool:
    """Verifica si el contenido está aprobado (alta calidad)."""
    if not isinstance(message, AgentExecutorResponse):
        return True
    try:
        revision = ResultadoRevision.model_validate_json(message.agent_run_response.text)
        return revision.puntaje >= 80
    except Exception:
        return True


# Crea el agente Escritor: genera contenido
def crear_escritor():
    return ChatAgent(
        chat_client=client,
        name="Escritor",
        instructions=(
            "Eres un excelente escritor de contenido. "
            "Crea contenido claro y atractivo basado en la solicitud del usuario. "
            "Enfócate en la claridad, precisión y estructura adecuada."
        ),
    )


# Crea el agente Revisor: evalúa y da retroalimentación estructurada
def crear_revisor():
    return ChatAgent(
        chat_client=client,
        name="Revisor",
        instructions=(
            "Eres un experto revisor de contenido. "
            "Evalúa el contenido del escritor basándote en:\n"
            "1. Claridad - ¿Es fácil de entender?\n"
            "2. Completitud - ¿Aborda completamente el tema?\n"
            "3. Precisión - ¿Es correcta la información?\n"
            "4. Estructura - ¿Está bien organizado?\n\n"
            "Devuelve un objeto JSON con:\n"
            "- puntaje: calidad general (0-100)\n"
            "- retroalimentacion: retroalimentación concisa y accionable\n"
            "- claridad, completitud, precision, estructura: puntajes individuales (0-100)"
        ),
        response_format=ResultadoRevision,
    )


# Crea el agente Editor: mejora el contenido según la retroalimentación
def crear_editor():
    return ChatAgent(
        chat_client=client,
        name="Editor",
        instructions=(
            "Eres un editor habilidoso. "
            "Recibirás contenido junto con retroalimentación de revisión. "
            "Mejora el contenido abordando todos los problemas mencionados en la retroalimentación. "
            "Mantén la intención original mientras mejoras la claridad, completitud, precisión y estructura."
        ),
    )


# Crea el agente Publicador: formatea el contenido para publicación
def crear_publicador():
    return ChatAgent(
        chat_client=client,
        name="Publicador",
        instructions=(
            "Eres un agente de publicación. "
            "Recibes contenido aprobado o editado. "
            "Formatea el contenido para publicación con encabezados y estructura adecuados."
        ),
    )


# Crea el agente Resumidor: arma el informe final de publicación
def crear_resumidor():
    return ChatAgent(
        chat_client=client,
        name="Resumidor",
        instructions=(
            "Eres un agente resumidor. "
            "Crea un informe de publicación final que incluya:\n"
            "1. Un breve resumen del contenido publicado\n"
            "2. El camino del flujo de trabajo seguido (aprobación directa o editado)\n"
            "3. Aspectos destacados y conclusiones clave\n"
            "Mantén la concisión y el profesionalismo."
        ),
    )


# Construye el workflow con ramificación y convergencia:
# Escritor → Revisor → [ramas]:
#   - Si puntaje >= 80: → Publicador → Resumidor (ruta de aprobación directa)
#   - Si puntaje < 80: → Editor → Publicador → Resumidor (ruta de mejora)
# Ambas rutas convergen en Resumidor para el informe final
flujo_trabajo = (
    WorkflowBuilder(
        name="Flujo de Trabajo de Revisión de Contenido",
        description="Creación de contenido con enrutamiento basado en calidad (Escritor → Revisor → Editor/Publicador)",
    )
    .register_agent(crear_escritor, name="Escritor")
    .register_agent(crear_revisor, name="Revisor")
    .register_agent(crear_editor, name="Editor")
    .register_agent(crear_publicador, name="Publicador")
    .register_agent(crear_resumidor, name="Resumidor")
    .set_start_executor("Escritor")
    .add_edge("Escritor", "Revisor")
    # Rama 1: Alta calidad (>= 80) va directamente al publicador
    .add_edge("Revisor", "Publicador", condition=esta_aprobado)
    # Rama 2: Baja calidad (< 80) va primero al editor, luego al publicador
    .add_edge("Revisor", "Editor", condition=necesita_edicion)
    .add_edge("Editor", "Publicador")
    # Ambas rutas convergen: Publicador → Resumidor
    .add_edge("Publicador", "Resumidor")
    .build()
)


def main():
    from agent_framework.devui import serve

    serve(entities=[flujo_trabajo], port=8093, auto_open=True)


if __name__ == "__main__":
    main()

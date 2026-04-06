<!--
---
name: Python Agent Framework Demos
description: Colección de ejemplos en Python para Microsoft Agent Framework usando Microsoft Foundry.
languages:
- python
products:
- azure-openai
- azure
- ai-services
page_type: sample
urlFragment: python-agentframework-demos
---
-->

# Demos de Microsoft Agent Framework en Python

[![Abrir en GitHub Codespaces](https://img.shields.io/static/v1?style=for-the-badge&label=GitHub+Codespaces&message=Open&color=brightgreen&logo=github)](https://codespaces.new/Azure-Samples/python-agentframework-demos)
[![Abrir en Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/python-agentframework-demos)

Este repositorio ofrece ejemplos de [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) usando LLMs de [Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/) u otros proveedores de modelos.

* [Cómo empezar](#cómo-empezar)
  * [GitHub Codespaces](#github-codespaces)
  * [VS Code Dev Containers](#vs-code-dev-containers)
  * [Entorno local](#entorno-local)
* [Configurar proveedores de modelos](#configurar-proveedores-de-modelos)
  * [Usar modelos de Microsoft Foundry](#usar-modelos-de-microsoft-foundry)
  * [Usar modelos de OpenAI.com](#usar-modelos-de-openaicom)
* [Ejecutar los ejemplos en Python](#ejecutar-los-ejemplos-en-python)
* [Recursos](#recursos)

## Cómo empezar

Tienes varias opciones para comenzar con este repositorio.
La forma más rápida es usar GitHub Codespaces, ya que te deja todo listo automáticamente, pero también puedes [configurarlo localmente](#entorno-local).

### GitHub Codespaces

Puedes ejecutar este repositorio virtualmente usando GitHub Codespaces. El botón abrirá una instancia de VS Code basada en web en tu navegador:

1. Abre el repositorio (esto puede tardar varios minutos):

    [![Abrir en GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Azure-Samples/python-agentframework-demos)

2. Abre una ventana de terminal
3. Continúa con los pasos para ejecutar los ejemplos

### VS Code Dev Containers

Una opción relacionada es VS Code Dev Containers, que abrirá el proyecto en tu VS Code local usando la [extensión Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Inicia Docker Desktop (instálalo si no lo tienes ya)
2. Abre el proyecto:

    [![Abrir en Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/python-agentframework-demos)

3. En la ventana de VS Code que se abre, una vez que aparezcan los archivos del proyecto (esto puede tardar varios minutos), abre una ventana de terminal.
4. Continúa con los pasos para ejecutar los ejemplos

El dev container incluye un servidor Redis, que se usa en el ejemplo `agent_history_redis.py`.

### Entorno local

1. Asegúrate de tener instaladas las siguientes herramientas:

    * [Python 3.10+](https://www.python.org/downloads/)
    * [uv](https://docs.astral.sh/uv/getting-started/installation/)
    * Git

2. Clona el repositorio:

    ```shell
    git clone https://github.com/Azure-Samples/python-agentframework-demos
    cd python-agentframework-demos
    ```

3. Instala las dependencias:

    ```shell
    uv sync
    ```

4. *Opcional:* Para ejecutar el ejemplo `agent_history_redis.py`, necesitas un servidor Redis corriendo localmente:

    ```shell
    docker run -d -p 6379:6379 redis:7-alpine
    ```

5. *Opcional:* Para ejecutar los ejemplos de PostgreSQL (`agent_knowledge_postgres.py`, `agent_knowledge_pg.py`, `agent_knowledge_pg_rewrite.py`), necesitas PostgreSQL con pgvector corriendo localmente:

    ```shell
    docker run -d -p 5432:5432 -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=LocalPasswordOnly pgvector/pgvector:pg17
    ```

## Configurar proveedores de modelos

Estos ejemplos se pueden ejecutar con Microsoft Foundry u OpenAI.com, dependiendo de las variables de entorno que configures. Todos los scripts hacen referencia a las variables de entorno de un archivo `.env`, y se proporciona un archivo de ejemplo `.env.sample`. Las instrucciones específicas de cada proveedor se encuentran a continuación.

## Usar modelos de Microsoft Foundry

Este proyecto incluye infraestructura como código (IaC) para provisionar despliegues de Azure OpenAI de "gpt-5.4" y "text-embedding-3-large" a través de Microsoft Foundry. La IaC está definida en el directorio `infra` y usa Azure Developer CLI para provisionar los recursos.

1. Asegúrate de tener instalado [Azure Developer CLI (azd)](https://aka.ms/install-azd).

2. Inicia sesión en Azure:

    ```shell
    azd auth login
    ```

    Para usuarios de GitHub Codespaces, si el comando anterior falla, prueba:

   ```shell
    azd auth login --use-device-code
    ```

3. Provisiona la cuenta de OpenAI:

    ```shell
    azd provision
    ```

    Te pedirá que proporciones un nombre de entorno `azd` (como "agents-demos"), selecciones una suscripción de tu cuenta de Azure y selecciones una ubicación. Luego aprovisionará los recursos en tu cuenta.

4. Una vez que los recursos estén aprovisionados, deberías ver un archivo local `.env` con todas las variables de entorno necesarias para ejecutar los scripts.
5. Para eliminar los recursos, ejecuta:

    ```shell
    azd down
    ```

## Usar modelos de OpenAI.com

1. Crea un archivo `.env` copiando el archivo `.env.sample` y actualizándolo con tu clave API de OpenAI y el nombre del modelo deseado.

    ```bash
    cp .env.sample .env
    ```

2. Actualiza el archivo `.env` con tu clave API de OpenAI y el nombre del modelo deseado:

    ```bash
    API_HOST=openai
    OPENAI_API_KEY=tu_clave_api_de_openai
    OPENAI_MODEL=gpt-4o-mini
    ```

## Ejecutar los ejemplos en Python

Puedes ejecutar los ejemplos en este repositorio ejecutando los scripts en el directorio `examples/spanish`. Cada script demuestra un patrón diferente de Microsoft Agent Framework.

| Ejemplo | Descripción |
| ------- | ----------- |
| [agent_basic.py](agent_basic.py) | Un agente informativo básico. |
| [agent_tool.py](agent_tool.py) | Un agente con una sola herramienta de clima. |
| [agent_tools.py](agent_tools.py) | Un agente planificador de fin de semana con múltiples herramientas. |
| [agent_session.py](agent_session.py) | Sesiones en memoria para conversaciones multi-turno con memoria entre mensajes. |
| [agent_history_sqlite.py](agent_history_sqlite.py) | Historial de chat persistente con un proveedor de historial SQLite personalizado para persistencia local en archivo. |
| [agent_history_redis.py](agent_history_redis.py) | Historial de chat persistente con Redis para conversación que sobrevive reinicios. |
| [agent_memory_redis.py](agent_memory_redis.py) | Memoria de largo plazo con RedisContextProvider, guardando y recuperando contexto conversacional desde Redis. |
| [agent_memory_mem0.py](agent_memory_mem0.py) | Memoria de largo plazo con Mem0 OSS, extrayendo y recordando hechos del usuario entre sesiones. |
| [agent_supervisor.py](agent_supervisor.py) | Un supervisor que orquesta subagentes de actividades y recetas. |
| [agent_with_subagent.py](agent_with_subagent.py) | Aislamiento de contexto con subagentes para mantener los prompts enfocados en herramientas relevantes. |
| [agent_without_subagent.py](agent_without_subagent.py) | Ejemplo de inflado de contexto cuando un solo agente carga todos los esquemas de herramientas en un mismo prompt. |
| [agent_summarization.py](agent_summarization.py) | Compactación de contexto mediante middleware de resumen para reducir el uso de tokens en conversaciones largas. |
| [workflow_magenticone.py](workflow_magenticone.py) | Un workflow multi-agente MagenticOne. |
| [agent_tool_approval.py](agent_tool_approval.py) | Agente independiente con aprobación de herramientas — controla operaciones sensibles antes de ejecutarlas. |
| [agent_middleware.py](agent_middleware.py) | Middleware de agente, chat y funciones para logging, timing y bloqueo. |
| [agent_knowledge_aisearch.py](agent_knowledge_aisearch.py) | Recuperación de conocimiento (RAG) usando Azure AI Search con AgentFrameworkAzureAISearchRAG. |
| [agent_knowledge_sqlite.py](agent_knowledge_sqlite.py) | Recuperación de conocimiento (RAG) usando un proveedor de contexto personalizado con SQLite FTS5. |
| [agent_knowledge_pg.py](agent_knowledge_pg.py) | Recuperación de conocimiento (RAG) con PostgreSQL y búsqueda híbrida (pgvector + texto completo) usando Reciprocal Rank Fusion. |
| [agent_knowledge_pg_rewrite.py](agent_knowledge_pg_rewrite.py) | Recuperación de conocimiento con reescritura de consultas para conversaciones multi-turno sobre PostgreSQL. |
| [agent_knowledge_postgres.py](agent_knowledge_postgres.py) | Recuperación de conocimiento (RAG) con búsqueda híbrida en PostgreSQL (pgvector + texto completo) usando Reciprocal Rank Fusion. |
| [agent_mcp_remote.py](agent_mcp_remote.py) | Un agente usando un servidor MCP remoto (Microsoft Learn) para búsqueda de documentación. |
| [agent_mcp_local.py](agent_mcp_local.py) | Un agente conectado a un servidor MCP local (p. ej. para registro de gastos). |
| [openai_tool_calling.py](openai_tool_calling.py) | Llamadas a herramientas con el SDK de OpenAI de bajo nivel, mostrando despacho manual de herramientas. |
| [workflow_rag_ingest.py](workflow_rag_ingest.py) | Un pipeline de ingesta para RAG con ejecutores Python puros: descarga un documento con markitdown, lo divide en fragmentos y genera embeddings con un modelo de OpenAI. |
| [workflow_fan_out_fan_in_edges.py](workflow_fan_out_fan_in_edges.py) | Fan-out/fan-in con grupos de aristas explícitos usando `add_fan_out_edges` y `add_fan_in_edges`. |
| [workflow_aggregator_summary.py](workflow_aggregator_summary.py) | Fan-out/fan-in con resumen por LLM: sintetiza salidas de expertos en un brief ejecutivo. |
| [workflow_aggregator_structured.py](workflow_aggregator_structured.py) | Fan-out/fan-in con extracción estructurada por LLM en un modelo Pydantic tipado (`response_format`). |
| [workflow_aggregator_voting.py](workflow_aggregator_voting.py) | Fan-out/fan-in con agregación por voto mayoritario entre clasificadores (conteo de lógica pura). |
| [workflow_aggregator_ranked.py](workflow_aggregator_ranked.py) | Fan-out/fan-in con LLM como juez: puntúa y ordena múltiples candidatos en una lista tipada. |
| [workflow_agents.py](workflow_agents.py) | Un workflow con agentes de IA como ejecutores: un Escritor redacta contenido y un Revisor da retroalimentación. |
| [workflow_agents_sequential.py](workflow_agents_sequential.py) | Una orquestación secuencial usando `SequentialBuilder`: Escritor y Revisor se ejecutan en orden compartiendo todo el historial de la conversación. |
| [workflow_agents_streaming.py](workflow_agents_streaming.py) | El mismo workflow Escritor → Revisor usando `run(stream=True)` para observar los eventos `executor_invoked`, `executor_completed` y `output` en tiempo real. |
| [workflow_agents_concurrent.py](workflow_agents_concurrent.py) | Orquestación concurrente usando `ConcurrentBuilder`: ejecuta agentes especialistas en paralelo y junta las conversaciones. |
| [workflow_conditional.py](workflow_conditional.py) | Un workflow mínimo con aristas condicionales: el Revisor enruta al Publicador (aprobado) o al Editor (necesita revisión) según una señal de texto. |
| [workflow_conditional_structured.py](workflow_conditional_structured.py) | El mismo patrón de enrutamiento con aristas condicionales, pero usando salida estructurada del revisor (`response_format`) para decisiones tipadas en vez de matching por cadena. |
| [workflow_conditional_state.py](workflow_conditional_state.py) | Un workflow condicional con estado y bucle iterativo: guarda el último borrador en el estado del workflow y publica desde ese estado tras la aprobación. |
| [workflow_conditional_state_isolated.py](workflow_conditional_state_isolated.py) | El workflow condicional con estado usando una fábrica `create_workflow(...)` para crear agentes/workflow nuevos por tarea y así aislar estado e hilos de agente. |
| [workflow_switch_case.py](workflow_switch_case.py) | Un workflow con enrutamiento switch-case: un agente Clasificador usa salidas estructuradas para categorizar un mensaje y enrutarlo al manejador especializado. |
| [workflow_multi_selection_edge_group.py](workflow_multi_selection_edge_group.py) | Enrutamiento multi-selección con LLM usando `add_multi_selection_edge_group` para activar uno o varios manejadores. |
| [workflow_converge.py](workflow_converge.py) | Un workflow con rama y convergencia: Revisor enruta a Publicador o Editor y luego converge antes del resumen final. |
| [workflow_handoffbuilder.py](workflow_handoffbuilder.py) | Orquestación de handoff autónoma usando `HandoffBuilder` (los agentes se transfieren el control sin HITL). |
| [workflow_handoffbuilder_rules.py](workflow_handoffbuilder_rules.py) | Orquestación de handoff con reglas explícitas usando `HandoffBuilder.add_handoff()`. |
| [workflow_hitl_requests.py](workflow_hitl_requests.py) | Chat HITL simple — siempre pausa para entrada humana después de cada respuesta del agente (`ctx.request_info`, `@response_handler`). |
| [workflow_hitl_requests_structured.py](workflow_hitl_requests_structured.py) | Planificador de viajes HITL con salidas estructuradas — el agente decide cuándo preguntar vs. finalizar vía `PlannerOutput.status`. |
| [workflow_hitl_tool_approval.py](workflow_hitl_tool_approval.py) | Workflow de agente de correo con `@tool(approval_mode="always_require")` para controlar llamadas sensibles. |
| [workflow_hitl_checkpoint.py](workflow_hitl_checkpoint.py) | Revisión de contenido con `FileCheckpointStorage` — pausar, salir del proceso y reanudar desde checkpoint. |
| [workflow_hitl_checkpoint_pg.py](workflow_hitl_checkpoint_pg.py) | Mismo workflow de revisión con un backend personalizado `PostgresCheckpointStorage`. |
| [workflow_hitl_handoff.py](workflow_hitl_handoff.py) | Handoff interactivo (sin modo autónomo) — el framework pausa para entrada del usuario vía `HandoffAgentUserRequest`. |
| [agent_otel_aspire.py](agent_otel_aspire.py) | Un agente con trazas, métricas y logs estructurados de OpenTelemetry exportados al [Aspire Dashboard](https://aspire.dev/dashboard/standalone/). |
| [agent_otel_appinsights.py](agent_otel_appinsights.py) | Un agente con trazas, métricas y logs estructurados de OpenTelemetry exportados a [Azure Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview). Requiere aprovisionamiento de Azure con `azd provision`. |
| [agent_evaluation_generate.py](agent_evaluation_generate.py) | Genera datos sintéticos de evaluación para el agente planificador de viajes. |
| [agent_evaluation.py](agent_evaluation.py) | Evalúa un agente planificador de viajes usando evaluadores de [Azure AI Evaluation](https://learn.microsoft.com/azure/ai-foundry/concepts/evaluation-evaluators/agent-evaluators) (IntentResolution, ToolCallAccuracy, TaskAdherence, ResponseCompleteness). Opcionalmente configura `AZURE_AI_PROJECT` en `.env` para registrar resultados en [Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/agent-evaluate-sdk). |
| [agent_evaluation_batch.py](agent_evaluation_batch.py) | Evaluación por lotes de respuestas de agentes con la función `evaluate()` de Azure AI Evaluation. |
| [agent_redteam.py](agent_redteam.py) | Prueba de red team a un agente asesor financiero usando [Azure AI Evaluation](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/red-teaming-agent) para evaluar su resiliencia ante ataques adversariales en categorías de riesgo (Violence, HateUnfairness, Sexual, SelfHarm). Requiere `AZURE_AI_PROJECT` en `.env`. |

## Usar el Aspire Dashboard para telemetría

El ejemplo [agent_otel_aspire.py](agent_otel_aspire.py) puede exportar trazas, métricas y logs estructurados de OpenTelemetry a un [Aspire Dashboard](https://aspire.dev/dashboard/standalone/).

### En GitHub Codespaces / Dev Containers

El Aspire Dashboard se ejecuta automáticamente como un servicio junto al dev container. No necesitas configuración adicional.

1. La variable de entorno `OTEL_EXPORTER_OTLP_ENDPOINT` ya está configurada por el dev container.

2. Ejecuta el ejemplo:

    ```sh
    uv run agent_otel_aspire.py
    ```

3. Abre el dashboard en <http://localhost:18888> y explora:

    * **Traces**: Ve el arbol completo de spans — invocacion del agente → completado del chat → ejecucion de herramientas
    * **Metrics**: Consulta histogramas de uso de tokens y duracion de operaciones
    * **Structured Logs**: Navega los mensajes de la conversacion (sistema, usuario, asistente, herramienta)
    * **Visualizador GenAI**: Selecciona un span de completado del chat para ver la conversacion renderizada

### Entorno local (sin Dev Containers)

Si ejecutas localmente sin Dev Containers, necesitas iniciar el Aspire Dashboard manualmente:

1. Inicia el Aspire Dashboard:

    ```sh
    docker run --rm -it -d -p 18888:18888 -p 4317:18889 --name aspire-dashboard \
        -e DASHBOARD__FRONTEND__AUTHMODE=Unsecured \
        mcr.microsoft.com/dotnet/aspire-dashboard:latest
    ```

2. Agrega el endpoint OTLP a tu archivo `.env`:

    ```sh
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
    ```

3. Ejecuta el ejemplo:

    ```sh
    uv run agent_otel_aspire.py
    ```

4. Abre el dashboard en <http://localhost:18888> y explora.

5. Cuando termines, detén el dashboard:

    ```sh
    docker stop aspire-dashboard
    ```

Para la guía completa de Python + Aspire, consulta [Usar el Aspire Dashboard con apps de Python](https://aspire.dev/dashboard/standalone-for-python/).

## Exportar telemetría a Azure Application Insights

El ejemplo [agent_otel_appinsights.py](agent_otel_appinsights.py) exporta trazas, métricas y logs estructurados de OpenTelemetry a [Azure Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview).

### Configuración

Este ejemplo requiere la variable de entorno `APPLICATIONINSIGHTS_CONNECTION_STRING`. Puedes obtenerla automáticamente o manualmente:

**Opción A: Automática con `azd provision`**

Si ejecutas `azd provision` (consulta [Usar modelos de Microsoft Foundry](#usar-modelos-de-microsoft-foundry)), el recurso de Application Insights se provisiona automáticamente y la cadena de conexión se escribe en tu archivo `.env`.

**Opción B: Manual desde el Portal de Azure**

1. Crea un recurso de Application Insights en el [Portal de Azure](https://portal.azure.com).
2. Copia la cadena de conexión desde la página de resumen del recurso.
3. Agrégala a tu archivo `.env`:

    ```sh
    APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...
    ```

### Ejecutar el ejemplo

```sh
uv run examples/spanish/agent_otel_appinsights.py
```

### Ver telemetría

Después de ejecutar el ejemplo, navega a tu recurso de Application Insights en el Portal de Azure:

* **Búsqueda de transacciones**: Ve trazas de extremo a extremo para invocaciones de agentes, completados de chat y ejecuciones de herramientas.
* **Métricas en vivo**: Monitorea tasas de solicitudes y rendimiento en tiempo real.
* **Rendimiento**: Analiza duraciones de operaciones e identifica cuellos de botella.

Los datos de telemetría pueden tardar entre 2 y 5 minutos en aparecer en el portal.

## Recursos

* [Documentación de Agent Framework](https://learn.microsoft.com/agent-framework/)

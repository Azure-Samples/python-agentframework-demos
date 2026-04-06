<!--
---
name: Python Agent Framework Demos
description: Collection of Python examples for Microsoft Agent Framework using Microsoft Foundry.
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
# Python Agent Framework Demos

[![Open in GitHub Codespaces](https://img.shields.io/static/v1?style=for-the-badge&label=GitHub+Codespaces&message=Open&color=brightgreen&logo=github)](https://codespaces.new/Azure-Samples/python-agentframework-demos)
[![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/python-agentframework-demos)

This repository provides examples of [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) using LLMs from [Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/) or other model providers.

* [Getting started](#getting-started)
  * [GitHub Codespaces](#github-codespaces)
  * [VS Code Dev Containers](#vs-code-dev-containers)
  * [Local environment](#local-environment)
* [Configuring model providers](#configuring-model-providers)
  * [Using Microsoft Foundry models](#using-microsoft-foundry-models)
  * [Using OpenAI.com models](#using-openaicom-models)
* [Running the Python examples](#running-the-python-examples)
* [Resources](#resources)

## Getting started

You have a few options for getting started with this repository.
The quickest way to get started is GitHub Codespaces, since it will setup everything for you, but you can also [set it up locally](#local-environment).

### GitHub Codespaces

You can run this repository virtually by using GitHub Codespaces. The button will open a web-based VS Code instance in your browser:

1. Open the repository (this may take several minutes):

    [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Azure-Samples/python-agentframework-demos)

2. Open a terminal window
3. Continue with the steps to run the examples

### VS Code Dev Containers

A related option is VS Code Dev Containers, which will open the project in your local VS Code using the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Start Docker Desktop (install it if not already installed)
2. Open the project:

    [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/python-agentframework-demos)

3. In the VS Code window that opens, once the project files show up (this may take several minutes), open a terminal window.
4. Continue with the steps to run the examples

The dev container includes a Redis server, which is used by the `agent_history_redis.py` example.

### Local environment

1. Make sure the following tools are installed:

    * [Python 3.10+](https://www.python.org/downloads/)
    * [uv](https://docs.astral.sh/uv/getting-started/installation/)
    * Git

2. Clone the repository:

    ```shell
    git clone https://github.com/Azure-Samples/python-agentframework-demos
    cd python-agentframework-demos
    ```

3. Install the dependencies:

    ```shell
    uv sync
    ```

4. *Optional:* To run the `agent_history_redis.py` example, you need a Redis server running locally:

    ```shell
    docker run -d -p 6379:6379 redis:7-alpine
    ```

5. *Optional:* To run the PostgreSQL examples (`agent_knowledge_postgres.py`, `agent_knowledge_pg.py`, `agent_knowledge_pg_rewrite.py`), you need PostgreSQL with pgvector running locally:

    ```shell
    docker run -d -p 5432:5432 -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=LocalPasswordOnly pgvector/pgvector:pg17
    ```

## Configuring model providers

These examples can be run with Microsoft Foundry or OpenAI.com, depending on the environment variables you set. All the scripts reference the environment variables from a `.env` file, and an example `.env.sample` file is provided. Host-specific instructions are below.

## Using Microsoft Foundry models

This project includes infrastructure as code (IaC) to provision Azure OpenAI deployments of "gpt-5.4" and "text-embedding-3-large" via Microsoft Foundry. The IaC is defined in the `infra` directory and uses the Azure Developer CLI to provision the resources.

1. Make sure the [Azure Developer CLI (azd)](https://aka.ms/install-azd) is installed.

2. Login to Azure:

    ```shell
    azd auth login
    ```

    For GitHub Codespaces users, if the previous command fails, try:

   ```shell
    azd auth login --use-device-code
    ```

    If you are using a tenant besides the default tenant, you may need to also login with Azure CLI to that tenant:

    ```shell
    az login --tenant your-tenant-id
    ```

3. Provision the OpenAI account:

    ```shell
    azd provision
    ```

    It will prompt you to provide an `azd` environment name (like "agents-demos"), select a subscription from your Azure account, and select a location. Then it will provision the resources in your account.

4. Once the resources are provisioned, you should now see a local `.env` file with all the environment variables needed to run the scripts.
5. To delete the resources, run:

    ```shell
    azd down
    ```

## Using OpenAI.com models

1. Create a `.env` file by copying the `.env.sample` file and updating it with your OpenAI API key and desired model name.

    ```bash
    cp .env.sample .env
    ```

2. Update the `.env` file with your OpenAI API key and desired model name:

    ```bash
    API_HOST=openai
    OPENAI_API_KEY=your_openai_api_key
    OPENAI_MODEL=gpt-4o-mini
    ```

## Running the Python examples

You can run the examples in this repository by executing the scripts in the `examples` directory. Each script demonstrates a different Agent Framework pattern.

| Example | Description |
| ------- | ----------- |
| [agent_basic.py](examples/agent_basic.py) | A basic informational agent. |
| [agent_tool.py](examples/agent_tool.py) | An agent with a single weather tool. |
| [agent_tools.py](examples/agent_tools.py) | A weekend planning agent with multiple tools. |
| [agent_session.py](examples/agent_session.py) | In-memory sessions for multi-turn conversations with memory across messages. |
| [agent_history_sqlite.py](examples/agent_history_sqlite.py) | Persistent chat history with a custom SQLite history provider for local file-based conversation persistence. |
| [agent_history_redis.py](examples/agent_history_redis.py) | Persistent chat history with Redis for conversation history that survives restarts. |
| [agent_memory_redis.py](examples/agent_memory_redis.py) | Long-term memory with RedisContextProvider, storing and retrieving conversational context from Redis. |
| [agent_memory_mem0.py](examples/agent_memory_mem0.py) | Long-term memory with Mem0 OSS, extracting and recalling distilled user facts across sessions. |
| [agent_supervisor.py](examples/agent_supervisor.py) | A supervisor orchestrating activity and recipe sub-agents. |
| [agent_with_subagent.py](examples/agent_with_subagent.py) | Context isolation with sub-agents to keep prompts focused on relevant tools. |
| [agent_without_subagent.py](examples/agent_without_subagent.py) | Context bloat example where one agent carries all tool schemas in a single prompt. |
| [agent_summarization.py](examples/agent_summarization.py) | Context compaction via summarization middleware to reduce token usage in long conversations. |
| [workflow_magenticone.py](examples/workflow_magenticone.py) | A MagenticOne multi-agent workflow. |
| [agent_tool_approval.py](examples/agent_tool_approval.py) | Standalone agent with tool approval — gates sensitive operations before execution. |
| [agent_middleware.py](examples/agent_middleware.py) | Agent, chat, and function middleware for logging, timing, and blocking. |
| [agent_knowledge_aisearch.py](examples/agent_knowledge_aisearch.py) | Knowledge retrieval (RAG) using Azure AI Search with AgentFrameworkAzureAISearchRAG. |
| [agent_knowledge_sqlite.py](examples/agent_knowledge_sqlite.py) | Knowledge retrieval (RAG) using a custom context provider with SQLite FTS5. |
| [agent_knowledge_pg.py](examples/agent_knowledge_pg.py) | Knowledge retrieval (RAG) with PostgreSQL hybrid search (pgvector + full-text) using Reciprocal Rank Fusion. |
| [agent_knowledge_pg_rewrite.py](examples/agent_knowledge_pg_rewrite.py) | Knowledge retrieval with query rewriting for multi-turn conversations over PostgreSQL. |
| [agent_knowledge_postgres.py](examples/agent_knowledge_postgres.py) | Knowledge retrieval (RAG) with PostgreSQL hybrid search (pgvector + full-text) using Reciprocal Rank Fusion. |
| [agent_mcp_remote.py](examples/agent_mcp_remote.py) | An agent using a remote MCP server (Microsoft Learn) for documentation search. |
| [agent_mcp_local.py](examples/agent_mcp_local.py) | An agent connected to a local MCP server (e.g. for expense logging). |
| [openai_tool_calling.py](examples/openai_tool_calling.py) | Tool calling with the low-level OpenAI SDK, showing manual tool dispatch. |
| [workflow_rag_ingest.py](examples/workflow_rag_ingest.py) | A RAG ingestion pipeline using plain Python executors: fetch a document with markitdown, split into chunks, and embed with an OpenAI model. |
| [workflow_fan_out_fan_in_edges.py](examples/workflow_fan_out_fan_in_edges.py) | Fan-out/fan-in with explicit edge groups using `add_fan_out_edges` and `add_fan_in_edges`. |
| [workflow_aggregator_summary.py](examples/workflow_aggregator_summary.py) | Fan-out/fan-in with LLM summarization: synthesize expert outputs into an executive brief. |
| [workflow_aggregator_structured.py](examples/workflow_aggregator_structured.py) | Fan-out/fan-in with LLM structured extraction into a typed Pydantic model (`response_format`). |
| [workflow_aggregator_voting.py](examples/workflow_aggregator_voting.py) | Fan-out/fan-in with majority-vote aggregation across multiple classifiers (pure logic tally). |
| [workflow_aggregator_ranked.py](examples/workflow_aggregator_ranked.py) | Fan-out/fan-in with LLM-as-judge ranking: score and rank multiple candidates into a typed list. |
| [workflow_agents.py](examples/workflow_agents.py) | A workflow with AI agents as executors: a Writer drafts content and a Reviewer provides feedback. |
| [workflow_agents_sequential.py](examples/workflow_agents_sequential.py) | A sequential orchestration using `SequentialBuilder`: Writer and Reviewer run in order while sharing full conversation history. |
| [workflow_agents_streaming.py](examples/workflow_agents_streaming.py) | The same Writer → Reviewer workflow using `run(stream=True)` to observe `executor_invoked`, `executor_completed`, and streaming `output` events in real-time. |
| [workflow_agents_concurrent.py](examples/workflow_agents_concurrent.py) | Concurrent orchestration using `ConcurrentBuilder`: run specialist agents in parallel and collect merged conversations. |
| [workflow_conditional.py](examples/workflow_conditional.py) | A minimal workflow with conditional edges: the Reviewer routes to a Publisher (approved) or Editor (needs revision) based on a sentinel token. |
| [workflow_conditional_structured.py](examples/workflow_conditional_structured.py) | The same conditional-edge routing pattern, but with structured reviewer output (`response_format`) for typed branch decisions instead of sentinel string matching. |
| [workflow_conditional_state.py](examples/workflow_conditional_state.py) | A stateful conditional workflow with iterative revision loops: stores the latest draft in workflow state and publishes from that state after approval. |
| [workflow_conditional_state_isolated.py](examples/workflow_conditional_state_isolated.py) | The stateful conditional workflow using a `create_workflow(...)` factory to build fresh agents/workflow per task for state isolation and thread safety. |
| [workflow_switch_case.py](examples/workflow_switch_case.py) | A workflow with switch-case routing: a Classifier agent uses structured outputs to categorize a message and route to a specialized handler. |
| [workflow_multi_selection_edge_group.py](examples/workflow_multi_selection_edge_group.py) | LLM-powered multi-selection routing using `add_multi_selection_edge_group` to activate one-or-many downstream handlers. |
| [workflow_converge.py](examples/workflow_converge.py) | A branch-and-converge workflow: Reviewer routes to Publisher or Editor, then converges before final summary output. |
| [workflow_handoffbuilder.py](examples/workflow_handoffbuilder.py) | Autonomous handoff orchestration using `HandoffBuilder` (agents transfer control without human-in-the-loop). |
| [workflow_handoffbuilder_rules.py](examples/workflow_handoffbuilder_rules.py) | Handoff orchestration with explicit routing rules using `HandoffBuilder.add_handoff()`. |
| [workflow_hitl_requests.py](examples/workflow_hitl_requests.py) | Simple HITL chat — always pause for human input after every agent response (`ctx.request_info`, `@response_handler`). |
| [workflow_hitl_requests_structured.py](examples/workflow_hitl_requests_structured.py) | Trip planner HITL with structured outputs — agent decides when to ask vs. finish via `PlannerOutput.status`. |
| [workflow_hitl_tool_approval.py](examples/workflow_hitl_tool_approval.py) | Email agent workflow with `@tool(approval_mode="always_require")` for gating sensitive tool calls. |
| [workflow_hitl_checkpoint.py](examples/workflow_hitl_checkpoint.py) | Content review with `FileCheckpointStorage` — pause, exit process, and resume from checkpoint. |
| [workflow_hitl_checkpoint_pg.py](examples/workflow_hitl_checkpoint_pg.py) | Same content review workflow with a custom `PostgresCheckpointStorage` backend. |
| [workflow_hitl_handoff.py](examples/workflow_hitl_handoff.py) | Interactive handoff (no autonomous mode) — framework pauses for user input via `HandoffAgentUserRequest`. |
| [agent_otel_aspire.py](examples/agent_otel_aspire.py) | An agent with OpenTelemetry tracing, metrics, and structured logs exported to the [Aspire Dashboard](https://aspire.dev/dashboard/standalone/). |
| [agent_otel_appinsights.py](examples/agent_otel_appinsights.py) | An agent with OpenTelemetry tracing, metrics, and structured logs exported to [Azure Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview). Requires Azure provisioning via `azd provision`. |
| [agent_evaluation_generate.py](examples/agent_evaluation_generate.py) | Generate synthetic evaluation data for the travel planner agent. |
| [agent_evaluation.py](examples/agent_evaluation.py) | Evaluate a travel planner agent using [Azure AI Evaluation](https://learn.microsoft.com/azure/ai-foundry/concepts/evaluation-evaluators/agent-evaluators) agent evaluators (IntentResolution, ToolCallAccuracy, TaskAdherence, ResponseCompleteness). Optionally set `AZURE_AI_PROJECT` in `.env` to log results to [Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/agent-evaluate-sdk). |
| [agent_evaluation_batch.py](examples/agent_evaluation_batch.py) | Batch evaluation of agent responses using Azure AI Evaluation's `evaluate()` function. |
| [agent_redteam.py](examples/agent_redteam.py) | Red-team a financial advisor agent using [Azure AI Evaluation](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/red-teaming-agent) to test resilience against adversarial attacks across risk categories (Violence, HateUnfairness, Sexual, SelfHarm). Requires `AZURE_AI_PROJECT` in `.env`. |

## Using the Aspire Dashboard for telemetry

The [agent_otel_aspire.py](examples/agent_otel_aspire.py) example can export OpenTelemetry traces, metrics, and structured logs to a [Aspire Dashboard](https://aspire.dev/dashboard/standalone/).

### In GitHub Codespaces / Dev Containers

The Aspire Dashboard runs automatically as a service alongside the dev container. No extra setup is needed.

1. The `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable is already set by the dev container.

2. Run the example:

    ```sh
    uv run examples/agent_otel_aspire.py
    ```

3. Open the dashboard at <http://localhost:18888> and explore:

    * **Traces**: See the full span tree — agent invocation → chat completion → tool execution
    * **Metrics**: View token usage and operation duration histograms
    * **Structured Logs**: Browse conversation messages (system, user, assistant, tool)
    * **GenAI visualizer**: Select a chat completion span to see the rendered conversation

### Local environment (without Dev Containers)

If you're running locally without Dev Containers, you need to start the Aspire Dashboard manually:

1. Start the Aspire Dashboard:

    ```sh
    docker run --rm -it -d -p 18888:18888 -p 4317:18889 --name aspire-dashboard \
        -e DASHBOARD__FRONTEND__AUTHMODE=Unsecured \
        mcr.microsoft.com/dotnet/aspire-dashboard:latest
    ```

2. Add the OTLP endpoint to your `.env` file:

    ```sh
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
    ```

3. Run the example:

    ```sh
    uv run agent_otel_aspire.py
    ```

4. Open the dashboard at <http://localhost:18888> and explore.

5. When done, stop the dashboard:

    ```shell
    docker stop aspire-dashboard
    ```

For the full Python + Aspire guide, see [Use the Aspire dashboard with Python apps](https://aspire.dev/dashboard/standalone-for-python/).

## Exporting telemetry to Azure Application Insights

The [agent_otel_appinsights.py](examples/agent_otel_appinsights.py) example exports OpenTelemetry traces, metrics, and structured logs to [Azure Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview).

### Setup

This example requires an `APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable. You can get this automatically or manually:

**Option A: Automatic via `azd provision`**

If you run `azd provision` (see [Using Microsoft Foundry models](#using-microsoft-foundry-models)), the Application Insights resource is provisioned automatically and the connection string is written to your `.env` file.

**Option B: Manual from the Azure Portal**

1. Create an Application Insights resource in the [Azure Portal](https://portal.azure.com).
2. Copy the connection string from the resource's Overview page.
3. Add it to your `.env` file:

    ```sh
    APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...
    ```

### Running the example

```sh
uv run examples/agent_otel_appinsights.py
```

### Viewing telemetry

After running the example, navigate to your Application Insights resource in the Azure Portal:

* **Transaction search**: See end-to-end traces for agent invocations, chat completions, and tool executions.
* **Live Metrics**: Monitor real-time request rates and performance.
* **Performance**: Analyze operation durations and identify bottlenecks.

Telemetry data may take 2–5 minutes to appear in the portal.

## Resources

* [(February 2026) Python + Agents: Learn how to build agents and workflows in Python](https://aka.ms/pythonagents/rewatch)
* [Agent Framework Documentation](https://learn.microsoft.com/agent-framework/)

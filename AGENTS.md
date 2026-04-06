# Instructions for coding agents

This repository contains many examples of using the Microsoft Agent Framework in Python (agent-framework), sometimes abbreviated as MAF.

The agent-framework GitHub repo is here:
https://github.com/microsoft/agent-framework
It contains both Python and .NET agent framework code, but we are only using the Python packages in this repo.

MAF is changing rapidly still, so we sometimes need to check the repo changelog and issues to see if there are any breaking changes that might affect our code.
The Python changelog is here:
https://github.com/microsoft/agent-framework/blob/main/python/CHANGELOG.md

MAF documentation is available on Microsoft Learn here:
https://learn.microsoft.com/agent-framework/
When available, the MS Learn MCP server can be used to explore the documentation, ask questions, and get code examples.

## Package management

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Use `uv` commands instead of `pip`:

```bash
uv add <package>
uv sync
```

## Spanish translations

There are Spanish equivalents of each example in /examples/spanish.

Each example .py file should have a corresponding file with the same name under /examples/spanish/ that is the translation of the original, but with the same code. Here's a guide on what should be translated vs. what should be left in English:

* Comments: Spanish
* Docstrings: Spanish
* System prompts (agent instructions): Spanish
* Identifiers (functions/classes/vars): English
* User-facing output/data (e.g., example responses, sample values): Spanish
* @tool function names: English
* @tool parameter descriptions (Field(description=...)): English
* @tool docstrings: Spanish
* HITL control words: bilingual (approve/aprobar, exit/salir)
* Agent and workflow names: English ("TravelPlannerAgent" should be the same in both versions, not "AgentePlanificadorDeViajes")

Use informal (tuteo) LATAM Spanish, tu not usted, puedes not podes, etc. The content is technical so if a word is best kept in English, then do so.

The /examples/spanish/README.md corresponds to the root README.md and should be kept in sync with it, but translated to Spanish.

## Debugging Azure Python SDK HTTP requests

When debugging HTTP interactions between Azure Python SDKs (like `azure-ai-evaluation`) and Azure services, there are three levels of logging you can enable:

### 1. Azure SDK logger (request headers and URLs)

Set the Azure SDK loggers to DEBUG level to see request URLs, headers, and status codes:

```python
import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("azure").setLevel(logging.DEBUG)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.DEBUG)
```

### 2. Raw HTTP wire data (request/response headers)

Enable `http.client` debug logging to see the raw HTTP wire protocol, including request and response headers:

```python
import http.client
http.client.HTTPConnection.debuglevel = 1
```

Note: Response bodies will typically not be visible at this level because Azure SDKs use gzip compression, and `http.client` logs the raw compressed bytes.

### 3. Decompressed response bodies

To see actual response bodies, monkey-patch the Azure SDK's `HttpLoggingPolicy.on_response` method. This works because `response.http_response.body()` returns the decompressed content:

```python
from azure.core.pipeline.policies import HttpLoggingPolicy

_original_on_response = HttpLoggingPolicy.on_response

def _on_response_with_body(self, request, response):
    _original_on_response(self, request, response)
    try:
        body = response.http_response.body()
        if body:
            _logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
            _logger.debug("Response body: %s", body[:4096].decode("utf-8", errors="replace"))
    except Exception:
        pass

HttpLoggingPolicy.on_response = _on_response_with_body
```

## Manual test plan

After upgrading dependencies or making changes across examples, use this plan to verify everything works. Run each example with `uv run python examples/<file>.py`.

### No extra setup (Azure OpenAI only)

These work with just `API_HOST=azure` and the standard `.env` from `azd up`:

| Examples | Notes |
|----------|-------|
| `agent_basic.py` | Interactive chat loop |
| `agent_tool.py`, `agent_tools.py` | Tool calling |
| `agent_session.py` | Session persistence |
| `agent_with_subagent.py`, `agent_without_subagent.py` | Sub-agent patterns |
| `agent_supervisor.py` | Supervisor pattern |
| `agent_middleware.py` | Middleware pipeline |
| `agent_summarization.py` | Summarization middleware |
| `agent_tool_approval.py` | Tool approval |
| `workflow_agents.py`, `workflow_agents_sequential.py`, `workflow_agents_concurrent.py`, `workflow_agents_streaming.py` | Basic workflows |
| `workflow_conditional.py`, `workflow_conditional_state.py`, `workflow_conditional_state_isolated.py`, `workflow_conditional_structured.py` | Conditional workflows |
| `workflow_switch_case.py` | Switch/case workflow |
| `workflow_converge.py`, `workflow_fan_out_fan_in_edges.py` | Converge / fan-out patterns |
| `workflow_aggregator_ranked.py`, `workflow_aggregator_structured.py`, `workflow_aggregator_summary.py`, `workflow_aggregator_voting.py` | Aggregator workflows |
| `workflow_multi_selection_edge_group.py` | Multi-selection edges |
| `workflow_handoffbuilder.py`, `workflow_handoffbuilder_rules.py` | Handoff builder |
| `workflow_hitl_handoff.py`, `workflow_hitl_requests.py`, `workflow_hitl_requests_structured.py`, `workflow_hitl_tool_approval.py` | HITL workflows |
| `workflow_hitl_checkpoint.py` | HITL with file-based checkpoints |
| `agent_knowledge_sqlite.py` | SQLite knowledge provider |
| `agent_history_sqlite.py` | SQLite history provider (no tools — see [agent-framework#3295](https://github.com/microsoft/agent-framework/issues/3295)) |
| `agent_memory_mem0.py` | Mem0 memory provider |

### Requires Redis (dev container)

Redis runs automatically in the dev container at `redis://redis:6379`.

| Examples | Notes |
|----------|-------|
| `agent_history_redis.py` | Redis history provider (no tools — see [agent-framework#3295](https://github.com/microsoft/agent-framework/issues/3295)) |
| `agent_memory_redis.py` | Redis memory provider |

### Requires PostgreSQL (dev container)

PostgreSQL runs automatically in the dev container at `postgresql://admin:LocalPasswordOnly@db:5432/postgres`.

| Examples | Notes |
|----------|-------|
| `agent_knowledge_pg.py` | PG + pgvector knowledge |
| `agent_knowledge_pg_rewrite.py` | PG knowledge with query rewrite |
| `agent_knowledge_postgres.py` | PG knowledge (alternative) |
| `workflow_hitl_checkpoint_pg.py` | HITL with PG-backed checkpoints |

### Requires Azure AI Search

Needs `AZURE_SEARCH_ENDPOINT` and `AZURE_SEARCH_KNOWLEDGE_BASE_NAME` in `.env`.

| Examples | Notes |
|----------|-------|
| `agent_knowledge_aisearch.py` | Azure AI Search knowledge base (agentic mode) |

### Requires MCP server

Start the MCP server first: `uv run python examples/mcp_server.py`

| Examples | Notes |
|----------|-------|
| `agent_mcp_local.py` | Local MCP server (stdio) |
| `agent_mcp_remote.py` | Remote MCP server (SSE) |

### Requires OTel / Aspire

| Examples | Notes |
|----------|-------|
| `agent_otel_aspire.py` | Aspire dashboard (runs in dev container at `http://aspire-dashboard:18888`) |
| `agent_otel_appinsights.py` | Needs `APPLICATIONINSIGHTS_CONNECTION_STRING` in `.env` |

### Slow-running examples (⏱ 2–10 minutes)

These take significantly longer than other examples:

| Examples | Notes |
|----------|-------|
| `agent_evaluation.py` | Runs agent + evaluators inline. ~2–3 min. |
| `agent_evaluation_generate.py` | Generates eval data JSONL. ~2 min. |
| `agent_evaluation_batch.py` | Batch evaluators on JSONL. ~3–5 min. Needs `eval_data.jsonl` from `agent_evaluation_generate.py`. |
| `agent_redteam.py` | Red team attack simulation. ~5–10 min. |
| `workflow_magenticone.py` | Multi-agent MagenticOne orchestration. ~2–5 min. |

### Spanish examples

Spanish files under `examples/spanish/` mirror the English examples exactly (same code, translated strings). After changes, spot-check 3–5 Spanish files to confirm they run correctly.

# Upgrade Plan: MAF 1.0.0

Upgrade all examples (English + Spanish, ~110 files) to Microsoft Agent Framework 1.0.0.

## Resources consulted

- [Migration guide: Python 2026 Significant Changes](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes)
- [python-1.0.0 release notes](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0)
- [python-1.0.0rc6 release notes](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0rc6)
- [python-1.0.0rc5 release notes](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0rc5)
- [python-1.0.0rc4 release notes](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0rc4)
- [python-1.0.0rc3 release notes](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0rc3)
- [python-1.0.0rc2 release notes](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0rc2)

## Phase 1: Mechanical fixes (all files, English + Spanish)

These are identifiable by search and can be fixed with confidence before running anything.

### Step 1: `model_id=` → `model=` in all `OpenAIChatClient` constructors

From [rc6 — Model selection standardized on `model`](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes#python-100rc6):

> Use `model` everywhere you previously used `model_id`.

**Scope**: Every file that creates an `OpenAIChatClient` (~50 English + ~50 Spanish files).

**Before:**

```python
client = OpenAIChatClient(
    base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
    api_key=token_provider,
    model_id=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
)
```

**After:**

```python
client = OpenAIChatClient(
    base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
    api_key=token_provider,
    model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
)
```

### Step 2: `Message(text=...)` → `Message(contents=[...])`

From [1.0.0 — `Message(..., text=...)` construction is fully removed](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes#python-100):

> Build text messages as `Message(role="user", contents=["Hello"])` instead of `Message(role="user", text="Hello")`.

**Scope**: ~16 English + ~16 Spanish files.

**Before:**

```python
Message(role="system", text="You are a helpful assistant.")
Message("user", text=request)
```

**After:**

```python
Message(role="system", contents=["You are a helpful assistant."])
Message("user", contents=[request])
```

**Note:** Reading `.text` on responses/messages (e.g., `response.text`, `message.text`) is NOT affected — that's a computed property, not the removed constructor parameter.

**Affected files (English):**

| File | Occurrences |
|------|-------------|
| `examples/agent_summarization.py` | 3 |
| `examples/agent_middleware.py` | 1 |
| `examples/agent_knowledge_pg.py` | 1 |
| `examples/agent_knowledge_pg_rewrite.py` | 3 |
| `examples/agent_knowledge_postgres.py` | 1 |
| `examples/agent_knowledge_sqlite.py` | 1 |
| `examples/workflow_aggregator_ranked.py` | 2 |
| `examples/workflow_aggregator_structured.py` | 1 |
| `examples/workflow_converge.py` | 1 |
| `examples/workflow_hitl_checkpoint.py` | 2 |
| `examples/workflow_hitl_checkpoint_pg.py` | 2 |
| `examples/workflow_hitl_requests.py` | 2 |
| `examples/workflow_hitl_requests_structured.py` | 2 |
| `examples/workflow_multi_selection_edge_group.py` | 1 |

Plus all corresponding `examples/spanish/` equivalents.

### Step 3: `BaseContextProvider` → `ContextProvider`, `BaseHistoryProvider` → `HistoryProvider`

From [1.0.0 — Remove deprecated `BaseContextProvider` and `BaseHistoryProvider` aliases](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0) and [rc6 — Context providers can add middleware](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes#python-100rc6):

> `ContextProvider` and `HistoryProvider` are now the canonical Python base classes. `BaseContextProvider` and `BaseHistoryProvider` remain temporarily as deprecated aliases... [then in 1.0.0] Remove deprecated `BaseContextProvider` and `BaseHistoryProvider` aliases.

**Scope**: 5 English + 5 Spanish files.

**Before:**

```python
from agent_framework import BaseContextProvider
class MyProvider(BaseContextProvider):
```

**After:**

```python
from agent_framework import ContextProvider
class MyProvider(ContextProvider):
```

**Affected files:**

| File | Class to rename |
|------|----------------|
| `examples/agent_history_sqlite.py` | `BaseHistoryProvider` → `HistoryProvider` |
| `examples/agent_knowledge_pg.py` | `BaseContextProvider` → `ContextProvider` |
| `examples/agent_knowledge_pg_rewrite.py` | `BaseContextProvider` → `ContextProvider` |
| `examples/agent_knowledge_postgres.py` | `BaseContextProvider` → `ContextProvider` |
| `examples/agent_knowledge_sqlite.py` | `BaseContextProvider` → `ContextProvider` |

Plus all corresponding `examples/spanish/` equivalents.

## Phase 2: Run and verify each example group

Run examples in logical groups, simplest first, fixing any additional runtime breakage discovered.

### Step 4: Simple agent examples (no external dependencies)

- `agent_basic.py`
- `agent_tool.py`
- `agent_tools.py`
- `agent_session.py`
- `agent_with_subagent.py`
- `agent_without_subagent.py`
- `agent_supervisor.py`

### Step 5: Middleware and summarization examples

- `agent_middleware.py`
- `agent_summarization.py`
- `agent_tool_approval.py`

### Step 6: Knowledge provider examples (require DB/service setup)

- `agent_knowledge_sqlite.py` — can test locally
- `agent_knowledge_pg.py` — needs Postgres
- `agent_knowledge_pg_rewrite.py` — needs Postgres
- `agent_knowledge_postgres.py` — needs Postgres
- `agent_knowledge_aisearch.py` — needs Azure AI Search

### Step 7: Memory/history examples

- `agent_history_sqlite.py` — can test locally
- `agent_history_redis.py` — needs Redis
- `agent_memory_redis.py` — needs Redis
- `agent_memory_mem0.py` — needs Mem0

### Step 8: MCP examples

- `agent_mcp_local.py` — needs local MCP server running
- `agent_mcp_remote.py` — needs remote MCP server

### Step 9: OTel / Evaluation examples

- `agent_otel_aspire.py` — needs Aspire dashboard
- `agent_otel_appinsights.py` — needs Application Insights
- `agent_evaluation.py` — needs azure-ai-evaluation
- `agent_evaluation_batch.py`
- `agent_evaluation_generate.py`
- `agent_redteam.py` — needs red team setup

### Step 10: Simple workflow examples

- `workflow_agents.py`
- `workflow_agents_sequential.py`
- `workflow_agents_concurrent.py`
- `workflow_agents_streaming.py`
- `workflow_conditional.py`
- `workflow_conditional_state.py`
- `workflow_conditional_state_isolated.py`
- `workflow_conditional_structured.py`
- `workflow_switch_case.py`

### Step 11: Complex workflow examples

- `workflow_converge.py`
- `workflow_fan_out_fan_in_edges.py`
- `workflow_aggregator_ranked.py`
- `workflow_aggregator_structured.py`
- `workflow_aggregator_summary.py`
- `workflow_aggregator_voting.py`
- `workflow_multi_selection_edge_group.py`
- `workflow_rag_ingest.py`

### Step 12: HITL and handoff workflow examples

- `workflow_handoffbuilder.py`
- `workflow_handoffbuilder_rules.py`
- `workflow_hitl_handoff.py`
- `workflow_hitl_requests.py`
- `workflow_hitl_requests_structured.py`
- `workflow_hitl_tool_approval.py`
- `workflow_hitl_checkpoint.py`
- `workflow_hitl_checkpoint_pg.py` — needs Postgres

### Step 13: MagenticOne workflow

- `workflow_magenticone.py`

## Phase 3: Spanish translations

### Step 14: Apply same fixes to all Spanish files

After English files are verified, apply the same mechanical fixes (steps 1–3) to all `examples/spanish/` equivalents. Spot-check 3–5 Spanish files to confirm they import and start correctly.

## Verification

1. After Phase 1 fixes, run `ruff check examples/` to catch import errors and unused imports.
2. For each example in Phase 2, run `python examples/<file>.py` and confirm no import/startup errors.
3. For interactive examples, confirm at least one successful prompt→response cycle.
4. For workflow examples, confirm the workflow runs to completion.
5. Spot-check 3–5 Spanish files after Phase 3.
6. Final sweep — should return zero hits:
   ```bash
   grep -rn "model_id\|BaseContextProvider\|BaseHistoryProvider" examples/
   ```

## Decisions and notes

- **`.text` read access** (e.g., `response.text`, `message.text`) is NOT broken — only the `text=` constructor kwarg was removed.
- **`SupportsAgentRun`** import and type hints in custom providers are still valid — no change needed.
- **`call_next()`** in middleware already has no arguments — already correct per the [rc5 middleware changes](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes#python-100rc5--python-100b260319-march-19-2026).
- **`pyproject.toml`** already has 1.0.0 versions — no dependency changes needed.
- **Spanish files** should mirror English changes exactly (same code, different strings).
- Examples requiring external services (Postgres, Redis, Azure AI Search, etc.) may only be verifiable as "imports and starts without crash" unless those services are available.

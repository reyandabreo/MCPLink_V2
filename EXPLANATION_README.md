# MCPLink V2 Backend Architecture & Integration

## Overview

MCPLink V2 is a modular AI orchestration backend built with FastAPI, designed for extensibility, secure sandboxed execution, and seamless integration with a CLI frontend. This document provides a detailed explanation of the backend architecture, request flow, tool system, and integration points for frontend and extensibility.

---

## 1. High-Level Structure

- **Framework:** FastAPI (Python)
- **Entry Point:** `app/main.py`
- **API Routing:** `app/api/routes.py`
- **Core Logic:**
  - `app/core/agent.py` (AgentOrchestrator)
  - `app/core/planner.py` (Planner)
  - `app/core/executor.py` (Executor)
- **Tool Registry:** `app/tools/registry.py`
- **Tool Implementations:**
  - `app/tools/filesystem.py`
  - `app/tools/code_tools.py`
  - `app/tools/document_tools.py`
  - `app/tools/execution.py`
  - `app/tools/git_tools.py`
- **Session & Memory:**
  - `app/memory/session_store.py`
  - `app/memory/history.py`
- **Sandbox:**
  - `app/sandbox/limits.py`
  - `app/sandbox/workspace/`

---

## 2. Backend Request Flow

### Flowchart

```mermaid
graph TD
A[Frontend UI] --> B[FastAPI Server (main.py)]
B --> C[API Router (routes.py)]
C --> D[AgentOrchestrator (agent.py)]
D --> E[Planner (planner.py)]
D --> F[Executor (executor.py)]
D --> G[Session Store (session_store.py)]
D --> H[Tool Registry (registry.py)]
H --> I[Tool Implementations (tools/*.py)]
```

### Step-by-step

1. **Frontend UI** sends HTTP requests (via CLI or web).
2. **FastAPI** receives requests in `main.py`, applies CORS, and includes API router.
3. **API Router** (`routes.py`) maps endpoints to logic:
   - Session management
   - Plan creation/execution
   - Tool listing
   - File upload
   - Policy management
4. **AgentOrchestrator** (`agent.py`) handles session, planning, and execution:
   - **Planner** generates step-by-step plans using LLM (`planner.py`).
   - **Executor** runs plan steps securely (`executor.py`).
   - **Session Store** tracks session state (`session_store.py`).
   - **History Manager** logs prompts and executions (`history.py`).
5. **Tool Registry** (`registry.py`) manages available tools.
6. **Tool Implementations** (filesystem, code, document, execution, git) are registered and invoked as needed.

---

## 3. Frontend Integration

- **CLI UI:** `cli/main.py` and screens (dashboard, plans, execute, files, tools, policy, history)
- **API Client:** `cli/api_client.py` interacts with backend endpoints.
- **Screens:** Each screen (e.g., dashboard, plans, execute) calls API endpoints, displays data, and triggers actions.

### Frontend-Backend Flow

- User action → CLI screen → API client → FastAPI endpoint → Core logic → Tool execution → Response → UI update

---

## 4. Tools: Adding & Improving

### Where to add/improve tools

- **Tool Registry:** `app/tools/registry.py` — register new tools.
- **Tool Implementations:** Add new tool files in `app/tools/` (e.g., `new_tool.py`).
- **Register Tool:** Use `@tool_registry.register` decorator in your tool file.
- **Schemas:** Define argument schemas using Pydantic models.
- **Sandbox Logic:** Use `app/sandbox/limits.py` for file/path safety.
- **Policy Enforcement:** Update `app/core/policy.py` for security checks.

### Directory Structure for Tools

- `app/tools/` — each file is a tool module.
- `app/tools/registry.py` — central registry.
- `app/core/policy.py` — policy enforcement.

---

## 5. Improvement Entry Points

- **To add a new tool:** Create a new file in `app/tools/`, define a Pydantic schema, implement logic, and register with the registry.
- **To improve an existing tool:** Edit the relevant tool file (e.g., `app/tools/filesystem.py`), update logic, schemas, or error handling.
- **To extend tool policies:** Update `app/core/policy.py` for validation and restrictions.
- **To enhance frontend integration:** Update `cli/api_client.py` and relevant screen files.

---

## 6. Detailed Backend Module Roles

### `app/main.py`
- FastAPI app setup, CORS, tool imports, router inclusion.

### `app/api/routes.py`
- Defines all API endpoints for session, plan, execution, tools, files, and policy.
- Handles HTTP request/response logic.

### `app/core/agent.py`
- Orchestrates session lifecycle, planning, and execution.
- Calls Planner and Executor.

### `app/core/planner.py`
- Interacts with LLM to generate structured execution plans.
- Injects available tools and schemas into LLM prompt.

### `app/core/executor.py`
- Executes plan steps securely, updates session state.
- Handles step-by-step and full execution modes.

### `app/tools/registry.py`
- Central registry for all tools.
- Decorator-based registration, schema validation, listing.

### `app/tools/*.py`
- Each file implements a tool (filesystem, code, document, execution, git).
- Tools are registered and exposed via API.

### `app/core/policy.py`
- Enforces tool existence, execution timeout, and step validation.

### `app/memory/session_store.py`, `app/memory/history.py`
- Track session state, plans, execution jobs, and history.

### `app/sandbox/limits.py`
- Path resolution, file size checks, sandbox enforcement.

---

## 7. Summary Diagram

```mermaid
flowchart LR
subgraph Backend
    A[FastAPI (main.py)]
    B[API Router (routes.py)]
    C[AgentOrchestrator (agent.py)]
    D[Planner (planner.py)]
    E[Executor (executor.py)]
    F[Tool Registry (registry.py)]
    G[Tool Implementations (tools/*.py)]
    H[Session Store (session_store.py)]
    I[History Manager (history.py)]
    J[Sandbox (limits.py)]
end
subgraph Frontend
    K[CLI UI (main.py)]
    L[API Client (api_client.py)]
    M[Screens (dashboard, plans, execute, files, tools)]
end
K --> L --> A
A --> B --> C
C --> D & E & F & H & I & J
F --> G
```

---

## 8. Where to Start

- **For new tools:** Start in `app/tools/`, register in `app/tools/registry.py`.
- **For improving tools:** Edit the tool file, update schemas, logic, and error handling.
- **For policy/security:** Update `app/core/policy.py`.
- **For frontend integration:** Update `cli/api_client.py` and relevant screen files.

---

## 9. Example: Adding a New Tool

1. Create a new file in `app/tools/` (e.g., `my_tool.py`).
2. Define a Pydantic schema for arguments.
3. Implement the tool logic.
4. Register the tool using `@tool_registry.register`.
5. Test via API endpoint `/tools` and integrate in frontend.

---

## 10. Security & Extensibility

- All tool executions are sandboxed and validated.
- Policies enforce tool registration, argument schema, and execution limits.
- Tools can be extended or restricted via policy and registry.

---

## 11. Frontend UI Integration

- CLI screens interact with backend via API client.
- Each screen maps to backend endpoints for data and actions.
- Tool registry and execution metrics are visualized in the UI.

---

## 12. References

- [app/main.py](app/main.py)
- [app/api/routes.py](app/api/routes.py)
- [app/core/agent.py](app/core/agent.py)
- [app/core/planner.py](app/core/planner.py)
- [app/core/executor.py](app/core/executor.py)
- [app/tools/registry.py](app/tools/registry.py)
- [app/tools/filesystem.py](app/tools/filesystem.py)
- [app/tools/code_tools.py](app/tools/code_tools.py)
- [app/tools/document_tools.py](app/tools/document_tools.py)
- [app/tools/execution.py](app/tools/execution.py)
- [app/tools/git_tools.py](app/tools/git_tools.py)
- [app/core/policy.py](app/core/policy.py)
- [app/memory/session_store.py](app/memory/session_store.py)
- [app/memory/history.py](app/memory/history.py)
- [app/sandbox/limits.py](app/sandbox/limits.py)
- [cli/main.py](cli/main.py)
- [cli/api_client.py](cli/api_client.py)

---

For further details or specific module explanations, see the referenced files or ask for a deep dive into any component.

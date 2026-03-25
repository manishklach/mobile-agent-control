from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status

from app.api.deps import get_agent_manager, get_event_bus
from app.core.auth import get_current_token
from app.core.config import get_settings
from app.models import (
    AgentDetailResponse,
    AgentEventsResponse,
    AgentListResponse,
    AgentMetricsResponse,
    AuditLogResponse,
    HealthResponse,
    LaunchAgentRequest,
    LaunchProfilesResponse,
    LogsResponse,
    McpServersResponse,
    MachineHealthStatus,
    MachineListResponse,
    MachineSelfResponse,
    PromptAgentRequest,
    RestartAgentRequest,
    RuntimeAdapterStatusResponse,
    RuntimeAdaptersResponse,
    RunningAgentsResponse,
    SlashCommandsResponse,
    StartAgentRequest,
    SubmitTaskRequest,
    TaskDetailResponse,
    TaskListResponse,
    UpsertSlashCommandRequest,
    WorkspacesResponse,
)
from app.services.agent_manager import AgentManager
from app.services.event_bus import EventBus

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> HealthResponse:
    return await manager.health()


@router.get("/machines/self", response_model=MachineSelfResponse)
async def machine_self(
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> MachineSelfResponse:
    return await manager.machine_self()


@router.get("/machines", response_model=MachineListResponse)
async def list_machines(
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> MachineListResponse:
    return await manager.machines()


@router.get("/machines/{machine_id}/health", response_model=MachineHealthStatus)
async def machine_health(
    machine_id: str,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> MachineHealthStatus:
    return await manager.machine_health(machine_id)


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentListResponse:
    return await manager.list_agents()


@router.get("/agents/running", response_model=RunningAgentsResponse)
async def running_agents(
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> RunningAgentsResponse:
    return await manager.running_agents()


@router.get("/agents/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(
    agent_id: str,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentDetailResponse:
    return await manager.get_agent(agent_id)


@router.post("/agents/start", response_model=AgentDetailResponse, status_code=status.HTTP_201_CREATED)
async def start_agent(
    request: StartAgentRequest,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentDetailResponse:
    return await manager.start_agent(request)


@router.get("/launch-profiles", response_model=LaunchProfilesResponse)
async def launch_profiles(
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> LaunchProfilesResponse:
    return await manager.get_launch_profiles()


@router.get("/runtime/adapters", response_model=RuntimeAdaptersResponse)
async def runtime_adapters(
    workspace: str | None = Query(default=None),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> RuntimeAdaptersResponse:
    return await manager.list_runtime_adapters(workspace)


@router.get("/runtime/adapters/{adapter_id}", response_model=RuntimeAdapterStatusResponse)
async def runtime_adapter(
    adapter_id: str,
    workspace: str | None = Query(default=None),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> RuntimeAdapterStatusResponse:
    return await manager.get_runtime_adapter(adapter_id, workspace)


@router.get("/runtime/adapters/{adapter_id}/commands", response_model=SlashCommandsResponse)
async def slash_commands(
    adapter_id: str,
    workspace: str | None = Query(default=None),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> SlashCommandsResponse:
    return await manager.list_slash_commands(adapter_id, workspace)


@router.post("/runtime/adapters/{adapter_id}/commands", response_model=SlashCommandsResponse)
async def upsert_slash_command(
    adapter_id: str,
    request: UpsertSlashCommandRequest,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> SlashCommandsResponse:
    return await manager.upsert_slash_command(
        adapter_id,
        name=request.name,
        prompt=request.prompt,
        description=request.description,
        scope=request.scope,
        workspace=request.workspace,
    )


@router.delete("/runtime/adapters/{adapter_id}/commands/{command_name}", response_model=SlashCommandsResponse)
async def delete_slash_command(
    adapter_id: str,
    command_name: str,
    scope: str = Query(default="project"),
    workspace: str | None = Query(default=None),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> SlashCommandsResponse:
    return await manager.delete_slash_command(adapter_id, command_name, scope=scope, workspace=workspace)


@router.get("/workspaces", response_model=WorkspacesResponse)
async def workspaces(
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> WorkspacesResponse:
    return await manager.list_workspaces()


@router.get("/machines/{machine_id}/mcp", response_model=McpServersResponse)
async def machine_mcp(
    machine_id: str,
    workspace: str | None = Query(default=None),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> McpServersResponse:
    return await manager.machine_mcp_servers(machine_id, workspace)


@router.post("/agents/launch", response_model=AgentDetailResponse, status_code=status.HTTP_201_CREATED)
async def launch_agent(
    request: LaunchAgentRequest,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentDetailResponse:
    return await manager.launch_agent(request)


@router.post("/agents/{agent_id}/stop", response_model=AgentDetailResponse)
async def stop_agent(
    agent_id: str,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentDetailResponse:
    return await manager.stop_agent(agent_id)


@router.post("/agents/{agent_id}/restart", response_model=AgentDetailResponse)
async def restart_agent(
    agent_id: str,
    request: RestartAgentRequest,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentDetailResponse:
    return await manager.restart_agent(agent_id, request)


@router.post("/agents/{agent_id}/prompt", response_model=AgentDetailResponse)
async def prompt_agent(
    agent_id: str,
    request: PromptAgentRequest,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentDetailResponse:
    return await manager.send_prompt(agent_id, request)


@router.post("/agents/{agent_id}/tasks", response_model=AgentDetailResponse)
async def submit_task(
    agent_id: str,
    request: SubmitTaskRequest,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentDetailResponse:
    return await manager.submit_task(agent_id, request)


@router.get("/agents/{agent_id}/logs", response_model=LogsResponse)
async def agent_logs(
    agent_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> LogsResponse:
    return await manager.get_logs(agent_id, limit=limit)


@router.get("/agents/{agent_id}/events", response_model=AgentEventsResponse)
async def agent_events(
    agent_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentEventsResponse:
    return await manager.get_agent_events(agent_id, limit=limit)


@router.get("/agents/{agent_id}/metrics", response_model=AgentMetricsResponse)
async def agent_metrics(
    agent_id: str,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AgentMetricsResponse:
    return await manager.get_agent_metrics(agent_id)


@router.get("/audit", response_model=AuditLogResponse)
async def audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> AuditLogResponse:
    return await manager.get_audit_log(limit)


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    limit: int = Query(default=100, ge=1, le=500),
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> TaskListResponse:
    return await manager.list_tasks(limit)


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: str,
    manager: AgentManager = Depends(get_agent_manager),
    _: str = Depends(get_current_token),
) -> TaskDetailResponse:
    return await manager.get_task(task_id)


@router.websocket("/ws")
async def websocket_updates(websocket: WebSocket, bus: EventBus = Depends(get_event_bus)) -> None:
    token = websocket.headers.get("authorization")
    if not token:
        token_query = websocket.query_params.get("token")
        token = f"Bearer {token_query}" if token_query else ""

    settings = get_settings()
    if token != f"Bearer {settings.bearer_token}":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    queue = bus.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)

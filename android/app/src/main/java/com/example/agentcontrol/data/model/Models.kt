package com.example.agentcontrol.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

@Serializable
data class MachineConfig(
    val id: String,
    val name: String,
    val baseUrl: String,
    val token: String
)

@Serializable
data class HealthResponse(
    val status: String,
    val time: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_name") val machineName: String,
    @SerialName("agents_total") val agentsTotal: Int,
    @SerialName("agents_running") val agentsRunning: Int,
    @SerialName("queued_jobs") val queuedJobs: Int
)

@Serializable
data class MachineHealthStatus(
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_name") val machineName: String,
    val status: String,
    @SerialName("monitor_state") val monitorState: String,
    @SerialName("last_heartbeat") val lastHeartbeat: String,
    @SerialName("last_seen") val lastSeen: String,
    @SerialName("agents_total") val agentsTotal: Int,
    @SerialName("agents_running") val agentsRunning: Int,
    @SerialName("agents_failed") val agentsFailed: Int,
    @SerialName("queued_jobs") val queuedJobs: Int,
    @SerialName("warning_count") val warningCount: Int,
    @SerialName("worker_pool") val workerPool: WorkerPoolState,
    val resources: ResourceUsage = ResourceUsage(),
    @SerialName("mcp_server_count") val mcpServerCount: Int = 0,
    @SerialName("mcp_healthy_count") val mcpHealthyCount: Int = 0,
    @SerialName("adapter_warnings") val adapterWarnings: List<String> = emptyList()
)

@Serializable
data class WorkerPoolState(
    @SerialName("desired_workers") val desiredWorkers: Int,
    @SerialName("busy_workers") val busyWorkers: Int,
    @SerialName("idle_workers") val idleWorkers: Int,
    @SerialName("queue_depth") val queueDepth: Int,
    @SerialName("supports_pause_resume") val supportsPauseResume: Boolean
)

@Serializable
data class MachineRecord(
    val id: String,
    val name: String,
    val status: String,
    @SerialName("started_at") val startedAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("worker_pool") val workerPool: WorkerPoolState,
    val capabilities: Map<String, Boolean>
)

@Serializable
data class MachineListResponse(
    val machines: List<MachineRecord>
)

@Serializable
data class MachineSelfResponse(
    val machine: MachineRecord,
    @SerialName("agents_total") val agentsTotal: Int,
    @SerialName("active_agents") val activeAgents: Int,
    @SerialName("queued_jobs") val queuedJobs: Int,
    @SerialName("max_active_agents") val maxActiveAgents: Int
)

@Serializable
data class LogEntry(
    val timestamp: String,
    val stream: String,
    val message: String
)

@Serializable
data class AgentRecord(
    val id: String,
    val name: String = "",
    val type: String,
    val state: String,
    @SerialName("current_state") val currentState: String = "IDLE",
    val progress: Int = 0,
    @SerialName("current_step") val currentStep: String = "Idle",
    @SerialName("last_updated_ts") val lastUpdatedTs: String? = null,
    @SerialName("error_message") val errorMessage: String? = null,
    val pid: Int? = null,
    val workspace: String? = null,
    @SerialName("launch_profile") val launchProfile: String? = null,
    @SerialName("current_task") val currentTask: String? = null,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("worker_id") val workerId: String? = null,
    @SerialName("current_job_id") val currentJobId: String? = null,
    @SerialName("runtime_model") val runtimeModel: String? = null,
    @SerialName("command_name") val commandName: String? = null,
    @SerialName("last_output_at") val lastOutputAt: String? = null,
    @SerialName("mcp_enabled") val mcpEnabled: Boolean = false,
    @SerialName("mcp_servers") val mcpServers: List<String> = emptyList(),
    @SerialName("recent_logs") val recentLogs: List<LogEntry> = emptyList(),
    val metadata: JsonObject = JsonObject(emptyMap())
)

@Serializable
data class JobRecord(
    val id: String,
    @SerialName("agent_id") val agentId: String,
    val kind: String,
    val state: String,
    @SerialName("input_text") val inputText: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("finished_at") val finishedAt: String? = null,
    val summary: String? = null,
    val error: String? = null
)

@Serializable
data class AuditEntry(
    val id: String,
    val timestamp: String,
    val action: String,
    @SerialName("target_type") val targetType: String,
    @SerialName("target_id") val targetId: String,
    val status: String,
    val message: String,
    val details: JsonObject = JsonObject(emptyMap())
)

@Serializable
data class AgentListResponse(val agents: List<AgentRecord>)

@Serializable
data class AgentDetailResponse(
    val agent: AgentRecord,
    @SerialName("current_job") val currentJob: JobRecord? = null,
    @SerialName("latest_completed_job") val latestCompletedJob: JobRecord? = null,
    @SerialName("recent_jobs") val recentJobs: List<JobRecord> = emptyList()
)

@Serializable
data class AgentOverviewRecord(
    val agent: AgentRecord,
    val status: AgentRuntimeStatus,
    @SerialName("current_job") val currentJob: JobRecord? = null,
    @SerialName("latest_completed_job") val latestCompletedJob: JobRecord? = null
)

@Serializable
data class AgentOverviewListResponse(
    val agents: List<AgentOverviewRecord>
)

@Serializable
data class LogsResponse(
    @SerialName("agent_id") val agentId: String,
    val logs: List<LogEntry>
)

@Serializable
data class ResourceUsage(
    @SerialName("cpu_percent") val cpuPercent: Double? = null,
    @SerialName("memory_mb") val memoryMb: Double? = null
)

@Serializable
data class AgentRuntimeStatus(
    @SerialName("agent_id") val agentId: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_name") val machineName: String,
    val type: String,
    val state: String,
    @SerialName("current_state") val currentState: String = "IDLE",
    val progress: Int = 0,
    @SerialName("current_step") val currentStep: String = "Idle",
    @SerialName("last_updated_ts") val lastUpdatedTs: String? = null,
    @SerialName("error_message") val errorMessage: String? = null,
    @SerialName("monitor_state") val monitorState: String,
    @SerialName("elapsed_seconds") val elapsedSeconds: Int,
    @SerialName("silence_seconds") val silenceSeconds: Int? = null,
    @SerialName("last_heartbeat") val lastHeartbeat: String? = null,
    @SerialName("last_log_timestamp") val lastLogTimestamp: String? = null,
    @SerialName("warning_indicator") val warningIndicator: Boolean = false,
    @SerialName("stuck_indicator") val stuckIndicator: Boolean = false,
    @SerialName("warning_message") val warningMessage: String? = null,
    @SerialName("current_task") val currentTask: String? = null,
    val workspace: String? = null,
    @SerialName("launch_profile") val launchProfile: String? = null,
    @SerialName("runtime_model") val runtimeModel: String? = null,
    @SerialName("command_name") val commandName: String? = null,
    @SerialName("last_output_at") val lastOutputAt: String? = null,
    @SerialName("mcp_enabled") val mcpEnabled: Boolean = false,
    @SerialName("mcp_servers") val mcpServers: List<String> = emptyList(),
    val pid: Int? = null,
    @SerialName("recent_logs") val recentLogs: List<LogEntry> = emptyList(),
    val resources: ResourceUsage = ResourceUsage()
)

@Serializable
data class RunningAgentsResponse(
    val agents: List<AgentRuntimeStatus>
)

@Serializable
data class AgentEventsResponse(
    @SerialName("agent_id") val agentId: String,
    val events: List<SupervisorEvent>
)

@Serializable
data class AgentMetricsResponse(
    @SerialName("agent_id") val agentId: String,
    val status: AgentRuntimeStatus
)

@Serializable
data class AgentStateSnapshot(
    @SerialName("agent_id") val agentId: String,
    val name: String,
    @SerialName("current_state") val currentState: String,
    val progress: Int = 0,
    @SerialName("current_step") val currentStep: String,
    @SerialName("last_updated_ts") val lastUpdatedTs: String,
    @SerialName("error_message") val errorMessage: String? = null
)

@Serializable
data class AgentStateResponse(
    @SerialName("agent_id") val agentId: String,
    val state: AgentStateSnapshot
)

@Serializable
data class AgentEvent(
    @SerialName("event_id") val eventId: String,
    @SerialName("agent_id") val agentId: String,
    val timestamp: String,
    val type: String,
    val payload: JsonObject = JsonObject(emptyMap())
)

@Serializable
data class AgentTimelineResponse(
    @SerialName("agent_id") val agentId: String,
    val events: List<AgentEvent>
)

@Serializable
data class ApprovalRequest(
    val id: String,
    @SerialName("agent_id") val agentId: String,
    @SerialName("action_type") val actionType: String,
    val payload: JsonObject = JsonObject(emptyMap()),
    val status: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_reason") val decisionReason: String? = null
)

@Serializable
data class ApprovalListResponse(
    val approvals: List<ApprovalRequest>
)

@Serializable
data class ApprovalDecisionResponse(
    val approval: ApprovalRequest
)

@Serializable
data class ReplayAgentRequest(
    val instruction: String? = null
)

@Serializable
data class OrchestrationTask(
    val id: String,
    val name: String,
    @SerialName("assigned_agent") val assignedAgent: String? = null,
    val status: String,
    val dependencies: List<String> = emptyList(),
    @SerialName("prompt_template") val promptTemplate: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("finished_at") val finishedAt: String? = null,
    @SerialName("error_message") val errorMessage: String? = null,
    val summary: String? = null
)

@Serializable
data class CreateTaskRequest(
    val name: String,
    @SerialName("prompt_template") val promptTemplate: String,
    @SerialName("assigned_agent") val assignedAgent: String? = null,
    val dependencies: List<String> = emptyList()
)

@Serializable
data class TaskListResponse(val tasks: List<OrchestrationTask>)

@Serializable
data class TaskDetailResponse(val task: OrchestrationTask)

@Serializable
data class JobListResponse(val jobs: List<JobRecord>)

@Serializable
data class AuditLogResponse(val entries: List<AuditEntry>)

@Serializable
data class StartAgentRequest(
    val type: String,
    @SerialName("initial_task") val initialTask: String? = null,
    val metadata: Map<String, JsonElement> = emptyMap()
)

@Serializable
data class LaunchProfileRecord(
    val id: String,
    @SerialName("agent_type") val agentType: String,
    @SerialName("adapter_id") val adapterId: String,
    val label: String,
    val description: String,
    @SerialName("workspace_required") val workspaceRequired: Boolean,
    @SerialName("supports_initial_prompt") val supportsInitialPrompt: Boolean,
    val capabilities: RuntimeCapabilities = RuntimeCapabilities(),
    val metadata: JsonObject = JsonObject(emptyMap())
)

@Serializable
data class LaunchProfilesResponse(val profiles: List<LaunchProfileRecord>)

@Serializable
data class RuntimeCapabilities(
    @SerialName("supports_initial_prompt") val supportsInitialPrompt: Boolean = true,
    @SerialName("supports_prompt_submission") val supportsPromptSubmission: Boolean = true,
    @SerialName("supports_background_process") val supportsBackgroundProcess: Boolean = true,
    @SerialName("supports_streaming_logs") val supportsStreamingLogs: Boolean = true,
    @SerialName("requires_workspace") val requiresWorkspace: Boolean = true,
    @SerialName("requires_local_auth") val requiresLocalAuth: Boolean = false,
    @SerialName("supports_resume") val supportsResume: Boolean = false,
    @SerialName("supports_command_templates") val supportsCommandTemplates: Boolean = false,
    @SerialName("supports_mcp") val supportsMcp: Boolean = false,
    @SerialName("supports_model_selection") val supportsModelSelection: Boolean = false
)

@Serializable
data class WorkspaceRecord(
    val path: String,
    val label: String,
    val source: String
)

@Serializable
data class WorkspacesResponse(val workspaces: List<WorkspaceRecord>)

@Serializable
data class LaunchAgentRequest(
    val type: String,
    @SerialName("launch_profile") val launchProfile: String,
    val workspace: String,
    @SerialName("initial_prompt") val initialPrompt: String? = null,
    @SerialName("runtime_model") val runtimeModel: String? = null,
    @SerialName("command_name") val commandName: String? = null
)

@Serializable
data class RuntimeFeatureStatus(
    val available: Boolean,
    val message: String? = null
)

@Serializable
data class RuntimeAdapterStatus(
    @SerialName("adapter_id") val adapterId: String,
    @SerialName("agent_type") val agentType: String,
    val label: String,
    val installed: RuntimeFeatureStatus,
    val auth: RuntimeFeatureStatus,
    val version: String? = null,
    @SerialName("binary_path") val binaryPath: String? = null,
    val capabilities: RuntimeCapabilities = RuntimeCapabilities(),
    val warnings: List<String> = emptyList()
)

@Serializable
data class RuntimeAdapterRecord(
    @SerialName("adapter_id") val adapterId: String,
    @SerialName("agent_type") val agentType: String,
    val label: String,
    val capabilities: RuntimeCapabilities = RuntimeCapabilities(),
    val status: RuntimeAdapterStatus
)

@Serializable
data class RuntimeAdaptersResponse(val adapters: List<RuntimeAdapterRecord>)

@Serializable
data class RuntimeAdapterStatusResponse(val adapter: RuntimeAdapterRecord)

@Serializable
data class SlashCommandRecord(
    val name: String,
    val description: String? = null,
    val scope: String,
    val path: String,
    val source: String,
    val managed: Boolean = false,
    @SerialName("prompt_preview") val promptPreview: String? = null
)

@Serializable
data class SlashCommandsResponse(
    @SerialName("adapter_id") val adapterId: String,
    val commands: List<SlashCommandRecord>
)

@Serializable
data class McpServerRecord(
    val name: String,
    val scope: String,
    val transport: String,
    val health: String,
    val enabled: Boolean = true,
    val command: String? = null,
    val endpoint: String? = null,
    val description: String? = null,
    val warning: String? = null
)

@Serializable
data class McpServersResponse(
    @SerialName("machine_id") val machineId: String,
    val servers: List<McpServerRecord>
)

@Serializable
data class RestartAgentRequest(val reason: String? = null)

@Serializable
data class PromptAgentRequest(val prompt: String)

@Serializable
data class SupervisorEvent(
    val event: String,
    val timestamp: String,
    val machine: MachineRecord? = null,
    @SerialName("machine_health") val machineHealth: MachineHealthStatus? = null,
    val agent: AgentRecord? = null,
    @SerialName("agent_status") val agentStatus: AgentRuntimeStatus? = null,
    @SerialName("state_update") val stateUpdate: AgentStateSnapshot? = null,
    @SerialName("timeline_event") val timelineEvent: AgentEvent? = null,
    val approval: ApprovalRequest? = null,
    val job: JobRecord? = null,
    val task: OrchestrationTask? = null,
    val log: LogEntry? = null,
    val audit: AuditEntry? = null,
    val message: String? = null
)

data class MachineOverview(
    val config: MachineConfig,
    val health: HealthResponse? = null,
    val machineHealth: MachineHealthStatus? = null,
    val machine: MachineRecord? = null,
    val error: String? = null,
    val lastSeenAt: String? = null
) {
    val isOnline: Boolean get() = health != null && machine != null
}

data class RunningAgentOverview(
    val machine: MachineConfig,
    val machineHealth: MachineHealthStatus?,
    val status: AgentRuntimeStatus
)

data class LaunchSupport(
    val adapter: RuntimeAdapterRecord? = null,
    val commands: List<SlashCommandRecord> = emptyList(),
    val mcpServers: List<McpServerRecord> = emptyList()
)

data class DashboardActivityItem(
    val machineId: String,
    val machineName: String,
    val timestamp: String,
    val category: String,
    val status: String,
    val title: String,
    val detail: String
)

data class DashboardSummary(
    val connectedMachines: Int = 0,
    val onlineMachines: Int = 0,
    val offlineMachines: Int = 0,
    val runningAgents: Int = 0,
    val warningAgents: Int = 0,
    val stuckAgents: Int = 0,
    val failedAgents: Int = 0,
    val queuedTasks: Int = 0,
    val recentCompletionsLastHour: Int = 0
)

data class DashboardMachineHealthCard(
    val machine: MachineOverview,
    val activeAgentCount: Int = 0,
    val unhealthy: Boolean = false
)

data class DashboardSnapshot(
    val summary: DashboardSummary = DashboardSummary(),
    val agents: List<DashboardAgentCard> = emptyList(),
    val machines: List<DashboardMachineHealthCard> = emptyList(),
    val recentActivity: List<DashboardActivityItem> = emptyList(),
    val lastUpdatedEpochMs: Long? = null
)

data class DashboardAgentCard(
    val machine: MachineConfig,
    val machineHealth: MachineHealthStatus? = null,
    val overview: AgentOverviewRecord
)

val AgentRecord.launchRequest: JsonObject?
    get() = metadata["launch_request"]?.jsonObject

val AgentRecord.promptTemplate: String?
    get() = launchRequest?.get("initial_prompt_template")?.jsonPrimitive?.contentOrNull?.ifBlank { null }

val AgentRecord.runtimeSummary: String?
    get() = listOfNotNull(runtimeModel, commandName?.let { "/$it" }).joinToString(" • ").ifBlank { null }

val LaunchProfileRecord.defaultModel: String?
    get() = metadata["default_model"]?.jsonPrimitive?.contentOrNull?.ifBlank { null }

val AgentOverviewRecord.primaryIssue: String?
    get() = when {
        agent.state.equals("failed", ignoreCase = true) -> latestCompletedJob?.error ?: latestCompletedJob?.summary
        status.monitorState.equals("stuck", ignoreCase = true) -> status.warningMessage
        status.monitorState.equals("warning", ignoreCase = true) -> status.warningMessage
        else -> null
    }

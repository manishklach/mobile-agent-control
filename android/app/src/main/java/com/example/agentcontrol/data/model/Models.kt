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
    val resources: ResourceUsage = ResourceUsage()
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
    val type: String,
    val state: String,
    val pid: Int? = null,
    val workspace: String? = null,
    @SerialName("launch_profile") val launchProfile: String? = null,
    @SerialName("current_task") val currentTask: String? = null,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("worker_id") val workerId: String? = null,
    @SerialName("current_job_id") val currentJobId: String? = null,
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
    @SerialName("monitor_state") val monitorState: String,
    @SerialName("elapsed_seconds") val elapsedSeconds: Int,
    @SerialName("last_heartbeat") val lastHeartbeat: String? = null,
    @SerialName("last_log_timestamp") val lastLogTimestamp: String? = null,
    @SerialName("warning_indicator") val warningIndicator: Boolean = false,
    @SerialName("stuck_indicator") val stuckIndicator: Boolean = false,
    @SerialName("warning_message") val warningMessage: String? = null,
    @SerialName("current_task") val currentTask: String? = null,
    val workspace: String? = null,
    @SerialName("launch_profile") val launchProfile: String? = null,
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
data class TaskListResponse(val tasks: List<JobRecord>)

@Serializable
data class TaskDetailResponse(val task: JobRecord)

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
    val capabilities: RuntimeCapabilities = RuntimeCapabilities()
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
    @SerialName("supports_resume") val supportsResume: Boolean = false
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
    @SerialName("initial_prompt") val initialPrompt: String? = null
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
    val job: JobRecord? = null,
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

data class DashboardActivityItem(
    val machineId: String,
    val machineName: String,
    val timestamp: String,
    val category: String,
    val status: String,
    val title: String,
    val detail: String
)

val AgentRecord.launchRequest: JsonObject?
    get() = metadata["launch_request"]?.jsonObject

val AgentRecord.promptTemplate: String?
    get() = launchRequest?.get("initial_prompt_template")?.jsonPrimitive?.contentOrNull?.ifBlank { null }

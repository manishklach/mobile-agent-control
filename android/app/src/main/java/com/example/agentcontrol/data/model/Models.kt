package com.example.agentcontrol.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

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
data class MachineSelfResponse(
    val machine: MachineRecord,
    @SerialName("agents_total") val agentsTotal: Int,
    @SerialName("active_agents") val activeAgents: Int,
    @SerialName("queued_jobs") val queuedJobs: Int
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
    @SerialName("current_job") val currentJob: JobRecord? = null
)

@Serializable
data class LogsResponse(
    @SerialName("agent_id") val agentId: String,
    val logs: List<LogEntry>
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
    val label: String,
    val description: String,
    @SerialName("workspace_required") val workspaceRequired: Boolean,
    @SerialName("supports_initial_prompt") val supportsInitialPrompt: Boolean
)

@Serializable
data class LaunchProfilesResponse(val profiles: List<LaunchProfileRecord>)

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
    val agent: AgentRecord? = null,
    val job: JobRecord? = null,
    val log: LogEntry? = null,
    val audit: AuditEntry? = null,
    val message: String? = null
)

data class MachineOverview(
    val config: MachineConfig,
    val health: HealthResponse? = null,
    val machine: MachineRecord? = null,
    val error: String? = null,
    val lastSeenAt: String? = null
) {
    val isOnline: Boolean get() = health != null && machine != null
}

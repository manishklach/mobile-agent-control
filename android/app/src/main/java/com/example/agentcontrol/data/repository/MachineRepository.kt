package com.example.agentcontrol.data.repository

import com.example.agentcontrol.data.local.MachineStore
import com.example.agentcontrol.data.model.AgentDetailResponse
import com.example.agentcontrol.data.model.AgentEventsResponse
import com.example.agentcontrol.data.model.AgentListResponse
import com.example.agentcontrol.data.model.AgentMetricsResponse
import com.example.agentcontrol.data.model.AuditLogResponse
import com.example.agentcontrol.data.model.DashboardActivityItem
import com.example.agentcontrol.data.model.HealthResponse
import com.example.agentcontrol.data.model.LaunchAgentRequest
import com.example.agentcontrol.data.model.LaunchProfilesResponse
import com.example.agentcontrol.data.model.LogsResponse
import com.example.agentcontrol.data.model.MachineConfig
import com.example.agentcontrol.data.model.MachineHealthStatus
import com.example.agentcontrol.data.model.MachineOverview
import com.example.agentcontrol.data.model.RunningAgentOverview
import com.example.agentcontrol.data.model.MachineSelfResponse
import com.example.agentcontrol.data.model.PromptAgentRequest
import com.example.agentcontrol.data.model.RestartAgentRequest
import com.example.agentcontrol.data.model.RunningAgentsResponse
import com.example.agentcontrol.data.model.StartAgentRequest
import com.example.agentcontrol.data.model.SupervisorEvent
import com.example.agentcontrol.data.model.TaskDetailResponse
import com.example.agentcontrol.data.model.TaskListResponse
import com.example.agentcontrol.data.model.WorkspacesResponse
import com.example.agentcontrol.data.network.ApiClientFactory
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import retrofit2.HttpException
import java.io.IOException

data class BestMachineLaunchResult(
    val machine: MachineConfig,
    val agent: AgentDetailResponse
)

class MachineRepository(
    private val machineStore: MachineStore,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    fun observeMachines(): StateFlow<List<MachineConfig>> = machineStore.machines

    suspend fun addMachine(name: String, baseUrl: String, token: String) {
        machineStore.addMachine(name, baseUrl, token)
    }

    suspend fun loadMachineOverview(machine: MachineConfig): MachineOverview = withContext(ioDispatcher) {
        runCatching {
            val (api, _) = ApiClientFactory.create(machine.baseUrl) { machine.token }
            val health = api.health()
            val self = api.machineSelf()
            val machineHealth = api.machineHealth(self.machine.id)
            MachineOverview(config = machine, health = health, machineHealth = machineHealth, machine = self.machine)
        }.getOrElse { error ->
            MachineOverview(config = machine, error = error.message ?: "Failed to load machine")
        }
    }

    suspend fun health(machineId: String): HealthResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.health()
    }

    suspend fun machineSelf(machineId: String): MachineSelfResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.machineSelf()
    }

    suspend fun machineHealth(machineId: String): MachineHealthStatus = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        val (api, _) = ApiClientFactory.create(machine.baseUrl) { machine.token }
        val self = api.machineSelf()
        api.machineHealth(self.machine.id)
    }

    suspend fun listAgents(machineId: String): AgentListResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.listAgents()
    }

    suspend fun getAgent(machineId: String, agentId: String): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.getAgent(agentId)
    }

    suspend fun runningAgents(machineId: String): RunningAgentsResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.runningAgents()
    }

    suspend fun startAgent(machineId: String, request: StartAgentRequest): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.startAgent(request)
    }

    suspend fun launchProfiles(machineId: String): LaunchProfilesResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.launchProfiles()
    }

    suspend fun workspaces(machineId: String): WorkspacesResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.workspaces()
    }

    suspend fun launchAgent(machineId: String, request: LaunchAgentRequest): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.launchAgent(request).also {
            machineStore.saveLastWorkspace(machineId, request.workspace)
        }
    }

    suspend fun stopAgent(machineId: String, agentId: String): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.stopAgent(agentId)
    }

    suspend fun restartAgent(machineId: String, agentId: String, reason: String?): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.restartAgent(agentId, RestartAgentRequest(reason))
    }

    suspend fun sendPrompt(machineId: String, agentId: String, prompt: String): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.promptAgent(agentId, PromptAgentRequest(prompt))
    }

    suspend fun getLogs(machineId: String, agentId: String): LogsResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.logs(agentId)
    }

    suspend fun getAgentEvents(machineId: String, agentId: String): AgentEventsResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.agentEvents(agentId)
    }

    suspend fun getAgentMetrics(machineId: String, agentId: String): AgentMetricsResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.agentMetrics(agentId)
    }

    suspend fun listTasks(machineId: String): TaskListResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.listTasks()
    }

    suspend fun getTask(machineId: String, taskId: String): TaskDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.getTask(taskId)
    }

    suspend fun getAudit(machineId: String): AuditLogResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.audit()
    }

    suspend fun launchAgentOnBestMachine(request: LaunchAgentRequest): BestMachineLaunchResult = withContext(ioDispatcher) {
        val candidates = machineStore.machines.value.mapNotNull { machine ->
            runCatching {
                val (api, _) = ApiClientFactory.create(machine.baseUrl) { machine.token }
                val health = api.health()
                if (!health.status.equals("ok", ignoreCase = true)) return@runCatching null
                val self = api.machineSelf()
                if (self.activeAgents >= self.maxActiveAgents) return@runCatching null
                val profiles = api.launchProfiles().profiles
                if (profiles.none { it.id == request.launchProfile && it.agentType == request.type }) return@runCatching null
                val workspaces = api.workspaces().workspaces
                if (workspaces.none { it.path == request.workspace }) return@runCatching null
                Triple(machine, self, health)
            }.getOrNull()
        }

        val best = candidates
            .sortedWith(
                compareByDescending<Triple<MachineConfig, com.example.agentcontrol.data.model.MachineSelfResponse, HealthResponse>> { it.second.machine.workerPool.idleWorkers }
                    .thenBy { it.second.machine.workerPool.queueDepth }
                    .thenBy { it.second.activeAgents }
            )
            .firstOrNull()
            ?: error("No online machine supports that workspace/profile combination right now")

        val machine = best.first
        val response = ApiClientFactory.create(machine.baseUrl) { machine.token }.first.launchAgent(request)
        machineStore.saveLastWorkspace(machine.id, request.workspace)
        BestMachineLaunchResult(machine = machine, agent = response)
    }

    suspend fun loadRunningAgentsAcrossMachines(): List<RunningAgentOverview> = withContext(ioDispatcher) {
        machineStore.machines.value.flatMap { machine ->
            runCatching {
                val (api, _) = ApiClientFactory.create(machine.baseUrl) { machine.token }
                val self = api.machineSelf()
                val machineHealth = api.machineHealth(self.machine.id)
                api.runningAgents().agents.map { status ->
                    RunningAgentOverview(
                        machine = machine,
                        machineHealth = machineHealth,
                        status = status
                    )
                }
            }.getOrElse { emptyList() }
        }.sortedWith(
            compareByDescending<RunningAgentOverview> { it.status.monitorState == "stuck" }
                .thenByDescending { it.status.monitorState == "warning" }
                .thenByDescending { it.status.monitorState == "running" }
                .thenByDescending { it.status.elapsedSeconds }
        )
    }

    suspend fun loadDashboardActivityAcrossMachines(limit: Int = 20): List<DashboardActivityItem> = withContext(ioDispatcher) {
        machineStore.machines.value.flatMap { machine ->
            runCatching {
                val (api, _) = ApiClientFactory.create(machine.baseUrl) { machine.token }
                val auditItems = api.audit(limit = 10).entries.mapNotNull { entry ->
                    if (entry.action !in setOf("launch_agent", "restart_agent", "start_agent", "stop_agent")) return@mapNotNull null
                    DashboardActivityItem(
                        machineId = machine.id,
                        machineName = machine.name,
                        timestamp = entry.timestamp,
                        category = "audit",
                        status = entry.status,
                        title = when (entry.action) {
                            "launch_agent" -> "Launch"
                            "restart_agent" -> "Restart"
                            "stop_agent" -> "Stop"
                            else -> "Start"
                        },
                        detail = entry.message
                    )
                }
                val taskItems = api.listTasks(limit = 10).tasks.mapNotNull { task ->
                    if (task.state !in setOf("completed", "failed", "cancelled")) return@mapNotNull null
                    DashboardActivityItem(
                        machineId = machine.id,
                        machineName = machine.name,
                        timestamp = task.updatedAt,
                        category = "task",
                        status = task.state,
                        title = when (task.state) {
                            "completed" -> "Completion"
                            "failed" -> "Failure"
                            else -> "Cancelled"
                        },
                        detail = task.summary ?: task.error ?: task.inputText
                    )
                }
                auditItems + taskItems
            }.getOrElse { emptyList() }
        }.sortedByDescending { it.timestamp }.take(limit)
    }

    fun observeEvents(machineId: String): Flow<SupervisorEvent> = callbackFlow {
        val machine = requireMachineSync(machineId)
        val (_, client) = ApiClientFactory.create(machine.baseUrl) { machine.token }
        val socket = client.newWebSocket(
            ApiClientFactory.websocketRequest(machine.baseUrl, machine.token),
            object : WebSocketListener() {
                override fun onMessage(webSocket: WebSocket, text: String) {
                    runCatching { json.decodeFromString<SupervisorEvent>(text) }
                        .onSuccess { trySend(it).isSuccess }
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: okhttp3.Response?) {
                    close(t as? IOException ?: IOException(t.message ?: "WebSocket failure", t))
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    close()
                }
            }
        )
        awaitClose {
            socket.close(1000, "Closed")
            client.dispatcher.executorService.shutdown()
        }
    }

    private suspend fun requireMachine(id: String): MachineConfig {
        return machineStore.getMachine(id) ?: error("Machine not found")
    }

    private fun requireMachineSync(id: String): MachineConfig {
        return machineStore.getMachine(id) ?: error("Machine not found")
    }

    fun allMachines(): List<MachineConfig> = machineStore.machines.value

    fun lastWorkspace(machineId: String): String? = machineStore.getLastWorkspace(machineId)

    fun userMessage(error: Throwable): String {
        val http = error as? HttpException ?: return error.message ?: "Request failed"
        val body = http.response()?.errorBody()?.string().orEmpty()
        val detail = Regex("\"detail\"\\s*:\\s*\"([^\"]+)\"").find(body)?.groupValues?.getOrNull(1)
        return detail ?: error.message ?: "Request failed"
    }
}

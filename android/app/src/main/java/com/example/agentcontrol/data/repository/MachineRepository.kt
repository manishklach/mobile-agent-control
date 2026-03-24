package com.example.agentcontrol.data.repository

import com.example.agentcontrol.data.local.MachineStore
import com.example.agentcontrol.data.model.AgentDetailResponse
import com.example.agentcontrol.data.model.AgentListResponse
import com.example.agentcontrol.data.model.AuditLogResponse
import com.example.agentcontrol.data.model.HealthResponse
import com.example.agentcontrol.data.model.LaunchAgentRequest
import com.example.agentcontrol.data.model.LaunchProfilesResponse
import com.example.agentcontrol.data.model.LogsResponse
import com.example.agentcontrol.data.model.MachineConfig
import com.example.agentcontrol.data.model.MachineOverview
import com.example.agentcontrol.data.model.MachineSelfResponse
import com.example.agentcontrol.data.model.PromptAgentRequest
import com.example.agentcontrol.data.model.RestartAgentRequest
import com.example.agentcontrol.data.model.StartAgentRequest
import com.example.agentcontrol.data.model.SupervisorEvent
import com.example.agentcontrol.data.model.TaskDetailResponse
import com.example.agentcontrol.data.model.TaskListResponse
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
import java.io.IOException

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
            MachineOverview(config = machine, health = health, machine = self.machine)
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

    suspend fun listAgents(machineId: String): AgentListResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.listAgents()
    }

    suspend fun getAgent(machineId: String, agentId: String): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.getAgent(agentId)
    }

    suspend fun startAgent(machineId: String, request: StartAgentRequest): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.startAgent(request)
    }

    suspend fun launchProfiles(machineId: String): LaunchProfilesResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.launchProfiles()
    }

    suspend fun launchAgent(machineId: String, request: LaunchAgentRequest): AgentDetailResponse = withContext(ioDispatcher) {
        val machine = requireMachine(machineId)
        ApiClientFactory.create(machine.baseUrl) { machine.token }.first.launchAgent(request)
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
}

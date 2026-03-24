package com.example.agentcontrol.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.agentcontrol.data.model.AgentDetailResponse
import com.example.agentcontrol.data.model.AgentRecord
import com.example.agentcontrol.data.model.AuditEntry
import com.example.agentcontrol.data.model.JobRecord
import com.example.agentcontrol.data.model.LaunchAgentRequest
import com.example.agentcontrol.data.model.LaunchProfileRecord
import com.example.agentcontrol.data.model.MachineOverview
import com.example.agentcontrol.data.model.MachineSelfResponse
import com.example.agentcontrol.data.model.StartAgentRequest
import com.example.agentcontrol.data.model.SupervisorEvent
import com.example.agentcontrol.data.repository.MachineRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class AppUiState(
    val machines: UiState<List<MachineOverview>> = UiState.Loading,
    val machineDetail: UiState<MachineSelfResponse> = UiState.Loading,
    val agents: UiState<List<AgentRecord>> = UiState.Loading,
    val selectedAgent: UiState<AgentDetailResponse> = UiState.Loading,
    val tasks: UiState<List<JobRecord>> = UiState.Loading,
    val audit: UiState<List<AuditEntry>> = UiState.Loading,
    val launchProfiles: UiState<List<LaunchProfileRecord>> = UiState.Loading,
    val liveEvents: List<SupervisorEvent> = emptyList(),
    val selectedMachineId: String? = null,
    val actionError: String? = null,
    val actionMessage: String? = null,
    val launchedAgentId: String? = null,
    val streamStatus: String = "Disconnected"
)

class AppViewModel(private val repository: MachineRepository) : ViewModel() {
    private val _uiState = MutableStateFlow(AppUiState())
    val uiState: StateFlow<AppUiState> = _uiState.asStateFlow()

    private var machineEventsJob: Job? = null

    fun loadMachines() {
        viewModelScope.launch {
            _uiState.update { it.copy(machines = UiState.Loading) }
            val previous = (_uiState.value.machines as? UiState.Success)?.data.orEmpty().associateBy { it.config.id }
            val results = repository.observeMachines().value.map { repository.loadMachineOverview(it) }.map { overview ->
                val prior = previous[overview.config.id]
                if (overview.isOnline) {
                    overview.copy(lastSeenAt = overview.health?.time ?: overview.machine?.updatedAt ?: prior?.lastSeenAt)
                } else {
                    overview.copy(health = prior?.health, machine = prior?.machine, lastSeenAt = prior?.lastSeenAt)
                }
            }
            _uiState.update {
                it.copy(machines = if (results.isEmpty()) UiState.Error("No machines configured") else UiState.Success(results))
            }
        }
    }

    fun addMachine(name: String, baseUrl: String, token: String) {
        viewModelScope.launch {
            repository.addMachine(name, baseUrl, token)
            loadMachines()
        }
    }

    fun selectMachine(machineId: String) {
        _uiState.update {
            it.copy(
                selectedMachineId = machineId,
                liveEvents = emptyList(),
                actionError = null,
                actionMessage = null,
                launchedAgentId = null
            )
        }
    }

    fun clearLaunchNavigation() {
        _uiState.update { it.copy(launchedAgentId = null) }
    }

    fun loadMachineDetail(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(machineDetail = UiState.Loading, selectedMachineId = machineId) }
            runCatching { repository.machineSelf(machineId) }
                .onSuccess { response -> _uiState.update { it.copy(machineDetail = UiState.Success(response)) } }
                .onFailure { error -> _uiState.update { it.copy(machineDetail = UiState.Error(error.message ?: "Failed to load machine")) } }
        }
    }

    fun loadAgents(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(agents = UiState.Loading) }
            runCatching { repository.listAgents(machineId).agents }
                .onSuccess { agents -> _uiState.update { it.copy(agents = UiState.Success(agents), actionError = null) } }
                .onFailure { error -> _uiState.update { it.copy(agents = UiState.Error(error.message ?: "Failed to load agents")) } }
        }
    }

    fun loadAgent(machineId: String, agentId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(selectedAgent = UiState.Loading) }
            runCatching { repository.getAgent(machineId, agentId) }
                .onSuccess { response -> _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null) } }
                .onFailure { error -> _uiState.update { it.copy(selectedAgent = UiState.Error(error.message ?: "Failed to load agent")) } }
        }
    }

    fun loadTasks(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(tasks = UiState.Loading) }
            runCatching { repository.listTasks(machineId).tasks }
                .onSuccess { tasks -> _uiState.update { it.copy(tasks = UiState.Success(tasks)) } }
                .onFailure { error -> _uiState.update { it.copy(tasks = UiState.Error(error.message ?: "Failed to load tasks")) } }
        }
    }

    fun loadAudit(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(audit = UiState.Loading) }
            runCatching { repository.getAudit(machineId).entries }
                .onSuccess { entries -> _uiState.update { it.copy(audit = UiState.Success(entries)) } }
                .onFailure { error -> _uiState.update { it.copy(audit = UiState.Error(error.message ?: "Failed to load audit")) } }
        }
    }

    fun loadLaunchProfiles(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(launchProfiles = UiState.Loading) }
            runCatching { repository.launchProfiles(machineId).profiles }
                .onSuccess { profiles -> _uiState.update { it.copy(launchProfiles = UiState.Success(profiles)) } }
                .onFailure { error -> _uiState.update { it.copy(launchProfiles = UiState.Error(error.message ?: "Failed to load launch profiles")) } }
        }
    }

    fun startAgent(machineId: String, type: String, initialTask: String?) {
        viewModelScope.launch {
            runCatching { repository.startAgent(machineId, StartAgentRequest(type = type, initialTask = initialTask?.takeIf { it.isNotBlank() })) }
                .onSuccess { response ->
                    _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null, actionMessage = "Agent started") }
                    refreshMachine(machineId)
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = error.message ?: "Failed to start agent", actionMessage = null) } }
        }
    }

    fun launchAgent(machineId: String, type: String, launchProfile: String, workspace: String, initialPrompt: String?) {
        if (workspace.isBlank()) {
            _uiState.update { it.copy(actionError = "Workspace is required", actionMessage = null) }
            return
        }
        viewModelScope.launch {
            runCatching {
                repository.launchAgent(
                    machineId,
                    LaunchAgentRequest(
                        type = type,
                        launchProfile = launchProfile,
                        workspace = workspace,
                        initialPrompt = initialPrompt?.takeIf { it.isNotBlank() }
                    )
                )
            }.onSuccess { response ->
                _uiState.update {
                    it.copy(
                        selectedAgent = UiState.Success(response),
                        actionError = null,
                        actionMessage = "Agent launched",
                        launchedAgentId = response.agent.id
                    )
                }
                refreshMachine(machineId)
            }.onFailure { error ->
                _uiState.update { it.copy(actionError = error.message ?: "Failed to launch agent", actionMessage = null) }
            }
        }
    }

    fun startAgentOnBestMachine(type: String, initialTask: String?) {
        viewModelScope.launch(Dispatchers.Default) {
            val machines = (_uiState.value.machines as? UiState.Success)?.data.orEmpty()
            val best = machines
                .filter { it.isOnline && it.machine != null }
                .sortedWith(
                    compareByDescending<MachineOverview> { it.machine?.workerPool?.idleWorkers ?: 0 }
                        .thenBy { it.machine?.workerPool?.queueDepth ?: Int.MAX_VALUE }
                        .thenBy { it.health?.agentsRunning ?: Int.MAX_VALUE }
                )
                .firstOrNull()
            if (best == null) {
                _uiState.update { it.copy(actionError = "No online machine with available supervisor data", actionMessage = null) }
                return@launch
            }
            runCatching { repository.startAgent(best.config.id, StartAgentRequest(type = type, initialTask = initialTask?.takeIf { it.isNotBlank() })) }
                .onSuccess {
                    _uiState.update { state -> state.copy(actionError = null, actionMessage = "Dispatched $type to ${best.config.name}", selectedMachineId = best.config.id) }
                    loadMachines()
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = error.message ?: "Failed to dispatch to best machine", actionMessage = null) } }
        }
    }

    fun stopAgent(machineId: String, agentId: String) {
        viewModelScope.launch {
            runCatching { repository.stopAgent(machineId, agentId) }
                .onSuccess { response ->
                    _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null, actionMessage = "Agent stopped") }
                    refreshMachine(machineId)
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = error.message ?: "Failed to stop agent", actionMessage = null) } }
        }
    }

    fun restartAgent(machineId: String, agentId: String, reason: String?) {
        viewModelScope.launch {
            runCatching { repository.restartAgent(machineId, agentId, reason) }
                .onSuccess { response ->
                    _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null, actionMessage = "Agent restart queued") }
                    refreshMachine(machineId)
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = error.message ?: "Failed to restart agent", actionMessage = null) } }
        }
    }

    fun sendPrompt(machineId: String, agentId: String, prompt: String) {
        viewModelScope.launch {
            runCatching { repository.sendPrompt(machineId, agentId, prompt) }
                .onSuccess { response ->
                    _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null, actionMessage = "Prompt submitted") }
                    refreshMachine(machineId)
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = error.message ?: "Failed to send prompt", actionMessage = null) } }
        }
    }

    fun observeMachine(machineId: String) {
        machineEventsJob?.cancel()
        machineEventsJob = viewModelScope.launch {
            while (isActive) {
                _uiState.update { it.copy(streamStatus = "Connecting…") }
                runCatching {
                    repository.observeEvents(machineId).collect { event ->
                        _uiState.update { current ->
                            current.copy(
                                machineDetail = mergeMachineEvent(current.machineDetail, event),
                                agents = mergeAgentEvent(current.agents, event),
                                selectedAgent = mergeAgentDetailEvent(current.selectedAgent, event),
                                tasks = mergeTaskEvent(current.tasks, event),
                                audit = mergeAuditEvent(current.audit, event),
                                liveEvents = (listOf(event) + current.liveEvents).take(100),
                                streamStatus = "Live",
                                actionMessage = completionMessage(current.actionMessage, event)
                            )
                        }
                    }
                }.onFailure { error ->
                    _uiState.update { it.copy(streamStatus = "Reconnecting…", actionError = error.message ?: it.actionError) }
                    delay(1500)
                }
            }
        }
    }

    private fun refreshMachine(machineId: String) {
        loadMachineDetail(machineId)
        loadAgents(machineId)
        loadTasks(machineId)
        loadAudit(machineId)
    }

    private fun mergeMachineEvent(current: UiState<MachineSelfResponse>, event: SupervisorEvent): UiState<MachineSelfResponse> {
        val machine = event.machine ?: return current
        return when (current) {
            is UiState.Success -> UiState.Success(current.data.copy(machine = machine))
            else -> current
        }
    }

    private fun mergeAgentEvent(current: UiState<List<AgentRecord>>, event: SupervisorEvent): UiState<List<AgentRecord>> {
        val agent = event.agent ?: return current
        return when (current) {
            is UiState.Success -> {
                val previous = current.data.firstOrNull { it.id == agent.id }
                val merged = mergeAgent(previous, agent, event)
                UiState.Success((current.data.filterNot { it.id == agent.id } + merged).sortedByDescending { it.updatedAt })
            }
            else -> current
        }
    }

    private fun mergeAgentDetailEvent(current: UiState<AgentDetailResponse>, event: SupervisorEvent): UiState<AgentDetailResponse> {
        val agent = event.agent ?: return current
        return when (current) {
            is UiState.Success -> {
                if (current.data.agent.id != agent.id) current
                else UiState.Success(current.data.copy(agent = mergeAgent(current.data.agent, agent, event), currentJob = if (event.job?.agentId == agent.id) event.job else current.data.currentJob))
            }
            else -> current
        }
    }

    private fun mergeTaskEvent(current: UiState<List<JobRecord>>, event: SupervisorEvent): UiState<List<JobRecord>> {
        val job = event.job ?: return current
        return when (current) {
            is UiState.Success -> UiState.Success((current.data.filterNot { it.id == job.id } + job).sortedByDescending { it.updatedAt })
            else -> current
        }
    }

    private fun mergeAuditEvent(current: UiState<List<AuditEntry>>, event: SupervisorEvent): UiState<List<AuditEntry>> {
        val audit = event.audit ?: return current
        return when (current) {
            is UiState.Success -> UiState.Success((listOf(audit) + current.data.filterNot { it.id == audit.id }).take(100))
            else -> current
        }
    }

    private fun mergeAgent(previous: AgentRecord?, incoming: AgentRecord, event: SupervisorEvent): AgentRecord {
        if (event.log == null) return incoming
        val mergedLogs = ((previous?.recentLogs ?: emptyList()) + event.log)
            .distinctBy { "${it.timestamp}-${it.stream}-${it.message}" }
            .takeLast(200)
        return incoming.copy(recentLogs = mergedLogs)
    }

    private fun completionMessage(currentMessage: String?, event: SupervisorEvent): String? {
        return when (event.event) {
            "job.completed" -> event.message ?: "Task completed"
            "job.failed" -> event.message ?: "Task failed"
            "agent.stopped" -> event.message ?: "Agent stopped"
            else -> currentMessage
        }
    }

    override fun onCleared() {
        machineEventsJob?.cancel()
        super.onCleared()
    }

    class Factory(private val repository: MachineRepository) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = AppViewModel(repository) as T
    }
}

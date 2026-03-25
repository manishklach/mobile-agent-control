package com.example.agentcontrol.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.agentcontrol.data.model.AgentDetailResponse
import com.example.agentcontrol.data.model.AgentRecord
import com.example.agentcontrol.data.model.AgentRuntimeStatus
import com.example.agentcontrol.data.model.AuditEntry
import com.example.agentcontrol.data.model.DashboardActivityItem
import com.example.agentcontrol.data.model.JobRecord
import com.example.agentcontrol.data.model.LaunchAgentRequest
import com.example.agentcontrol.data.model.LaunchSupport
import com.example.agentcontrol.data.model.LaunchProfileRecord
import com.example.agentcontrol.data.model.MachineHealthStatus
import com.example.agentcontrol.data.model.MachineOverview
import com.example.agentcontrol.data.model.MachineSelfResponse
import com.example.agentcontrol.data.model.RunningAgentOverview
import com.example.agentcontrol.data.model.StartAgentRequest
import com.example.agentcontrol.data.model.SupervisorEvent
import com.example.agentcontrol.data.model.WorkspaceRecord
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
    val launchSupport: UiState<LaunchSupport> = UiState.Loading,
    val workspaces: UiState<List<WorkspaceRecord>> = UiState.Loading,
    val runningAgents: UiState<List<RunningAgentOverview>> = UiState.Loading,
    val dashboardActivity: UiState<List<DashboardActivityItem>> = UiState.Loading,
    val selectedAgentMetrics: UiState<AgentRuntimeStatus> = UiState.Loading,
    val selectedAgentEvents: UiState<List<SupervisorEvent>> = UiState.Loading,
    val liveEvents: List<SupervisorEvent> = emptyList(),
    val selectedMachineId: String? = null,
    val lastWorkspace: String? = null,
    val actionError: String? = null,
    val actionMessage: String? = null,
    val launchedAgentId: String? = null,
    val launchedAgentMachineId: String? = null,
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
                    overview.copy(lastSeenAt = overview.machineHealth?.lastSeen ?: overview.health?.time ?: overview.machine?.updatedAt ?: prior?.lastSeenAt)
                } else {
                    overview.copy(health = prior?.health, machineHealth = prior?.machineHealth, machine = prior?.machine, lastSeenAt = prior?.lastSeenAt)
                }
            }
            _uiState.update {
                it.copy(machines = if (results.isEmpty()) UiState.Error("No machines configured") else UiState.Success(results))
            }
            loadRunningAgents()
            loadDashboardActivity()
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
                launchedAgentId = null,
                launchedAgentMachineId = null
            )
        }
    }

    fun clearLaunchNavigation() {
        _uiState.update { it.copy(launchedAgentId = null, launchedAgentMachineId = null) }
    }

    fun loadMachineDetail(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(machineDetail = UiState.Loading, selectedMachineId = machineId) }
            runCatching { repository.machineSelf(machineId) }
                .onSuccess { response -> _uiState.update { it.copy(machineDetail = UiState.Success(response)) } }
                .onFailure { error -> _uiState.update { it.copy(machineDetail = UiState.Error(repository.userMessage(error))) } }
        }
    }

    fun loadAgents(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(agents = UiState.Loading) }
            runCatching { repository.listAgents(machineId).agents }
                .onSuccess { agents -> _uiState.update { it.copy(agents = UiState.Success(agents), actionError = null) } }
                .onFailure { error -> _uiState.update { it.copy(agents = UiState.Error(repository.userMessage(error))) } }
        }
    }

    fun loadAgent(machineId: String, agentId: String) {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    selectedAgent = UiState.Loading,
                    selectedAgentMetrics = UiState.Loading,
                    selectedAgentEvents = UiState.Loading
                )
            }
            runCatching {
                Triple(
                    repository.getAgent(machineId, agentId),
                    repository.getAgentMetrics(machineId, agentId).status,
                    repository.getAgentEvents(machineId, agentId).events
                )
            }.onSuccess { (response, metrics, events) ->
                _uiState.update {
                    it.copy(
                        selectedAgent = UiState.Success(response),
                        selectedAgentMetrics = UiState.Success(metrics),
                        selectedAgentEvents = UiState.Success(events.sortedByDescending { event -> event.timestamp }),
                        actionError = null
                    )
                }
            }.onFailure { error ->
                _uiState.update {
                    it.copy(
                        selectedAgent = UiState.Error(repository.userMessage(error)),
                        selectedAgentMetrics = UiState.Error(repository.userMessage(error)),
                        selectedAgentEvents = UiState.Error(repository.userMessage(error))
                    )
                }
            }
        }
    }

    fun loadRunningAgents() {
        viewModelScope.launch {
            _uiState.update { it.copy(runningAgents = UiState.Loading) }
            runCatching { repository.loadRunningAgentsAcrossMachines() }
                .onSuccess { agents ->
                    _uiState.update { it.copy(runningAgents = UiState.Success(agents)) }
                }
                .onFailure { error ->
                    _uiState.update { it.copy(runningAgents = UiState.Error(repository.userMessage(error))) }
                }
        }
    }

    fun loadDashboardActivity() {
        viewModelScope.launch {
            _uiState.update { it.copy(dashboardActivity = UiState.Loading) }
            runCatching { repository.loadDashboardActivityAcrossMachines() }
                .onSuccess { items -> _uiState.update { it.copy(dashboardActivity = UiState.Success(items)) } }
                .onFailure { error -> _uiState.update { it.copy(dashboardActivity = UiState.Error(repository.userMessage(error))) } }
        }
    }

    fun loadTasks(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(tasks = UiState.Loading) }
            runCatching { repository.listTasks(machineId).tasks }
                .onSuccess { tasks -> _uiState.update { it.copy(tasks = UiState.Success(tasks)) } }
                .onFailure { error -> _uiState.update { it.copy(tasks = UiState.Error(repository.userMessage(error))) } }
        }
    }

    fun loadAudit(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(audit = UiState.Loading) }
            runCatching { repository.getAudit(machineId).entries }
                .onSuccess { entries -> _uiState.update { it.copy(audit = UiState.Success(entries)) } }
                .onFailure { error -> _uiState.update { it.copy(audit = UiState.Error(repository.userMessage(error))) } }
        }
    }

    fun loadLaunchProfiles(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(launchProfiles = UiState.Loading) }
            runCatching { repository.launchProfiles(machineId).profiles }
                .onSuccess { profiles -> _uiState.update { it.copy(launchProfiles = UiState.Success(profiles)) } }
                .onFailure { error -> _uiState.update { it.copy(launchProfiles = UiState.Error(repository.userMessage(error))) } }
        }
    }

    fun loadLaunchSupport(machineId: String, adapterId: String, workspace: String?) {
        viewModelScope.launch {
            _uiState.update { it.copy(launchSupport = UiState.Loading) }
            runCatching {
                LaunchSupport(
                    adapter = repository.runtimeAdapter(machineId, adapterId, workspace).adapter,
                    commands = repository.slashCommands(machineId, adapterId, workspace).commands,
                    mcpServers = repository.machineMcp(machineId, workspace).servers
                )
            }.onSuccess { support ->
                _uiState.update { it.copy(launchSupport = UiState.Success(support), actionError = null) }
            }.onFailure { error ->
                _uiState.update { it.copy(launchSupport = UiState.Error(repository.userMessage(error))) }
            }
        }
    }

    fun loadWorkspaces(machineId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(workspaces = UiState.Loading, lastWorkspace = repository.lastWorkspace(machineId)) }
            runCatching { repository.workspaces(machineId).workspaces }
                .onSuccess { workspaces ->
                    _uiState.update {
                        it.copy(
                            workspaces = UiState.Success(workspaces),
                            lastWorkspace = repository.lastWorkspace(machineId)
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(
                            workspaces = UiState.Error(repository.userMessage(error)),
                            lastWorkspace = repository.lastWorkspace(machineId)
                        )
                    }
                }
        }
    }

    fun startAgent(machineId: String, type: String, initialTask: String?) {
        viewModelScope.launch {
            runCatching { repository.startAgent(machineId, StartAgentRequest(type = type, initialTask = initialTask?.takeIf { it.isNotBlank() })) }
                .onSuccess { response ->
                    _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null, actionMessage = "Agent started") }
                    refreshMachine(machineId)
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = repository.userMessage(error), actionMessage = null) } }
        }
    }

    fun launchAgent(
        machineId: String,
        type: String,
        launchProfile: String,
        workspace: String,
        initialPrompt: String?,
        runtimeModel: String? = null,
        commandName: String? = null
    ) {
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
                        initialPrompt = initialPrompt?.takeIf { it.isNotBlank() },
                        runtimeModel = runtimeModel?.takeIf { it.isNotBlank() },
                        commandName = commandName?.takeIf { it.isNotBlank() }
                    )
                )
            }.onSuccess { response ->
                _uiState.update {
                    it.copy(
                        selectedAgent = UiState.Success(response),
                        actionError = null,
                        actionMessage = if (response.agent.state.equals("pending", ignoreCase = true)) "Launch queued" else "Agent launched",
                        launchedAgentId = response.agent.id,
                        launchedAgentMachineId = machineId
                    )
                }
                refreshMachine(machineId)
                loadRunningAgents()
                loadDashboardActivity()
            }.onFailure { error ->
                _uiState.update { it.copy(actionError = repository.userMessage(error), actionMessage = null) }
            }
        }
    }

    fun launchAgentOnBestMachine(
        type: String,
        launchProfile: String,
        workspace: String,
        initialPrompt: String?,
        runtimeModel: String? = null,
        commandName: String? = null
    ) {
        if (workspace.isBlank()) {
            _uiState.update { it.copy(actionError = "Workspace is required", actionMessage = null) }
            return
        }
        viewModelScope.launch {
            runCatching {
                repository.launchAgentOnBestMachine(
                    LaunchAgentRequest(
                        type = type,
                        launchProfile = launchProfile,
                        workspace = workspace,
                        initialPrompt = initialPrompt?.takeIf { it.isNotBlank() },
                        runtimeModel = runtimeModel?.takeIf { it.isNotBlank() },
                        commandName = commandName?.takeIf { it.isNotBlank() }
                    )
                )
            }.onSuccess { result ->
                _uiState.update {
                    it.copy(
                        selectedMachineId = result.machine.id,
                        selectedAgent = UiState.Success(result.agent),
                        actionError = null,
                        actionMessage = "Launched on ${result.machine.name}",
                        launchedAgentId = result.agent.agent.id,
                        launchedAgentMachineId = result.machine.id
                    )
                }
                refreshMachine(result.machine.id)
                loadMachines()
                loadRunningAgents()
                loadDashboardActivity()
            }.onFailure { error ->
                _uiState.update { it.copy(actionError = repository.userMessage(error), actionMessage = null) }
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
                    loadRunningAgents()
                    loadDashboardActivity()
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = repository.userMessage(error), actionMessage = null) } }
        }
    }

    fun stopAgent(machineId: String, agentId: String) {
        viewModelScope.launch {
            runCatching { repository.stopAgent(machineId, agentId) }
                .onSuccess { response ->
                    _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null, actionMessage = "Agent stopped") }
                    refreshMachine(machineId)
                    loadRunningAgents()
                    loadDashboardActivity()
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = repository.userMessage(error), actionMessage = null) } }
        }
    }

    fun restartAgent(machineId: String, agentId: String, reason: String?) {
        viewModelScope.launch {
            runCatching { repository.restartAgent(machineId, agentId, reason) }
                .onSuccess { response ->
                    _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null, actionMessage = "Agent restart queued") }
                    refreshMachine(machineId)
                    loadRunningAgents()
                    loadDashboardActivity()
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = repository.userMessage(error), actionMessage = null) } }
        }
    }

    fun sendPrompt(machineId: String, agentId: String, prompt: String) {
        viewModelScope.launch {
            runCatching { repository.sendPrompt(machineId, agentId, prompt) }
                .onSuccess { response ->
                    _uiState.update { it.copy(selectedAgent = UiState.Success(response), actionError = null, actionMessage = "Prompt submitted") }
                    refreshMachine(machineId)
                    loadRunningAgents()
                    loadDashboardActivity()
                }
                .onFailure { error -> _uiState.update { it.copy(actionError = repository.userMessage(error), actionMessage = null) } }
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
                                selectedAgentMetrics = mergeAgentMetricsEvent(current.selectedAgentMetrics, event),
                                selectedAgentEvents = mergeAgentEventsEvent(current.selectedAgentEvents, event),
                                tasks = mergeTaskEvent(current.tasks, event),
                                audit = mergeAuditEvent(current.audit, event),
                                runningAgents = mergeRunningAgentsEvent(current.runningAgents, event),
                                dashboardActivity = mergeDashboardActivityEvent(current.dashboardActivity, event),
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
        loadRunningAgents()
        loadDashboardActivity()
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
                else {
                    val mergedRecentJobs = mergeRecentJobs(current.data.recentJobs, event.job)
                    val latestCompletedJob = when {
                        event.job?.agentId == agent.id && event.job.state in setOf("completed", "failed", "cancelled") -> event.job
                        else -> mergedRecentJobs.firstOrNull { it.state in setOf("completed", "failed", "cancelled") } ?: current.data.latestCompletedJob
                    }
                    val mergedCurrentJob = when {
                        event.job?.agentId != agent.id -> current.data.currentJob
                        event.job.state in setOf("running", "queued") -> event.job
                        else -> event.job
                    }
                    UiState.Success(
                        current.data.copy(
                            agent = mergeAgent(current.data.agent, agent, event),
                            currentJob = mergedCurrentJob,
                            latestCompletedJob = latestCompletedJob,
                            recentJobs = mergedRecentJobs
                        )
                    )
                }
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

    private fun mergeRunningAgentsEvent(current: UiState<List<RunningAgentOverview>>, event: SupervisorEvent): UiState<List<RunningAgentOverview>> {
        val status = event.agentStatus ?: return current
        val machineId = event.machine?.id ?: status.machineId
        return when (current) {
            is UiState.Success -> {
                val machines = repository.allMachines().associateBy { it.id }
                val machine = machines[machineId] ?: return current
                val merged = RunningAgentOverview(machine = machine, machineHealth = event.machineHealth, status = status)
                val filtered = current.data.filterNot { it.status.agentId == status.agentId }
                val next = if (status.state.lowercase() in setOf("stopped", "failed") && !status.warningIndicator && !status.stuckIndicator) {
                    filtered
                } else {
                    filtered + merged
                }
                UiState.Success(
                    next.sortedWith(
                        compareByDescending<RunningAgentOverview> { it.status.monitorState == "stuck" }
                            .thenByDescending { it.status.monitorState == "warning" }
                            .thenByDescending { it.status.monitorState == "running" }
                            .thenByDescending { it.status.elapsedSeconds }
                    )
                )
            }
            else -> current
        }
    }

    private fun mergeAgentMetricsEvent(current: UiState<AgentRuntimeStatus>, event: SupervisorEvent): UiState<AgentRuntimeStatus> {
        val status = event.agentStatus ?: return current
        return when (current) {
            is UiState.Success -> if (current.data.agentId == status.agentId) UiState.Success(status) else current
            else -> current
        }
    }

    private fun mergeAgentEventsEvent(current: UiState<List<SupervisorEvent>>, event: SupervisorEvent): UiState<List<SupervisorEvent>> {
        val agentId = event.agent?.id ?: event.job?.agentId ?: event.agentStatus?.agentId ?: return current
        return when (current) {
            is UiState.Success -> {
                val existingAgentId = current.data.firstOrNull()?.agent?.id
                    ?: current.data.firstOrNull()?.job?.agentId
                    ?: current.data.firstOrNull()?.agentStatus?.agentId
                if (existingAgentId != null && existingAgentId != agentId) current
                else UiState.Success((listOf(event) + current.data).distinctBy { "${it.timestamp}-${it.event}-${it.message}" }.take(50))
            }
            else -> current
        }
    }

    private fun mergeDashboardActivityEvent(current: UiState<List<DashboardActivityItem>>, event: SupervisorEvent): UiState<List<DashboardActivityItem>> {
        val machine = event.machine ?: return current
        val item = when {
            event.audit != null && event.audit.action in setOf("launch_agent", "restart_agent", "start_agent", "stop_agent") ->
                DashboardActivityItem(
                    machineId = machine.id,
                    machineName = machine.name,
                    timestamp = event.audit.timestamp,
                    category = "audit",
                    status = event.audit.status,
                    title = when (event.audit.action) {
                        "launch_agent" -> "Launch"
                        "restart_agent" -> "Restart"
                        "stop_agent" -> "Stop"
                        else -> "Start"
                    },
                    detail = event.audit.message
                )
            event.job != null && event.job.state in setOf("completed", "failed", "cancelled") ->
                DashboardActivityItem(
                    machineId = machine.id,
                    machineName = machine.name,
                    timestamp = event.job.updatedAt,
                    category = "task",
                    status = event.job.state,
                    title = when (event.job.state) {
                        "completed" -> "Completion"
                        "failed" -> "Failure"
                        else -> "Cancelled"
                    },
                    detail = event.job.summary ?: event.job.error ?: event.job.inputText
                )
            else -> null
        } ?: return current

        return when (current) {
            is UiState.Success -> UiState.Success((listOf(item) + current.data).distinctBy { "${it.timestamp}-${it.title}-${it.detail}" }.take(20))
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

    private fun mergeRecentJobs(current: List<JobRecord>, incoming: JobRecord?): List<JobRecord> {
        if (incoming == null) return current
        return (current.filterNot { it.id == incoming.id } + incoming).sortedByDescending { it.updatedAt }.take(8)
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

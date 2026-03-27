package com.example.agentcontrol.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.agentcontrol.data.model.AgentDetailResponse
import com.example.agentcontrol.data.model.AgentRecord
import com.example.agentcontrol.data.model.AgentRuntimeStatus
import com.example.agentcontrol.data.model.AuditEntry
import com.example.agentcontrol.data.model.DashboardActivityItem
import com.example.agentcontrol.data.model.JobRecord
import com.example.agentcontrol.data.model.LaunchSupport
import com.example.agentcontrol.data.model.LaunchProfileRecord
import com.example.agentcontrol.data.model.MachineOverview
import com.example.agentcontrol.data.model.MachineSelfResponse
import com.example.agentcontrol.data.model.RunningAgentOverview
import com.example.agentcontrol.data.model.SupervisorEvent
import com.example.agentcontrol.data.model.WorkspaceRecord
import com.example.agentcontrol.data.model.defaultModel
import com.example.agentcontrol.data.model.promptTemplate
import com.example.agentcontrol.data.model.runtimeSummary
import com.example.agentcontrol.ui.components.EmptyState
import com.example.agentcontrol.ui.components.ErrorState
import com.example.agentcontrol.ui.components.LoadingState
import com.example.agentcontrol.ui.viewmodel.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    machinesState: UiState<List<MachineOverview>>,
    runningAgentsState: UiState<List<RunningAgentOverview>>,
    activityState: UiState<List<DashboardActivityItem>>,
    actionMessage: String?,
    actionError: String?,
    onMachinesClick: () -> Unit,
    onRunningAgentsClick: () -> Unit,
    onSettingsClick: () -> Unit,
    onRefresh: () -> Unit,
    onMachineClick: (String) -> Unit,
    onOpenAgent: (String, String) -> Unit,
    onQuickDispatch: (String, String?) -> Unit
) {
    var dispatchType by rememberSaveable { mutableStateOf("gemini") }
    var dispatchTask by rememberSaveable { mutableStateOf("") }
    val machines = (machinesState as? UiState.Success)?.data.orEmpty()
    val runningAgents = (runningAgentsState as? UiState.Success)?.data.orEmpty()
    val activities = (activityState as? UiState.Success)?.data.orEmpty()
    val connectedMachines = machines.size
    val onlineMachines = machines.count { it.isOnline }
    val offlineMachines = connectedMachines - onlineMachines
    val warningAgents = runningAgents.count { it.status.monitorState == "warning" }
    val stuckAgents = runningAgents.count { it.status.monitorState == "stuck" }
    val failedAgents = machines.sumOf { it.machineHealth?.agentsFailed ?: 0 }
    val launchCount = activities.count { it.title == "Launch" || it.title == "Start" }
    val completionCount = activities.count { it.title == "Completion" }
    val failureCount = activities.count { it.title == "Failure" }
    val restartCount = activities.count { it.title == "Restart" }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Operator Dashboard") },
                actions = {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(onClick = onMachinesClick) { Text("Machines") }
                        TextButton(onClick = onRunningAgentsClick) { Text("Running") }
                        TextButton(onClick = onSettingsClick) { Text("Settings") }
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("Fleet Overview", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            MetricBlock("Connected", connectedMachines.toString())
                            MetricBlock("Online", onlineMachines.toString())
                            MetricBlock("Offline", offlineMachines.toString())
                            MetricBlock("Running", runningAgents.size.toString())
                        }
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            MetricBlock("Warning", warningAgents.toString())
                            MetricBlock("Stuck", stuckAgents.toString())
                            MetricBlock("Failed", failedAgents.toString())
                            MetricBlock("Recent", activities.size.toString())
                        }
                    }
                }
            }
            actionMessage?.let { message ->
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
                        Text(message, modifier = Modifier.fillMaxWidth().padding(16.dp))
                    }
                }
            }
            actionError?.let { item { ErrorState(it, onRefresh) } }
            item {
                Card {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Quick Launch", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Text("Dispatch a new agent to the best available machine from the dashboard.", style = MaterialTheme.typography.bodySmall)
                        OutlinedTextField(
                            value = dispatchType,
                            onValueChange = { dispatchType = it.lowercase() },
                            label = { Text("Runtime type") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        OutlinedTextField(
                            value = dispatchTask,
                            onValueChange = { dispatchTask = it },
                            label = { Text("Initial task (optional)") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { onQuickDispatch(dispatchType, dispatchTask.ifBlank { null }) }, enabled = dispatchType.isNotBlank()) {
                                Text("Launch")
                            }
                            TextButton(onClick = onRefresh) { Text("Refresh Dashboard") }
                        }
                    }
                }
            }
            item {
                SectionHeader(title = "Running Now", action = "View All", onAction = onRunningAgentsClick)
            }
            when (runningAgentsState) {
                UiState.Loading -> item { LoadingState("Checking active agents…") }
                is UiState.Error -> item { ErrorState(runningAgentsState.message, onRefresh) }
                is UiState.Success -> {
                    if (runningAgents.isEmpty()) {
                        item { EmptyState("No active agents right now.") }
                    } else {
                        items(runningAgents.take(5)) { item ->
                            RunningAgentCard(item = item, onOpen = { onOpenAgent(item.machine.id, item.status.agentId) })
                        }
                    }
                }
            }
            item {
                SectionHeader(title = "Machine Health", action = "Open Machines", onAction = onMachinesClick)
            }
            when (machinesState) {
                UiState.Loading -> item { LoadingState("Loading machines…") }
                is UiState.Error -> item { ErrorState(machinesState.message, onRefresh) }
                is UiState.Success -> {
                    if (machines.isEmpty()) {
                        item { EmptyState("No machines configured.") }
                    } else {
                        items(machines) { machine ->
                            MachineCard(machine = machine, onClick = { onMachineClick(machine.config.id) })
                        }
                    }
                }
            }
            item {
                SectionHeader(title = "Recent Activity", action = "Refresh", onAction = onRefresh)
            }
            item {
                Card {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        MetricBlock("Launches", launchCount.toString())
                        MetricBlock("Completions", completionCount.toString())
                        MetricBlock("Failures", failureCount.toString())
                        MetricBlock("Restarts", restartCount.toString())
                    }
                }
            }
            when (activityState) {
                UiState.Loading -> item { LoadingState("Loading recent activity…") }
                is UiState.Error -> item { ErrorState(activityState.message, onRefresh) }
                is UiState.Success -> {
                    if (activities.isEmpty()) {
                        item { EmptyState("No recent launches, completions, failures, or restarts yet.") }
                    } else {
                        items(activities.take(8)) { activity ->
                            DashboardActivityCard(activity = activity, onMachineClick = { onMachineClick(activity.machineId) })
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MachinesScreen(
    state: UiState<List<MachineOverview>>,
    actionMessage: String?,
    actionError: String?,
    onMachineClick: (String) -> Unit,
    onRunningAgentsClick: () -> Unit,
    onSettingsClick: () -> Unit,
    onRefreshClick: () -> Unit,
    onQuickDispatch: (String, String?) -> Unit
) {
    var dispatchType by rememberSaveable { mutableStateOf("gemini") }
    var dispatchTask by rememberSaveable { mutableStateOf("") }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Machines") },
                actions = {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(onClick = onRunningAgentsClick) { Text("Running") }
                        TextButton(onClick = onRefreshClick) { Text("Refresh") }
                        TextButton(onClick = onSettingsClick) { Text("Settings") }
                    }
                }
            )
        }
    ) { padding ->
        when (state) {
            UiState.Loading -> LoadingState("Checking machine supervisors…")
            is UiState.Error -> ErrorState(state.message, onRefreshClick)
            is UiState.Success -> {
                if (state.data.isEmpty()) {
                    EmptyState("No machines configured. Add one in Settings.")
                } else {
                    val onlineCount = state.data.count { it.isOnline }
                    val totalAgents = state.data.sumOf { it.health?.agentsRunning ?: 0 }
                    LazyColumn(
                        modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        item {
                            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    MetricBlock("Online", "$onlineCount/${state.data.size}")
                                    MetricBlock("Running", totalAgents.toString())
                                    MetricBlock("Queued", state.data.sumOf { it.health?.queuedJobs ?: 0 }.toString())
                                    MetricBlock("Warnings", state.data.sumOf { it.machineHealth?.warningCount ?: 0 }.toString())
                                }
                            }
                        }
                        actionMessage?.let { message ->
                            item {
                                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
                                    Text(message, modifier = Modifier.fillMaxWidth().padding(16.dp))
                                }
                            }
                        }
                        actionError?.let { message ->
                            item { ErrorState(message, onRefreshClick) }
                        }
                        item {
                            Card {
                                Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("Best Available Dispatch", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                    Text("Start a new agent on the machine with the most available worker capacity.", style = MaterialTheme.typography.bodySmall)
                                    OutlinedTextField(
                                        value = dispatchType,
                                        onValueChange = { dispatchType = it.lowercase() },
                                        label = { Text("Agent type") },
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                    OutlinedTextField(
                                        value = dispatchTask,
                                        onValueChange = { dispatchTask = it },
                                        label = { Text("Initial task (optional)") },
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                    Button(onClick = { onQuickDispatch(dispatchType, dispatchTask.ifBlank { null }) }, enabled = dispatchType.isNotBlank()) {
                                        Text("Dispatch to Best Machine")
                                    }
                                }
                            }
                        }
                        items(state.data) { machine ->
                            MachineCard(machine = machine, onClick = { onMachineClick(machine.config.id) })
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MachineDetailScreen(
    machineState: UiState<MachineSelfResponse>,
    agentsState: UiState<List<AgentRecord>>,
    actionError: String?,
    actionMessage: String?,
    streamStatus: String,
    onBack: () -> Unit,
    onOpenAgent: (String) -> Unit,
    onOpenActivity: () -> Unit,
    onLaunchAgent: () -> Unit,
    onStopAgent: (String) -> Unit,
    onRestartAgent: (String) -> Unit,
    onRelaunch: (String, String, String, String?) -> Unit,
    onRelaunchBest: (String, String, String, String?) -> Unit,
    onRefresh: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Machine Detail") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
                actions = {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(onClick = onOpenActivity) { Text("Activity") }
                        TextButton(onClick = onRefresh) { Text("Refresh") }
                    }
                }
            )
        }
    ) { padding ->
        when (machineState) {
            UiState.Loading -> LoadingState("Loading machine state…")
            is UiState.Error -> ErrorState(machineState.message, onRefresh)
            is UiState.Success -> {
                val machine = machineState.data.machine
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    item {
                        Card {
                            Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text(machine.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                                        Text(machine.id, style = MaterialTheme.typography.bodySmall)
                                    }
                                    StateBadge(machine.status)
                                }
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    MetricPill("Workers", "${machine.workerPool.busyWorkers}/${machine.workerPool.desiredWorkers}")
                                    MetricPill("Queue", machine.workerPool.queueDepth.toString())
                                    MetricPill("Stream", streamStatus)
                                }
                                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                                    MetricBlock("Active agents", machineState.data.activeAgents.toString())
                                    MetricBlock("Queued jobs", machineState.data.queuedJobs.toString())
                                    MetricBlock("Max active", machineState.data.maxActiveAgents.toString())
                                }
                            }
                        }
                    }
                    item {
                        Card {
                            Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("Launch New Agent", style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "Start a supervised local process with a safe launch profile, workspace, and optional initial prompt.",
                                    style = MaterialTheme.typography.bodySmall
                                )
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Button(onClick = onLaunchAgent) {
                                        Text("Launch Agent")
                                    }
                                }
                            }
                        }
                    }
                    actionError?.let {
                        item { ErrorState(it) }
                    }
                    actionMessage?.let {
                        item {
                            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
                                Text(it, modifier = Modifier.fillMaxWidth().padding(16.dp))
                            }
                        }
                    }
                    item {
                        Text("Agents", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    }
                    when (agentsState) {
                        UiState.Loading -> item { LoadingState("Loading agents…") }
                        is UiState.Error -> item { ErrorState(agentsState.message, onRefresh) }
                        is UiState.Success -> {
                            val recentSessions = agentsState.data
                                .filter { !it.launchProfile.isNullOrBlank() && !it.workspace.isNullOrBlank() }
                                .sortedByDescending { it.updatedAt }
                                .take(5)
                            item {
                                Text("Recent Sessions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            }
                            if (recentSessions.isEmpty()) {
                                item { EmptyState("No recent launched sessions yet.") }
                            } else {
                                items(recentSessions) { agent ->
                                    SessionCard(
                                        agent = agent,
                                        onOpen = { onOpenAgent(agent.id) },
                                        onRelaunch = {
                                            onRelaunch(
                                                agent.type,
                                                agent.launchProfile.orEmpty(),
                                                agent.workspace.orEmpty(),
                                                agent.promptTemplate
                                            )
                                        },
                                        onRelaunchBest = {
                                            onRelaunchBest(
                                                agent.type,
                                                agent.launchProfile.orEmpty(),
                                                agent.workspace.orEmpty(),
                                                agent.promptTemplate
                                            )
                                        }
                                    )
                                }
                            }
                            item {
                                Text("All Agents", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            }
                            if (agentsState.data.isEmpty()) {
                                item { EmptyState("No supervised agents on this machine.") }
                            } else {
                                items(agentsState.data.sortedBy { stateRank(it.state) }) { agent ->
                                    AgentCard(
                                        agent = agent,
                                        onClick = { onOpenAgent(agent.id) },
                                        onStop = { onStopAgent(agent.id) },
                                        onRestart = { onRestartAgent(agent.id) }
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LaunchAgentScreen(
    machineName: String,
    profilesState: UiState<List<LaunchProfileRecord>>,
    launchSupportState: UiState<LaunchSupport>,
    workspacesState: UiState<List<WorkspaceRecord>>,
    lastWorkspace: String?,
    actionError: String?,
    actionMessage: String?,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
    onLaunchSupportRefresh: (String, String?) -> Unit,
    onLaunch: (String, String, String, String?, String?, String?) -> Unit,
    onLaunchBestAvailable: (String, String, String, String?, String?, String?) -> Unit
) {
    var agentType by rememberSaveable { mutableStateOf("gemini") }
    var selectedProfileId by rememberSaveable { mutableStateOf("") }
    var selectedWorkspace by rememberSaveable { mutableStateOf("") }
    var initialPrompt by rememberSaveable { mutableStateOf("") }
    var runtimeModel by rememberSaveable { mutableStateOf("") }
    var selectedCommand by rememberSaveable { mutableStateOf("") }
    LaunchedEffect(lastWorkspace, workspacesState) {
        if (selectedWorkspace.isNotBlank()) return@LaunchedEffect
        val options = (workspacesState as? UiState.Success)?.data.orEmpty()
        selectedWorkspace = when {
            !lastWorkspace.isNullOrBlank() && options.any { it.path == lastWorkspace } -> lastWorkspace
            options.isNotEmpty() -> options.first().path
            else -> ""
        }
    }
    val profileOptions = (profilesState as? UiState.Success)?.data.orEmpty()
    val visibleAgentTypes = profileOptions.map { it.agentType }.distinct().ifEmpty { listOf("gemini", "hermes", "codex") }
    val selectedProfile = profileOptions.firstOrNull { it.id == selectedProfileId }
    LaunchedEffect(agentType, selectedWorkspace, selectedProfileId, profilesState) {
        val adapterId = selectedProfile?.adapterId ?: when (agentType) {
            "gemini" -> "gemini-cli"
            "hermes" -> "hermes-cli"
            else -> "codex-cli"
        }
        onLaunchSupportRefresh(adapterId, selectedWorkspace.ifBlank { null })
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Launch Agent") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
                actions = { TextButton(onClick = onRefresh) { Text("Refresh") } }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                Card {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Target Machine", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Text(machineName)
                        Text("Remote launch uses supervisor-approved profiles only. Arbitrary shell commands are not accepted.", style = MaterialTheme.typography.bodySmall)
                        Text("You can also route the same request to the best currently available machine.", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            item {
                Card {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Agent Type", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            visibleAgentTypes.forEach { type ->
                                FilterChip(
                                    selected = agentType == type,
                                    onClick = {
                                        agentType = type
                                        selectedProfileId = ""
                                        runtimeModel = ""
                                        selectedCommand = ""
                                    },
                                    label = { Text(type.uppercase()) }
                                )
                            }
                        }
                    }
                }
            }
            item {
                when (profilesState) {
                    UiState.Loading -> LoadingState("Loading launch profiles…")
                    is UiState.Error -> ErrorState(profilesState.message, onRefresh)
                    is UiState.Success -> {
                        val filteredProfiles = profilesState.data.filter { it.agentType == agentType }
                        LaunchedEffect(filteredProfiles.map { it.id }) {
                            if (selectedProfileId.isBlank() && filteredProfiles.isNotEmpty()) {
                                selectedProfileId = filteredProfiles.first().id
                            }
                        }
                        LaunchedEffect(selectedProfileId, filteredProfiles.map { it.id }) {
                            val selected = filteredProfiles.firstOrNull { it.id == selectedProfileId }
                            runtimeModel = if (selected?.capabilities?.supportsModelSelection == true) {
                                selected.defaultModel.orEmpty()
                            } else {
                                ""
                            }
                            if (selected?.capabilities?.supportsCommandTemplates != true) {
                                selectedCommand = ""
                            }
                        }
                        Card {
                            Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                Text("Launch Profile", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                if (filteredProfiles.isEmpty()) {
                                    EmptyState("No launch profiles available for $agentType.")
                                } else {
                                    filteredProfiles.forEach { profile ->
                                        Card(
                                            colors = CardDefaults.cardColors(
                                                containerColor = if (selectedProfileId == profile.id) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface
                                            )
                                        ) {
                                            Column(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .clickable { selectedProfileId = profile.id }
                                                    .padding(12.dp),
                                                verticalArrangement = Arrangement.spacedBy(4.dp)
                                            ) {
                                                Row(
                                                    modifier = Modifier.fillMaxWidth(),
                                                    horizontalArrangement = Arrangement.SpaceBetween,
                                                    verticalAlignment = Alignment.CenterVertically
                                                ) {
                                                    Text(profile.label, fontWeight = FontWeight.SemiBold)
                                                    if (selectedProfileId == profile.id) {
                                                        StateBadge("selected")
                                                    }
                                                }
                                                Text(profile.description, style = MaterialTheme.typography.bodySmall)
                                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                                    MetricPill("Workspace", if (profile.workspaceRequired) "Required" else "Optional")
                                                    MetricPill("Prompt", if (profile.supportsInitialPrompt) "Supported" else "Optional")
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            item {
                Card {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Workspace", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        when (workspacesState) {
                            UiState.Loading -> LoadingState("Loading safe workspaces…")
                            is UiState.Error -> ErrorState(workspacesState.message, onRefresh)
                            is UiState.Success -> {
                                if (workspacesState.data.isEmpty()) {
                                    EmptyState("No safe workspaces are configured on this machine.")
                                } else {
                                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                        lastWorkspace?.let { remembered ->
                                            Text("Last used: $remembered", style = MaterialTheme.typography.bodySmall)
                                        }
                                        workspacesState.data.forEach { workspace ->
                                            Card(
                                                colors = CardDefaults.cardColors(
                                                    containerColor = if (selectedWorkspace == workspace.path) {
                                                        MaterialTheme.colorScheme.secondaryContainer
                                                    } else {
                                                        MaterialTheme.colorScheme.surface
                                                    }
                                                )
                                            ) {
                                                Column(
                                                    modifier = Modifier
                                                        .fillMaxWidth()
                                                        .clickable { selectedWorkspace = workspace.path }
                                                        .padding(12.dp),
                                                    verticalArrangement = Arrangement.spacedBy(4.dp)
                                                ) {
                                                    Row(
                                                        modifier = Modifier.fillMaxWidth(),
                                                        horizontalArrangement = Arrangement.SpaceBetween,
                                                        verticalAlignment = Alignment.CenterVertically
                                                    ) {
                                                        Text(workspace.label, fontWeight = FontWeight.SemiBold)
                                                        if (selectedWorkspace == workspace.path) {
                                                            StateBadge("selected")
                                                        }
                                                    }
                                                    Text(workspace.path, style = MaterialTheme.typography.bodySmall)
                                                    MetricPill("Source", workspace.source)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        when (launchSupportState) {
                            UiState.Loading -> LoadingState("Checking runtime support…")
                            is UiState.Error -> ErrorState(launchSupportState.message, onRefresh)
                            is UiState.Success -> {
                                val support = launchSupportState.data
                                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                                    Column(modifier = Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                        Text(selectedProfile?.label ?: support.adapter?.label ?: "Runtime", fontWeight = FontWeight.SemiBold)
                                        Text(
                                            listOfNotNull(
                                                support.adapter?.status?.version?.let { "Version $it" },
                                                support.adapter?.status?.auth?.message,
                                            ).joinToString(" • ").ifBlank { "Runtime ready" },
                                            style = MaterialTheme.typography.bodySmall
                                        )
                                        support.adapter?.status?.installed?.message?.let { message ->
                                            if (!support.adapter.status.installed.available) {
                                                Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                                            }
                                        }
                                        support.adapter?.status?.warnings?.forEach { warning ->
                                            Text(warning, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                                        }
                                        if (support.adapter?.capabilities?.supportsModelSelection == true) {
                                            OutlinedTextField(
                                                value = runtimeModel,
                                                onValueChange = { runtimeModel = it },
                                                label = { Text("Model (optional)") },
                                                modifier = Modifier.fillMaxWidth()
                                            )
                                        }
                                        if (support.adapter?.capabilities?.supportsCommandTemplates == true && support.commands.isNotEmpty()) {
                                            Text("Slash Command", fontWeight = FontWeight.SemiBold)
                                            support.commands.take(8).forEach { command ->
                                                Card(
                                                    colors = CardDefaults.cardColors(
                                                        containerColor = if (selectedCommand == command.name) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface
                                                    )
                                                ) {
                                                    Column(
                                                        modifier = Modifier
                                                            .fillMaxWidth()
                                                            .clickable { selectedCommand = if (selectedCommand == command.name) "" else command.name }
                                                            .padding(10.dp),
                                                        verticalArrangement = Arrangement.spacedBy(4.dp)
                                                    ) {
                                                        Row(
                                                            modifier = Modifier.fillMaxWidth(),
                                                            horizontalArrangement = Arrangement.SpaceBetween,
                                                            verticalAlignment = Alignment.CenterVertically
                                                        ) {
                                                            Text("/${command.name}", fontWeight = FontWeight.SemiBold)
                                                            MetricPill("Scope", command.scope)
                                                        }
                                                        command.description?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                                                        command.promptPreview?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                                                    }
                                                }
                                            }
                                        }
                                        if (support.adapter?.capabilities?.supportsMcp == true && support.mcpServers.isNotEmpty()) {
                                            Text("MCP", fontWeight = FontWeight.SemiBold)
                                            support.mcpServers.take(6).forEach { server ->
                                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                                    StateBadge(server.health)
                                                    Text(server.name, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                                                    Text("${server.scope} • ${server.transport}", style = MaterialTheme.typography.bodySmall)
                                                }
                                                server.warning?.let {
                                                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Text("Initial Prompt", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        OutlinedTextField(
                            value = initialPrompt,
                            onValueChange = { initialPrompt = it },
                            label = { Text("Initial prompt (optional)") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        val canLaunch = selectedProfileId.isNotBlank() &&
                            selectedWorkspace.isNotBlank() &&
                            (workspacesState as? UiState.Success)?.data.orEmpty().any { it.path == selectedWorkspace }
                        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                            Column(modifier = Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("Launch Summary", fontWeight = FontWeight.SemiBold)
                                Text("Type: ${agentType.uppercase()}", style = MaterialTheme.typography.bodySmall)
                                Text("Profile: ${selectedProfileId.ifBlank { "Choose a profile" }}", style = MaterialTheme.typography.bodySmall)
                                Text("Workspace: ${selectedWorkspace.ifBlank { "Choose a workspace" }}", style = MaterialTheme.typography.bodySmall)
                                if (runtimeModel.isNotBlank()) {
                                    Text("Model: $runtimeModel", style = MaterialTheme.typography.bodySmall)
                                }
                                if (selectedCommand.isNotBlank()) {
                                    Text("Slash command: /$selectedCommand", style = MaterialTheme.typography.bodySmall)
                                }
                                Text(
                                    "Prompt: ${initialPrompt.ifBlank { "No initial prompt. Agent will start idle." }}",
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = { onLaunch(agentType, selectedProfileId, selectedWorkspace, initialPrompt.ifBlank { null }, runtimeModel.ifBlank { null }, selectedCommand.ifBlank { null }) },
                                enabled = canLaunch
                            ) {
                                Text("Launch Here")
                            }
                            Button(
                                onClick = { onLaunchBestAvailable(agentType, selectedProfileId, selectedWorkspace, initialPrompt.ifBlank { null }, runtimeModel.ifBlank { null }, selectedCommand.ifBlank { null }) },
                                enabled = canLaunch
                            ) {
                                Text("Best Available")
                            }
                        }
                    }
                }
            }
            actionError?.let { item { ErrorState(it, onRefresh) } }
            actionMessage?.let {
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
                        Text(it, modifier = Modifier.fillMaxWidth().padding(16.dp))
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MachineActivityScreen(
    tasksState: UiState<List<JobRecord>>,
    auditState: UiState<List<AuditEntry>>,
    onBack: () -> Unit,
    onRefresh: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Activity") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
                actions = { TextButton(onClick = onRefresh) { Text("Refresh") } }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item { Text("Task History", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
            when (tasksState) {
                UiState.Loading -> item { LoadingState("Loading task history…") }
                is UiState.Error -> item { ErrorState(tasksState.message, onRefresh) }
                is UiState.Success -> {
                    if (tasksState.data.isEmpty()) item { EmptyState("No task history yet.") } else items(tasksState.data.take(25)) { task ->
                        TaskCard(task)
                    }
                }
            }
            item { HorizontalDivider() }
            item { Text("Audit Events", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
            when (auditState) {
                UiState.Loading -> item { LoadingState("Loading audit events…") }
                is UiState.Error -> item { ErrorState(auditState.message, onRefresh) }
                is UiState.Success -> {
                    if (auditState.data.isEmpty()) item { EmptyState("No audit entries yet.") } else items(auditState.data.take(25)) { entry ->
                        AuditCard(entry)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RunningAgentsScreen(
    state: UiState<List<RunningAgentOverview>>,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
    onOpenAgent: (String, String) -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Running Agents") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
                actions = { TextButton(onClick = onRefresh) { Text("Refresh") } }
            )
        }
    ) { padding ->
        when (state) {
            UiState.Loading -> LoadingState("Checking running agents across machines…")
            is UiState.Error -> ErrorState(state.message, onRefresh)
            is UiState.Success -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    item {
                        Text("Active monitored agents across all connected supervisors.", style = MaterialTheme.typography.bodySmall)
                    }
                    if (state.data.isEmpty()) {
                        item { EmptyState("No running or queued agents across connected machines.") }
                    } else {
                        items(state.data) { item ->
                            RunningAgentCard(item = item, onOpen = { onOpenAgent(item.machine.id, item.status.agentId) })
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentDetailScreen(
    state: UiState<AgentDetailResponse>,
    metricsState: UiState<AgentRuntimeStatus>,
    eventsState: UiState<List<SupervisorEvent>>,
    liveEvents: List<SupervisorEvent>,
    actionError: String?,
    actionMessage: String?,
    streamStatus: String,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
    onStop: () -> Unit,
    onRestart: (String?) -> Unit,
    onPrompt: (String) -> Unit
) {
    var prompt by remember { mutableStateOf("") }
    var restartReason by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Agent Detail") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
                actions = { TextButton(onClick = onRefresh) { Text("Refresh") } }
            )
        }
    ) { padding ->
        when (state) {
            UiState.Loading -> LoadingState("Loading agent…")
            is UiState.Error -> ErrorState(state.message, onRefresh)
            is UiState.Success -> {
                val agent = state.data.agent
                val latestCompletedJob = state.data.latestCompletedJob
                val metrics = (metricsState as? UiState.Success)?.data
                val recentEvents = (eventsState as? UiState.Success)?.data ?: liveEvents
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    item {
                        Card {
                            Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text("${agent.type.uppercase()} Agent", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                                        Text(agent.id, style = MaterialTheme.typography.bodySmall)
                                    }
                                    StateBadge(metrics?.monitorState ?: agent.state)
                                }
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    MetricPill("Worker", agent.workerId ?: "-")
                                    MetricPill("Stream", streamStatus)
                                    MetricPill("PID", agent.pid?.toString() ?: "-")
                                    MetricPill("Job", agent.currentJobId ?: "-")
                                }
                                Text("Status: ${statusHeadline(metrics?.monitorState ?: agent.state, state.data.currentJob)}")
                                Text("Current task: ${agent.currentTask ?: latestCompletedJob?.inputText ?: "-"}")
                                Text("Workspace: ${agent.workspace ?: "-"}")
                                Text("Launch profile: ${agent.launchProfile ?: "-"}")
                                agent.runtimeModel?.let { Text("Model: $it") }
                                agent.commandName?.let { Text("Slash command: /$it") }
                                if (agent.mcpServers.isNotEmpty()) {
                                    Text("MCP: ${agent.mcpServers.joinToString(", ")}")
                                }
                                Text("Started: ${agent.startedAt ?: "-"}")
                                metrics?.let { status ->
                                    HorizontalDivider()
                                    Text("Live Monitoring", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        StateBadge(status.monitorState)
                                        MetricPill("Elapsed", formatDuration(status.elapsedSeconds))
                                        MetricPill("Heartbeat", status.lastHeartbeat ?: "-")
                                    }
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        MetricPill("Last log", status.lastLogTimestamp ?: "-")
                                        MetricPill("Last output", status.lastOutputAt ?: "-")
                                        MetricPill("CPU", status.resources.cpuPercent?.let { "${it.toInt()}%" } ?: "-")
                                        MetricPill("Memory", status.resources.memoryMb?.let { "${it} MB" } ?: "-")
                                    }
                                    if (status.runtimeModel != null || status.commandName != null || status.mcpServers.isNotEmpty()) {
                                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                            status.runtimeModel?.let { MetricPill("Model", it) }
                                            status.commandName?.let { MetricPill("Slash", "/$it") }
                                            if (status.mcpServers.isNotEmpty()) {
                                                MetricPill("MCP", status.mcpServers.joinToString(", "))
                                            }
                                        }
                                    }
                                    if (status.warningMessage != null) {
                                        Text(status.warningMessage, color = if (status.stuckIndicator) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                                    }
                                }
                                state.data.currentJob?.let { job ->
                                    HorizontalDivider()
                                    Text("Current job", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                                    Text("Kind: ${job.kind}")
                                    Text("State: ${job.state}")
                                    Text("Input: ${job.inputText}")
                                    Text(job.summary ?: job.error ?: "In progress")
                                }
                            }
                        }
                    }
                    latestCompletedJob?.let { job ->
                        item {
                            Card(colors = CardDefaults.cardColors(containerColor = resultContainer(job.state))) {
                                Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text("Latest Result", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                        StateBadge(job.state)
                                        Text(job.kind.uppercase(), fontWeight = FontWeight.SemiBold)
                                    }
                                    Text(job.inputText, style = MaterialTheme.typography.bodySmall)
                                    Text(job.summary ?: job.error ?: "No summary available")
                                }
                            }
                        }
                    }
                    item {
                        Card {
                            Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                Text("Quick Actions", style = MaterialTheme.typography.titleMedium)
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Button(onClick = onStop) { Text("Stop") }
                                }
                                OutlinedTextField(
                                    value = restartReason,
                                    onValueChange = { restartReason = it },
                                    label = { Text("Restart reason") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                Button(onClick = { onRestart(restartReason.ifBlank { null }) }) { Text("Restart") }
                                OutlinedTextField(
                                    value = prompt,
                                    onValueChange = { prompt = it },
                                    label = { Text("Send prompt") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                Button(onClick = { onPrompt(prompt); prompt = "" }, enabled = prompt.isNotBlank()) { Text("Send Prompt") }
                            }
                        }
                    }
                    actionError?.let { item { ErrorState(it) } }
                    actionMessage?.let {
                        item {
                            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
                                Text(it, modifier = Modifier.fillMaxWidth().padding(16.dp))
                            }
                        }
                    }
                    item { Text("Recent Runs", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
                    if (state.data.recentJobs.isEmpty()) {
                        item { EmptyState("No runs yet.") }
                    } else {
                        items(state.data.recentJobs.take(6)) { job ->
                            TaskCard(job)
                        }
                    }
                    item { Text("Recent Logs", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
                    val effectiveLogs = metrics?.recentLogs?.ifEmpty { agent.recentLogs } ?: agent.recentLogs
                    if (effectiveLogs.isEmpty()) {
                        item { EmptyState("No logs yet.") }
                    } else {
                        items(effectiveLogs.takeLast(20).reversed()) { log ->
                            Card(modifier = Modifier.fillMaxWidth()) {
                                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text("${log.stream} • ${log.timestamp}", style = MaterialTheme.typography.bodySmall)
                                    Text(log.message)
                                }
                            }
                        }
                    }
                    item { Text("Live Events", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
                    if (recentEvents.isEmpty()) {
                        item { EmptyState("No live events yet.") }
                    } else {
                        items(recentEvents.take(20)) { event ->
                            Card(modifier = Modifier.fillMaxWidth()) {
                                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                        StateBadge(event.agentStatus?.monitorState ?: event.event)
                                        Text(event.timestamp, style = MaterialTheme.typography.bodySmall)
                                    }
                                    Text(event.message ?: event.job?.inputText ?: "-")
                                }
                            }
                        }
                    }
                    item { Spacer(modifier = Modifier.height(24.dp)) }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit, onSave: (String, String, String) -> Unit) {
    var name by rememberSaveable { mutableStateOf("Workstation") }
    var baseUrl by rememberSaveable { mutableStateOf("http://machine-name.tailnet.ts.net:8000") }
    var token by rememberSaveable { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text("Register Supervisor", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Machine name") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(value = baseUrl, onValueChange = { baseUrl = it }, label = { Text("Base URL") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(value = token, onValueChange = { token = it }, label = { Text("Bearer token") }, modifier = Modifier.fillMaxWidth())
            Text("Use a private Tailscale-reachable URL for pre-release deployments.", style = MaterialTheme.typography.bodySmall)
            Button(onClick = { onSave(name, baseUrl, token) }, enabled = name.isNotBlank() && baseUrl.isNotBlank() && token.isNotBlank()) {
                Text("Save Machine")
            }
        }
    }
}

@Composable
private fun MachineCard(machine: MachineOverview, onClick: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable { onClick() }) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(machine.config.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(machine.config.baseUrl, style = MaterialTheme.typography.bodySmall)
                }
                StateBadge(
                    when {
                        !machine.isOnline -> "offline"
                        machine.machineHealth != null -> machine.machineHealth.monitorState
                        else -> "online"
                    }
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MetricPill("Running", (machine.health?.agentsRunning ?: 0).toString())
                MetricPill("Queued", (machine.health?.queuedJobs ?: 0).toString())
                MetricPill(
                    "Workers",
                    machine.machine?.workerPool?.let { "${it.busyWorkers}/${it.desiredWorkers}" } ?: "-"
                )
            }
            machine.machineHealth?.let { health ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MetricPill("Warnings", health.warningCount.toString())
                    MetricPill("Failed", health.agentsFailed.toString())
                    MetricPill("Heartbeat", health.lastHeartbeat)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MetricPill("MCP", "${health.mcpHealthyCount}/${health.mcpServerCount}")
                }
                if (health.resources.cpuPercent != null || health.resources.memoryMb != null) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        MetricPill("CPU", health.resources.cpuPercent?.let { "${it.toInt()}%" } ?: "-")
                        MetricPill("Memory", health.resources.memoryMb?.let { "${it.toInt()} MB" } ?: "-")
                    }
                }
                health.adapterWarnings.take(2).forEach { warning ->
                    Text(warning, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
            Text(
                if (machine.lastSeenAt != null) "Last seen: ${machine.lastSeenAt}" else "Last seen: never",
                style = MaterialTheme.typography.bodySmall
            )
            machine.error?.let { Text("Last error: $it", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        }
    }
}

@Composable
private fun RunningAgentCard(item: RunningAgentOverview, onOpen: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable { onOpen() }) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("${item.status.type.uppercase()} on ${item.machine.name}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(item.status.agentId, style = MaterialTheme.typography.bodySmall)
                }
                StateBadge(item.status.monitorState)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MetricPill("Machine", item.status.machineName)
                MetricPill("Elapsed", formatDuration(item.status.elapsedSeconds))
                MetricPill("PID", item.status.pid?.toString() ?: "-")
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MetricPill("Workspace", item.status.workspace ?: "-")
                MetricPill("Profile", item.status.launchProfile ?: "-")
            }
            item.status.runtimeModel?.let { MetricPill("Model", it) }
            item.status.commandName?.let { MetricPill("Slash", "/$it") }
            if (item.status.mcpServers.isNotEmpty()) {
                MetricPill("MCP", item.status.mcpServers.joinToString(", "))
            }
            Text(item.status.currentTask ?: "No current task", style = MaterialTheme.typography.bodySmall)
            item.status.recentLogs.lastOrNull()?.message?.let { snippet ->
                Text(snippet, style = MaterialTheme.typography.bodySmall)
            }
            item.status.warningMessage?.let {
                Text(it, color = if (item.status.stuckIndicator) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
            }
            TextButton(onClick = onOpen) { Text("Open Agent") }
        }
    }
}

@Composable
private fun DashboardActivityCard(activity: DashboardActivityItem, onMachineClick: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(activity.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    Text(activity.machineName, style = MaterialTheme.typography.bodySmall)
                }
                StateBadge(activity.status)
            }
            Text(activity.detail, style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                MetricPill("Type", activity.category)
                Text(activity.timestamp, style = MaterialTheme.typography.bodySmall)
            }
            TextButton(onClick = onMachineClick) { Text("Open Machine") }
        }
    }
}

@Composable
private fun SectionHeader(title: String, action: String, onAction: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        TextButton(onClick = onAction) { Text(action) }
    }
}

@Composable
private fun AgentCard(agent: AgentRecord, onClick: () -> Unit, onStop: () -> Unit, onRestart: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable { onClick() }) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("${agent.type.uppercase()} Agent", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(agent.id, style = MaterialTheme.typography.bodySmall)
                }
                StateBadge(agent.state)
            }
            Text("Current task: ${agent.currentTask ?: "-"}")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MetricPill("Worker", agent.workerId ?: "-")
                MetricPill("PID", agent.pid?.toString() ?: "-")
                MetricPill("Job", agent.currentJobId ?: "-")
            }
            if (agent.launchProfile != null || agent.workspace != null) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MetricPill("Profile", agent.launchProfile ?: "-")
                    MetricPill("Workspace", agent.workspace ?: "-")
                }
            }
            agent.runtimeSummary?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            if (agent.mcpServers.isNotEmpty()) {
                MetricPill("MCP", agent.mcpServers.joinToString(", "))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onClick) { Text("Open") }
                TextButton(onClick = onRestart) { Text("Restart") }
                TextButton(onClick = onStop) { Text("Stop") }
            }
        }
    }
}

@Composable
private fun SessionCard(agent: AgentRecord, onOpen: () -> Unit, onRelaunch: () -> Unit, onRelaunchBest: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Recent ${agent.type.uppercase()} Session", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(agent.id, style = MaterialTheme.typography.bodySmall)
                }
                StateBadge(agent.state)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MetricPill("Profile", agent.launchProfile ?: "-")
                MetricPill("Workspace", agent.workspace ?: "-")
            }
            agent.runtimeSummary?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            Text(agent.promptTemplate ?: "No saved prompt template", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onOpen) { Text("Open") }
                TextButton(onClick = onRelaunch) { Text("Relaunch Here") }
                TextButton(onClick = onRelaunchBest) { Text("Best Available") }
            }
        }
    }
}

@Composable
private fun TaskCard(task: JobRecord) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                StateBadge(task.state)
                Text(task.kind.uppercase(), fontWeight = FontWeight.SemiBold)
            }
            Text(task.inputText)
            Text("Task ID: ${task.id}", style = MaterialTheme.typography.bodySmall)
            Text(task.summary ?: task.error ?: "No summary yet", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun AuditCard(entry: AuditEntry) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                StateBadge(entry.status)
                Text(entry.action, fontWeight = FontWeight.SemiBold)
            }
            Text(entry.message)
            Text("${entry.targetType}: ${entry.targetId}", style = MaterialTheme.typography.bodySmall)
            Text(entry.timestamp, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun MetricBlock(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall)
        Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun MetricPill(label: String, value: String) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = MaterialTheme.shapes.small
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(label, style = MaterialTheme.typography.bodySmall)
            Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun StateBadge(state: String) {
    val background = when (state.lowercase()) {
        "online", "live", "idle", "completed", "healthy" -> Color(0xFFDDEED5)
        "running", "starting", "connecting…", "connecting" -> Color(0xFFFFE8BF)
        "warning", "stopping", "reconnecting…" -> Color(0xFFFFD9B8)
        "stuck" -> Color(0xFFFFCBA6)
        "selected" -> Color(0xFFD8E5F7)
        "offline", "failed", "stopped", "rejected", "error" -> Color(0xFFF6D4D7)
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    Box(
        modifier = Modifier.background(background, shape = MaterialTheme.shapes.small).padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Text(state.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    }
}

private fun statusHeadline(state: String, currentJob: JobRecord?): String = when {
    currentJob?.state.equals("running", ignoreCase = true) -> "Running ${currentJob?.kind ?: "job"}"
    state.equals("pending", ignoreCase = true) -> "Queued and waiting for worker capacity"
    state.equals("starting", ignoreCase = true) -> "Launching local process"
    state.equals("idle", ignoreCase = true) -> "Ready for the next task"
    state.equals("failed", ignoreCase = true) -> "Needs operator attention"
    state.equals("stopped", ignoreCase = true) -> "Stopped"
    else -> state.replaceFirstChar { it.uppercase() }
}

@Composable
private fun resultContainer(state: String): Color = when (state.lowercase()) {
    "completed" -> Color(0xFFDDEED5)
    "failed", "cancelled" -> Color(0xFFF6D4D7)
    else -> MaterialTheme.colorScheme.surfaceVariant
}

private fun stateRank(state: String): Int = when (state.lowercase()) {
    "running" -> 0
    "starting" -> 1
    "idle" -> 2
    "pending" -> 3
    "stopping" -> 4
    "stopped" -> 5
    "failed" -> 6
    else -> 7
}

private fun formatDuration(totalSeconds: Int): String {
    val hours = totalSeconds / 3600
    val minutes = (totalSeconds % 3600) / 60
    val seconds = totalSeconds % 60
    return when {
        hours > 0 -> "${hours}h ${minutes}m"
        minutes > 0 -> "${minutes}m ${seconds}s"
        else -> "${seconds}s"
    }
}

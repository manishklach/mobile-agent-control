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
import com.example.agentcontrol.data.model.AuditEntry
import com.example.agentcontrol.data.model.JobRecord
import com.example.agentcontrol.data.model.LaunchProfileRecord
import com.example.agentcontrol.data.model.MachineOverview
import com.example.agentcontrol.data.model.MachineSelfResponse
import com.example.agentcontrol.data.model.SupervisorEvent
import com.example.agentcontrol.ui.components.EmptyState
import com.example.agentcontrol.ui.components.ErrorState
import com.example.agentcontrol.ui.components.LoadingState
import com.example.agentcontrol.ui.viewmodel.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MachinesScreen(
    state: UiState<List<MachineOverview>>,
    actionMessage: String?,
    actionError: String?,
    onMachineClick: (String) -> Unit,
    onSettingsClick: () -> Unit,
    onRefreshClick: () -> Unit,
    onQuickDispatch: (String, String?) -> Unit
) {
    var dispatchType by rememberSaveable { mutableStateOf("codex") }
    var dispatchTask by rememberSaveable { mutableStateOf("") }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Machines") },
                actions = {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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
    actionError: String?,
    actionMessage: String?,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
    onLaunch: (String, String, String, String?) -> Unit
) {
    var agentType by rememberSaveable { mutableStateOf("codex") }
    var selectedProfileId by rememberSaveable { mutableStateOf("") }
    var workspace by rememberSaveable { mutableStateOf("C:\\Users\\ManishKL\\Documents\\Playground") }
    var initialPrompt by rememberSaveable { mutableStateOf("") }

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
                    }
                }
            }
            item {
                Card {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Agent Type", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            listOf("codex", "gemini").forEach { type ->
                                FilterChip(
                                    selected = agentType == type,
                                    onClick = {
                                        agentType = type
                                        selectedProfileId = ""
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
                        Text("Launch Options", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        OutlinedTextField(
                            value = workspace,
                            onValueChange = { workspace = it },
                            label = { Text("Workspace / repo path") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        OutlinedTextField(
                            value = initialPrompt,
                            onValueChange = { initialPrompt = it },
                            label = { Text("Initial prompt (optional)") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Button(
                            onClick = { onLaunch(agentType, selectedProfileId, workspace, initialPrompt.ifBlank { null }) },
                            enabled = selectedProfileId.isNotBlank() && workspace.isNotBlank()
                        ) {
                            Text("Launch Agent")
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
fun AgentDetailScreen(
    state: UiState<AgentDetailResponse>,
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
                                    StateBadge(agent.state)
                                }
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    MetricPill("Worker", agent.workerId ?: "-")
                                    MetricPill("Stream", streamStatus)
                                    MetricPill("PID", agent.pid?.toString() ?: "-")
                                    MetricPill("Job", agent.currentJobId ?: "-")
                                }
                                Text("Current task: ${agent.currentTask ?: "-"}")
                                Text("Workspace: ${agent.workspace ?: "-"}")
                                Text("Launch profile: ${agent.launchProfile ?: "-"}")
                                Text("Started: ${agent.startedAt ?: "-"}")
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
                    item { Text("Recent Logs", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
                    if (agent.recentLogs.isEmpty()) {
                        item { EmptyState("No logs yet.") }
                    } else {
                        items(agent.recentLogs.takeLast(20).reversed()) { log ->
                            Card(modifier = Modifier.fillMaxWidth()) {
                                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text("${log.stream} • ${log.timestamp}", style = MaterialTheme.typography.bodySmall)
                                    Text(log.message)
                                }
                            }
                        }
                    }
                    item { Text("Live Events", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
                    if (liveEvents.isEmpty()) {
                        item { EmptyState("No live events yet.") }
                    } else {
                        items(liveEvents.take(20)) { event ->
                            Card(modifier = Modifier.fillMaxWidth()) {
                                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                        StateBadge(event.event)
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
                StateBadge(if (machine.isOnline) "online" else "offline")
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MetricPill("Running", (machine.health?.agentsRunning ?: 0).toString())
                MetricPill("Queued", (machine.health?.queuedJobs ?: 0).toString())
                MetricPill(
                    "Workers",
                    machine.machine?.workerPool?.let { "${it.busyWorkers}/${it.desiredWorkers}" } ?: "-"
                )
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
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onClick) { Text("Open") }
                TextButton(onClick = onRestart) { Text("Restart") }
                TextButton(onClick = onStop) { Text("Stop") }
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
        "online", "live", "idle", "completed" -> Color(0xFFDDEED5)
        "running", "starting", "connecting…", "connecting" -> Color(0xFFFFE8BF)
        "stopping", "reconnecting…" -> Color(0xFFFFD9B8)
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

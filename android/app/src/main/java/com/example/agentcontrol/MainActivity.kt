package com.example.agentcontrol

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.agentcontrol.data.local.MachineStore
import com.example.agentcontrol.data.repository.MachineRepository
import com.example.agentcontrol.ui.navigation.Route
import com.example.agentcontrol.ui.screens.AgentDetailScreen
import com.example.agentcontrol.ui.screens.DashboardScreen
import com.example.agentcontrol.ui.screens.LaunchAgentScreen
import com.example.agentcontrol.ui.screens.MachineActivityScreen
import com.example.agentcontrol.ui.screens.MachineDetailScreen
import com.example.agentcontrol.ui.screens.MachinesScreen
import com.example.agentcontrol.ui.screens.RunningAgentsScreen
import com.example.agentcontrol.ui.screens.SettingsScreen
import com.example.agentcontrol.ui.theme.AgentControlTheme
import com.example.agentcontrol.ui.viewmodel.AppViewModel

class MainActivity : ComponentActivity() {
    private var lastNotifiedEventKey: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        ensureNotificationChannel()

        val repository = MachineRepository(MachineStore(applicationContext))

        setContent {
            AgentControlTheme {
                val navController = rememberNavController()
                val viewModel: AppViewModel = viewModel(factory = AppViewModel.Factory(repository))
                val uiState by viewModel.uiState.collectAsStateWithLifecycle()

                LaunchedEffect(uiState.liveEvents.firstOrNull()?.timestamp, uiState.liveEvents.firstOrNull()?.event) {
                    uiState.liveEvents.firstOrNull()?.let { event ->
                        val key = "${event.timestamp}-${event.event}-${event.job?.id ?: event.agent?.id ?: ""}"
                        if (key != lastNotifiedEventKey && (event.event == "job.completed" || event.event == "job.failed")) {
                            lastNotifiedEventKey = key
                            notifyOperator(event.event, event.message ?: event.job?.inputText ?: "Supervisor event")
                        }
                    }
                }

                NavHost(navController = navController, startDestination = Route.Dashboard.value) {
                    composable(Route.Dashboard.value) {
                        LaunchedEffect(navController.currentBackStackEntry?.destination?.route) {
                            viewModel.loadMachines()
                            viewModel.loadRunningAgents()
                            viewModel.loadDashboardActivity()
                        }
                        DashboardScreen(
                            machinesState = uiState.machines,
                            runningAgentsState = uiState.runningAgents,
                            activityState = uiState.dashboardActivity,
                            actionMessage = uiState.actionMessage,
                            actionError = uiState.actionError,
                            onMachinesClick = { navController.navigate(Route.Machines.value) },
                            onRunningAgentsClick = { navController.navigate(Route.RunningAgents.value) },
                            onSettingsClick = { navController.navigate(Route.Settings.value) },
                            onRefresh = {
                                viewModel.loadMachines()
                                viewModel.loadRunningAgents()
                                viewModel.loadDashboardActivity()
                            },
                            onMachineClick = { machineId ->
                                viewModel.selectMachine(machineId)
                                navController.navigate("machine/$machineId")
                            },
                            onOpenAgent = { machineId, agentId ->
                                viewModel.selectMachine(machineId)
                                navController.navigate("machine/$machineId/agent/$agentId")
                            },
                            onQuickDispatch = { type, task -> viewModel.startAgentOnBestMachine(type, task) }
                        )
                    }
                    composable(Route.Machines.value) {
                        LaunchedEffect(navController.currentBackStackEntry?.destination?.route) {
                            viewModel.loadMachines()
                            viewModel.loadRunningAgents()
                            viewModel.loadDashboardActivity()
                        }
                        MachinesScreen(
                            state = uiState.machines,
                            actionMessage = uiState.actionMessage,
                            actionError = uiState.actionError,
                            onMachineClick = { machineId ->
                                viewModel.selectMachine(machineId)
                                navController.navigate("machine/$machineId")
                            },
                            onRunningAgentsClick = { navController.navigate(Route.RunningAgents.value) },
                            onSettingsClick = { navController.navigate(Route.Settings.value) },
                            onRefreshClick = { viewModel.loadMachines() },
                            onQuickDispatch = { type, task -> viewModel.startAgentOnBestMachine(type, task) }
                        )
                    }
                    composable(Route.RunningAgents.value) {
                        LaunchedEffect(Unit) {
                            viewModel.loadRunningAgents()
                        }
                        RunningAgentsScreen(
                            state = uiState.runningAgents,
                            onBack = { navController.popBackStack() },
                            onRefresh = { viewModel.loadRunningAgents() },
                            onOpenAgent = { machineId, agentId ->
                                viewModel.selectMachine(machineId)
                                navController.navigate("machine/$machineId/agent/$agentId")
                            }
                        )
                    }
                    composable(
                        route = Route.MachineDetail.value,
                        arguments = listOf(navArgument("machineId") { type = NavType.StringType })
                    ) { entry ->
                        val machineId = entry.arguments?.getString("machineId") ?: return@composable
                        LaunchedEffect(machineId) {
                            viewModel.selectMachine(machineId)
                            viewModel.loadMachineDetail(machineId)
                            viewModel.loadAgents(machineId)
                            viewModel.loadTasks(machineId)
                            viewModel.loadAudit(machineId)
                            viewModel.observeMachine(machineId)
                        }
                        MachineDetailScreen(
                            machineState = uiState.machineDetail,
                            agentsState = uiState.agents,
                            actionError = uiState.actionError,
                            actionMessage = uiState.actionMessage,
                            streamStatus = uiState.streamStatus,
                            onBack = { navController.popBackStack() },
                            onOpenAgent = { agentId -> navController.navigate("machine/$machineId/agent/$agentId") },
                            onOpenActivity = { navController.navigate("machine/$machineId/activity") },
                            onLaunchAgent = { navController.navigate("machine/$machineId/launch") },
                            onStopAgent = { agentId -> viewModel.stopAgent(machineId, agentId) },
                            onRestartAgent = { agentId -> viewModel.restartAgent(machineId, agentId, "Restarted from machine dashboard") },
                            onRelaunch = { type, launchProfile, workspace, initialPrompt ->
                                viewModel.launchAgent(machineId, type, launchProfile, workspace, initialPrompt)
                            },
                            onRelaunchBest = { type, launchProfile, workspace, initialPrompt ->
                                viewModel.launchAgentOnBestMachine(type, launchProfile, workspace, initialPrompt)
                            },
                            onRefresh = {
                                viewModel.loadMachineDetail(machineId)
                                viewModel.loadAgents(machineId)
                                viewModel.loadTasks(machineId)
                                viewModel.loadAudit(machineId)
                                viewModel.loadRunningAgents()
                            }
                        )
                    }
                    composable(
                        route = Route.LaunchAgent.value,
                        arguments = listOf(navArgument("machineId") { type = NavType.StringType })
                    ) { entry ->
                        val machineId = entry.arguments?.getString("machineId") ?: return@composable
                        LaunchedEffect(machineId) {
                            viewModel.selectMachine(machineId)
                            viewModel.loadMachineDetail(machineId)
                            viewModel.loadLaunchProfiles(machineId)
                            viewModel.loadWorkspaces(machineId)
                            viewModel.loadLaunchSupport(machineId, "gemini-cli", null)
                        }
                        LaunchedEffect(uiState.launchedAgentId) {
                            val launchedAgentId = uiState.launchedAgentId
                            val launchedMachineId = uiState.launchedAgentMachineId ?: machineId
                            if (!launchedAgentId.isNullOrBlank()) {
                                navController.navigate("machine/$launchedMachineId/agent/$launchedAgentId") {
                                    popUpTo("machine/$machineId/launch") { inclusive = true }
                                }
                                viewModel.clearLaunchNavigation()
                            }
                        }
                        val machineName = when (val detail = uiState.machineDetail) {
                            is com.example.agentcontrol.ui.viewmodel.UiState.Success -> detail.data.machine.name
                            else -> machineId
                        }
                        LaunchAgentScreen(
                            machineName = machineName,
                            profilesState = uiState.launchProfiles,
                            launchSupportState = uiState.launchSupport,
                            workspacesState = uiState.workspaces,
                            lastWorkspace = uiState.lastWorkspace,
                            actionError = uiState.actionError,
                            actionMessage = uiState.actionMessage,
                            onBack = { navController.popBackStack() },
                            onRefresh = {
                                viewModel.loadMachineDetail(machineId)
                                viewModel.loadLaunchProfiles(machineId)
                                viewModel.loadWorkspaces(machineId)
                                viewModel.loadLaunchSupport(machineId, "gemini-cli", uiState.lastWorkspace)
                            },
                            onLaunchSupportRefresh = { adapterId, workspace ->
                                viewModel.loadLaunchSupport(machineId, adapterId, workspace)
                            },
                            onLaunch = { type, launchProfile, workspace, initialPrompt, runtimeModel, commandName ->
                                viewModel.launchAgent(machineId, type, launchProfile, workspace, initialPrompt, runtimeModel, commandName)
                            },
                            onLaunchBestAvailable = { type, launchProfile, workspace, initialPrompt, runtimeModel, commandName ->
                                viewModel.launchAgentOnBestMachine(type, launchProfile, workspace, initialPrompt, runtimeModel, commandName)
                            }
                        )
                    }
                    composable(
                        route = Route.MachineActivity.value,
                        arguments = listOf(navArgument("machineId") { type = NavType.StringType })
                    ) { entry ->
                        val machineId = entry.arguments?.getString("machineId") ?: return@composable
                        LaunchedEffect(machineId) {
                            viewModel.loadTasks(machineId)
                            viewModel.loadAudit(machineId)
                            viewModel.observeMachine(machineId)
                        }
                        MachineActivityScreen(
                            tasksState = uiState.tasks,
                            auditState = uiState.audit,
                            onBack = { navController.popBackStack() },
                            onRefresh = {
                                viewModel.loadTasks(machineId)
                                viewModel.loadAudit(machineId)
                            }
                        )
                    }
                    composable(
                        route = Route.AgentDetail.value,
                        arguments = listOf(
                            navArgument("machineId") { type = NavType.StringType },
                            navArgument("agentId") { type = NavType.StringType }
                        )
                    ) { entry ->
                        val machineId = entry.arguments?.getString("machineId") ?: return@composable
                        val agentId = entry.arguments?.getString("agentId") ?: return@composable
                        LaunchedEffect(machineId, agentId) {
                            viewModel.loadAgent(machineId, agentId)
                            viewModel.observeMachine(machineId)
                        }
                        AgentDetailScreen(
                            state = uiState.selectedAgent,
                            metricsState = uiState.selectedAgentMetrics,
                            eventsState = uiState.selectedAgentEvents,
                            liveEvents = uiState.liveEvents.filter { event ->
                                event.agent?.id == agentId || event.job?.agentId == agentId
                            },
                            actionError = uiState.actionError,
                            actionMessage = uiState.actionMessage,
                            streamStatus = uiState.streamStatus,
                            onBack = { navController.popBackStack() },
                            onRefresh = { viewModel.loadAgent(machineId, agentId) },
                            onStop = { viewModel.stopAgent(machineId, agentId) },
                            onRestart = { reason -> viewModel.restartAgent(machineId, agentId, reason) },
                            onPrompt = { prompt -> viewModel.sendPrompt(machineId, agentId, prompt) }
                        )
                    }
                    composable(Route.Settings.value) {
                        SettingsScreen(
                            onBack = { navController.popBackStack() },
                            onSave = { name, baseUrl, token ->
                                viewModel.addMachine(name, baseUrl, token)
                                navController.popBackStack()
                            }
                        )
                    }
                }
            }
        }
    }

    private fun ensureNotificationChannel() {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel("operator-events", "Operator Events", NotificationManager.IMPORTANCE_DEFAULT)
        manager.createNotificationChannel(channel)
    }

    private fun notifyOperator(title: String, body: String) {
        val notification = NotificationCompat.Builder(this, "operator-events")
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()
        NotificationManagerCompat.from(this).notify(title.hashCode(), notification)
    }
}

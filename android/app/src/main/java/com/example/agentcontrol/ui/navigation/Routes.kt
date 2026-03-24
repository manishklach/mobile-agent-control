package com.example.agentcontrol.ui.navigation

sealed class Route(val value: String) {
    data object Machines : Route("machines")
    data object MachineDetail : Route("machine/{machineId}")
    data object LaunchAgent : Route("machine/{machineId}/launch")
    data object MachineActivity : Route("machine/{machineId}/activity")
    data object AgentDetail : Route("machine/{machineId}/agent/{agentId}")
    data object Settings : Route("settings")
}

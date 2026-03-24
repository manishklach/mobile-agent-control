package com.example.agentcontrol.data.local

import android.content.Context
import com.example.agentcontrol.data.model.MachineConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import java.util.UUID

class MachineStore(context: Context) {
    private val prefs = context.getSharedPreferences("agent_control_store", Context.MODE_PRIVATE)
    private val json = Json { ignoreUnknownKeys = true }
    private val serializer = ListSerializer(MachineConfig.serializer())

    private val _machines = MutableStateFlow(loadMachines())
    val machines: StateFlow<List<MachineConfig>> = _machines

    fun addMachine(name: String, baseUrl: String, token: String) {
        val normalizedName = name.trim()
        val existing = _machines.value.firstOrNull { it.name.equals(normalizedName, ignoreCase = true) }
        val updatedMachine = MachineConfig(
            id = existing?.id ?: UUID.randomUUID().toString(),
            name = normalizedName,
            baseUrl = baseUrl.trimEnd('/'),
            token = token.trim()
        )
        val updated = _machines.value
            .filterNot { it.name.equals(normalizedName, ignoreCase = true) }
            .plus(updatedMachine)
        _machines.value = updated
        saveMachines(updated)
    }

    fun getMachine(id: String): MachineConfig? = _machines.value.firstOrNull { it.id == id }

    private fun loadMachines(): List<MachineConfig> {
        val raw = prefs.getString("machines", null) ?: return emptyList()
        return runCatching { json.decodeFromString(serializer, raw) }.getOrDefault(emptyList())
    }

    private fun saveMachines(machines: List<MachineConfig>) {
        prefs.edit().putString("machines", json.encodeToString(serializer, machines)).apply()
    }
}

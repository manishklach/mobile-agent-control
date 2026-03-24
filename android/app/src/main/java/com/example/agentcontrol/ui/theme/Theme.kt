package com.example.agentcontrol.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val appColors = darkColorScheme()

@Composable
fun AgentControlTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = appColors, content = content)
}

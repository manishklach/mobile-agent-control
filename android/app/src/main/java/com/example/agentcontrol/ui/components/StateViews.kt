package com.example.agentcontrol.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun LoadingState(label: String) {
    Card(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            CircularProgressIndicator()
            Text(text = label)
        }
    }
}

@Composable
fun ErrorState(message: String, onRetry: (() -> Unit)? = null) {
    Card(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(text = "Error", color = MaterialTheme.colorScheme.error)
            Text(text = message, color = MaterialTheme.colorScheme.error)
            onRetry?.let { Button(onClick = it) { Text("Retry") } }
        }
    }
}

@Composable
fun EmptyState(message: String) {
    Card(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Text(text = message, modifier = Modifier.fillMaxWidth().padding(24.dp))
    }
}

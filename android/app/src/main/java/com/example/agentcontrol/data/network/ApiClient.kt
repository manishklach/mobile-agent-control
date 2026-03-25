package com.example.agentcontrol.data.network

import com.example.agentcontrol.data.model.AgentDetailResponse
import com.example.agentcontrol.data.model.AgentEventsResponse
import com.example.agentcontrol.data.model.AgentListResponse
import com.example.agentcontrol.data.model.AgentMetricsResponse
import com.example.agentcontrol.data.model.AuditLogResponse
import com.example.agentcontrol.data.model.HealthResponse
import com.example.agentcontrol.data.model.LaunchAgentRequest
import com.example.agentcontrol.data.model.LaunchProfilesResponse
import com.example.agentcontrol.data.model.LogsResponse
import com.example.agentcontrol.data.model.McpServersResponse
import com.example.agentcontrol.data.model.MachineHealthStatus
import com.example.agentcontrol.data.model.MachineListResponse
import com.example.agentcontrol.data.model.MachineSelfResponse
import com.example.agentcontrol.data.model.PromptAgentRequest
import com.example.agentcontrol.data.model.RestartAgentRequest
import com.example.agentcontrol.data.model.RuntimeAdapterStatusResponse
import com.example.agentcontrol.data.model.RuntimeAdaptersResponse
import com.example.agentcontrol.data.model.RunningAgentsResponse
import com.example.agentcontrol.data.model.SlashCommandsResponse
import com.example.agentcontrol.data.model.StartAgentRequest
import com.example.agentcontrol.data.model.TaskDetailResponse
import com.example.agentcontrol.data.model.TaskListResponse
import com.example.agentcontrol.data.model.WorkspacesResponse
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory

interface MachineApi {
    @GET("health")
    suspend fun health(): HealthResponse

    @GET("machines/self")
    suspend fun machineSelf(): MachineSelfResponse

    @GET("machines")
    suspend fun machines(): MachineListResponse

    @GET("machines/{id}/health")
    suspend fun machineHealth(@Path("id") id: String): MachineHealthStatus

    @GET("agents")
    suspend fun listAgents(): AgentListResponse

    @GET("agents/running")
    suspend fun runningAgents(): RunningAgentsResponse

    @GET("agents/{id}")
    suspend fun getAgent(@Path("id") id: String): AgentDetailResponse

    @POST("agents/start")
    suspend fun startAgent(@Body request: StartAgentRequest): AgentDetailResponse

    @GET("launch-profiles")
    suspend fun launchProfiles(): LaunchProfilesResponse

    @GET("runtime/adapters")
    suspend fun runtimeAdapters(@Query("workspace") workspace: String? = null): RuntimeAdaptersResponse

    @GET("runtime/adapters/{adapterId}")
    suspend fun runtimeAdapter(
        @Path("adapterId") adapterId: String,
        @Query("workspace") workspace: String? = null
    ): RuntimeAdapterStatusResponse

    @GET("runtime/adapters/{adapterId}/commands")
    suspend fun slashCommands(
        @Path("adapterId") adapterId: String,
        @Query("workspace") workspace: String? = null
    ): SlashCommandsResponse

    @GET("workspaces")
    suspend fun workspaces(): WorkspacesResponse

    @GET("machines/{id}/mcp")
    suspend fun machineMcp(
        @Path("id") id: String,
        @Query("workspace") workspace: String? = null
    ): McpServersResponse

    @POST("agents/launch")
    suspend fun launchAgent(@Body request: LaunchAgentRequest): AgentDetailResponse

    @POST("agents/{id}/stop")
    suspend fun stopAgent(@Path("id") id: String): AgentDetailResponse

    @POST("agents/{id}/restart")
    suspend fun restartAgent(@Path("id") id: String, @Body request: RestartAgentRequest): AgentDetailResponse

    @POST("agents/{id}/prompt")
    suspend fun promptAgent(@Path("id") id: String, @Body request: PromptAgentRequest): AgentDetailResponse

    @GET("agents/{id}/logs")
    suspend fun logs(@Path("id") id: String, @Query("limit") limit: Int = 100): LogsResponse

    @GET("agents/{id}/events")
    suspend fun agentEvents(@Path("id") id: String, @Query("limit") limit: Int = 100): AgentEventsResponse

    @GET("agents/{id}/metrics")
    suspend fun agentMetrics(@Path("id") id: String): AgentMetricsResponse

    @GET("tasks")
    suspend fun listTasks(@Query("limit") limit: Int = 100): TaskListResponse

    @GET("tasks/{id}")
    suspend fun getTask(@Path("id") id: String): TaskDetailResponse

    @GET("audit")
    suspend fun audit(@Query("limit") limit: Int = 100): AuditLogResponse
}

private class AuthInterceptor(private val tokenProvider: () -> String) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
            .newBuilder()
            .header("Authorization", "Bearer ${tokenProvider()}")
            .build()
        return chain.proceed(request)
    }
}

object ApiClientFactory {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    fun create(baseUrl: String, tokenProvider: () -> String): Pair<MachineApi, OkHttpClient> {
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(tokenProvider))
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl("${baseUrl.trimEnd('/')}/")
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()

        return retrofit.create(MachineApi::class.java) to client
    }

    fun websocketRequest(baseUrl: String, token: String): Request {
        val wsBase = when {
            baseUrl.startsWith("https://") -> baseUrl.replaceFirst("https://", "wss://")
            baseUrl.startsWith("http://") -> baseUrl.replaceFirst("http://", "ws://")
            else -> baseUrl
        }.trimEnd('/')

        return Request.Builder()
            .url("$wsBase/ws?token=$token")
            .build()
    }
}

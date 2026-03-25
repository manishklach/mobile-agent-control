from __future__ import annotations

import json
import os
import subprocess
import threading
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.adapters.base import CliAgentRuntimeAdapter
from app.models import (
    AgentType,
    McpServerRecord,
    RuntimeAdapterStatus,
    RuntimeCapabilities,
    RuntimeFeatureStatus,
    SlashCommandRecord,
)


def _stream_pipe(pipe, sink: list[str], emit) -> None:
    try:
        for line in iter(pipe.readline, ""):
            text = line.rstrip()
            if text:
                sink.append(text)
                emit(text)
    finally:
        pipe.close()


class GeminiCliAdapter(CliAgentRuntimeAdapter):
    adapter_id = "gemini-cli"
    agent_type = AgentType.GEMINI
    label = "Gemini CLI"
    capabilities = RuntimeCapabilities(
        supports_initial_prompt=True,
        supports_prompt_submission=True,
        supports_background_process=True,
        supports_streaming_logs=True,
        requires_workspace=True,
        requires_local_auth=True,
        supports_resume=False,
        supports_command_templates=True,
        supports_mcp=True,
        supports_model_selection=True,
    )

    def __init__(self) -> None:
        self._cached_version: tuple[datetime, str | None] | None = None
        self._cached_status: dict[str, tuple[datetime, RuntimeAdapterStatus]] = {}

    def binary_candidates(self) -> tuple[str, ...]:
        return ("gemini.cmd", "gemini.exe", "gemini")

    def _binary_path(self) -> str | None:
        binary = self.find_binary(*self.binary_candidates())
        if binary:
            return binary
        npm_shim = Path.home() / "AppData" / "Roaming" / "npm" / "gemini.cmd"
        if npm_shim.exists():
            return str(npm_shim)
        return None

    def runtime_status(self, workspace: str | None = None) -> RuntimeAdapterStatus:
        cache_key = workspace or "__default__"
        cached = self._cached_status.get(cache_key)
        now = datetime.now(UTC)
        if cached and (now - cached[0]) < timedelta(seconds=20):
            return cached[1]
        binary_path = self._binary_path()
        installed = RuntimeFeatureStatus(
            available=binary_path is not None,
            message=None if binary_path else "Gemini CLI is not installed or not on PATH",
        )
        auth = self._auth_status()
        warnings: list[str] = []
        if binary_path and not auth.available:
            warnings.append(auth.message or "Gemini CLI auth is not configured")
        mcp_servers = self.list_mcp_servers(workspace)
        if mcp_servers and any(server.health != "healthy" for server in mcp_servers):
            warnings.append("One or more configured MCP servers need attention")
        status = RuntimeAdapterStatus(
            adapter_id=self.adapter_id,
            agent_type=self.agent_type,
            label=self.label,
            installed=installed,
            auth=auth,
            version=self._detect_version(binary_path) if binary_path else None,
            binary_path=binary_path,
            capabilities=self.capabilities,
            warnings=warnings,
        )
        self._cached_status[cache_key] = (now, status)
        return status

    def list_command_templates(self, workspace: str | None = None) -> list[SlashCommandRecord]:
        commands: list[SlashCommandRecord] = []
        seen: set[tuple[str, str]] = set()
        for scope, directory in self._command_directories(workspace):
            if not directory.exists():
                continue
            for path in sorted(directory.rglob("*.toml")):
                record = self._read_command_template(path, directory, scope)
                if record is None:
                    continue
                key = (record.scope, record.name)
                if key in seen:
                    continue
                seen.add(key)
                commands.append(record)
        return sorted(commands, key=lambda item: (item.scope, item.name.lower()))

    def upsert_command_template(
        self,
        *,
        name: str,
        prompt: str,
        description: str | None = None,
        scope: str = "project",
        workspace: str | None = None,
    ) -> SlashCommandRecord:
        target = self._command_target_path(name=name, scope=scope, workspace=workspace)
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = [f'prompt = {json.dumps(prompt)}']
        if description:
            lines.append(f'description = {json.dumps(description)}')
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        record = self._read_command_template(target, target.parent if target.parent.name == "commands" else self._commands_dir_for_scope(scope, workspace), scope)
        if record is None:
            raise ValueError("Failed to write Gemini slash command")
        return record

    def delete_command_template(self, *, name: str, scope: str = "project", workspace: str | None = None) -> None:
        target = self._command_target_path(name=name, scope=scope, workspace=workspace)
        if not target.exists():
            raise ValueError("Gemini slash command was not found")
        target.unlink()

    def list_mcp_servers(self, workspace: str | None = None) -> list[McpServerRecord]:
        records: list[McpServerRecord] = []
        for scope, settings_path in self._settings_paths(workspace):
            payload = self._load_settings_payload(settings_path)
            servers = payload.get("mcpServers")
            if not isinstance(servers, dict):
                continue
            for name, raw in servers.items():
                if not isinstance(raw, dict):
                    continue
                transport = self._mcp_transport(raw)
                command = raw.get("command")
                endpoint = raw.get("url") or raw.get("httpUrl") or raw.get("tcp")
                warning = None
                health = "healthy"
                if transport == "stdio" and not command:
                    health = "warning"
                    warning = "Missing command for stdio MCP server"
                elif transport != "stdio" and not endpoint:
                    health = "warning"
                    warning = "Missing endpoint for MCP server"
                elif transport == "stdio" and command and not self.find_binary(command):
                    health = "warning"
                    warning = f"Command '{command}' is not on PATH"
                records.append(
                    McpServerRecord(
                        name=str(name),
                        scope=scope,
                        transport=transport,
                        health=health,
                        enabled=bool(raw.get("enabled", True)),
                        command=str(command) if command else None,
                        endpoint=str(endpoint) if endpoint else None,
                        description=str(raw.get("description")) if raw.get("description") else None,
                        warning=warning,
                    )
                )
        return sorted(records, key=lambda item: (item.scope, item.name.lower()))

    def classify_runtime_error(self, message: str, exit_code: int | None = None) -> str:
        lowered = message.lower()
        if "429" in lowered or "too many requests" in lowered or "resource_exhausted" in lowered:
            return "Gemini CLI hit a rate limit or quota limit. Retry shortly or switch auth/billing configuration."
        if "api key not valid" in lowered or "invalid api key" in lowered:
            return "Gemini CLI API key is invalid on this machine"
        if "selected auth type" in lowered or "login" in lowered or "oauth" in lowered or "auth" in lowered:
            return "Gemini CLI local auth is missing or expired on this machine"
        if "must specify the gemini_api_key" in lowered:
            return "Gemini CLI needs local auth. Set GEMINI_API_KEY or run gemini locally once on the machine."
        if "model" in lowered and "not found" in lowered:
            return "The requested Gemini model is not available for this local CLI configuration"
        if exit_code is not None and exit_code != 0 and "exit code" not in lowered:
            return f"{message} (Gemini exit code {exit_code})"
        return super().classify_runtime_error(message, exit_code)

    def run_prompt(
        self,
        prompt: str,
        workspace: str,
        *,
        runtime_model: str | None = None,
        command_name: str | None = None,
    ) -> tuple[int, str]:
        gemini_binary = self._binary_path()
        if not gemini_binary:
            raise FileNotFoundError("Gemini CLI was not found on PATH")
        effective_prompt = prompt
        if command_name:
            effective_prompt = f"/{command_name} {prompt}".strip()
        command = [gemini_binary, "-p", effective_prompt, "--output-format", "json"]
        if runtime_model:
            command.extend(["-m", runtime_model])
        process = subprocess.Popen(
            command,
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self.environment_with(),
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_thread = threading.Thread(target=_stream_pipe, args=(process.stdout, stdout_lines, print), daemon=True)
        stderr_thread = threading.Thread(target=_stream_pipe, args=(process.stderr, stderr_lines, lambda text: print(text, file=os.sys.stderr)), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        exit_code = process.wait()
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
        combined_output = "\n".join([*stdout_lines, *stderr_lines]).strip()
        return exit_code, self.extract_summary(combined_output)

    def _auth_status(self) -> RuntimeFeatureStatus:
        if os.environ.get("GEMINI_API_KEY"):
            return RuntimeFeatureStatus(available=True, message="Using GEMINI_API_KEY from supervisor environment")
        gemini_home = self._gemini_home()
        settings_payload = self._load_settings_payload(gemini_home / "settings.json")
        selected_type = (
            settings_payload.get("security", {})
            .get("auth", {})
            .get("selectedType")
            if isinstance(settings_payload.get("security"), dict)
            else None
        )
        oauth_creds = gemini_home / "oauth_creds.json"
        if selected_type == "gemini-api-key":
            return RuntimeFeatureStatus(
                available=False,
                message="Gemini CLI is set to API-key auth but GEMINI_API_KEY is not present in the supervisor environment",
            )
        if oauth_creds.exists():
            return RuntimeFeatureStatus(available=True, message=f"Using local Gemini auth ({selected_type or 'oauth'})")
        return RuntimeFeatureStatus(
            available=False,
            message="Gemini local auth is missing. Run gemini locally once or set GEMINI_API_KEY before starting the supervisor",
        )

    def _detect_version(self, binary_path: str) -> str | None:
        now = datetime.now(UTC)
        if self._cached_version and (now - self._cached_version[0]) < timedelta(minutes=5):
            return self._cached_version[1]
        try:
            result = subprocess.run(
                [binary_path, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=self.environment_with(),
            )
        except Exception:
            return None
        version = (result.stdout or result.stderr).strip()
        resolved = version or None
        self._cached_version = (now, resolved)
        return resolved

    def _gemini_home(self) -> Path:
        return Path.home() / ".gemini"

    def _command_directories(self, workspace: str | None) -> list[tuple[str, Path]]:
        directories = [("user", self._gemini_home() / "commands")]
        if workspace:
            directories.append(("project", Path(workspace).resolve() / ".gemini" / "commands"))
        return directories

    def _commands_dir_for_scope(self, scope: str, workspace: str | None) -> Path:
        if scope == "user":
            return self._gemini_home() / "commands"
        if scope != "project":
            raise ValueError("Gemini slash command scope must be 'user' or 'project'")
        if not workspace:
            raise ValueError("Workspace is required for project-scoped Gemini slash commands")
        return Path(workspace).resolve() / ".gemini" / "commands"

    def _command_target_path(self, *, name: str, scope: str, workspace: str | None) -> Path:
        normalized = name.strip().replace("\\", "/").strip("/")
        if not normalized or any(part in {"..", ""} for part in normalized.split("/")):
            raise ValueError("Slash command name must be a safe relative path")
        path = self._commands_dir_for_scope(scope, workspace) / f"{normalized}.toml"
        return path.resolve()

    def _read_command_template(self, path: Path, base_dir: Path, scope: str) -> SlashCommandRecord | None:
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return None
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return None
        relative = path.relative_to(base_dir).with_suffix("")
        name = ":".join(relative.parts)
        description = payload.get("description")
        return SlashCommandRecord(
            name=name,
            description=description if isinstance(description, str) else None,
            scope=scope,
            path=str(path),
            source="gemini-cli",
            managed=scope in {"user", "project"},
            prompt_preview=prompt.strip()[:160],
        )

    def _settings_paths(self, workspace: str | None) -> list[tuple[str, Path]]:
        paths = [("user", self._gemini_home() / "settings.json")]
        if workspace:
            paths.append(("project", Path(workspace).resolve() / ".gemini" / "settings.json"))
        return paths

    def _load_settings_payload(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _mcp_transport(raw: dict) -> str:
        if raw.get("type"):
            return str(raw["type"])
        if raw.get("command"):
            return "stdio"
        if raw.get("url") or raw.get("httpUrl"):
            return "http"
        if raw.get("tcp"):
            return "tcp"
        return "unknown"

    @staticmethod
    def extract_summary(output_text: str) -> str:
        if not output_text:
            return ""
        stripped = output_text.strip()
        json_lines = [line for line in stripped.splitlines() if line.strip().startswith("{") and line.strip().endswith("}")]
        for line in reversed(json_lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = payload.get("response")
            if isinstance(response, str) and response.strip():
                return response.strip()
        return stripped

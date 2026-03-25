from __future__ import annotations

import argparse
import json
import os
import sys

from app.adapters.registry import get_runtime_adapter

EVENT_PREFIX = "__SUPERVISOR_EVENT__"


def emit(message: str, *, stream=sys.stdout) -> None:
    print(message, file=stream, flush=True)


def emit_event(event: str, **payload: object) -> None:
    emit(EVENT_PREFIX + json.dumps({"event": event, **payload}))


def parse_command(line: str) -> tuple[str | None, str]:
    stripped = line.strip()
    if not stripped:
        return None, ""
    if stripped.lower() == "exit":
        return "exit", ""
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None, stripped
    command = str(payload.get("command", "prompt"))
    if command == "exit":
        return "exit", ""
    return str(payload.get("job_id") or ""), str(payload.get("prompt") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", required=True)
    args = parser.parse_args()

    adapter = get_runtime_adapter(args.adapter)
    workspace = os.getcwd()
    profile = os.getenv("AGENT_PROFILE", adapter.adapter_id)
    initial_prompt = os.getenv("AGENT_INITIAL_PROMPT") or ""
    runtime_model = os.getenv("AGENT_RUNTIME_MODEL") or None
    command_name = os.getenv("AGENT_COMMAND_NAME") or None
    emit(f"[{profile}] workspace={workspace}")
    emit(f"initial_prompt={initial_prompt if initial_prompt else '<none>'}")
    if runtime_model:
        emit(f"runtime_model={runtime_model}")
    if command_name:
        emit(f"command_name={command_name}")

    for line in sys.stdin:
        job_id, prompt = parse_command(line)
        if job_id == "exit":
            emit("shutting down")
            return 0
        if not prompt:
            continue
        emit_event("job.started", job_id=job_id or None)
        exit_code, summary = adapter.run_prompt(
            prompt,
            workspace,
            runtime_model=runtime_model,
            command_name=command_name,
        )
        if summary:
            emit(summary)
        if exit_code == 0:
            emit_event("job.completed", job_id=job_id or None, summary=summary)
        else:
            error = adapter.classify_runtime_error(summary or f"{adapter.adapter_id} exited with code {exit_code}", exit_code)
            emit_event("job.failed", job_id=job_id or None, summary=summary, error=error)

    emit("stdin closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

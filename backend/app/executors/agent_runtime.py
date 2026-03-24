from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

EVENT_PREFIX = "__SUPERVISOR_EVENT__"


def emit(message: str, *, stream=sys.stdout) -> None:
    print(message, file=stream, flush=True)


def emit_event(event: str, **payload: object) -> None:
    emit(EVENT_PREFIX + json.dumps({"event": event, **payload}))


def stream_pipe(pipe, prefix: str, *, stream) -> None:
    try:
        for line in iter(pipe.readline, ""):
            text = line.rstrip()
            if text:
                emit(f"{prefix}{text}", stream=stream)
    finally:
        pipe.close()


def run_codex(prompt: str, workspace: str) -> tuple[int, str]:
    output_file = Path(tempfile.mkstemp(prefix="codex-output-", suffix=".txt")[1])
    env = os.environ.copy()
    env.pop("CODEX_THREAD_ID", None)
    env["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] = "Agent Control Supervisor"
    codex_binary = shutil.which("codex.cmd") or shutil.which("codex.exe") or shutil.which("codex")
    if not codex_binary:
        raise FileNotFoundError("codex CLI was not found on PATH")
    command = [
        codex_binary,
        "exec",
        "--skip-git-repo-check",
        "-C",
        workspace,
        "-o",
        str(output_file),
        prompt,
    ]
    process = subprocess.Popen(
        command,
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    stdout_thread = threading.Thread(target=stream_pipe, args=(process.stdout, "",), kwargs={"stream": sys.stdout}, daemon=True)
    stderr_thread = threading.Thread(target=stream_pipe, args=(process.stderr, "",), kwargs={"stream": sys.stderr}, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    exit_code = process.wait()
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    summary = output_file.read_text(encoding="utf-8").strip() if output_file.exists() else ""
    try:
        output_file.unlink(missing_ok=True)
    except PermissionError:
        pass
    return exit_code, summary


def run_gemini(prompt: str, workspace: str) -> tuple[int, str]:
    gemini_binary = shutil.which("gemini.cmd") or shutil.which("gemini.exe") or shutil.which("gemini")
    if not gemini_binary:
        raise FileNotFoundError("gemini CLI was not found on PATH")
    command = [
        gemini_binary,
        "-p",
        prompt,
        "--output-format",
        "json",
    ]
    process = subprocess.Popen(
        command,
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )
    stdout_lines: list[str] = []

    def capture_stdout(pipe) -> None:
        try:
            for line in iter(pipe.readline, ""):
                text = line.rstrip()
                if text:
                    stdout_lines.append(text)
                    emit(text)
        finally:
            pipe.close()

    stdout_thread = threading.Thread(target=capture_stdout, args=(process.stdout,), daemon=True)
    stderr_thread = threading.Thread(target=stream_pipe, args=(process.stderr, "",), kwargs={"stream": sys.stderr}, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    exit_code = process.wait()
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    stdout_text = "\n".join(stdout_lines).strip()
    return exit_code, extract_gemini_summary(stdout_text)


def extract_gemini_summary(stdout_text: str) -> str:
    if not stdout_text:
        return ""
    stripped = stdout_text.strip()
    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        response = payload.get("response")
        if isinstance(response, str) and response.strip():
            return response.strip()
    return stripped


def run_prompt(runner: str, prompt: str, workspace: str) -> tuple[int, str]:
    if runner == "codex":
        return run_codex(prompt, workspace)
    if runner == "gemini":
        return run_gemini(prompt, workspace)
    raise ValueError(f"Unsupported runner: {runner}")


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
    parser.add_argument("--runner", required=True, choices=["codex", "gemini"])
    args = parser.parse_args()

    workspace = os.getcwd()
    profile = os.getenv("AGENT_PROFILE", args.runner)
    initial_prompt = os.getenv("AGENT_INITIAL_PROMPT") or ""
    emit(f"[{profile}] workspace={workspace}")
    emit(f"initial_prompt={initial_prompt if initial_prompt else '<none>'}")

    for line in sys.stdin:
        job_id, prompt = parse_command(line)
        if job_id == "exit":
            emit("shutting down")
            return 0
        if not prompt:
            continue
        emit_event("job.started", job_id=job_id or None)
        exit_code, summary = run_prompt(args.runner, prompt, workspace)
        if summary:
            emit(summary)
        if exit_code == 0:
            emit_event("job.completed", job_id=job_id or None, summary=summary)
        else:
            emit_event("job.failed", job_id=job_id or None, summary=summary, error=f"{args.runner} exited with code {exit_code}")

    emit("stdin closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

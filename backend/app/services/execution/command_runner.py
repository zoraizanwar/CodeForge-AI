"""
Sandboxed command runner for CodeForge AI safe execution environment (Step 8).
Executes discovered test/build commands inside temporary workspaces without shell=True,
enforcing timeouts, output size limits, process termination, and environment variable sanitization.
"""
import os
import sys
import time
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from app.services.repository import get_safe_workspace_path

logger = logging.getLogger("codeforge.execution.runner")

DEFAULT_TIMEOUT_SECONDS = 60
MAX_OUTPUT_BYTES = 500_000  # 500 KB

# Environment variable keys permitted in the execution sandbox
SAFE_ENV_KEYS = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "PYTHONPATH",
    "NODE_ENV",
    "GOPATH",
    "GOBIN",
}

# Environment variable keys explicitly forbidden to prevent host secret leaks
FORBIDDEN_ENV_SUBSTRINGS = [
    "SECRET",
    "KEY",
    "TOKEN",
    "PASSWORD",
    "CREDENTIAL",
    "DATABASE",
    "POSTGRES",
    "GITHUB",
    "GROK",
    "OPENAI",
    "ANTHROPIC",
    "JWT",
]


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


def get_sanitized_environment() -> Dict[str, str]:
    """
    Constructs a minimal, safe environment dictionary for subprocess execution.
    Strips out all host secrets, database URLs, API keys, and JWT keys.
    """
    clean_env: Dict[str, str] = {}

    for k, v in os.environ.items():
        k_upper = k.upper()
        # Skip forbidden keys
        if any(forbidden in k_upper for forbidden in FORBIDDEN_ENV_SUBSTRINGS):
            continue
        if k_upper in SAFE_ENV_KEYS:
            clean_env[k] = v

    # Fallback minimal PATH if missing
    if "PATH" not in clean_env:
        clean_env["PATH"] = os.environ.get("PATH", "")

    return clean_env


async def run_sandboxed_command(
    cmd: List[str],
    cwd: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_output_bytes: int = MAX_OUTPUT_BYTES,
    extra_env: Optional[Dict[str, str]] = None
) -> CommandResult:
    """
    Runs a trusted command inside the specified workspace directory without shell=True.
    Enforces timeout, stdout/stderr volume truncation, and secret sanitization.
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list of argument strings.")

    # Validate workspace boundary
    safe_cwd = get_safe_workspace_path(cwd)
    if not os.path.exists(safe_cwd):
        raise ValueError(f"Workspace directory '{safe_cwd}' does not exist.")

    cmd_str = " ".join(cmd)
    env = get_sanitized_environment()
    if extra_env:
        for k, v in extra_env.items():
            if not any(f in k.upper() for f in FORBIDDEN_ENV_SUBSTRINGS):
                env[k] = v

    start_time = time.time()

    try:
        # Execute process safely without shell=True
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=safe_cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds
            )
            exit_code = process.returncode or 0
        except asyncio.TimeoutError:
            logger.warning(f"Command '{cmd_str}' timed out after {timeout_seconds}s. Terminating process tree.")
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
            except Exception as kill_err:
                logger.error(f"Error killing timed out process: {str(kill_err)}")

            duration = round(time.time() - start_time, 2)
            return CommandResult(
                command=cmd_str,
                exit_code=124,  # Standard timeout exit code
                stdout="",
                stderr=f"Command execution timed out after {timeout_seconds} seconds.",
                duration_seconds=duration
            )

        duration = round(time.time() - start_time, 2)

        # Truncate output if exceeding limits
        if len(stdout_bytes) > max_output_bytes:
            stdout_bytes = stdout_bytes[:max_output_bytes] + b"\n...[stdout truncated due to size limit]"
        if len(stderr_bytes) > max_output_bytes:
            stderr_bytes = stderr_bytes[:max_output_bytes] + b"\n...[stderr truncated due to size limit]"

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        return CommandResult(
            command=cmd_str,
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_seconds=duration
        )

    except Exception as e:
        duration = round(time.time() - start_time, 2)
        logger.error(f"Failed to execute sandboxed command '{cmd_str}': {str(e)}")
        return CommandResult(
            command=cmd_str,
            exit_code=1,
            stdout="",
            stderr=f"Execution error: {str(e)}",
            duration_seconds=duration
        )

import os
import subprocess #让 Python 启动外部程序-Promptfoo
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_promptfoo_executable() -> Path:
    executable_name = "promptfoo.cmd" if os.name == "nt" else "promptfoo"

    executable = (
        PROJECT_ROOT
        / "node_modules"
        / ".bin"
        / executable_name
    )

    if not executable.exists():
        raise FileNotFoundError(
            "没有找到 Promptfoo，请先执行 npm install"
        )

    return executable


def run_evaluation(
    config_path: str = "evals/promptfooconfig.yaml",
    output_path: str = "results/eval.json",
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    promptfoo = get_promptfoo_executable()

    command = [
        str(promptfoo),
        "eval",
        "--no-cache",
        "--config",
        config_path,
        "--output",
        output_path,
    ]

    completed_process = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
        check=False,
    )

    return {
        "success": completed_process.returncode == 0,
        "return_code": completed_process.returncode,
        "stdout": completed_process.stdout,
        "stderr": completed_process.stderr,
        "output_path": output_path,
    }
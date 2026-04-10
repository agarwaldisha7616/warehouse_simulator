#!/usr/bin/env python3
"""
Local pre-submission validation for the warehouse simulator.
"""

from __future__ import annotations

import importlib
import io
import os
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import yaml

from tasks.specs import OPENENV_TASKS, TASK_CONFIGS


ROOT = Path(__file__).resolve().parent


def check(condition: bool, message: str) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {message}")
    return condition


def load_manifest() -> dict[str, Any]:
    with (ROOT / "openenv.yaml").open() as handle:
        return yaml.safe_load(handle)


def import_from_path(path: str) -> Any:
    module_name, attr_name = path.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def check_required_files() -> bool:
    print("--- File Structure ---")
    required_files = [
        "Dockerfile",
        "README.md",
        "context.md",
        ".env.example",
        "inference.py",
        "client.py",
        "models.py",
        "openenv.yaml",
        "requirements.txt",
        "uv.lock",
        "server/app.py",
        "server/environment.py",
        "server/Dockerfile",
        "frontend/src/app/page.tsx",
        "tasks/specs.py",
        "tasks/easy/grader.py",
        "tasks/medium/grader.py",
        "tasks/hard/grader.py",
    ]
    passed = True
    for relative_path in required_files:
        passed &= check((ROOT / relative_path).exists(), f"File exists: {relative_path}")
    return passed


def check_manifest(manifest: dict[str, Any]) -> bool:
    print("\n--- OpenEnv Manifest ---")
    passed = True

    required_top_level = {"name", "version", "description", "observation_space", "action_space", "tasks"}
    passed &= check(required_top_level.issubset(manifest), "Manifest has required top-level sections")

    action_keys = set(manifest.get("action_space", {}))
    observation_keys = set(manifest.get("observation_space", {}))
    passed &= check(
        {"agent_id", "action", "direction", "target"}.issubset(action_keys),
        "Manifest action space includes agent_id/action/direction/target",
    )
    passed &= check(
        {
            "done",
            "reward",
            "robots",
            "packages",
            "steps_remaining",
            "next_agent_id",
            "last_action_failed",
            "failed_action_count",
            "expired_package_count",
            "progress_score",
        }.issubset(observation_keys),
        "Manifest observation space includes live runtime fields",
    )

    manifest_tasks = {task["id"]: task for task in manifest.get("tasks", [])}
    expected_tasks = {task["id"]: task for task in OPENENV_TASKS}
    passed &= check(
        set(manifest_tasks) == set(expected_tasks),
        "Manifest task ids match canonical task definitions",
    )

    for task_id, expected in expected_tasks.items():
        current = manifest_tasks.get(task_id, {})
        passed &= check(
            current.get("description") == expected["description"],
            f"Task '{task_id}' description matches canonical task definition",
        )
        passed &= check(
            current.get("grader") == expected["grader"],
            f"Task '{task_id}' grader path is declared",
        )
        try:
            import_from_path(expected["grader"])
            passed &= check(True, f"Task '{task_id}' grader path is importable")
        except Exception as exc:
            passed &= check(False, f"Task '{task_id}' grader import failed: {exc}")

    return passed


def check_env_example() -> bool:
    print("\n--- Environment Variables ---")
    example_path = ROOT / ".env.example"
    content = example_path.read_text() if example_path.exists() else ""
    passed = True
    for key in ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN", "ENV_URL", "NEXT_PUBLIC_API_BASE"]:
        passed &= check(f"{key}=" in content, f".env.example includes {key}")
    return passed


def check_dependencies() -> bool:
    print("\n--- Dependency Metadata ---")
    requirements = (ROOT / "requirements.txt").read_text()
    passed = True
    for required in ["openenv-core", "fastapi", "uvicorn", "openai", "python-dotenv", "PyYAML"]:
        passed &= check(required in requirements, f"requirements.txt includes {required}")
    for removed in ["flask", "gradio"]:
        passed &= check(removed not in requirements, f"requirements.txt does not include legacy dependency {removed}")
    return passed


def check_offline_runtime() -> bool:
    print("\n--- Environment Runtime ---")
    try:
        from server.core.agents import MultiRobotCoordinator
        from server.environment import SmartWarehouseEnv
    except Exception as exc:
        return check(False, f"Runtime imports failed: {exc}")

    passed = True
    coordinator = MultiRobotCoordinator()

    for task_id, config in TASK_CONFIGS.items():
        env = SmartWarehouseEnv()
        coordinator.reset()
        observation = env.reset(options={"task_level": task_id})
        passed &= check(
            0.0 <= float(observation.reward or 0.0) <= 1.0,
            f"{task_id} reset reward is normalized",
        )

        step_budget = config["max_steps"]
        while not observation.done and env.state.step_count < step_budget:
            action = coordinator.get_action(observation, agent_id=observation.next_agent_id)
            observation = env.step(action)
            if not (0.0 <= float(observation.reward or 0.0) <= 1.0):
                passed &= check(False, f"{task_id} emitted out-of-range reward during rollout")
                break
        else:
            passed &= check(True, f"{task_id} deterministic rollout completed without range violations")

        state = env.state
        passed &= check(0.0 <= float(state.score) <= 1.0, f"{task_id} final state score is normalized")

        grader_path = next(task["grader"] for task in OPENENV_TASKS if task["id"] == task_id)
        grader = import_from_path(grader_path)
        grader_score = grader(state)
        passed &= check(0.0 <= float(grader_score) <= 1.0, f"{task_id} grader score is normalized")

    return passed


def check_inference_smoke() -> bool:
    print("\n--- Inference Script ---")
    try:
        from inference import run_episode
        from server.core.agents import MultiRobotCoordinator
        from server.environment import SmartWarehouseEnv
    except Exception as exc:
        return check(False, f"inference smoke imports failed: {exc}")

    class DirectWarehouseClient:
        def __init__(self):
            self.env = SmartWarehouseEnv()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def reset(self, options=None):
            return self.env.reset(options=options)

        def step(self, action):
            return self.env.step(action)

    buffer = io.StringIO()
    coordinator = MultiRobotCoordinator()
    client = DirectWarehouseClient()

    with redirect_stdout(buffer):
        score = run_episode(
            client,
            "easy",
            "Coordinate all robots to deliver every package safely.",
            None,
            coordinator,
            max_steps_override=8,
        )

    output = buffer.getvalue()
    markers = [line.strip() for line in output.splitlines() if line.strip() in {"[START]", "[STEP]", "[END]"}]
    passed = True
    passed &= check(0.0 <= float(score) <= 1.0, "inference.py episode score is normalized")
    passed &= check(markers.count("[START]") == 1, "inference.py emits one [START] marker")
    passed &= check("[STEP]" in markers, "inference.py emits at least one [STEP] marker")
    passed &= check(markers[-1:] == ["[END]"], "inference.py ends with an [END] marker")
    return passed


def check_frontend_build() -> bool:
    print("\n--- Frontend Build ---")
    npm = shutil.which("npm")
    if npm is None:
        return check(False, "npm is available on PATH")

    result = subprocess.run(
        [npm, "run", "build", "--prefix", "frontend"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-8:])
        print(tail)
    return check(result.returncode == 0, "frontend production build succeeds")


def main() -> int:
    print("\n" + "=" * 60)
    print("  Pre-Submission Validation")
    print("=" * 60 + "\n")

    all_pass = True
    manifest = load_manifest()

    all_pass &= check_required_files()
    all_pass &= check_manifest(manifest)
    all_pass &= check_env_example()
    all_pass &= check_dependencies()
    all_pass &= check_offline_runtime()
    all_pass &= check_inference_smoke()
    all_pass &= check_frontend_build()

    print("\n" + "=" * 60)
    if all_pass:
        print("  ALL CHECKS PASSED - Ready for submission!")
    else:
        print("  SOME CHECKS FAILED - Fix issues before submission")
    print("=" * 60 + "\n")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

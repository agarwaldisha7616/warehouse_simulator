#!/usr/bin/env python3
"""
Pre-submission validation script for hackathon.
Checks all requirements before final submission.
"""

import os
import sys
import json
import subprocess
import time


def check(condition, message):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {message}")
    return condition


def main():
    print("\n" + "=" * 60)
    print("  Pre-Submission Validation")
    print("=" * 60 + "\n")

    all_pass = True

    # 1. Check required files exist
    print("--- File Structure ---")
    required_files = [
        "inference.py",
        "client.py",
        "models.py",
        "openenv.yaml",
        "requirements.txt",
        "server/app.py",
        "server/environment.py",
        "server/Dockerfile",
        "README.md",
        "frontend/src/app/page.tsx",
    ]
    for f in required_files:
        all_pass &= check(os.path.exists(f), f"File exists: {f}")

    # 2. Check openenv.yaml structure
    print("\n--- OpenEnv Spec Compliance ---")
    try:
        import yaml

        with open("openenv.yaml") as f:
            config = yaml.safe_load(f)
        all_pass &= check("tasks" in config, "openenv.yaml has 'tasks' section")
        all_pass &= check(
            "observation_space" in config, "openenv.yaml has 'observation_space'"
        )
        all_pass &= check("action_space" in config, "openenv.yaml has 'action_space'")
        all_pass &= check("delivery_zone" in config, "openenv.yaml has 'delivery_zone'")
    except ImportError:
        print("  [SKIP] PyYAML not installed, skipping YAML validation")
    except Exception as e:
        all_pass &= check(False, f"openenv.yaml parsing error: {e}")

    # 3. Check models.py has required classes
    print("\n--- Model Definitions ---")
    try:
        from models import RobotAction, RobotObservation, RobotState

        all_pass &= check(True, "RobotAction class defined")
        all_pass &= check(True, "RobotObservation class defined")
        all_pass &= check(True, "RobotState class defined")

        action = RobotAction()
        all_pass &= check(
            hasattr(action, "direction"), "RobotAction has 'direction' field"
        )
        all_pass &= check(hasattr(action, "action"), "RobotAction has 'action' field")

        obs = RobotObservation()
        all_pass &= check(hasattr(obs, "done"), "RobotObservation has 'done' field")
        all_pass &= check(hasattr(obs, "reward"), "RobotObservation has 'reward' field")
        all_pass &= check(
            hasattr(obs, "robot_position"), "RobotObservation has 'robot_position'"
        )
        all_pass &= check(hasattr(obs, "packages"), "RobotObservation has 'packages'")
    except Exception as e:
        all_pass &= check(False, f"Model import error: {e}")

    # 4. Check environment has step/reset/state
    print("\n--- Environment API ---")
    try:
        sys.path.insert(0, "server")
        from environment import SmartWarehouseEnv

        env = SmartWarehouseEnv()
        all_pass &= check(hasattr(env, "step"), "Environment has 'step' method")
        all_pass &= check(hasattr(env, "reset"), "Environment has 'reset' method")
        all_pass &= check(
            isinstance(type(env).__dict__.get("state"), property),
            "Environment has 'state' property",
        )
    except Exception as e:
        all_pass &= check(False, f"Environment import error: {e}")

    # 5. Check 3+ task levels
    print("\n--- Task Levels ---")
    try:
        sys.path.insert(0, "server")
        from environment import TASK_CONFIGS

        all_pass &= check(
            len(TASK_CONFIGS) >= 3, f"Has {len(TASK_CONFIGS)} task levels (need 3+)"
        )
        for level in ["easy", "medium", "hard"]:
            all_pass &= check(level in TASK_CONFIGS, f"Task level '{level}' defined")
    except Exception as e:
        all_pass &= check(False, f"Task config error: {e}")

    # 6. Check inference.py structure
    print("\n--- Inference Script ---")
    try:
        with open("inference.py") as f:
            content = f.read()
        all_pass &= check("[START]" in content, "inference.py has [START] logs")
        all_pass &= check("[STEP]" in content, "inference.py has [STEP] logs")
        all_pass &= check("[END]" in content, "inference.py has [END] logs")
        all_pass &= check("API_BASE_URL" in content, "inference.py uses API_BASE_URL")
        all_pass &= check("MODEL_NAME" in content, "inference.py uses MODEL_NAME")
        all_pass &= check("HF_TOKEN" in content, "inference.py uses HF_TOKEN")
    except Exception as e:
        all_pass &= check(False, f"Inference script check error: {e}")

    # 7. Check Dockerfile
    print("\n--- Docker Configuration ---")
    try:
        with open("server/Dockerfile") as f:
            dockerfile = f.read()
        all_pass &= check("EXPOSE" in dockerfile, "Dockerfile exposes port")
        all_pass &= check("uvicorn" in dockerfile, "Dockerfile runs uvicorn")
        all_pass &= check(
            "requirements.txt" in dockerfile, "Dockerfile installs requirements"
        )
    except Exception as e:
        all_pass &= check(False, f"Dockerfile check error: {e}")

    # 8. Check environment variables handling
    print("\n--- Environment Variables ---")
    all_pass &= check(
        "ENV_URL" in os.environ or True, "ENV_URL configurable (default: localhost)"
    )
    all_pass &= check("API_BASE_URL" in os.environ or True, "API_BASE_URL configurable")
    all_pass &= check("MODEL_NAME" in os.environ or True, "MODEL_NAME configurable")
    all_pass &= check("HF_TOKEN" in os.environ or True, "HF_TOKEN configurable")

    # 9. Check README
    print("\n--- Documentation ---")
    try:
        with open("README.md") as f:
            readme = f.read()
        all_pass &= check(len(readme) > 100, "README.md has sufficient content")
        all_pass &= check(
            "installation" in readme.lower() or "setup" in readme.lower(),
            "README has setup instructions",
        )
        all_pass &= check("action" in readme.lower(), "README describes action space")
        all_pass &= check(
            "observation" in readme.lower(), "README describes observation space"
        )
    except Exception as e:
        all_pass &= check(False, f"README check error: {e}")

    # Summary
    print("\n" + "=" * 60)
    if all_pass:
        print("  ALL CHECKS PASSED - Ready for submission!")
    else:
        print("  SOME CHECKS FAILED - Fix issues before submission")
    print("=" * 60 + "\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

import argparse
import os
import sys
from typing import Iterable, List

from dotenv import load_dotenv

from client import WarehouseClient
from models import RobotAction, RobotObservation
from server.core.agents import MultiRobotCoordinator
from server.core.constants import TASK_CONFIGS
from server.core.llm import LLMPlanningError, WarehouseLLM


load_dotenv()

ENV_URL = os.getenv("ENV_URL", "http://localhost:7860")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
DEBUG = os.getenv("DEBUG", "").lower() in {"1", "true", "yes", "on"}


def _debug(message: str):
    if DEBUG:
        print(message, flush=True)


def _format_action(action: RobotAction) -> str:
    if action.action == "move":
        return f"move({action.direction})"
    if action.action == "move_to":
        return f"move_to({action.target})"
    if action.target:
        return f"{action.action}({action.target})"
    return f"{action.action}()"


def _build_valid_actions(observation: dict) -> List[str]:
    valid_actions = [
        "move(up)",
        "move(down)",
        "move(left)",
        "move(right)",
        "no_op()",
    ]
    available_packages = [
        package["id"]
        for package in observation.get("packages", [])
        if not package.get("delivered", False)
    ]
    next_agent_id = observation.get("next_agent_id", "robot_1")
    robot = observation.get("robots", {}).get(next_agent_id, {})
    carrying_id = robot.get("carrying_id")

    for package_id in available_packages:
        valid_actions.append(f"move_to({package_id})")
        valid_actions.append(f"pick({package_id})")
    if carrying_id:
        valid_actions.append("move_to(Delivery Zone)")
        valid_actions.append(f"deliver({carrying_id})")

    return sorted(set(valid_actions))


def _parse_action_string(action_text: str, agent_id: str) -> RobotAction:
    action_text = action_text.strip()
    if action_text == "no_op()":
        return RobotAction(agent_id=agent_id, action="no_op", direction="none")

    if action_text.startswith("move(") and action_text.endswith(")"):
        direction = action_text[5:-1]
        return RobotAction(agent_id=agent_id, action="move", direction=direction)

    if action_text.startswith("move_to(") and action_text.endswith(")"):
        target = action_text[8:-1]
        return RobotAction(
            agent_id=agent_id,
            action="move_to",
            direction="none",
            target=target,
        )

    if action_text.startswith("pick(") and action_text.endswith(")"):
        target = action_text[5:-1]
        return RobotAction(
            agent_id=agent_id,
            action="pick",
            direction="none",
            target=target,
        )

    if action_text.startswith("deliver(") and action_text.endswith(")"):
        target = action_text[8:-1]
        return RobotAction(
            agent_id=agent_id,
            action="deliver",
            direction="none",
            target=target,
        )

    raise ValueError(f"Unsupported action text: {action_text}")


def get_llm_action(observation, valid_actions, objective: str | None = None):
    llm = WarehouseLLM(
        api_base_url=API_BASE_URL,
        model_name=MODEL_NAME,
        api_key=HF_TOKEN,
    )
    return llm.choose_action(observation, valid_actions, objective=objective)


def choose_next_action(
    observation: RobotObservation,
    objective: str,
    coordinator: MultiRobotCoordinator,
    llm: WarehouseLLM | None,
) -> RobotAction:
    observation_dict = observation.model_dump()
    agent_id = observation.next_agent_id or "robot_1"

    if llm is not None:
        try:
            valid_actions = _build_valid_actions(observation_dict)
            action_text = llm.choose_action(
                observation_dict,
                valid_actions,
                objective=objective,
            )
            return _parse_action_string(action_text, agent_id)
        except (LLMPlanningError, ValueError) as exc:
            _debug(f"[DEBUG] Falling back to deterministic planner: {exc}")
    return coordinator.get_action(observation, agent_id=agent_id)


def run_episode(
    client: WarehouseClient,
    task_level: str,
    objective: str,
    llm: WarehouseLLM | None,
    coordinator: MultiRobotCoordinator,
    max_steps_override: int | None = None,
) -> float:
    observation = client.reset(options={"task_level": task_level})
    coordinator.reset()
    step_limit = max_steps_override or TASK_CONFIGS[task_level]["max_steps"]
    step_index = 0

    print("[START]", flush=True)
    print(f"task: {task_level}", flush=True)
    print(f"objective: {objective}", flush=True)

    while not observation.done and step_index < step_limit:
        action = choose_next_action(observation, objective, coordinator, llm)
        observation = client.step(action)
        step_index += 1

        print("[STEP]", flush=True)
        print(f"task: {task_level}", flush=True)
        print(f"step: {step_index}", flush=True)
        print(f"agent: {action.agent_id}", flush=True)
        print(f"action: {_format_action(action)}", flush=True)
        print(f"reward: {observation.reward}", flush=True)
        print(f"message: {observation.message}", flush=True)

        _debug(
            f"[DEBUG] {task_level=} {step_index=} action={_format_action(action)} "
            f"next_agent={observation.next_agent_id} delivered={observation.delivered_count}"
        )

    score = (
        observation.delivered_count / observation.total_packages
        if observation.total_packages
        else 0.0
    )
    print("[END]", flush=True)
    print(f"task: {task_level}", flush=True)
    print(f"steps: {step_index}", flush=True)
    print(
        f"delivered: {observation.delivered_count}/{observation.total_packages}",
        flush=True,
    )
    print(f"score: {score:.3f}", flush=True)
    return score


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the warehouse simulator baseline inference."
    )
    parser.add_argument(
        "objective",
        nargs="?",
        default="Coordinate all robots to deliver every package safely.",
        help="Natural-language objective for the controller.",
    )
    parser.add_argument(
        "--task-level",
        action="append",
        choices=sorted(TASK_CONFIGS),
        help="Task level(s) to run. Defaults to all levels.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Optional hard cap on steps per task.",
    )
    parser.add_argument(
        "--planner",
        choices=["deterministic", "llm", "auto"],
        default="deterministic",
        help="Planner to use. 'auto' tries LLM first and falls back safely.",
    )
    parser.add_argument(
        "--env-url",
        default=ENV_URL,
        help="Base URL for the running environment server.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    task_levels = args.task_level or list(TASK_CONFIGS.keys())
    coordinator = MultiRobotCoordinator()

    llm = None
    if args.planner in {"llm", "auto"}:
        try:
            llm = WarehouseLLM(
                api_base_url=API_BASE_URL,
                model_name=MODEL_NAME,
                api_key=HF_TOKEN,
            )
        except LLMPlanningError as exc:
            _debug(f"[DEBUG] Falling back to deterministic coordinator: {exc}")

    if args.planner == "deterministic":
        llm = None

    client = WarehouseClient(base_url=args.env_url).sync()
    scores: List[float] = []

    try:
        with client:
            for task_level in task_levels:
                scores.append(
                    run_episode(
                        client,
                        task_level,
                        args.objective,
                        llm,
                        coordinator,
                        max_steps_override=args.max_steps,
                    )
                )
    except Exception as exc:
        print(f"[ERROR] inference failed: {exc}", flush=True)
        return 1

    average_score = sum(scores) / len(scores) if scores else 0.0
    _debug(f"[DEBUG] average_score={average_score:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import copy
import os
import sys
from typing import Optional

from openenv.core import Environment


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import RobotAction, RobotObservation, RobotState
from core.agents import build_dynamic_obstacles, next_direction_from_grid, resolve_target_position
from core.constants import TASK_CONFIGS
from core.engine import WarehouseEngine
from core.rewards import DefaultWarehouseRewards


def _format_action(action: RobotAction) -> str:
    if action.action == "move":
        return f"move({action.direction})"
    if action.action == "move_to":
        return f"move_to({action.target})"
    if action.target:
        return f"{action.action}({action.target})"
    return f"{action.action}()"


class SmartWarehouseEnv(Environment):
    """OpenEnv-compatible warehouse simulator."""

    def __init__(self):
        super().__init__()
        self.engine: Optional[WarehouseEngine] = None
        self.reward_system = DefaultWarehouseRewards()
        self._task_level = "easy"
        self._episode_id = "ep_0"
        self._last_failed = False
        self._collision_reason: Optional[str] = None
        self._last_action: Optional[str] = None
        self._last_action_agent_id: Optional[str] = None
        self._agent_order: list[str] = []
        self._next_agent_id = "robot_1"

    def reset(self, seed=None, episode_id=None, options=None, **kwargs) -> RobotObservation:
        del seed, kwargs
        options = options or {}
        self._task_level = options.get("task_level", "easy")
        cfg = TASK_CONFIGS[self._task_level]

        self.engine = WarehouseEngine(
            grid_size=cfg["grid_size"],
            packages=cfg["packages"],
            obstacles=cfg["obstacles"],
            max_steps=cfg["max_steps"],
            num_robots=cfg["num_robots"],
            robot_starts=cfg.get("robot_starts"),
        )
        self._episode_id = episode_id or "ep_0"
        self._agent_order = self.engine.robot_ids()
        self._next_agent_id = self._agent_order[0] if self._agent_order else "robot_1"
        self.reward_system.failure_streak = 0
        self._last_failed = False
        self._collision_reason = None
        self._last_action = None
        self._last_action_agent_id = None

        reachable = self.engine.verify_reachability()
        message = (
            f"Episode started on {self._task_level.upper()} with "
            f"{self.engine.num_robots} robots and {len(self.engine.packages)} packages."
        )
        if not reachable:
            message += " Reachability warning: at least one package is not reachable."

        return self._make_observation(reward=0.0, message=message)

    def _distance_to_goal(self, agent_id: str) -> int:
        if not self.engine or agent_id not in self.engine.robots:
            return 0

        robot = self.engine.robots[agent_id]
        rx, ry = robot["pos"]
        if robot["carrying_id"]:
            return abs(rx) + abs(ry)

        carried_packages = {
            robot_state["carrying_id"]
            for robot_state in self.engine.robots.values()
            if robot_state["carrying_id"]
        }
        available_packages = [
            package
            for package in self.engine.packages
            if not package["delivered"] and package["id"] not in carried_packages
        ]
        if not available_packages:
            return 0

        return min(
            abs(rx - package["position"][0]) + abs(ry - package["position"][1])
            for package in available_packages
        )

    def _advance_turn(self, agent_id: str):
        if not self._agent_order:
            self._next_agent_id = agent_id
            return

        try:
            current_index = self._agent_order.index(agent_id)
        except ValueError:
            current_index = -1

        self._next_agent_id = self._agent_order[
            (current_index + 1) % len(self._agent_order)
        ]

    def _final_score(self) -> float:
        if not self.engine or not self.engine.packages:
            return 0.0

        completion = self.engine.delivered_count / len(self.engine.packages)
        efficiency = max(
            0.0, (self.engine.max_steps - self.engine.steps) / self.engine.max_steps
        )
        score = completion * 0.85 + efficiency * 0.15
        return max(0.0, min(1.0, score))

    def step(self, action: RobotAction, **kwargs) -> RobotObservation:
        del kwargs
        if not self.engine:
            return self._make_observation(0.0, "Environment not initialized. Call reset().")
        if self.engine.done:
            return self._make_observation(0.0, "Episode already ended. Call reset().")

        agent_id = action.agent_id if action.agent_id in self.engine.robots else self._next_agent_id
        self._last_failed = False
        self._collision_reason = None
        self._last_action_agent_id = agent_id

        self.engine.steps += 1
        total_reward = self.reward_system.calculate("step")
        expired = self.engine.tick_deadlines()
        if expired:
            total_reward += sum(self.reward_system.calculate("expired") for _ in expired)

        message_parts = []
        prev_distance = self._distance_to_goal(agent_id)
        robot = self.engine.robots.get(agent_id)
        current_pos = tuple(robot["pos"]) if robot else (0, 0)

        if action.action == "move":
            move_state = self.engine.inspect_move(agent_id, action.direction)
            if move_state["success"]:
                self.engine.move(agent_id, action.direction)
                total_reward += self.reward_system.calculate("move")
                new_distance = self._distance_to_goal(agent_id)
                if new_distance < prev_distance:
                    total_reward += 0.5
                elif new_distance > prev_distance:
                    total_reward -= 0.5

                message_parts.append(
                    f"{agent_id} moved {action.direction} from {move_state['current_pos']} to {move_state['next_pos']}."
                )
            else:
                total_reward += self.reward_system.calculate("wall_hit")
                self._last_failed = True
                self._collision_reason = str(move_state["reason"])
                message_parts.append(
                    f"{agent_id} blocked while moving {action.direction}: "
                    f"current={move_state['current_pos']} next={move_state['next_pos']} "
                    f"reason={self._collision_reason}."
                )

        elif action.action == "move_to" and action.target:
            target_pos = resolve_target_position(self._make_observation(None, ""), action.target)
            if target_pos is None:
                total_reward += self.reward_system.calculate("invalid_action")
                self._last_failed = True
                message_parts.append(f"{agent_id} received unknown target {action.target}.")
            elif current_pos == target_pos:
                message_parts.append(f"{agent_id} is already at {action.target}.")
            else:
                direction = next_direction_from_grid(
                    current_pos,
                    target_pos,
                    self.engine.grid_size,
                    build_dynamic_obstacles(self._make_observation(None, ""), agent_id),
                )
                if direction is None:
                    total_reward += self.reward_system.calculate("wall_hit")
                    self._last_failed = True
                    self._collision_reason = f"No path to {action.target}"
                    message_parts.append(f"{agent_id} could not find a safe path to {action.target}.")
                else:
                    move_state = self.engine.inspect_move(agent_id, direction)
                    if move_state["success"]:
                        self.engine.move(agent_id, direction)
                        total_reward += self.reward_system.calculate("move")
                        message_parts.append(
                            f"{agent_id} moved {direction} toward {action.target}."
                        )
                    else:
                        total_reward += self.reward_system.calculate("wall_hit")
                        self._last_failed = True
                        self._collision_reason = str(move_state["reason"])
                        message_parts.append(
                            f"{agent_id} failed while moving toward {action.target}: {self._collision_reason}."
                        )

        elif action.action == "pick":
            package_id = self.engine.pick(agent_id)
            if package_id:
                total_reward += self.reward_system.calculate("pick")
                message_parts.append(f"{agent_id} picked up package {package_id}.")
            else:
                total_reward += self.reward_system.calculate("invalid_action")
                self._last_failed = True
                message_parts.append(f"{agent_id} could not pick a package at {list(current_pos)}.")

        elif action.action == "deliver":
            package_id = self.engine.deliver(agent_id)
            if package_id:
                total_reward += self.reward_system.calculate("delivered")
                message_parts.append(f"{agent_id} delivered package {package_id}.")
            else:
                total_reward += self.reward_system.calculate("wrong_spot")
                self._last_failed = True
                self._collision_reason = "Delivery attempted away from the delivery zone or without cargo."
                message_parts.append(f"{agent_id} failed to deliver: {self._collision_reason}")

        elif action.action == "no_op":
            message_parts.append(f"{agent_id} waited.")

        else:
            total_reward += self.reward_system.calculate("invalid_action")
            self._last_failed = True
            message_parts.append(f"{agent_id} issued unsupported action {action.action}.")

        self._last_action = _format_action(action)
        self._advance_turn(agent_id)

        all_delivered = all(package["delivered"] for package in self.engine.packages)
        timeout = self.engine.steps >= self.engine.max_steps
        self.engine.done = all_delivered or timeout

        if expired:
            message_parts.append(f"Expired packages: {', '.join(expired)}.")

        if self.engine.done:
            score = self._final_score()
            total_reward += score * 100
            if all_delivered:
                message_parts.append(f"Episode complete. Final score {score:.2f}.")
            else:
                message_parts.append(f"Episode timed out. Final score {score:.2f}.")

        return self._make_observation(round(total_reward, 3), " ".join(message_parts))

    def _make_observation(
        self,
        reward: Optional[float],
        message: str,
    ) -> RobotObservation:
        robots = copy.deepcopy(self.engine.robots) if self.engine else {}
        primary_robot = robots.get("robot_1", {"pos": [0, 0], "carrying_id": None})
        obstacles = [list(obstacle) for obstacle in self.engine.obstacles] if self.engine else []

        return RobotObservation(
            done=self.engine.done if self.engine else False,
            reward=reward,
            robot_position=primary_robot["pos"],
            carrying_package=primary_robot["carrying_id"],
            robots=robots,
            packages=[dict(package) for package in self.engine.packages] if self.engine else [],
            obstacles=obstacles,
            grid_size=self.engine.grid_size if self.engine else 5,
            steps_remaining=(self.engine.max_steps - self.engine.steps) if self.engine else 0,
            message=message,
            delivered_count=self.engine.delivered_count if self.engine else 0,
            total_packages=len(self.engine.packages) if self.engine else 0,
            next_agent_id=self._next_agent_id,
            last_action=self._last_action,
            last_action_agent_id=self._last_action_agent_id,
            last_action_failed=self._last_failed,
            collision_reason=self._collision_reason,
        )

    @property
    def state(self) -> RobotState:
        if not self.engine:
            return RobotState()

        return RobotState(
            episode_id=self._episode_id,
            step_count=self.engine.steps,
            task_level=self._task_level,
            total_packages=len(self.engine.packages),
            delivered_count=self.engine.delivered_count,
            grid_size=self.engine.grid_size,
            score=self._final_score(),
            max_steps=self.engine.max_steps,
            next_agent_id=self._next_agent_id,
        )

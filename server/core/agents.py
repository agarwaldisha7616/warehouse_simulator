from abc import ABC, abstractmethod
from collections import deque
from typing import Deque, Dict, List, Optional, Set, Tuple

from models import RobotAction, RobotObservation


MOVE_DELTAS = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}

OPPOSITE_DIRECTIONS = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}


def resolve_target_position(
    observation: RobotObservation, target: Optional[str]
) -> Optional[Tuple[int, int]]:
    if not target:
        return None
    if target in {"Delivery Zone", "0, 0", "0,0"}:
        return (0, 0)

    package = next((p for p in observation.packages if p["id"] == target), None)
    if not package:
        return None
    return tuple(package["position"])


def build_dynamic_obstacles(
    observation: RobotObservation, agent_id: str
) -> List[List[int]]:
    dynamic_obstacles = [list(obstacle) for obstacle in observation.obstacles]
    for other_id, robot in observation.robots.items():
        if other_id != agent_id:
            dynamic_obstacles.append(list(robot["pos"]))
    return dynamic_obstacles


def next_direction_from_grid(
    start: Tuple[int, int],
    target: Tuple[int, int],
    grid_size: int,
    obstacles: List[List[int]],
) -> Optional[str]:
    if start == target:
        return None

    obstacle_set = {tuple(obstacle) for obstacle in obstacles}
    queue = deque([(start, [])])
    visited = {start}

    while queue:
        current, path = queue.popleft()
        if current == target:
            return path[0] if path else None

        cx, cy = current
        for direction, (dx, dy) in MOVE_DELTAS.items():
            nx, ny = cx + dx, cy + dy
            next_pos = (nx, ny)
            if (
                0 <= nx < grid_size
                and 0 <= ny < grid_size
                and next_pos not in obstacle_set
                and next_pos not in visited
            ):
                visited.add(next_pos)
                queue.append((next_pos, path + [direction]))

    return None


class BaseAgent(ABC):
    @abstractmethod
    def get_action(self, observation: RobotObservation) -> RobotAction:
        raise NotImplementedError


class GreedyAgent(BaseAgent):
    """Single-robot deterministic controller with oscillation guards."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.last_action: Optional[RobotAction] = None
        self.failure_count = 0
        self.position_history: Deque[Tuple[int, int]] = deque(maxlen=6)

    def reset(self):
        self.last_action = None
        self.failure_count = 0
        self.position_history.clear()

    def _record_position(self, pos: Tuple[int, int]):
        if not self.position_history or self.position_history[-1] != pos:
            self.position_history.append(pos)

    def _is_recent_position(self, pos: Tuple[int, int]) -> bool:
        return pos in self.position_history

    def _is_other_robot_carrying(
        self, observation: RobotObservation, package_id: str
    ) -> bool:
        return any(
            robot["carrying_id"] == package_id
            for robot_id, robot in observation.robots.items()
            if robot_id != self.agent_id
        )

    def _choose_target(
        self,
        observation: RobotObservation,
        forced_target: Optional[str] = None,
    ) -> Tuple[Optional[Tuple[int, int]], Optional[str]]:
        robot = observation.robots.get(self.agent_id)
        if not robot:
            return None, None

        if robot["carrying_id"]:
            return (0, 0), "Delivery Zone"

        if forced_target:
            target_pos = resolve_target_position(observation, forced_target)
            if target_pos is not None:
                return target_pos, forced_target

        available_packages = [
            package
            for package in observation.packages
            if not package["delivered"]
            and not self._is_other_robot_carrying(observation, package["id"])
        ]
        if not available_packages:
            return None, None

        rx, ry = robot["pos"]
        chosen = min(
            available_packages,
            key=lambda package: (
                abs(package["position"][0] - rx) + abs(package["position"][1] - ry),
                package["deadline"],
                package["position"][1],
                package["position"][0],
                package["id"],
            ),
        )
        return tuple(chosen["position"]), chosen["id"]

    def _candidate_moves(
        self,
        rx: int,
        ry: int,
        target: Tuple[int, int],
        grid_size: int,
        obstacles: Set[Tuple[int, int]],
    ) -> List[Dict[str, object]]:
        previous_direction = (
            self.last_action.direction
            if self.last_action and self.last_action.action == "move"
            else None
        )
        candidates: List[Dict[str, object]] = []
        for direction, (dx, dy) in MOVE_DELTAS.items():
            next_pos = (rx + dx, ry + dy)
            if not (0 <= next_pos[0] < grid_size and 0 <= next_pos[1] < grid_size):
                continue
            if next_pos in obstacles:
                continue
            candidates.append(
                {
                    "direction": direction,
                    "next_pos": next_pos,
                    "distance": abs(next_pos[0] - target[0])
                    + abs(next_pos[1] - target[1]),
                    "recent": self._is_recent_position(next_pos),
                }
            )
        return candidates

    def _select_move_direction(
        self,
        observation: RobotObservation,
        start: Tuple[int, int],
        target: Tuple[int, int],
    ) -> Optional[str]:
        obstacles = build_dynamic_obstacles(observation, self.agent_id)
        obstacle_set = {tuple(obstacle) for obstacle in obstacles}
        rx, ry = start
        candidates = self._candidate_moves(
            rx,
            ry,
            target,
            observation.grid_size,
            obstacle_set,
        )
        if not candidates:
            return None

        bfs_direction = next_direction_from_grid(
            start,
            target,
            observation.grid_size,
            obstacles,
        )
        if bfs_direction:
            direct = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate["direction"] == bfs_direction
                ),
                None,
            )
            if direct:
                return str(direct["direction"])

        preferred = min(
            candidates,
            key=lambda candidate: (
                bool(candidate["recent"]),
                int(candidate["distance"]),
                str(candidate["direction"]),
            ),
        )
        return str(preferred["direction"])

    def _clear_delivery_zone_direction(
        self,
        observation: RobotObservation,
        position: Tuple[int, int],
    ) -> Optional[str]:
        if abs(position[0]) + abs(position[1]) > 1:
            return None
        if not any(
            robot["carrying_id"]
            for robot_id, robot in observation.robots.items()
            if robot_id != self.agent_id
        ):
            return None

        obstacle_set = {
            tuple(obstacle)
            for obstacle in build_dynamic_obstacles(observation, self.agent_id)
        }
        candidates: List[Tuple[int, str]] = []
        for direction in ("up", "right", "left", "down"):
            dx, dy = MOVE_DELTAS[direction]
            next_pos = (position[0] + dx, position[1] + dy)
            if (
                0 <= next_pos[0] < observation.grid_size
                and 0 <= next_pos[1] < observation.grid_size
                and next_pos not in obstacle_set
            ):
                candidates.append((abs(next_pos[0]) + abs(next_pos[1]), direction))

        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    def get_action(
        self,
        observation: RobotObservation,
        forced_target: Optional[str] = None,
    ) -> RobotAction:
        robot = observation.robots.get(self.agent_id)
        if not robot:
            return RobotAction(
                agent_id=self.agent_id,
                action="no_op",
                direction="none",
                reasoning="Robot is not present in the observation.",
            )

        position = tuple(robot["pos"])
        self._record_position(position)

        if observation.last_action_agent_id == self.agent_id and observation.last_action_failed:
            self.failure_count += 1
        elif observation.last_action_agent_id == self.agent_id:
            self.failure_count = 0

        if robot["carrying_id"] and position == (0, 0):
            action = RobotAction(
                agent_id=self.agent_id,
                action="deliver",
                direction="none",
                target="Delivery Zone",
                reasoning=f"{self.agent_id} is at the delivery zone with a package.",
            )
            self.last_action = action
            return action

        target_pos, target_label = self._choose_target(observation, forced_target)
        if target_pos is None or target_label is None:
            staging_direction = self._clear_delivery_zone_direction(
                observation,
                position,
            )
            if staging_direction:
                action = RobotAction(
                    agent_id=self.agent_id,
                    action="move",
                    direction=staging_direction,
                    target="staging",
                    reasoning=f"{self.agent_id} is clearing the delivery zone.",
                )
                self.last_action = action
                return action

            action = RobotAction(
                agent_id=self.agent_id,
                action="no_op",
                direction="none",
                reasoning=f"{self.agent_id} has no remaining assignment.",
            )
            self.last_action = action
            return action

        if not robot["carrying_id"] and position == target_pos:
            action = RobotAction(
                agent_id=self.agent_id,
                action="pick",
                direction="none",
                target=target_label,
                reasoning=f"{self.agent_id} is on package {target_label}.",
            )
            self.last_action = action
            return action

        direction = self._select_move_direction(observation, position, target_pos)
        if direction is None:
            action = RobotAction(
                agent_id=self.agent_id,
                action="no_op",
                direction="none",
                target=target_label,
                reasoning=f"{self.agent_id} could not find a safe path to {target_label}.",
            )
            self.last_action = action
            return action

        action = RobotAction(
            agent_id=self.agent_id,
            action="move",
            direction=direction,
            target=target_label,
            reasoning=f"{self.agent_id} moving {direction} toward {target_label}.",
        )
        self.last_action = action
        return action


class MultiRobotCoordinator:
    """Deterministic robot scheduler used by the UI and inference baseline."""

    def __init__(self):
        self.agents: Dict[str, GreedyAgent] = {}

    def reset(self):
        for agent in self.agents.values():
            agent.reset()

    def _ensure_agents(self, observation: RobotObservation):
        for agent_id in sorted(observation.robots):
            if agent_id not in self.agents:
                self.agents[agent_id] = GreedyAgent(agent_id)

    def assign_targets(self, observation: RobotObservation) -> Dict[str, Optional[str]]:
        assignments: Dict[str, Optional[str]] = {}
        claimed_packages: Set[str] = set()

        for agent_id in sorted(observation.robots):
            robot = observation.robots[agent_id]
            if robot["carrying_id"]:
                assignments[agent_id] = "Delivery Zone"
                continue

            rx, ry = robot["pos"]
            available_packages = [
                package
                for package in observation.packages
                if not package["delivered"]
                and package["id"] not in claimed_packages
                and not any(
                    other_robot["carrying_id"] == package["id"]
                    for other_robot in observation.robots.values()
                )
            ]

            if not available_packages:
                assignments[agent_id] = None
                continue

            chosen = min(
                available_packages,
                key=lambda package: (
                    abs(package["position"][0] - rx) + abs(package["position"][1] - ry),
                    package["deadline"],
                    package["position"][1],
                    package["position"][0],
                    package["id"],
                ),
            )
            assignments[agent_id] = chosen["id"]
            claimed_packages.add(chosen["id"])

        return assignments

    def get_action(
        self,
        observation: RobotObservation,
        agent_id: Optional[str] = None,
    ) -> RobotAction:
        self._ensure_agents(observation)

        selected_agent_id = (
            agent_id
            or observation.next_agent_id
            or sorted(observation.robots)[0]
        )
        assignments = self.assign_targets(observation)
        forced_target = assignments.get(selected_agent_id)
        return self.agents[selected_agent_id].get_action(observation, forced_target)


def task_to_robot_action(
    observation: RobotObservation,
    task_action: str,
    agent_id: Optional[str] = None,
    target: Optional[str] = None,
    direction: Optional[str] = None,
) -> RobotAction:
    selected_agent_id = agent_id or observation.next_agent_id or sorted(observation.robots)[0]
    robot = observation.robots.get(selected_agent_id)
    if robot is None:
        return RobotAction(
            agent_id=selected_agent_id,
            action="no_op",
            direction="none",
            reasoning="Requested robot is not active.",
        )

    if task_action in {"pick", "deliver", "no_op"}:
        return RobotAction(
            agent_id=selected_agent_id,
            action=task_action,
            direction="none",
            target=target,
            reasoning=f"Executing explicit {task_action} command.",
        )

    if task_action == "move":
        return RobotAction(
            agent_id=selected_agent_id,
            action="move",
            direction=direction or "none",
            target=target,
            reasoning=f"Executing explicit move {direction or 'none'}.",
        )

    if task_action != "move_to":
        return RobotAction(
            agent_id=selected_agent_id,
            action="no_op",
            direction="none",
            target=target,
            reasoning=f"Unsupported task action '{task_action}'.",
        )

    target_pos = resolve_target_position(observation, target)
    if target_pos is None:
        return RobotAction(
            agent_id=selected_agent_id,
            action="no_op",
            direction="none",
            target=target,
            reasoning=f"Unknown target '{target}'.",
        )

    current_pos = tuple(robot["pos"])
    if current_pos == target_pos:
        if target == "Delivery Zone" and robot["carrying_id"]:
            return RobotAction(
                agent_id=selected_agent_id,
                action="deliver",
                direction="none",
                target=target,
                reasoning=f"{selected_agent_id} reached the delivery zone.",
            )
        if any(
            package["id"] == target
            and not package["delivered"]
            and package["position"] == list(current_pos)
            for package in observation.packages
        ):
            return RobotAction(
                agent_id=selected_agent_id,
                action="pick",
                direction="none",
                target=target,
                reasoning=f"{selected_agent_id} reached package {target}.",
            )
        return RobotAction(
            agent_id=selected_agent_id,
            action="no_op",
            direction="none",
            target=target,
            reasoning=f"{selected_agent_id} is already at {target}.",
        )

    move_direction = next_direction_from_grid(
        current_pos,
        target_pos,
        observation.grid_size,
        build_dynamic_obstacles(observation, selected_agent_id),
    )
    if move_direction is None:
        return RobotAction(
            agent_id=selected_agent_id,
            action="no_op",
            direction="none",
            target=target,
            reasoning=f"No safe path found to {target}.",
        )

    return RobotAction(
        agent_id=selected_agent_id,
        action="move",
        direction=move_direction,
        target=target,
        reasoning=f"{selected_agent_id} moving toward {target}.",
    )

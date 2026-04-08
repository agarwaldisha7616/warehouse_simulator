import copy
from collections import deque
from typing import Dict, List, Optional, Tuple

MOVE_DELTAS = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
    "none": (0, 0),
}


class WarehouseEngine:
    """State engine for the warehouse simulator."""

    def __init__(
        self,
        grid_size: int,
        packages: List[dict],
        obstacles: List[List[int]],
        max_steps: int,
        num_robots: int = 1,
        robot_starts: Optional[List[List[int]]] = None,
    ):
        self.grid_size = grid_size
        self.initial_packages = copy.deepcopy(packages)
        self.packages = copy.deepcopy(packages)
        self.obstacles = [tuple(o) for o in obstacles]
        self.obstacle_set = frozenset(self.obstacles)
        self.max_steps = max_steps
        self.num_robots = num_robots
        self.robot_starts = self._normalize_robot_starts(robot_starts or [])

        self.robots = self._build_robot_state()
        self.steps = 0
        self.delivered_count = 0
        self.done = False

    def _normalize_robot_starts(self, robot_starts: List[List[int]]) -> List[List[int]]:
        starts = [list(pos) for pos in robot_starts[: self.num_robots]]
        occupied = {tuple(pos) for pos in starts}

        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if len(starts) >= self.num_robots:
                    return starts
                candidate = (x, y)
                if candidate in occupied or candidate in self.obstacle_set:
                    continue
                starts.append([x, y])
                occupied.add(candidate)

        raise ValueError("Unable to place all robots on valid starting cells")

    def _build_robot_state(self) -> Dict[str, Dict[str, Optional[List[int]]]]:
        return {
            f"robot_{i + 1}": {
                "pos": copy.deepcopy(self.robot_starts[i]),
                "carrying_id": None,
            }
            for i in range(self.num_robots)
        }

    def robot_ids(self) -> List[str]:
        return list(self.robots.keys())

    def reset(self):
        self.robots = self._build_robot_state()
        self.steps = 0
        self.delivered_count = 0
        self.done = False
        self.packages = copy.deepcopy(self.initial_packages)

    def inspect_move(self, agent_id: str, direction: str) -> Dict[str, object]:
        if agent_id not in self.robots or direction not in MOVE_DELTAS or direction == "none":
            return {
                "success": False,
                "current_pos": None,
                "next_pos": None,
                "reason": "Invalid move request",
            }

        dx, dy = MOVE_DELTAS[direction]
        rx, ry = self.robots[agent_id]["pos"]
        nx, ny = rx + dx, ry + dy

        if not (0 <= nx < self.grid_size and 0 <= ny < self.grid_size):
            return {
                "success": False,
                "current_pos": [rx, ry],
                "next_pos": [nx, ny],
                "reason": f"Boundary violation at ({nx}, {ny})",
            }
        if (nx, ny) in self.obstacle_set:
            return {
                "success": False,
                "current_pos": [rx, ry],
                "next_pos": [nx, ny],
                "reason": f"Obstacle at ({nx}, {ny})",
            }

        for other_id, r_data in self.robots.items():
            if other_id != agent_id and tuple(r_data["pos"]) == (nx, ny):
                return {
                    "success": False,
                    "current_pos": [rx, ry],
                    "next_pos": [nx, ny],
                    "reason": f"Collision with {other_id} at ({nx}, {ny})",
                }

        return {
            "success": True,
            "current_pos": [rx, ry],
            "next_pos": [nx, ny],
            "reason": None,
        }

    def move(self, agent_id: str, direction: str) -> bool:
        move_state = self.inspect_move(agent_id, direction)
        if not move_state["success"]:
            return False

        next_pos = move_state["next_pos"]
        assert isinstance(next_pos, list)
        self.robots[agent_id]["pos"] = next_pos
        return True

    def pick(self, agent_id: str) -> Optional[str]:
        """Attempt to pick up a package at current position for a given agent."""
        if (
            agent_id not in self.robots
            or self.robots[agent_id]["carrying_id"] is not None
        ):
            return None

        rx, ry = self.robots[agent_id]["pos"]
        for p in self.packages:
            if (
                not p["delivered"]
                and p["position"] == [rx, ry]
                and not self._is_carried_by_others(p["id"])
            ):
                self.robots[agent_id]["carrying_id"] = p["id"]
                return p["id"]
        return None

    def _is_carried_by_others(self, pkg_id: str) -> bool:
        return any(r_data["carrying_id"] == pkg_id for r_data in self.robots.values())

    def deliver(self, agent_id: str) -> Optional[str]:
        """Attempt to deliver current package at (0,0) for a given agent."""
        if agent_id not in self.robots:
            return None

        rx, ry = self.robots[agent_id]["pos"]
        carrying_id = self.robots[agent_id]["carrying_id"]

        if carrying_id and rx == 0 and ry == 0:
            for p in self.packages:
                if p["id"] == carrying_id:
                    p["delivered"] = True
                    self.delivered_count += 1
                    self.robots[agent_id]["carrying_id"] = None
                    return carrying_id
        return None

    def tick_deadlines(self) -> List[str]:
        """Decrement package deadlines. Returns list of IDs that just expired."""
        expired = []
        for p in self.packages:
            if not p["delivered"] and p["deadline"] > 0:
                p["deadline"] -= 1
                if p["deadline"] == 0:
                    expired.append(p["id"])
        return expired

    def verify_reachability(self) -> bool:
        """Ensure all packages and robot starts are reachable from the delivery zone."""
        start = (0, 0)
        visited = {start}
        queue = deque([start])

        while queue:
            cx, cy = queue.popleft()
            for dx, dy in MOVE_DELTAS.values():
                nx, ny = cx + dx, cy + dy
                if (
                    0 <= nx < self.grid_size
                    and 0 <= ny < self.grid_size
                    and (nx, ny) not in self.obstacle_set
                    and (nx, ny) not in visited
                ):
                    visited.add((nx, ny))
                    queue.append((nx, ny))

        package_cells = [tuple(p["position"]) for p in self.packages]
        robot_cells = [tuple(robot["pos"]) for robot in self.robots.values()]
        return all(cell in visited for cell in package_cells + robot_cells)

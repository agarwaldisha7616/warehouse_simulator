import copy
from collections import deque
from openenv.core import Environment
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import RobotAction, RobotObservation, RobotState

TASK_CONFIGS = {
    "easy": {
        "grid_size": 5,
        "packages": [
            {"id": "A", "position": [2, 2], "deadline": 15, "delivered": False},
            {"id": "B", "position": [3, 3], "deadline": 15, "delivered": False},
        ],
        "obstacles": [],
        "max_steps": 20,
    },
    "medium": {
        "grid_size": 10,
        "packages": [
            {"id": "A", "position": [2, 2], "deadline": 10, "delivered": False},
            {"id": "B", "position": [8, 8], "deadline": 8,  "delivered": False},
            {"id": "C", "position": [5, 5], "deadline": 12, "delivered": False},
            {"id": "D", "position": [3, 7], "deadline": 7,  "delivered": False},
        ],
        "obstacles": [[1,3],[4,6],[6,2],[7,8],[9,4]],
        "max_steps": 50,
    },
    "hard": {
        "grid_size": 15,
        "packages": [
            {"id": "A", "position": [2, 2],   "deadline": 8,  "delivered": False},
            {"id": "B", "position": [14, 14],  "deadline": 5,  "delivered": False},
            {"id": "C", "position": [7, 7],    "deadline": 10, "delivered": False},
            {"id": "D", "position": [3, 10],   "deadline": 6,  "delivered": False},
            {"id": "E", "position": [11, 3],   "deadline": 9,  "delivered": False},
            {"id": "F", "position": [9, 11],   "deadline": 7,  "delivered": False},
        ],
        "obstacles": [
            [1,5],[3,4],[5,2],[6,8],[8,6],[10,4],
            [4,12],[12,10],[2,9],[9,3],[7,14],[14,7],
            [6,11],[11,6],[13,2]
        ],
        "max_steps": 100,
    },
}

DELIVERY_ZONE = (0, 0)

# Precomputed direction deltas (frozen for speed)
_MOVE_DELTAS = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}


class SmartWarehouseEnv(Environment):

    def reset(self, seed=None, episode_id=None, options=None, **kwargs) -> RobotObservation:
        options = options or {}
        self._task_level = options.get("task_level", "easy")
        cfg = copy.deepcopy(TASK_CONFIGS[self._task_level])
        self._grid_size   = cfg["grid_size"]
        self._packages    = cfg["packages"]
        # OPTIMIZED: Use a frozenset of tuples for O(1) obstacle lookup
        self._obstacle_set = frozenset(tuple(o) for o in cfg["obstacles"])
        self._max_steps   = cfg["max_steps"]
        self._steps       = 0
        self._robot_pos   = [0, 0]
        self._carrying    = None
        self._total_packages  = len(self._packages)
        self._delivered_count = 0
        self._episode_id  = episode_id or "ep_0"
        self._done        = False

        self._state = RobotState(
            episode_id=self._episode_id,
            step_count=0,
            task_level=self._task_level,
            total_packages=self._total_packages,
            delivered_count=0,
            grid_size=self._grid_size,
        )

        # SAFETY: Verify every package is reachable from robot start via BFS
        self._verify_reachability()

        return RobotObservation(
            done=False,
            reward=None,
            robot_position=list(self._robot_pos),
            packages=self._pkg_snapshot(),
            obstacles=[list(o) for o in self._obstacle_set],
            grid_size=self._grid_size,
            steps_remaining=self._max_steps,
            carrying_package=None,
            message=(
                f"Episode started! {self._task_level.upper()} task. "
                f"{self._total_packages} packages to deliver to (0,0). "
                f"Max steps: {self._max_steps}."
            ),
        )

    def step(self, action: RobotAction, **kwargs) -> RobotObservation:
        if self._done:
            return self._make_obs(0.0, "Episode already ended. Call reset().")

        self._steps += 1
        reward  = -0.01
        message = ""

        # ── Deadline countdown every step ──────────────────────────
        for p in self._packages:
            if not p["delivered"] and p["deadline"] > 0:
                p["deadline"] -= 1
                if p["deadline"] == 0:
                    reward  -= 0.5
                    message += f"Package {p['id']} deadline expired! -0.5 "

        # ── Process the action ─────────────────────────────────────
        act = action.action
        if act == "no_op":
            message = message or "No-op."

        elif act == "move":
            # OPTIMIZED: Use precomputed deltas and frozenset for O(1) lookup
            dx, dy   = _MOVE_DELTAS[action.direction]
            nx, ny   = self._robot_pos[0] + dx, self._robot_pos[1] + dy
            in_bounds = 0 <= nx < self._grid_size and 0 <= ny < self._grid_size

            if in_bounds and (nx, ny) not in self._obstacle_set:
                # Valid move — compute shaping reward inline
                prev_d = self._dist_to_nearest_undelivered(self._robot_pos)
                self._robot_pos = [nx, ny]
                new_d  = self._dist_to_nearest_undelivered(self._robot_pos)
                if new_d < prev_d:
                    reward  += 0.2
                    message  = message or f"Moved {action.direction} — closer to target! +0.2"
                else:
                    message  = message or f"Moved {action.direction}."
            else:
                # Wall hit or out of bounds: -0.5 penalty, stay in place
                reward  -= 0.5
                message  = message or f"Hit wall/boundary moving {action.direction}! -0.5"

        elif act == "pick":
            picked = False
            px, py = self._robot_pos
            if self._carrying is None:
                for p in self._packages:
                    if not p["delivered"] and p["position"][0] == px and p["position"][1] == py:
                        self._carrying = p["id"]
                        picked  = True
                        message = f"Picked up Package {p['id']}!"
                        break
            if not picked:
                message = message or "Nothing to pick here."

        elif act == "deliver":
            if self._carrying:
                if self._robot_pos[0] == DELIVERY_ZONE[0] and self._robot_pos[1] == DELIVERY_ZONE[1]:
                    for p in self._packages:
                        if p["id"] == self._carrying and not p["delivered"]:
                            p["delivered"]        = True
                            self._delivered_count += 1
                            pkg_id                = self._carrying
                            self._carrying        = None
                            reward  += 1.0
                            message  = f"Package {pkg_id} delivered to (0,0)! +1.0"
                            break
                else:
                    reward  -= 0.2
                    message  = "Wrong delivery spot! Bring package to (0,0). -0.2"
            else:
                message = message or "Not carrying anything to deliver."

        # ── Episode termination check ──────────────────────────────
        all_done = all(p["delivered"] for p in self._packages)
        timeout  = self._steps >= self._max_steps
        self._done = all_done or timeout

        if self._done:
            score    = self._delivered_count / self._total_packages
            message += (f" | EPISODE ENDED — "
                        f"{self._delivered_count}/{self._total_packages} delivered. "
                        f"Score: {score:.2f}")

        self._state = RobotState(
            episode_id=self._episode_id,
            step_count=self._steps,
            task_level=self._task_level,
            total_packages=self._total_packages,
            delivered_count=self._delivered_count,
            grid_size=self._grid_size,
        )

        return self._make_obs(round(reward, 3), message or "Action taken.")

    @property
    def state(self) -> RobotState:
        return self._state

    # ── Private helpers ────────────────────────────────────────────

    def _make_obs(self, reward: float, message: str) -> RobotObservation:
        return RobotObservation(
            done=self._done,
            reward=reward,
            robot_position=list(self._robot_pos),
            packages=self._pkg_snapshot(),
            obstacles=[list(o) for o in self._obstacle_set],
            grid_size=self._grid_size,
            steps_remaining=self._max_steps - self._steps,
            carrying_package=self._carrying,
            message=message,
        )

    def _pkg_snapshot(self):
        return [dict(p) for p in self._packages]

    def _dist_to_nearest_undelivered(self, pos) -> float:
        undelivered = [p for p in self._packages if not p["delivered"]]
        if not undelivered:
            return 0.0
        return min(
            abs(pos[0]-p["position"][0]) + abs(pos[1]-p["position"][1])
            for p in undelivered
        )

    def _verify_reachability(self):
        """BFS from robot start — warns if any package is unreachable."""
        gs = self._grid_size
        obs = self._obstacle_set
        start = (self._robot_pos[0], self._robot_pos[1])

        visited = {start}
        queue = deque([start])
        while queue:
            cx, cy = queue.popleft()
            for dx, dy in _MOVE_DELTAS.values():
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < gs and 0 <= ny < gs and (nx, ny) not in obs and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))

        for p in self._packages:
            pkg = tuple(p["position"])
            if pkg not in visited:
                print(
                    f"[WARNING] Package {p['id']} at {list(pkg)} is NOT reachable "
                    f"from {list(start)} in episode {self._episode_id}!"
                )
import copy
from openenv.core import Environment
import sys, os
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
            {"id": "A", "position": [2,  2],  "deadline": 8,  "delivered": False},
            {"id": "B", "position": [14, 14], "deadline": 5,  "delivered": False},
            {"id": "C", "position": [7,  7],  "deadline": 10, "delivered": False},
            {"id": "D", "position": [3,  10], "deadline": 6,  "delivered": False},
            {"id": "E", "position": [11, 3],  "deadline": 9,  "delivered": False},
            {"id": "F", "position": [9,  11], "deadline": 7,  "delivered": False},
        ],
        "obstacles": [
            [1,5],[3,4],[5,2],[6,8],[8,6],[10,4],
            [4,12],[12,10],[2,9],[9,3],[7,14],[14,7],
            [6,11],[11,6],[13,2]
        ],
        "max_steps": 100,
    },
}

DELIVERY_ZONE = [0, 0]  # Robot must come here to deliver


class SmartWarehouseEnv(Environment):

    def reset(self, seed=None, episode_id=None, options=None, **kwargs) -> RobotObservation:
        options = options or {}
        self._task_level = options.get("task_level", "easy")

        cfg = copy.deepcopy(TASK_CONFIGS[self._task_level])
        self._grid_size       = cfg["grid_size"]
        self._packages        = cfg["packages"]
        self._obstacles       = cfg["obstacles"]
        self._max_steps       = cfg["max_steps"]
        self._steps           = 0
        self._robot_pos       = [0, 0]
        self._carrying        = None
        self._total_packages  = len(self._packages)
        self._delivered_count = 0
        self._episode_id      = episode_id or "ep_0"
        self._done            = False

        self._state = RobotState(
            episode_id=self._episode_id,
            step_count=0,
            task_level=self._task_level,
            total_packages=self._total_packages,
            delivered_count=0,
            grid_size=self._grid_size,
        )

        return RobotObservation(
            done=False,
            reward=None,
            robot_position=tuple(self._robot_pos),
            packages=self._pkg_snapshot(),
            obstacles=[tuple(o) for o in self._obstacles],
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
        reward  = -0.01  # step penalty every move
        message = ""

        # ── Deadline countdown every step ──────────────────────────
        for p in self._packages:
            if not p["delivered"] and p["deadline"] > 0:
                p["deadline"] -= 1
                if p["deadline"] == 0:
                    reward  -= 0.5
                    message += f"Package {p['id']} deadline expired! -0.5  "

        # ── Process the action ─────────────────────────────────────
        if action.action == "no_op":
            message = message or "No-op."

        elif action.action == "move":
            delta = {"up":(0,1), "down":(0,-1), "left":(-1,0), "right":(1,0)}
            dx, dy = delta.get(action.direction, (0,0))
            new_pos = [self._robot_pos[0]+dx, self._robot_pos[1]+dy]

            in_bounds = (0 <= new_pos[0] < self._grid_size and
                         0 <= new_pos[1] < self._grid_size)
            not_wall  = new_pos not in self._obstacles

            if in_bounds and not_wall:
                prev_d = self._dist_to_nearest_undelivered(self._robot_pos)
                self._robot_pos = new_pos
                new_d  = self._dist_to_nearest_undelivered(self._robot_pos)
                if new_d < prev_d:
                    reward  += 0.2
                    message  = message or f"Moved {action.direction} — closer to target! +0.2"
                else:
                    message  = message or f"Moved {action.direction}."
            else:
                reward  -= 0.5
                message  = message or f"Invalid move {action.direction} — boundary/obstacle! -0.5"

        elif action.action == "pick":
            picked = False
            for p in self._packages:
                if (not p["delivered"]
                        and p["position"] == self._robot_pos
                        and self._carrying is None):
                    self._carrying = p["id"]
                    picked = True
                    message = f"Picked up Package {p['id']}!"
                    break
            if not picked:
                message = message or "Nothing to pick here."

        elif action.action == "deliver":
            if self._carrying and self._robot_pos == DELIVERY_ZONE:
                for p in self._packages:
                    if p["id"] == self._carrying and not p["delivered"]:
                        p["delivered"]         = True
                        self._delivered_count += 1
                        pkg_id                 = self._carrying
                        self._carrying         = None
                        reward                += 1.0
                        message = f"Package {pkg_id} delivered to (0,0)! +1.0"
                        break
            elif self._carrying and self._robot_pos != DELIVERY_ZONE:
                reward  -= 0.2
                message  = "Wrong delivery spot! Bring package to (0,0). -0.2"
            else:
                message  = message or "Not carrying anything to deliver."

        # ── Episode termination check ──────────────────────────────
        all_done      = all(p["delivered"] for p in self._packages)
        timeout       = self._steps >= self._max_steps
        self._done    = all_done or timeout

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
            robot_position=tuple(self._robot_pos),
            packages=self._pkg_snapshot(),
            obstacles=[tuple(o) for o in self._obstacles],
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
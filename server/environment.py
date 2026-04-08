import copy
from openenv.core import Environment
import sys, os

# Setup paths to find modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import RobotAction, RobotObservation, RobotState
from core.engine import WarehouseEngine
from core.rewards import DefaultWarehouseRewards
from core.constants import TASK_CONFIGS

class SmartWarehouseEnv(Environment):
    """Clean Architecture Adapter for OpenEnv."""
    
    def __init__(self):
        super().__init__()
        self.engine: Optional[WarehouseEngine] = None
        self.reward_system = DefaultWarehouseRewards()
        self._task_level = "easy"
        self._episode_id = "ep_0"
        self._state = None

    def reset(self, seed=None, episode_id=None, options=None, **kwargs) -> RobotObservation:
        options = options or {}
        self._task_level = options.get("task_level", "easy")
        cfg = TASK_CONFIGS[self._task_level]
        
        # Initialize Engine
        self.engine = WarehouseEngine(
            grid_size=cfg["grid_size"],
            packages=cfg["packages"],
            obstacles=cfg["obstacles"],
            max_steps=cfg["max_steps"]
        )
        
        self._episode_id = episode_id or "ep_0"
        self.engine.verify_reachability()
        
        return self._make_observation(
            reward=None,
            message=f"Episode started! {self._task_level.upper()} task. {len(self.engine.packages)} packages."
        )

    def step(self, action: RobotAction, **kwargs) -> RobotObservation:
        if not self.engine or self.engine.done:
            return self._make_observation(0.0, "Episode already ended. Call reset().")

        self.engine.steps += 1
        # Step penalty always applied
        total_reward = self.reward_system.calculate("step")
        message = ""

        # 1. Tick Deadlines
        expired = self.engine.tick_deadlines()
        for _ in expired:
            total_reward += self.reward_system.calculate("expired")
            message += "Package expired! "

        # 2. Process Action
        act = action.act
        if act == "move":
            success = self.engine.move(action.direction)
            if success:
                total_reward += self.reward_system.calculate("move")
                message += f"Moved {action.direction}."
            else:
                total_reward += self.reward_system.calculate("wall_hit")
                message += "Hit wall! "

        elif act == "pick":
            pkg_id = self.engine.pick()
            if pkg_id:
                total_reward += self.reward_system.calculate("pick")
                message += f"Picked up {pkg_id}."
            else:
                message += "Nothing to pick here."

        elif act == "deliver":
            pkg_id = self.engine.deliver()
            if pkg_id:
                total_reward += self.reward_system.calculate("delivered")
                message += f"Delivered {pkg_id}!"
            else:
                # Penalty if they try to deliver at the wrong spot
                if self.engine.carrying_id:
                    total_reward += self.reward_system.calculate("wrong_spot")
                    message += "Wrong delivery spot!"
                else:
                    message += "Not carrying anything."

        # 3. Termination Check
        all_delivered = all(p["delivered"] for p in self.engine.packages)
        timeout = self.engine.steps >= self.engine.max_steps
        self.engine.done = all_delivered or timeout

        if self.engine.done:
            score = self.engine.delivered_count / len(self.engine.packages)
            message += f" | ENDED. Score: {score:.2f}"

        return self._make_observation(round(total_reward, 3), message)

    def _make_observation(self, reward: Optional[float], message: str) -> RobotObservation:
        return RobotObservation(
            done=self.engine.done if self.engine else False,
            reward=reward,
            robot_position=list(self.engine.robot_pos) if self.engine else [0,0],
            packages=[dict(p) for p in self.engine.packages] if self.engine else [],
            obstacles=[list(o) for o in self.engine.obstacles] if self.engine else [],
            grid_size=self.engine.grid_size if self.engine else 5,
            steps_remaining=(self.engine.max_steps - self.engine.steps) if self.engine else 20,
            carrying_package=self.engine.carrying_id if self.engine else None,
            message=message,
            delivered_count=self.engine.delivered_count if self.engine else 0,
            total_packages=len(self.engine.packages) if self.engine else 0,
        )

    def _dist_to_nearest_undelivered(self) -> float:
        undelivered = [p for p in self.engine.packages if not p["delivered"]]
        if not undelivered: return 0.0
        pos = self.engine.robot_pos
        return min(abs(pos[0]-p["position"][0]) + abs(pos[1]-p["position"][1]) for p in undelivered)

    @property
    def state(self) -> RobotState:
        if not self.engine: return RobotState()
        return RobotState(
            episode_id=self._episode_id,
            step_count=self.engine.steps,
            task_level=self._task_level,
            total_packages=len(self.engine.packages),
            delivered_count=self.engine.delivered_count,
            grid_size=self.engine.grid_size
        )

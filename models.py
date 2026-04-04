# models.py
# └─ Define data types (Pydantic)
# - RobotAction      (what agent can do)
# - RobotObservation (what agent sees + done/reward explicitly declared)
# - RobotState       (environment metadata)

from typing import List, Optional
import os
import torch
from pydantic import ConfigDict
from openenv.core.env_server import Action, Observation, State


def save_checkpoint(
    model: torch.nn.Module,
    epsilon: float,
    episode: int,
    checkpoint_dir: str = "checkpoints",
    checkpoint_name: str = "checkpoint.pt",
) -> str:
    os.makedirs(checkpoint_dir, exist_ok=True)
    filepath = os.path.join(checkpoint_dir, checkpoint_name)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "epsilon": epsilon,
            "episode": episode,
        },
        filepath,
    )
    return filepath


class RobotAction(Action):
    direction: str = "none"  # "up", "down", "left", "right", "none"
    action: str = "move"  # "move", "pick", "deliver", "no_op"


class RobotObservation(Observation):
    model_config = ConfigDict(extra="ignore")  # safely ignore unknown base class fields

    # Explicitly declared so obs.done and obs.reward ALWAYS work in inference.py
    done: bool = False  # FIX: explicitly declare — base class may call it differently
    reward: Optional[float] = (
        None  # FIX: explicitly declare — base class may call it differently
    )

    # Environment-specific fields
    robot_position: List[int] = [0, 0]
    grid_size: int = 5
    packages: List[dict] = []
    obstacles: List[List[int]] = []
    steps_remaining: int = 20
    carrying_package: Optional[str] = None
    message: str = ""
    delivered_count: int = 0
    total_packages: int = 0


class RobotState(State):
    model_config = ConfigDict(extra="ignore")  # safely ignore unknown base class fields

    # 'episode_id' and 'step_count' are inherited from State base class
    task_level: str = "easy"
    total_packages: int = 0
    delivered_count: int = 0
    grid_size: int = 5
    score: float = 0.0
    max_steps: int = 20

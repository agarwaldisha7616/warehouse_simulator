# models.py
#   └─ Define data types (Pydantic)
#      - RobotAction (what agent can do)
#      - RobotObservation (what agent sees)
#      - RobotState (environment response)

from typing import List, Optional
from openenv.core.env_server import Action, Observation, State


class RobotAction(Action):
    direction: str = "none"   # "up", "down", "left", "right", "none"
    action_type: str = "move" # "move", "pick", "deliver"


class PackageInfo(dict):
    pass


class RobotObservation(Observation):
    # 'done' and 'reward' are already in Observation base class — FREE
    robot_position: List[int] = [0, 0]          # [row, col]
    grid_size: int = 5                            # 5, 10, or 15
    packages: List[dict] = []                     # list of package dicts
    obstacles: List[List[int]] = []               # list of [row, col]
    steps_remaining: int = 20                     # steps left
    carrying_package: Optional[str] = None        # "A", "B" or None
    message: str = ""                             # feedback message
    delivered_count: int = 0                      # how many delivered
    total_packages: int = 0                       # total packages


class RobotState(State):
    # 'episode_id' and 'step_count' are already in State base class — FREE
    task_level: int = 1
    total_packages: int = 0
    delivered_packages: int = 0
    score: float = 0.0
    max_steps: int = 20
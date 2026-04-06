# models.py
from typing import List, Optional
import os
import torch
from pydantic import ConfigDict, BaseModel
from openenv.core.env_server import Action, Observation, State

class RobotAction(Action):
    model_config = ConfigDict(extra="allow")
    direction: str = "none"  # "up", "down", "left", "right", "none"
    act: str = "move"        # "move", "pick", "deliver", "no_op"
    reasoning: Optional[str] = None
    target: Optional[str] = None

class RobotObservation(Observation):
    model_config = ConfigDict(extra="ignore")
    done: bool = False
    reward: Optional[float] = None
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
    model_config = ConfigDict(extra="ignore")
    task_level: str = "easy"
    total_packages: int = 0
    delivered_count: int = 0
    grid_size: int = 5
    score: float = 0.0
    max_steps: int = 20

class LLMRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = "default"

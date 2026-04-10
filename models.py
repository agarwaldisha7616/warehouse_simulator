from typing import Dict, List, Optional, Union

from pydantic import ConfigDict, BaseModel
from openenv.core.env_server import Action, Observation, State


class RobotAction(Action):
    model_config = ConfigDict(extra="allow")
    agent_id: str = "robot_1"
    direction: str = "none"
    action: str = "no_op"
    target: Optional[str] = None
    reasoning: Optional[str] = None


class RobotObservation(Observation):
    model_config = ConfigDict(extra="ignore")
    done: bool = False
    reward: Optional[float] = None
    robot_position: List[int] = [0, 0]
    carrying_package: Optional[str] = None
    robots: Dict[str, Dict[str, Union[List[int], Optional[str]]]] = {}
    grid_size: int = 5
    packages: List[dict] = []
    obstacles: List[List[int]] = []
    steps_remaining: int = 20
    message: str = ""
    delivered_count: int = 0
    total_packages: int = 0
    next_agent_id: str = "robot_1"
    last_action: Optional[str] = None
    last_action_agent_id: Optional[str] = None
    last_action_failed: bool = False
    collision_reason: Optional[str] = None
    failed_action_count: int = 0
    expired_package_count: int = 0
    progress_score: float = 0.0


class RobotState(State):
    model_config = ConfigDict(extra="ignore")
    task_level: str = "easy"
    total_packages: int = 0
    delivered_count: int = 0
    grid_size: int = 5
    score: float = 0.0
    max_steps: int = 20
    episode_id: str = "ep_0"
    step_count: int = 0
    next_agent_id: str = "robot_1"
    failed_action_count: int = 0
    expired_package_count: int = 0
    all_delivered: bool = False


class LLMRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = "default"

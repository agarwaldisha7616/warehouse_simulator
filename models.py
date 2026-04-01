# models.py
#   └─ Define data types (Pydantic)
#      - RobotAction (what agent can do)
#      - RobotObservation (what agent sees)
#      - RobotState (environment response)
from pydantic import BaseModel
from typing import Optional

class RobotAction(BaseModel):
    """
    What robot can do in one step
    Example:
      RobotAction(direction="right", intent="move")
    """                                         
    direction: str  # "up", "down", "left", "right", "none"
    intent: str     # "move", "pick", "dilever"

class RobotObservation(BaseModel):
    """
    What the robot sees/Knows
    
    Example
    obs.robot_x = 0
    obs.robot_y = 0
    obs.package = {...}
    """

    # Position of the robot in 2D grid
    robot_x: int    # Horizontal {Column}
    robot_y: int    # Vertical {Row}
    holding: Optional[str]  # which package robot is holding (if any)
    packages: dict 
    time_elapsed: int # Count of steps since start of episode
    time_remaining: int # Count of steps remaining in the episode
    grid: list 
    
class RobotState(BaseModel):
    """
    What environment returns after each step 
    
    Contains everything step() should returns
    """


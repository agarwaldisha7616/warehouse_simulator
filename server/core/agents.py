from abc import ABC, abstractmethod
from collections import deque
from typing import List, Tuple, Optional
from models import RobotAction, RobotObservation

class BaseAgent(ABC):
    @abstractmethod
    def act(self, observation: RobotObservation) -> RobotAction:
        pass

class GreedyAgent(BaseAgent):
    """A pathfinding-aware greedy agent using BFS."""
    
    def act(self, obs: RobotObservation) -> RobotAction:
        rx, ry = obs.robot_position
        
        # 1. Determine Target
        if obs.carrying_package:
            # Go to Delivery Zone
            if rx == 0 and ry == 0:
                return RobotAction(direction="none", act="deliver")
            target = (0, 0)
        else:
            # Find nearest undelivered package
            undelivered = [p for p in obs.packages if not p["delivered"]]
            if not undelivered:
                return RobotAction(direction="none", act="no_op")
            
            # Simple heuristic to pick the closest package based on Manhattan distance first
            closest_pkg = min(undelivered, key=lambda p: abs(p["position"][0]-rx) + abs(p["position"][1]-ry))
            target = tuple(closest_pkg["position"])
            
            if rx == target[0] and ry == target[1]:
                return RobotAction(direction="none", act="pick")

        # 2. Find Path to Target using BFS
        direction = self._get_next_direction(rx, ry, target[0], target[1], obs.grid_size, obs.obstacles)
        
        if direction:
            return RobotAction(direction=direction, act="move")
        
        return RobotAction(direction="none", act="no_op")

    def _get_next_direction(self, rx: int, ry: int, tx: int, ty: int, grid_size: int, obstacles: List[List[int]]) -> Optional[str]:
        """BFS to find the first move of the shortest path to target."""
        start = (rx, ry)
        target = (tx, ty)
        
        # If already at target, no move needed
        if start == target:
            return None
            
        obstacle_set = {tuple(o) for o in obstacles}
        
        queue = deque([(start, [])])
        visited = {start}
        
        # Priority order to prefer straight paths
        moves = [
            ("up", (0, 1)),
            ("down", (0, -1)),
            ("left", (-1, 0)),
            ("right", (1, 0))
        ]

        while queue:
            (cx, cy), path = queue.popleft()
            
            if (cx, cy) == target:
                return path[0] if path else None

            for name, (dx, dy) in moves:
                nx, ny = cx + dx, cy + dy
                
                # STRICT BOUNDARY AND OBSTACLE CHECKS
                if (0 <= nx < grid_size and 
                    0 <= ny < grid_size and 
                    (nx, ny) not in obstacle_set and 
                    (nx, ny) not in visited):
                    
                    visited.add((nx, ny))
                    new_path = path + [name]
                    queue.append(((nx, ny), new_path))
        
        # Fallback: if no path found, don't move
        return None

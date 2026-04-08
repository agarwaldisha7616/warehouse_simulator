import copy
from collections import deque
from typing import List, Tuple, Dict, Optional, Set

MOVE_DELTAS = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}

class WarehouseEngine:
    """The 'Physics' and State Engine of the Simulator."""
    
    def __init__(self, grid_size: int, packages: List[dict], obstacles: List[List[int]], max_steps: int):
        self.grid_size = grid_size
        self.initial_packages = copy.deepcopy(packages)
        self.packages = copy.deepcopy(packages)
        self.obstacles = [tuple(o) for o in obstacles]
        self.obstacle_set = frozenset(self.obstacles)
        self.max_steps = max_steps
        
        # State
        self.robot_pos = [0, 0]
        self.carrying_id = None
        self.steps = 0
        self.delivered_count = 0
        self.done = False

    def reset(self):
        self.robot_pos = [0, 0]
        self.carrying_id = None
        self.steps = 0
        self.delivered_count = 0
        self.done = False
        self.packages = copy.deepcopy(self.initial_packages)

    def move(self, direction: str) -> bool:
        """Execute movement. Returns True if move was successful (no wall hit)."""
        if direction not in MOVE_DELTAS:
            return False
            
        dx, dy = MOVE_DELTAS[direction]
        nx, ny = self.robot_pos[0] + dx, self.robot_pos[1] + dy
        
        if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size and (nx, ny) not in self.obstacle_set:
            self.robot_pos = [nx, ny]
            return True
        return False

    def pick(self) -> Optional[str]:
        """Attempt to pick up a package at current position."""
        if self.carrying_id is not None:
            return None
            
        for p in self.packages:
            if not p["delivered"] and p["position"] == self.robot_pos:
                self.carrying_id = p["id"]
                return p["id"]
        return None

    def deliver(self) -> Optional[str]:
        """Attempt to deliver current package at (0,0)."""
        if self.carrying_id and self.robot_pos == [0, 0]:
            pkg_id = self.carrying_id
            for p in self.packages:
                if p["id"] == pkg_id:
                    p["delivered"] = True
                    self.delivered_count += 1
                    self.carrying_id = None
                    return pkg_id
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
        """BFS to ensure all packages are reachable."""
        start = tuple(self.robot_pos)
        visited = {start}
        queue = deque([start])
        while queue:
            cx, cy = queue.popleft()
            for dx, dy in MOVE_DELTAS.values():
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size and (nx, ny) not in self.obstacle_set and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
        return all(tuple(p["position"]) in visited for p in self.packages)

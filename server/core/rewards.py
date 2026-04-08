from abc import ABC, abstractmethod
from typing import Optional

class BaseRewardSystem(ABC):
    @abstractmethod
    def calculate(self, event: str, **kwargs) -> float:
        pass

class DefaultWarehouseRewards(BaseRewardSystem):
    """Reward system for the warehouse simulator."""
    
    def __init__(self):
        self.VALID_MOVE = 1.0
        self.WALL_PENALTY = -5.0
        self.DELIVERY_SUCCESS = 10.0
        self.DEADLINE_EXPIRED = -2.0
        self.PICK_UP = 2.0
        self.WRONG_DELIVERY_SPOT = -2.0
        self.FAILURE_STREAK_PENALTY = -1.0
        self.failure_streak = 0

    def calculate(self, event: str, **kwargs) -> float:
        reward = 0.0
        
        if event == "move":
            reward = self.VALID_MOVE
            self.failure_streak = 0
        elif event == "wall_hit":
            self.failure_streak += 1
            reward = self.WALL_PENALTY + (self.failure_streak * self.FAILURE_STREAK_PENALTY)
        elif event == "delivered":
            reward = self.DELIVERY_SUCCESS
            self.failure_streak = 0
        elif event == "pick":
            reward = self.PICK_UP
            self.failure_streak = 0
        elif event == "expired":
            reward = self.DEADLINE_EXPIRED
        elif event == "wrong_spot":
            self.failure_streak += 1
            reward = self.WRONG_DELIVERY_SPOT + (self.failure_streak * self.FAILURE_STREAK_PENALTY)
        elif event == "step":
            # Small step penalty to encourage speed
            reward = -0.1
            
        return float(reward)

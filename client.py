# client.py
# └─ Adapter between Python code and the running environment server
# - Serializes RobotAction → JSON payload for /step
# - Deserializes JSON response → RobotObservation and RobotState

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Any, Dict
from openenv.core import EnvClient
from models import RobotAction, RobotObservation, RobotState


class WarehouseClient(EnvClient):

    def _step_payload(self, action: RobotAction) -> Dict[str, Any]:
        return {
            "direction": action.direction,
            "act": action.act,
        }

    def _parse_result(self, payload: Dict[str, Any]) -> RobotObservation:
        # The server returns { "observation": {...}, "reward": ..., "done": ..., "info": ... }
        # We need to flatten this for the RobotObservation model
        obs_data = payload.get("observation", {})
        flat_payload = {**payload, **obs_data}
        
        # safe parse — filter out any extra/inherited fields server may return
        res = RobotObservation(**{
            k: v for k, v in flat_payload.items()
            if k in RobotObservation.model_fields
        })
        return res

    def _parse_state(self, payload: Dict[str, Any]) -> RobotState:
        # RobotState is correctly kept — _parse_state is a framework contract
        # even if inference.py doesn't call client.state right now
        return RobotState(**{
            k: v for k, v in payload.items()
            if k in RobotState.model_fields
        })
    
    # Override async methods to make them sync-compatible
    def reset(self, seed=None, options=None, **kwargs):
        """Synchronous wrapper for reset"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            super().reset(seed=seed, options=options, **kwargs)
        )
    
    def step(self, action, **kwargs):
        """Synchronous wrapper for step"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            super().step(action, **kwargs)
        )

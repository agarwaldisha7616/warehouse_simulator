# client.py
# └─ Adapter between Python code and the running environment server

import sys, os
from typing import Any, Dict
from openenv.core import EnvClient
from models import RobotAction, RobotObservation, RobotState

class WarehouseClient(EnvClient):

    def _step_payload(self, action: RobotAction) -> Dict[str, Any]:
        return {
            "agent_id": action.agent_id,
            "direction": action.direction,
            "action": action.action,
            "target": action.target,
        }

    def _parse_result(self, payload: Dict[str, Any]) -> RobotObservation:
        # The server returns { "observation": {...}, "reward": ..., "done": ..., "info": ... }
        obs_data = payload.get("observation", {})
        flat_payload = {**payload, **obs_data}
        
        res = RobotObservation(**{
            k: v for k, v in flat_payload.items()
            if k in RobotObservation.model_fields
        })
        return res

    def _parse_state(self, payload: Dict[str, Any]) -> RobotState:
        return RobotState(**{
            k: v for k, v in payload.items()
            if k in RobotState.model_fields
        })

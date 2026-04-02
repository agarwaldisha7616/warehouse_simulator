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
            "action": action.action,       # correct — field is named 'action' in models.py
        }

    def _parse_result(self, payload: Dict[str, Any]) -> RobotObservation:
        # safe parse — filter out any extra/inherited fields server may return
        return RobotObservation(**{
            k: v for k, v in payload.items()
            if k in RobotObservation.model_fields
        })

    def _parse_state(self, payload: Dict[str, Any]) -> RobotState:
        # RobotState is correctly kept — _parse_state is a framework contract
        # even if inference.py doesn't call client.state right now
        return RobotState(**{
            k: v for k, v in payload.items()
            if k in RobotState.model_fields
        })
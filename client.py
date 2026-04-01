# client.py
from typing import Any, Dict
from openenv.core import EnvClient
from models import RobotAction, RobotObservation, RobotState
class WarehouseClient(EnvClient):

    def _step_payload(self, action: RobotAction) -> Dict[str, Any]:
        return {"direction": action.direction, "action": action.action}

    def _parse_result(self, payload: Dict[str, Any]) -> RobotObservation:
        return RobotObservation(**payload)

    def _parse_state(self, payload: Dict[str, Any]) -> RobotState:
        return RobotState(**payload)
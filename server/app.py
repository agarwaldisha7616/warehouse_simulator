import os
import threading
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openenv.core.env_server import create_fastapi_app

from models import LLMRequest, RobotAction, RobotObservation
from server.core.agents import MultiRobotCoordinator, task_to_robot_action
from server.core.constants import TASK_CONFIGS
from server.core.llm import LLMPlanningError, Task, WarehouseLLM, heuristic_plan
from server.environment import SmartWarehouseEnv


ALLOW_HEURISTIC_FALLBACK = os.getenv("ALLOW_HEURISTIC_FALLBACK", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class UIResetRequest(BaseModel):
    options: Dict[str, Any] = Field(default_factory=dict)


class UIStepRequest(BaseModel):
    action: RobotAction


class UIObservationResponse(BaseModel):
    done: bool
    reward: Optional[float]
    observation: RobotObservation


class DemoSession:
    def __init__(self):
        self._lock = threading.Lock()
        self._env: Optional[SmartWarehouseEnv] = None
        self._observation: Optional[RobotObservation] = None
        self._coordinator = MultiRobotCoordinator()

    def reset(self, task_level: str) -> RobotObservation:
        with self._lock:
            self._env = SmartWarehouseEnv()
            self._coordinator.reset()
            self._observation = self._env.reset(options={"task_level": task_level})
            return self._observation

    def get_observation(self) -> RobotObservation:
        with self._lock:
            if self._observation is None:
                raise HTTPException(status_code=409, detail="Demo session is not initialized.")
            return self._observation

    def step(self, action: RobotAction) -> RobotObservation:
        with self._lock:
            if self._env is None or self._observation is None:
                raise HTTPException(status_code=409, detail="Demo session is not initialized.")
            self._observation = self._env.step(action)
            return self._observation

    def greedy_action(self) -> RobotAction:
        with self._lock:
            if self._observation is None:
                raise HTTPException(status_code=409, detail="Demo session is not initialized.")
            return self._coordinator.get_action(
                self._observation,
                agent_id=self._observation.next_agent_id,
            )


app: FastAPI = create_fastapi_app(SmartWarehouseEnv, RobotAction, RobotObservation)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
demo_session = DemoSession()


def _ui_response(observation: RobotObservation) -> UIObservationResponse:
    return UIObservationResponse(
        done=observation.done,
        reward=observation.reward,
        observation=observation,
    )


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "smart-warehouse-simulator",
        "openenv_endpoints": ["/reset", "/step", "/state", "/ws", "/schema"],
        "ui_endpoints": [
            "/ui/reset",
            "/ui/step",
            "/ui/state",
            "/ui/agent_action",
            "/ui/task_to_action",
            "/ui/llm_plan",
        ],
    }


@app.post("/ui/reset", response_model=UIObservationResponse)
def ui_reset(request: UIResetRequest) -> UIObservationResponse:
    task_level = request.options.get("task_level", "easy")
    if task_level not in TASK_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown task level '{task_level}'.")
    observation = demo_session.reset(task_level)
    return _ui_response(observation)


@app.get("/ui/state", response_model=UIObservationResponse)
def ui_state() -> UIObservationResponse:
    return _ui_response(demo_session.get_observation())


@app.post("/ui/step", response_model=UIObservationResponse)
def ui_step(request: UIStepRequest) -> UIObservationResponse:
    observation = demo_session.step(request.action)
    return _ui_response(observation)


@app.get("/ui/agent_action", response_model=RobotAction)
def ui_agent_action() -> RobotAction:
    return demo_session.greedy_action()


@app.post("/ui/task_to_action", response_model=RobotAction)
def ui_task_to_action(task: Task) -> RobotAction:
    observation = demo_session.get_observation()
    return task_to_robot_action(
        observation,
        task_action=task.action,
        agent_id=task.agent_id,
        target=task.target,
        direction=task.direction,
    )


@app.post("/ui/llm_plan")
def ui_llm_plan(request: LLMRequest):
    observation = demo_session.get_observation()
    observation_payload = observation.model_dump()

    try:
        planner = WarehouseLLM()
        plan = planner.get_plan(request.prompt, observation_payload)
    except LLMPlanningError as exc:
        if not ALLOW_HEURISTIC_FALLBACK:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        plan = heuristic_plan(request.prompt, observation_payload)

    return plan.model_dump()


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("server.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

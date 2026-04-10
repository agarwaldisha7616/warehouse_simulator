from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _get_attr(source: Any, key: str, default: Any = 0) -> Any:
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _state_snapshot(final_state: Any) -> dict[str, float]:
    delivered_count = float(_get_attr(final_state, "delivered_count", 0))
    total_packages = max(1.0, float(_get_attr(final_state, "total_packages", 0)))
    step_count = float(_get_attr(final_state, "step_count", 0))
    max_steps = max(1.0, float(_get_attr(final_state, "max_steps", 1)))
    failed_action_count = float(_get_attr(final_state, "failed_action_count", 0))
    expired_package_count = float(_get_attr(final_state, "expired_package_count", 0))
    state_score = _get_attr(final_state, "score", None)

    completion = _clip(delivered_count / total_packages)
    efficiency = _clip((max_steps - step_count) / max_steps)
    safety = _clip(1.0 - (failed_action_count / max(1.0, step_count)))
    deadline_health = _clip(1.0 - (expired_package_count / total_packages))
    if state_score is None:
        state_score = completion * 0.85 + efficiency * 0.15

    return {
        "completion": completion,
        "efficiency": efficiency,
        "safety": safety,
        "deadline_health": deadline_health,
        "state_score": _clip(float(state_score)),
    }


TASK_WEIGHTS = {
    "easy": {
        "completion": 0.45,
        "efficiency": 0.15,
        "safety": 0.10,
        "deadline_health": 0.05,
        "state_score": 0.25,
    },
    "medium": {
        "completion": 0.40,
        "efficiency": 0.15,
        "safety": 0.10,
        "deadline_health": 0.10,
        "state_score": 0.25,
    },
    "hard": {
        "completion": 0.40,
        "efficiency": 0.20,
        "safety": 0.10,
        "deadline_health": 0.10,
        "state_score": 0.20,
    },
}


def grade_task(task_id: str, final_state: Any, trajectory: Any = None) -> float:
    del trajectory
    weights = TASK_WEIGHTS[task_id]
    snapshot = _state_snapshot(final_state)
    score = sum(weights[key] * snapshot[key] for key in weights)
    return _clip(score)

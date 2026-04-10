from __future__ import annotations

from typing import Any

from tasks.common import grade_task


def grade(final_state: Any, trajectory: Any = None) -> float:
    return grade_task("hard", final_state, trajectory)

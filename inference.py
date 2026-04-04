# inference.py
#   └─ Test script
#      - Creates environment
#      - Runs random agent
#      - Measures score

import os
import json
import random
from client import WarehouseClient
from models import RobotAction

ENV_URL    = os.environ.get("ENV_URL", "http://localhost:7860")
TASK_LEVELS = ["easy", "medium", "hard"]


def _direction_towards(fx, fy, tx, ty) -> str:
    if abs(tx - fx) >= abs(ty - fy):
        return "right" if tx > fx else "left"
    return "up" if ty > fy else "down"


def run_greedy_episode(client: WarehouseClient, task_level: str) -> float:
    """
    Greedy baseline agent:
    - Not carrying → go to nearest undelivered package → pick
    - Carrying      → go back to (0,0)                → deliver
    """
    obs = client.reset(options={"task_level": task_level})

    while not obs.done:
        rx, ry = obs.robot_position

        if obs.carrying_package is None:
            undelivered = [p for p in obs.packages if not p["delivered"]]
            if not undelivered:
                action = RobotAction(direction="up", action="no_op")
            else:
                target = min(
                    undelivered,
                    key=lambda p: abs(p["position"][0]-rx) + abs(p["position"][1]-ry)
                )
                tx, ty = target["position"]
                if [rx, ry] == [tx, ty]:
                    action = RobotAction(direction="up", action="pick")
                else:
                    action = RobotAction(
                        direction=_direction_towards(rx, ry, tx, ty),
                        action="move"
                    )
        else:
            if [rx, ry] == [0, 0]:
                action = RobotAction(direction="up", action="deliver")
            else:
                action = RobotAction(
                    direction=_direction_towards(rx, ry, 0, 0),
                    action="move"
                )

        obs = client.step(action)

    delivered = sum(1 for p in obs.packages if p["delivered"])
    total     = len(obs.packages)
    return round(delivered / total if total > 0 else 0.0, 4)


def main():
    client  = WarehouseClient(base_url=ENV_URL)
    results = {}

    print(f"\n{'='*52}")
    print(f"  Warehouse Simulator — Baseline Inference")
    print(f"  Environment: {ENV_URL}")
    print(f"{'='*52}\n")

    for task in TASK_LEVELS:
        score           = run_greedy_episode(client, task_level=task)
        results[task]   = score
        print(f"  Task [{task:>6}]  →  Score: {score:.4f}")

    overall = sum(results.values()) / len(results)
    print(f"\n  Overall Average: {overall:.4f}")
    print(f"{'='*52}\n")
    print(json.dumps(results))   # judges parse this line
    return results


if __name__ == "__main__":
    main()

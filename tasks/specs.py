from __future__ import annotations

import copy
from typing import Any, Dict


TaskDefinition = Dict[str, Any]


TASK_DEFINITIONS: Dict[str, TaskDefinition] = {
    "easy": {
        "name": "Easy Warehouse",
        "description": (
            "Coordinate 2 robots on a 6x6 grid to deliver 2 packages while "
            "navigating a light obstacle layout."
        ),
        "difficulty": "easy",
        "expected_score_random": 0.12,
        "grader": "tasks.easy.grader:grade",
        "config": {
            "num_robots": 2,
            "grid_size": 6,
            "robot_starts": [[0, 0], [0, 1]],
            "packages": [
                {"id": "A", "position": [2, 3], "deadline": 36, "delivered": False},
                {"id": "B", "position": [4, 4], "deadline": 36, "delivered": False},
            ],
            "obstacles": [[2, 1], [3, 1]],
            "max_steps": 48,
        },
    },
    "medium": {
        "name": "Medium Warehouse",
        "description": (
            "Coordinate 2 robots on a 10x10 grid to deliver 4 packages with "
            "tighter routing pressure and denser obstacles."
        ),
        "difficulty": "medium",
        "expected_score_random": 0.05,
        "grader": "tasks.medium.grader:grade",
        "config": {
            "num_robots": 2,
            "grid_size": 10,
            "robot_starts": [[0, 0], [0, 1]],
            "packages": [
                {"id": "A", "position": [2, 7], "deadline": 112, "delivered": False},
                {"id": "B", "position": [5, 4], "deadline": 112, "delivered": False},
                {"id": "C", "position": [8, 8], "deadline": 112, "delivered": False},
                {"id": "D", "position": [7, 2], "deadline": 112, "delivered": False},
            ],
            "obstacles": [
                [2, 2],
                [2, 3],
                [2, 4],
                [4, 6],
                [5, 6],
                [6, 6],
                [7, 4],
                [7, 5],
            ],
            "max_steps": 128,
        },
    },
    "hard": {
        "name": "Hard Warehouse",
        "description": (
            "Coordinate 3 robots on a 15x15 grid to deliver 6 packages under "
            "heavy routing pressure and a dense obstacle field."
        ),
        "difficulty": "hard",
        "expected_score_random": 0.01,
        "grader": "tasks.hard.grader:grade",
        "config": {
            "num_robots": 3,
            "grid_size": 15,
            "robot_starts": [[0, 0], [0, 1], [1, 0]],
            "packages": [
                {"id": "A", "position": [3, 12], "deadline": 260, "delivered": False},
                {"id": "B", "position": [5, 5], "deadline": 260, "delivered": False},
                {"id": "C", "position": [8, 13], "deadline": 260, "delivered": False},
                {"id": "D", "position": [10, 7], "deadline": 260, "delivered": False},
                {"id": "E", "position": [11, 2], "deadline": 260, "delivered": False},
                {"id": "F", "position": [13, 10], "deadline": 260, "delivered": False},
            ],
            "obstacles": [
                [4, 1],
                [4, 2],
                [4, 3],
                [4, 7],
                [4, 8],
                [4, 9],
                [6, 12],
                [7, 12],
                [8, 12],
                [7, 4],
                [8, 4],
                [9, 4],
                [10, 10],
                [11, 10],
                [12, 10],
                [11, 6],
                [12, 6],
            ],
            "max_steps": 300,
        },
    },
}


TASK_CONFIGS: Dict[str, Dict[str, Any]] = {
    task_id: copy.deepcopy(definition["config"])
    for task_id, definition in TASK_DEFINITIONS.items()
}

OPENENV_TASKS = [
    {
        "id": task_id,
        "name": definition["name"],
        "description": definition["description"],
        "difficulty": definition["difficulty"],
        "expected_score_random": f"{definition['expected_score_random']:.2f}",
        "grader": definition["grader"],
    }
    for task_id, definition in TASK_DEFINITIONS.items()
]

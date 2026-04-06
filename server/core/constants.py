TASK_CONFIGS = {
    "easy": {
        "grid_size": 5,
        "packages": [
            {"id": "A", "position": [2, 2], "deadline": 25, "delivered": False},
            {"id": "B", "position": [3, 3], "deadline": 25, "delivered": False},
        ],
        "obstacles": [],
        "max_steps": 40,
    },
    "medium": {
        "grid_size": 10,
        "packages": [
            {"id": "A", "position": [2, 2], "deadline": 40, "delivered": False},
            {"id": "B", "position": [8, 8], "deadline": 35, "delivered": False},
            {"id": "C", "position": [5, 5], "deadline": 45, "delivered": False},
            {"id": "D", "position": [3, 7], "deadline": 30, "delivered": False},
        ],
        "obstacles": [[1,3],[4,6],[6,2],[7,8],[9,4]],
        "max_steps": 100,
    },
    "hard": {
        "grid_size": 15,
        "packages": [
            {"id": "A", "position": [2, 2],   "deadline": 60,  "delivered": False},
            {"id": "B", "position": [14, 14],  "deadline": 50,  "delivered": False},
            {"id": "C", "position": [7, 7],    "deadline": 70, "delivered": False},
            {"id": "D", "position": [3, 10],   "deadline": 55,  "delivered": False},
            {"id": "E", "position": [11, 3],   "deadline": 65,  "delivered": False},
            {"id": "F", "position": [9, 11],   "deadline": 55,  "delivered": False},
        ],
        "obstacles": [
            [1,5],[3,4],[5,2],[6,8],[8,6],[10,4],
            [4,12],[12,10],[2,9],[9,3],[7,14],[14,7],
            [6,11],[11,6],[13,2]
        ],
        "max_steps": 250,
    },
}

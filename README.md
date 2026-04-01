# Smart Warehouse Simulator 

A sophisticated warehouse robot simulation environment built on top of the **OpenEnv** framework. In this environment, an AI agent navigates a grid warehouse, picks up packages, and delivers them to a designated zone `(0,0)` under constrained time deadlines.

## Features

- **OpenEnv Integration**: Fully compatible `Environment` and `EnvClient` wrappers.
- **Dynamic Task Grid**: Configurable grid size with obstacles and wall placements.
- **Time Constraints**: Each package has a strict delivery deadline.
- **Multi-Level Difficulty**: Built-in 3 levels (Easy, Medium, Hard) to evaluate agent capabilities progressively.
- **FastAPI Backend Server**: Exposes the environment interface over an HTTP API.

## Installation & Setup

1. **Install Dependencies:**
   Ensure you have Python 3.11+ installed.
   ```bash
   pip install -r requirements.txt
   # OR using pyproject.toml
   pip install -e .
   ```

2. **Run the Environment Server:**
   The server runs on FastAPI and Uvicorn.
   ```bash
   uvicorn server.app:app --host 0.0.0.0 --port 8000
   ```

3. **Run the Client / Inference Agent:**
   ```bash
   python inference.py
   ```

## How it Works (Flow)

```text
EPISODE START:

1. env.reset()
    |--- Initialize grid, robot at (0,0), place packages
    |--- Return initial observation

2. Agent sees Observation 
    |--- Robot at (0,0), packages at various initial locations

3. Agent decides action
    |--- RobotAction(direction="right", action="move")

4. env.step(action)
    |--- Update robot position (0,0) → (1,0)
    |--- Check if at package location -> No 
    |--- Update time (deadline countdown)
    |--- Calculate reward -> -0.01 (Just moved, wasted time)
    |--- Check if done -> No
    |--- Return: Observation, reward (-0.01), done (False), info

5. Agent learns 
    |--- That move got -0.01, not good

6. Repeat step 3-5 until done

EPISODE END:

When done=True:
  |--- All packages delivered OR max steps reached
  |--- Calculate total score
  |--- env.reset() for next episode
```

## REWARD STRUCTURE (Scoring)

```text
REWARD SYSTEM:

+1.0   = Package delivered successfully
+0.2   = Moved closer to target package
-0.01  = Each step (efficiency penalty, hurry!)
-0.5   = Missed package deadline
-0.2   = Delivered wrong package to destination
-0.5   = Invalid action (moved into boundary/obstacle)
0.0    = No-op action

"Agent learns:"
    "Delivery = BIG +1.0"
    "Each step = small -0.01"
    "Missing deadline = BIG -0.5"
    "Therefore: Hurry, pick urgent packages first"
```

##  Task Configuration (3 Levels)

### EASY TASK (LEVEL 1)
- **Grid Size**: 5x5
- **Robot**: (0,0)
- **Packages**: 2 packages (Deadlines: 15)
- **Obstacles**: NONE
- **Max Steps**: 20
- **Difficulty**: Simple
- **What agent learns**: Just pick and deliver
- **Expected Score**: `~0.4-0.6` (random agent sometimes succeeds)

### MEDIUM TASK (LEVEL 2)
- **Grid Size**: 10x10
- **Robot**: (0,0)
- **Packages**: 4 packages (Deadlines: 7-12)
- **Obstacles**: 5 Walls
- **Max Steps**: 50
- **Difficulty**: Moderate
- **What agent learns**: Pick urgent packages first
- **Expected Score**: `~0.2-0.4` (random agent rarely succeeds)

### HARD TASK (LEVEL 3)
- **Grid Size**: 15x15
- **Robot**: (0, 0)
- **Packages**: 6 packages (Deadlines: 5-10)
- **Obstacles**: 15 walls (maze-like)
- **Max Steps**: 100
- **Difficulty**: Complex
- **What agent learns**: Optimize complex priorities
- **Expected Score**: `~0.05-0.15` (random agent almost never succeeds)
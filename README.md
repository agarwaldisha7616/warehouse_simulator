# Smart Warehouse Simulator

A sophisticated warehouse robot simulation environment built on top of the **OpenEnv** framework. An AI agent navigates a configurable grid warehouse, picks up packages, and delivers them to a designated zone `(0,0)` under constrained time deadlines.

---

## Project Structure

```
warehouse_simulator/
├── models.py            # Pydantic data models (RobotAction, RobotObservation, RobotState)
├── client.py            # HTTP client — serializes actions, deserializes observations
├── inference.py         # Greedy baseline agent — runs episodes and reports score
├── requirements.txt     # Python dependencies
├── openenv.yaml         # OpenEnv configuration
├── .dockerignore        # Docker build exclusions
└── server/
    ├── app.py           # FastAPI app entry point
    ├── environment.py   # Core simulation logic (SmartWarehouseEnv)
    └── Dockerfile       # Container build (build context = project root)
```

---

## Features

- **OpenEnv Integration**: Fully compatible `Environment` and `EnvClient` wrappers
- **Dynamic Task Grid**: Configurable grid (5×5 / 10×10 / 15×15) with obstacles
- **Time Constraints**: Each package has a per-step deadline countdown
- **Multi-Level Difficulty**: Easy / Medium / Hard difficulty levels
- **FastAPI Backend**: Exposes environment over HTTP — local or Docker/HF Spaces
- **Greedy Baseline Agent**: Nearest-first greedy policy in `inference.py`
- **Pydantic v2**: All models use strict typing with `ConfigDict(extra="ignore")`

---

## Data Models (`models.py`)

### `RobotAction`
| Field | Type | Values |
|---|---|---|
| `direction` | `str` | `"up"`, `"down"`, `"left"`, `"right"`, `"none"` |
| `action` | `str` | `"move"`, `"pick"`, `"deliver"`, `"no_op"` |

### `RobotObservation`
| Field | Type | Description |
|---|---|---|
| `done` | `bool` | Episode ended flag |
| `reward` | `Optional[float]` | Step reward |
| `robot_position` | `List[int]` | `[row, col]` |
| `grid_size` | `int` | Grid dimension |
| `packages` | `List[dict]` | Package list with position, deadline, delivered |
| `obstacles` | `List[List[int]]` | Wall positions |
| `steps_remaining` | `int` | Steps until timeout |
| `carrying_package` | `Optional[str]` | Package ID being carried, or `None` |
| `message` | `str` | Human-readable step feedback |
| `delivered_count` | `int` | Packages delivered so far |
| `total_packages` | `int` | Total packages in episode |

### `RobotState`
| Field | Type | Description |
|---|---|---|
| `episode_id` | `str` | From base `State` class |
| `step_count` | `int` | From base `State` class |
| `task_level` | `str` | `"easy"`, `"medium"`, `"hard"` |
| `total_packages` | `int` | Total packages in episode |
| `delivered_count` | `int` | Number delivered |
| `grid_size` | `int` | Grid dimension |
| `score` | `float` | Delivery ratio |
| `max_steps` | `int` | Episode step limit |

---

## Installation & Setup

1. **Install Dependencies** (Python 3.11+ required):
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Environment Server:**
   ```bash
   uvicorn server.app:app --host 0.0.0.0 --port 7860
   ```

3. **Run the Greedy Inference Agent:**
   ```bash
   python inference.py
   ```

4. **Run with Docker** (build from project root):
   ```bash
   docker build -f server/Dockerfile .
   docker run -p 7860:7860 <image-id>
   ```

---

## How it Works (Episode Flow)

```text
EPISODE START

1. client.reset(options={"task_level": "easy"})
   └─ Server initializes grid, places robot at (0,0) and packages
   └─ Returns RobotObservation (done=False, reward=None, ...)

2. Agent reads observation
   └─ obs.robot_position, obs.packages, obs.carrying_package, obs.done

3. Agent selects action
   └─ RobotAction(direction="right", action="move")

4. client.step(action)
   └─ Server processes action → updates position, deadlines, rewards
   └─ Returns new RobotObservation with updated state

5. Repeat until obs.done == True
   └─ All packages delivered  →  success
   └─ Max steps exceeded      →  timeout

EPISODE END
   └─ Score = delivered_count / total_packages
```

---

## Reward Structure

| Event | Reward |
|---|---|
| Package successfully delivered to `(0,0)` | **+1.0** |
| Moved closer to nearest undelivered package | **+0.2** |
| Each step taken | **−0.01** |
| Package deadline expired | **−0.5** |
| Attempted delivery at wrong position | **−0.2** |
| Moved into boundary or obstacle | **−0.5** |
| No-op action | **0.0** |

---

## Task Configuration

### Easy
| Setting | Value |
|---|---|
| Grid | 5×5 |
| Packages | 2 (deadline: 15 steps each) |
| Obstacles | None |
| Max Steps | 20 |
| Expected Score | `~0.6–0.8` (greedy agent) |

### Medium
| Setting | Value |
|---|---|
| Grid | 10×10 |
| Packages | 4 (deadlines: 7–12 steps) |
| Obstacles | 5 walls |
| Max Steps | 50 |
| Expected Score | `~0.3–0.5` (greedy agent) |

### Hard
| Setting | Value |
|---|---|
| Grid | 15×15 |
| Packages | 6 (deadlines: 5–10 steps) |
| Obstacles | 15 walls (maze-like) |
| Max Steps | 100 |
| Expected Score | `~0.1–0.2` (greedy agent) |

---

## Deployment

### Local
```bash
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### Docker
```bash
# Build from project ROOT
docker build -f server/Dockerfile .
docker run -p 7860:7860 <image-id>
```

### Hugging Face Spaces
Set `ENV_URL` environment variable to the Space URL.  
The server auto-starts via `CMD uvicorn server.app:app --host 0.0.0.0 --port 7860`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENV_URL` | `http://localhost:7860` | Server URL used by `inference.py` and `client.py` |
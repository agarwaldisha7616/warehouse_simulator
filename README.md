---
title: Smart Warehouse Simulator
sdk: docker
pinned: false
---

# Smart Warehouse Simulator

OpenEnv-compliant warehouse simulation with multi-robot coordination, obstacle avoidance, package pickup and delivery, and an OpenAI-compatible LLM planning path.

## Architecture

### Backend
- FastAPI + OpenEnv server entrypoint: [server/app.py](/home/niku/Documents/warehouse_simulator/server/app.py)
- Environment implementation: [server/environment.py](/home/niku/Documents/warehouse_simulator/server/environment.py)
- Deterministic robot coordination and pathing: [server/core/agents.py](/home/niku/Documents/warehouse_simulator/server/core/agents.py)
- Task definitions by difficulty: [server/core/constants.py](/home/niku/Documents/warehouse_simulator/server/core/constants.py)
- OpenAI-compatible LLM planner: [server/core/llm.py](/home/niku/Documents/warehouse_simulator/server/core/llm.py)

### Frontend
- Next.js demo UI: [frontend/src/app/page.tsx](/home/niku/Documents/warehouse_simulator/frontend/src/app/page.tsx)
- The UI talks to session-aware demo endpoints under `/ui/*`

### Inference
- Root inference runner: [inference.py](/home/niku/Documents/warehouse_simulator/inference.py)
- Uses OpenAI-compatible chat completions and emits `[START]`, `[STEP]`, `[END]` logs

## Action Space
- `agent_id`: robot identifier such as `robot_1`
- `action`: `move | move_to | pick | deliver | no_op`
- `direction`: `up | down | left | right | none`
- `target`: optional package id or `Delivery Zone`

## Observation Space
- `robots`: per-robot position and carrying state
- `packages`: package id, position, deadline, delivery status
- `obstacles`: blocked grid cells
- `grid_size`: board size
- `steps_remaining`: remaining steps in the episode
- `message`: feedback from the last step
- `next_agent_id`: which robot acts next
- `last_action_failed`: failure flag for the previous action
- `collision_reason`: debug detail for blocked movement

## Environment Variables
- `API_BASE_URL`: OpenAI-compatible base URL, for example `https://router.huggingface.co/v1`
- `MODEL_NAME`: model identifier, for example `Qwen/Qwen2.5-7B-Instruct`
- `HF_TOKEN`: Hugging Face token or compatible API key
- `ENV_URL`: environment server URL, default `http://localhost:7860`

## Setup
```bash
pip install -r requirements.txt
```

## Run Backend
```bash
venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

OpenEnv endpoints:
- `/reset`
- `/step`
- `/state`
- `/schema`
- `/ws`

Demo UI endpoints:
- `/ui/reset`
- `/ui/step`
- `/ui/state`
- `/ui/agent_action`
- `/ui/task_to_action`
- `/ui/llm_plan`

## Run Frontend
```bash
npm run dev --prefix frontend
```

Optional custom backend URL for the frontend:
```bash
export NEXT_PUBLIC_API_BASE="http://localhost:7860/ui"
```

## Run Inference
```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-7B-Instruct"
export HF_TOKEN="hf_xxxxx"
export ENV_URL="http://localhost:7860"

python inference.py "Coordinate all robots to deliver every package safely."
```

Run a single level:
```bash
python inference.py --task-level hard "Deliver all packages safely."
```

## Validation
```bash
venv/bin/openenv validate . -v
venv/bin/python validate.py
npm run build --prefix frontend
```

## Difficulty Levels
- `easy`: 2 robots, small grid, light obstacles
- `medium`: 2 robots, more packages, tighter deadlines, more obstacles
- `hard`: 3 robots, larger grid, denser routing pressure, more packages

## Notes
- The submission path is FastAPI/OpenEnv, not Flask.
- The LLM path is OpenAI-compatible, not Gemini.
- Heuristic fallback is disabled unless `ALLOW_HEURISTIC_FALLBACK` is explicitly enabled.

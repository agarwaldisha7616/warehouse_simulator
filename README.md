---
title: Smart Warehouse Simulator
sdk: docker
pinned: false
---

# Smart Warehouse Simulator

OpenEnv-compatible warehouse simulation with multi-robot coordination, obstacle avoidance, package pickup and delivery, explicit task graders, and an optional OpenAI-compatible planning path.

## Repo Layout
- `server/app.py`: FastAPI + OpenEnv server entrypoint
- `server/environment.py`: warehouse environment implementation
- `server/core/agents.py`: deterministic multi-robot coordinator
- `server/core/llm.py`: optional OpenAI-compatible planner
- `inference.py`: baseline inference runner with deterministic default
- `tasks/`: task metadata and per-task grader modules
- `frontend/`: optional Next.js demo UI
- `openenv.yaml`: submission manifest
- `validate.py`: local submission validation script

## Action Space
- `agent_id`: robot id such as `robot_1`
- `action`: `move | move_to | pick | deliver | no_op`
- `direction`: `up | down | left | right | none`
- `target`: optional package id or `Delivery Zone`

## Observation Space
- `done`: episode completion flag
- `reward`: normalized progress reward in `0.0-1.0`
- `robots`: per-robot position and carrying state
- `packages`: package id, position, deadline, delivery status
- `obstacles`: blocked grid cells
- `grid_size`: board size
- `steps_remaining`: remaining steps in the episode
- `message`: feedback from the last step
- `delivered_count`: delivered package count
- `total_packages`: total packages in the episode
- `next_agent_id`: whose turn is next
- `last_action_failed`: whether the last action failed
- `collision_reason`: blocked-move detail
- `failed_action_count`: cumulative failed actions
- `expired_package_count`: packages that expired
- `progress_score`: normalized episode progress snapshot

## Tasks And Graders
- `easy`: `tasks.easy.grader:grade`
- `medium`: `tasks.medium.grader:grade`
- `hard`: `tasks.hard.grader:grade`

All task metadata is centralized in `tasks/specs.py`. `server/core/constants.py` imports that data directly so runtime config and `openenv.yaml` stay aligned.

## Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install --prefix frontend
cp .env.example .env
```

## Environment Variables
- `ENV_URL`: environment server URL, default `http://127.0.0.1:7860`
- `API_BASE_URL`: OpenAI-compatible base URL
- `MODEL_NAME`: model identifier for optional LLM planning
- `HF_TOKEN`: Hugging Face token or compatible API key
- `NEXT_PUBLIC_API_BASE`: frontend API base, default `http://127.0.0.1:7860/ui`

The backend and inference script auto-load `.env` if present.

## Run Backend
```bash
source venv/bin/activate
uvicorn server.app:app --host 0.0.0.0 --port 7860
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
source venv/bin/activate
npm run dev --prefix frontend
```

## Run Inference
Deterministic baseline, safe for submission smoke tests:
```bash
source venv/bin/activate
python inference.py --planner deterministic "Coordinate all robots to deliver every package safely."
```

Single task:
```bash
python inference.py --planner deterministic --task-level hard "Deliver all packages safely."
```

Optional LLM-assisted mode:
```bash
python inference.py --planner auto "Coordinate all robots to deliver every package safely."
```

## Validation
```bash
source venv/bin/activate
openenv validate . -v
python validate.py
```

`validate.py` checks:
- required submission files
- manifest/task/grader alignment
- task smoke tests using the deterministic coordinator
- normalized reward and score ranges
- local inference stdout markers
- frontend production build

## Docker And Deployment
- Root `Dockerfile`: for Hugging Face Docker Spaces
- `server/Dockerfile`: kept aligned for server-specific workflows

Local Docker test:
```bash
docker build -t warehouse-simulator .
docker run -p 7860:7860 warehouse-simulator
```

## Submission Checklist
- Run `python validate.py`
- Confirm your Hugging Face Space boots successfully from the root `Dockerfile`
- Verify `/reset` returns a valid observation on the deployed Space
- Verify `python inference.py --planner deterministic --task-level easy` completes without error
- Submit the deployed Space URL and repo details through the Scaler dashboard

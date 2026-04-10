# Smart Warehouse Simulator

## Current State
- OpenEnv-compatible FastAPI backend in `server/app.py`
- Deterministic baseline inference in `inference.py`
- Three submission tasks: `easy`, `medium`, `hard`
- Explicit grader modules under `tasks/`
- Optional Next.js demo UI in `frontend/`

## Submission Contract
- `openenv.yaml` matches the live action space, observation space, and task metadata
- Task graders are defined at:
  - `tasks.easy.grader:grade`
  - `tasks.medium.grader:grade`
  - `tasks.hard.grader:grade`
- Runtime scores and rewards are normalized to `0.0-1.0`
- Baseline inference defaults to a deterministic planner so it can run without external LLM credentials

## Local Validation
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install --prefix frontend
cp .env.example .env

python validate.py
```

## Optional LLM Mode
- Set `HF_TOKEN`, `API_BASE_URL`, and `MODEL_NAME`
- Run `python inference.py --planner auto`
- The UI endpoint `/ui/llm_plan` falls back to a deterministic heuristic when strict LLM mode is not enabled

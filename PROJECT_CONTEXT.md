# Smart Warehouse Simulator - Project Context (Updated April 8, 2026)

This file is the handoff context for a new session, new account, or new model. It reflects the current repo state after backend consolidation, OpenEnv validation fixes, frontend API rewiring, legacy cleanup, and the latest runtime errors observed during local testing.

---

## 1. Current Submission Status

The repo is now based on a single OpenEnv/FastAPI backend plus a Next.js frontend.

Current local status:
- `venv/bin/openenv validate . -v` passes
- `venv/bin/python validate.py` passes
- `npm run build --prefix frontend` passes
- Easy, medium, and hard levels complete with the deterministic coordinator
- Legacy Flask/Gemini stack has been removed from the live path

This means the repo is structurally close to submission-ready.

---

## 2. Current Architecture

### Backend
- Entry point: `server/app.py`
- OpenEnv module wrapper: `server/openenv_app.py`
- Environment: `server/environment.py`
- Core movement / collision / robot state: `server/core/engine.py`
- Deterministic multi-robot coordinator: `server/core/agents.py`
- Task levels and difficulty configs: `server/core/constants.py`
- LLM planning layer: `server/core/llm.py`

### Frontend
- Main UI: `frontend/src/app/page.tsx`
- Styling: `frontend/src/app/globals.css`
- Frontend talks to session-aware demo endpoints under `/ui/*`

### Inference
- Root script: `inference.py`
- Uses OpenAI-compatible client configuration via:
  - `API_BASE_URL`
  - `MODEL_NAME`
  - `HF_TOKEN`
  - `ENV_URL`

---

## 3. Important Live Endpoints

### OpenEnv endpoints
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /schema`
- `WS /ws`

### Frontend demo endpoints
- `POST /ui/reset`
- `POST /ui/step`
- `GET /ui/state`
- `GET /ui/agent_action`
- `POST /ui/task_to_action`
- `POST /ui/llm_plan`

The Next.js frontend should use `http://localhost:7860/ui` as its API base unless overridden with `NEXT_PUBLIC_API_BASE`.

---

## 4. What Was Fixed

### A. Broken Runtime Stack
Previously the repo mixed:
- old Flask app
- old `env.py` / `config.py`
- old Gemini-based planning
- OpenEnv FastAPI app

This caused confusion about which code path was actually active.

Current state:
- live backend path is only `server/app.py`
- live inference path is only `inference.py`
- live LLM path is OpenAI-compatible only

### B. LLM Integration Mismatch
Previously:
- one file used OpenAI-compatible HF routing
- another file used Gemini

Current state:
- `server/core/llm.py` uses `OpenAI(...)` compatible chat completions
- `inference.py` also uses the same env variable contract
- no Gemini path is required for the current stack

### C. Frontend Session Model
Previously the frontend treated stateless OpenEnv HTTP endpoints like persistent session endpoints.

Current state:
- frontend now uses `/ui/*`
- demo state is held in a server-side `DemoSession`

### D. CORS / Browser Preflight
Observed error:
- `OPTIONS /ui/reset HTTP/1.1 405 Method Not Allowed`

Cause:
- frontend on port `3000` was making browser preflight requests to backend on `7860`
- backend lacked CORS middleware

Fix:
- `server/app.py` now includes `CORSMiddleware`
- allowed origins:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`

### E. Legacy Cleanup
Removed unused files:
- `env.py`
- `config.py`
- `dummy_test.py`
- `web/app.py`

README was rewritten to match the current architecture.

---

## 5. Current Difficulty Design

### Easy
- 2 robots
- small grid
- light obstacle layout
- intended to clearly demonstrate multi-robot basics

### Medium
- 2 robots
- more packages
- more obstacles
- tighter routing than easy

### Hard
- 3 robots
- larger grid
- more packages
- denser obstacle field
- stronger coordination pressure

Important:
- each level now has multiple robots
- each level has its own difficulty pattern

---

## 6. Latest Real Errors Observed From Local User Testing

These happened after the repo was already structurally passing validation.

### Error 1
Command:
- `python inference.py ...`

Observed:
- `ModuleNotFoundError: No module named 'openenv'`

Cause:
- command was run outside the project virtual environment

Correct fix:
- activate venv first
- or use `venv/bin/python inference.py ...`

### Error 2
Command:
- `python inference.py --task-level easy "Coordinate all robots to deliver every package safely."`

Observed:
- `[ERROR] HF_TOKEN or OPENAI_API_KEY is required for LLM calls.`

Cause:
- backend / script reads env vars via `os.getenv(...)`
- `.env` exists but is not auto-loaded by current code
- activating the venv does not automatically load `.env`

Important fact:
- `.env` is safe for local use if it remains gitignored
- but it will only work if the shell loads it before starting backend/inference

Correct load sequence:
```bash
set -a
source .env
set +a
```

Most recent confirmed root cause:
- the `.env` file was malformed because the full Hugging Face modal text was pasted into it instead of only the raw token value
- this caused `401 Invalid username or password` from the OpenAI-compatible request to `https://router.huggingface.co/v1`

Correct `.env` format:
```env
API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
HF_TOKEN=hf_your_new_token_here
ENV_URL=http://localhost:7860
```

Token formatting rules:
- paste only the raw token after `HF_TOKEN=`
- do not paste page text like `Copy`, `Done`, or modal instructions
- do not include extra Unicode characters
- unquoted plain text is preferred
- because a real token was exposed in chat during debugging, it should be rotated and replaced with a new one

Then verify:
```bash
venv/bin/python -c "import os; print(bool(os.getenv('HF_TOKEN')), os.getenv('API_BASE_URL'), os.getenv('MODEL_NAME'), os.getenv('ENV_URL'))"
```

### Error 3
Frontend log:
- `[LLM] Could not parse any tasks from prompt.`

Likely causes:
1. backend process was started without `.env` loaded, so LLM request failed
2. model output was not valid JSON for `/ui/llm_plan`
3. prompt referred to non-existent labels like “object number one” instead of actual package ids like `A`, `B`, `C`

Better prompt examples:
- `Send robot_1 to package A safely and pick it.`
- `Use robot_2 to deliver the nearest package.`
- `Move robot_1 to package B, pick it, then deliver it.`

To debug directly:
1. start backend after loading `.env`
2. call:
```bash
curl -sS -X POST http://127.0.0.1:7860/ui/reset \
  -H "Content-Type: application/json" \
  -d '{"options":{"task_level":"easy"}}'
```
3. then call:
```bash
curl -sS -X POST http://127.0.0.1:7860/ui/llm_plan \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Send robot_1 to package A safely and pick it."}'
```

Expected success shape:
```json
{"tasks":[{"action":"move_to","agent_id":"robot_1","target":"A"}],"reasoning":"..."}
```

If it fails:
- missing env vars => backend was started without sourced `.env`
- LLM request error => token/base URL/model issue
- invalid JSON => model response formatting issue

---

## 7. Exact Run Instructions That Actually Work

Run from repo root.

### Step 1. Load `.env`
```bash
set -a
source .env
set +a
```

### Step 2. Confirm env vars are present
```bash
venv/bin/python -c "import os; print('HF_TOKEN', bool(os.getenv('HF_TOKEN'))); print('API_BASE_URL', os.getenv('API_BASE_URL')); print('MODEL_NAME', os.getenv('MODEL_NAME')); print('ENV_URL', os.getenv('ENV_URL'))"
```

Optional token-format sanity check:
```bash
venv/bin/python - <<'PY'
import os
t = os.getenv("HF_TOKEN")
print("present:", bool(t))
print("prefix:", repr(t[:12]) if t else None)
print("has_space:", (" " in t) if t else None)
print("has_newline:", ("\n" in t or "\r" in t) if t else None)
PY
```

### Step 3. Start backend
```bash
venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### Step 4. Start frontend
```bash
npm run dev --prefix frontend
```

### Step 5. Open UI
- `http://localhost:3000`

### Step 6. Optional inference run
In a new shell:
```bash
source venv/bin/activate
set -a
source .env
set +a
python inference.py --task-level easy "Coordinate all robots to deliver every package safely."
```

Important:
- activating `venv` is not enough
- sourcing `.env` is not enough if done in a different terminal than the one running backend/inference
- each terminal session needs its own env variables loaded

---

## 8. Validation Commands

Use these before submission:

```bash
venv/bin/openenv validate . -v
venv/bin/python validate.py
npm run build --prefix frontend
```

Optional inference smoke test:
```bash
source venv/bin/activate
set -a
source .env
set +a
python inference.py --task-level easy "Coordinate all robots to deliver every package safely."
```

---

## 9. What Still Needs Manual Verification

These are the last meaningful risks:

1. Real LLM API call with the actual `HF_TOKEN`
   - must confirm `/ui/llm_plan` returns valid tasks
   - must confirm `inference.py` can make live requests

2. Prompt robustness
   - current UI should work best with package ids like `A`, `B`, `C`
   - freeform prompts may still fail if the model returns non-JSON

3. Final hosted deployment
   - after local validation, deploy and verify that judges can reach the app

---

## 10. Guidance For The Next Agent / Next Account

If continuing this project in a fresh session:

- do not reintroduce Flask
- do not reintroduce Gemini
- keep `server/app.py` as the main backend entry
- keep `inference.py` at repo root
- do not assume `.env` is auto-loaded
- if frontend says `Could not parse any tasks from prompt`, inspect `/ui/llm_plan` directly with `curl`
- if browser shows `OPTIONS /ui/reset 405`, confirm the backend is the new CORS-enabled one and restart it
- if `python inference.py` says `No module named openenv`, run it inside the venv

---

## 11. Short Current Truth

The project is no longer “looping blindly + not using AI”.

Current state is:
- OpenEnv-compliant
- FastAPI-based
- multi-robot on all levels
- deterministic baseline works
- UI works against `/ui/*`
- LLM path is wired but still depends on a real correctly-loaded token and a model that returns valid JSON

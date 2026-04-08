# Warehouse Simulator - Project Context (v3)

This document tracks the evolution of the project, specifically the challenges faced and the architectural solutions implemented during the session on April 7, 2026.

---

## 1. Executive Summary
The project has been transformed from a basic single-step simulator into a robust, multi-step AI agent system. It now features high-fidelity 3D visualizations, structured LLM planning (Gemini/OpenAI), and a strict inference pipeline required for hackathon evaluation.

---

## 2. Problems & Solutions (Session: April 7, 2026)

### A. Agent Logic & Stability
**Problem**: The robot was getting stuck in "Hit wall!" loops because movement decisions were made naively on the client side without obstacle awareness.
**Solution**: 
- Implemented a **Smart BFS Pathfinding Agent** in `server/core/agents.py`.
- Moved movement decision logic from Frontend to Backend via the `/agent_action` endpoint.
- Added strict boundary and obstacle checks within the BFS algorithm.

### B. LLM Interaction & Planning
**Problem**: The LLM integration was "fake" or limited to single-step instructions. Multi-step prompts like "Pick A then deliver" would only perform the first move.
**Solution**:
- Developed a **Structured Planning Layer** in `server/core/llm.py` using the Gemini API.
- Implemented `/llm_plan` endpoint that returns a JSON array of tasks (`move_to`, `pick`, `move`, `deliver`).
- Added an **Execution Queue** in the Frontend that sequentially processes these high-level tasks until completion.

### C. UI Rendering & Feedback
**Problem**: The 3D canvas often appeared blank, robot movement was "teleporting" instead of animating, and the AI's "thought process" was invisible.
**Solution**:
- **Fixed Rendering**: Added a 3D floor, corrected coordinate mapping (Grid X/Y to 3D X/Z), and enhanced lighting/shadows.
- **Smooth Animations**: Used `useFrame` and `lerp` for position interpolation and smooth rotation towards targets.
- **AI Reasoning Panel**: Added a dedicated sidebar section showing the interpreted goal and reasoning from the LLM.
- **Target Highlighting**: Implemented a glowing emissive effect on the specific package or zone the AI is currently targeting.

### D. Hackathon Compliance (Inference Pipeline)
**Problem**: Evaluation required a specific `inference.py` script using the `OpenAI` client and strict log formatting (`[START]`, `[STEP]`, `[END]`).
**Solution**:
- Created a standalone `inference.py` at the root.
- Integrated the `OpenAI` client using environment variables (`API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`).
- Implemented a logging system that exactly matches the required evaluation format.

### E. Reward System Refinement
**Problem**: The initial reward system was too simple and didn't penalize repeated failures.
**Solution**:
- Refactored `server/core/rewards.py` to include:
    - `+1.0` for valid moves.
    - `-5.0` for wall hits.
    - `+10.0` for successful deliveries.
    - **Failure Streak Penalty**: Incremental penalties for repeated errors.

---

## 3. Current Architecture

- **Backend (FastAPI)**:
    - `/reset`: Initializes episode with task levels (Easy/Medium/Hard).
    - `/step`: Executes a low-level `RobotAction`.
    - `/agent_action`: Returns the next BFS move for auto-pilot.
    - `/llm_plan`: Parses prompts into a sequence of tasks.
    - `/task_to_action`: Decomposes high-level tasks into immediate `RobotAction` steps.
- **Frontend (Next.js)**:
    - **3D Engine**: React Three Fiber with smooth interpolation.
    - **State**: Tracks `executionQueue`, `aiReasoning`, and `isAutoPlaying`.
    - **Control**: Real-time speed adjustment and debug view toggle.

---

## 4. How to Reproduce/Run

1.  **Backend**: `PYTHONPATH=$(pwd) venv/bin/uvicorn server.app:app --port 7860 --reload`
2.  **Frontend**: `cd frontend && npm run dev`
3.  **Validate**: `python validate.py`

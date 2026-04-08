# Smart Warehouse Simulator (Hackathon Edition)

A high-fidelity warehouse robot simulation featuring **Multi-Step AI Planning**, **BFS Pathfinding**, and **LLM Integration (Gemini/OpenAI)**.

---

## 🚀 Key Features

- **Multi-Step LLM Planning**: Natural language instructions (e.g., "Pick up A then deliver it") are parsed into structured task sequences.
- **Smart BFS Pathfinding**: Robot automatically calculates the shortest path to targets while avoiding obstacles and boundaries.
- **High-Fidelity 3D UI**: Smooth robot animations (lerp/rotation), glassmorphism dashboard, and real-time efficiency metrics.
- **Strict Inference Pipeline**: Standardized `inference.py` using OpenAI-compatible clients and required logging format.
- **Robust Reward System**: Penalties for wall hits and failure streaks; bonuses for successful deliveries.

---

## 🛠️ Project Structure

```
warehouse_simulator/
├── server/              # FastAPI Backend
│   ├── app.py           # API endpoints (/llm_plan, /task_to_action, /reset)
│   ├── environment.py   # Simulation Engine
│   └── core/
│       ├── agents.py    # BFS Pathfinding Logic
│       ├── llm.py       # Gemini/OpenAI Integration
│       └── rewards.py   # Hackathon-ready Reward System
├── frontend/            # Next.js + React Three Fiber Web UI
│   └── src/app/page.tsx # 3D Visualization & Execution Queue
├── inference.py         # Standardized evaluation script
├── models.py            # Shared Pydantic schemas
├── requirements.txt     # Backend dependencies
└── README.md
```

---

## ⚡ Quick Start

### 1. Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set your API Key (Optional for Gemini)
export GEMINI_API_KEY="your_key_here"

# Start Backend (Terminal 1)
export PYTHONPATH=$(pwd)
venv/bin/uvicorn server.app:app --port 7860 --reload
```

### 2. Frontend Setup
```bash
# Go to frontend
cd frontend

# Install & Run (Terminal 2)
npm install
npm run dev
```
Open **http://localhost:3000**

### 3. Inference Run (Strict Format)
```bash
export API_BASE_URL="your_url"
export MODEL_NAME="your_model"
export HF_TOKEN="your_token"

python3 inference.py "Go to shelf B and pick it up"
```

---

## 🤖 LLM Agent Instruction Examples

- **"Go to A"** - Moves to package A using BFS.
- **"Pick up A then deliver it"** - Plans a 4-step mission: `move_to(A) -> pick -> move_to(0,0) -> deliver`.
- **"Move right 3 steps then up 2"** - Precise directional control.
- **"Avoid obstacles and go to B"** - Intelligent navigation.

---

## 📊 Environment Metrics

| Metric | Description |
|---|---|
| **Reward** | +1 (Valid Move), -5 (Wall Hit), +10 (Delivery) |
| **Efficiency** | Ratio of delivered packages to total packages |
| **Steps Left** | Budgeted steps remaining for the episode |
| **AI Reasoning** | Live display of the LLM's thought process |

---

## Pre-Submission Validation

```bash
python validate.py
```

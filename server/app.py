import sys, os
from fastapi.middleware.cors import CORSMiddleware

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openenv.core.env_server import create_fastapi_app
from environment import SmartWarehouseEnv
from models import RobotAction, RobotObservation
from core.agents import GreedyAgent
from core.llm import GeminiAgent, LLMPlan, Task
from models import RobotAction, RobotObservation, LLMRequest

# Global singleton instance to persist state across HTTP requests
_shared_env = SmartWarehouseEnv()
_llm_agent = GeminiAgent() # Configures itself from env vars

def get_env():
    return _shared_env

app = create_fastapi_app(get_env, RobotAction, RobotObservation)

@app.post("/agent_action", response_model=RobotAction)
async def agent_action():
    """Get the next recommended action from the Greedy BFS Agent."""
    env = get_env()
    obs = env._make_observation(reward=None, message="Agent thinking...")
    agent = GreedyAgent()
    action = agent.act(obs)
    # Add dummy reasoning since this bypasses LLM
    action.reasoning = "Using default Greedy BFS heuristic (closest un-delivered package or delivery zone)."
    action.target = "Nearest package or zone"
    return action

@app.post("/llm_plan", response_model=LLMPlan)
async def llm_plan(req: LLMRequest):
    """Use Gemini to understand prompt and return a multi-step plan."""
    env = get_env()
    obs = env._make_observation(reward=None, message="LLM planning...")
    plan = await _llm_agent.get_plan(req.prompt, obs.model_dump())
    return plan

@app.post("/task_to_action", response_model=RobotAction)
async def task_to_action(task: Task):
    """Convert a high-level task into the next immediate RobotAction."""
    env = get_env()
    obs = env._make_observation(reward=None, message="Converting task...")
    agent = GreedyAgent()
    rx, ry = obs.robot_position

    if task.action == "move_to":
        target_pos = None
        if task.target == "Delivery Zone" or task.target == "0,0":
            target_pos = (0, 0)
        else:
            for p in obs.packages:
                if p["id"] == task.target:
                    target_pos = tuple(p["position"])
                    break
        
        if target_pos:
            if (rx, ry) == target_pos:
                return RobotAction(direction="none", act="no_op", reasoning="Already at target.")
            direction = agent._get_next_direction(rx, ry, target_pos[0], target_pos[1], obs.grid_size, obs.obstacles)
            return RobotAction(direction=direction or "none", act="move" if direction else "no_op")
            
    elif task.action == "move":
        return RobotAction(direction=task.direction or "none", act="move")
        
    elif task.action == "pick":
        return RobotAction(direction="none", act="pick")
        
    elif task.action == "deliver":
        return RobotAction(direction="none", act="deliver")
        
    return RobotAction(direction="none", act="no_op")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

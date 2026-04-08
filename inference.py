# inference.py
import os
import json
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI

# 1. SETUP OPENAI CLIENT
API_BASE_URL = os.environ.get("API_BASE_URL")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-3.5-turbo")
HF_TOKEN = os.environ.get("HF_TOKEN")

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN or "dummy"
)

class InferenceEngine:
    def __init__(self):
        # We simulate a 5x5 grid for the demo if no observation is provided
        self.grid_size = 5
        self.robot_pos = [0, 0]
        self.carrying = None
        self.packages = {"A": [2, 2], "B": [4, 4], "C": [0, 4]}
        self.obstacles = [[1, 1], [2, 1], [3, 1]]

    def get_plan(self, prompt: str) -> Dict[str, Any]:
        """Convert natural language to structured JSON plan."""
        system_prompt = f"""
        You are a Warehouse AI. Convert instructions into a JSON plan.
        Grid: {self.grid_size}x{self.grid_size}
        Robot: {self.robot_pos}
        Packages: {self.packages}
        Obstacles: {self.obstacles}
        
        Allowed Actions:
        - {{"action": "move_to", "target": "ID or Delivery Zone"}}
        - {{"action": "pick", "target": "ID"}}
        - {{"action": "deliver"}}
        
        Example Output:
        {{
            "tasks": [
                {{"action": "move_to", "target": "A"}},
                {{"action": "pick", "target": "A"}},
                {{"action": "move_to", "target": "Delivery Zone"}},
                {{"action": "deliver"}}
            ]
        }}
        """
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            content = response.choices[0].message.content.strip()
            
            # Clean JSON markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            return json.loads(content.strip())
        except Exception as e:
            return {"tasks": [], "error": str(e)}

    def run(self, prompt: str):
        """Execute the plan with strict logging."""
        print("[START]")
        print(f"task: {prompt}\n")
        
        plan_data = self.get_plan(prompt)
        tasks = plan_data.get("tasks", [])
        
        if not tasks:
            print("[STEP]")
            print("action: error")
            print(f"message: {plan_data.get('error', 'Failed to generate plan')}")
            print("status: failed\n")
            print("[END]")
            print("result: aborted")
            return

        for task in tasks:
            action = task.get("action")
            target = task.get("target")
            
            print("[STEP]")
            print(f"action: {action}")
            if target:
                print(f"target: {target}")
            
            # SIMULATE EXECUTION LOGIC
            success = self._simulate_action(action, target)
            print(f"status: {'success' if success else 'failed'}\n")
            
            if not success:
                break
                
        print("[END]")
        print("result: completed")

    def _simulate_action(self, action: str, target: Optional[str]) -> bool:
        """Simple movement simulation."""
        time.sleep(0.1) # Simulate thinking/moving time
        
        if action == "move_to":
            if target == "Delivery Zone":
                self.robot_pos = [0, 0]
            elif target in self.packages:
                self.robot_pos = self.packages[target]
            return True
            
        elif action == "pick":
            if target in self.packages and self.robot_pos == self.packages[target]:
                self.carrying = target
                return True
            return False
            
        elif action == "deliver":
            if self.robot_pos == [0, 0] and self.carrying:
                self.carrying = None
                return True
            return False
            
        return False

def main():
    import sys
    engine = InferenceEngine()
    
    # Default prompt if none provided
    prompt = "Go to shelf B and pick it up"
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        
    engine.run(prompt)

if __name__ == "__main__":
    main()

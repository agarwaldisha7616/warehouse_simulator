import os
import json
import google.generativeai as genai
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class Task(BaseModel):
    action: str = Field(..., description="move_to, move, pick, deliver, no_op")
    target: Optional[str] = Field(None, description="Package ID or 'Delivery Zone'")
    direction: Optional[str] = Field(None, description="up, down, left, right")
    steps: Optional[int] = Field(None, description="Number of steps for 'move' action")

class LLMPlan(BaseModel):
    tasks: List[Task]
    reasoning: str

class GeminiAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None

    async def get_plan(self, user_prompt: str, observation: Dict[str, Any]) -> LLMPlan:
        if not self.model:
            return self._heuristic_fallback(user_prompt, observation)

        system_prompt = """
        You are an AI controller for a warehouse robot. 
        Convert the user request into a structured sequence of tasks.
        
        Grid Size: {grid_size}
        Robot Position: {robot_pos}
        Carrying: {carrying}
        Packages: {packages}
        Obstacles: {obstacles}
        
        User Request: "{user_prompt}"
        
        Return ONLY a JSON object matching this schema:
        {{
            "tasks": [
                {{ "action": "move_to", "target": "A" }},
                {{ "action": "pick" }},
                {{ "action": "move", "direction": "right", "steps": 2 }},
                {{ "action": "deliver" }}
            ],
            "reasoning": "string"
        }}
        
        Actions:
        - "move_to": requires "target" (package ID or "Delivery Zone")
        - "move": requires "direction" and "steps"
        - "pick": picks package at current location
        - "deliver": delivers package at (0,0)
        """
        
        formatted_prompt = system_prompt.format(
            grid_size=observation.get("grid_size"),
            robot_pos=observation.get("robot_position"),
            carrying=observation.get("carrying_package"),
            packages=observation.get("packages"),
            obstacles=observation.get("obstacles"),
            user_prompt=user_prompt
        )
        
        try:
            response = self.model.generate_content(formatted_prompt)
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text.strip())
            return LLMPlan(**data)
        except Exception as e:
            print(f"LLM Error: {e}")
            return self._heuristic_fallback(user_prompt, observation)

    def _heuristic_fallback(self, user_prompt: str, observation: Dict[str, Any]) -> LLMPlan:
        prompt = user_prompt.lower()
        tasks = []
        
        if "shelf a" in prompt or "go to a" in prompt:
            tasks.append(Task(action="move_to", target="A"))
        elif "move right" in prompt:
            tasks.append(Task(action="move", direction="right", steps=1))
            
        if not tasks:
            tasks.append(Task(action="no_op"))
            
        return LLMPlan(
            tasks=tasks,
            reasoning="Heuristic fallback due to missing API key or parsing error."
        )

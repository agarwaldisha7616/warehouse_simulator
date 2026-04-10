import json
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field


class Task(BaseModel):
    action: str = Field(..., description="move_to, move, pick, deliver, no_op")
    agent_id: Optional[str] = Field(None, description="Robot identifier")
    target: Optional[str] = Field(None, description="Package ID or Delivery Zone")
    direction: Optional[str] = Field(None, description="up, down, left, right")
    steps: Optional[int] = Field(None, description="Optional move repetition count")


class LLMPlan(BaseModel):
    tasks: List[Task]
    reasoning: str


class LLMPlanningError(RuntimeError):
    pass


def _extract_json_block(text: str) -> Dict[str, Any]:
    candidate = text.strip()
    if "```json" in candidate:
        candidate = candidate.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in candidate:
        candidate = candidate.split("```", 1)[1].split("```", 1)[0]

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMPlanningError(f"LLM did not return JSON: {text}")

    return json.loads(candidate[start : end + 1])


def _available_targets(observation: Dict[str, Any]) -> List[str]:
    return [
        package["id"]
        for package in observation.get("packages", [])
        if not package.get("delivered", False)
    ]


def _coerce_valid_action(text: str, valid_actions: List[str]) -> str:
    candidate = text.strip().strip("`").strip('"').strip("'")
    if candidate in valid_actions:
        return candidate

    first_line = candidate.splitlines()[0].strip() if candidate else ""
    if first_line in valid_actions:
        return first_line

    for action in sorted(valid_actions, key=len, reverse=True):
        if action in candidate:
            return action

    raise LLMPlanningError(f"LLM produced invalid action: {text}")


def heuristic_plan(user_prompt: str, observation: Dict[str, Any]) -> LLMPlan:
    del user_prompt
    next_agent = observation.get("next_agent_id", "robot_1")
    available = _available_targets(observation)
    if available:
        return LLMPlan(
            tasks=[Task(action="move_to", agent_id=next_agent, target=available[0])],
            reasoning="Explicit heuristic fallback selected the first undelivered package.",
        )
    return LLMPlan(
        tasks=[Task(action="no_op", agent_id=next_agent)],
        reasoning="Explicit heuristic fallback found no work remaining.",
    )


class WarehouseLLM:
    def __init__(
        self,
        api_base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.api_base_url = api_base_url or os.getenv(
            "API_BASE_URL", "https://router.huggingface.co/v1"
        )
        self.model_name = model_name or os.getenv(
            "MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct"
        )
        self.api_key = api_key or os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMPlanningError("HF_TOKEN or OPENAI_API_KEY is required for LLM calls.")

        self.client = OpenAI(base_url=self.api_base_url, api_key=self.api_key)

    def _chat(self, messages: List[Dict[str, str]], max_tokens: int = 256) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise LLMPlanningError(f"LLM request failed: {exc}") from exc

        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise LLMPlanningError("LLM returned an empty response.")
        return content

    def choose_action(
        self,
        observation: Dict[str, Any],
        valid_actions: List[str],
        objective: Optional[str] = None,
    ) -> str:
        next_agent = observation.get("next_agent_id", "robot_1")
        last_action_agent_id = observation.get("last_action_agent_id")
        last_action = observation.get("last_action")
        collision_reason = observation.get("collision_reason")

        system_prompt = (
            "You control warehouse robots. Output exactly one action string and nothing else."
        )
        user_prompt = f"""
Objective: {objective or 'Deliver all undelivered packages safely and efficiently.'}
Current robot turn: {next_agent}
Robots: {json.dumps(observation.get('robots', {}), sort_keys=True)}
Packages: {json.dumps(observation.get('packages', []), sort_keys=True)}
Obstacles: {json.dumps(observation.get('obstacles', []), sort_keys=True)}
Steps remaining: {observation.get('steps_remaining')}
Valid actions: {valid_actions}

Rules:
1. Output only one action from the valid actions list.
2. Never repeat a failed action for the same robot.
3. Avoid collisions and obstacles.
4. Prefer progress toward picking or delivering a package.

Last action: {last_action}
Last action agent: {last_action_agent_id}
Last action failed: {observation.get('last_action_failed')}
Collision reason: {collision_reason}
"""

        raw_action = self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=16,
        )
        return _coerce_valid_action(raw_action, valid_actions)

    def get_plan(self, user_prompt: str, observation: Dict[str, Any]) -> LLMPlan:
        system_prompt = """
You are a warehouse orchestration planner.
Return strict JSON with this schema:
{
  "tasks": [
    {
      "action": "move_to" | "move" | "pick" | "deliver" | "no_op",
      "agent_id": "robot_1",
      "target": "A",
      "direction": "up",
      "steps": 1
    }
  ],
  "reasoning": "short explanation"
}

Rules:
- Use only robot ids that exist in the observation.
- Use target "Delivery Zone" for deliveries.
- If the last action failed for a robot, do not repeat that action for the same robot.
- Keep the plan short and executable.
"""
        prompt = f"""
Observation:
{json.dumps(observation, sort_keys=True)}

Instruction:
{user_prompt}
"""

        raw = self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
        )
        data = _extract_json_block(raw)
        plan = LLMPlan(**data)
        if not plan.tasks:
            raise LLMPlanningError("LLM returned an empty task plan.")
        return plan

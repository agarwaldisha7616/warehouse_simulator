"""
Gradio Web UI for Smart Warehouse Simulator
Deploy on Hugging Face Spaces or run locally.
"""

import os
import sys
import json
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import gradio as gr
import numpy as np
from client import WarehouseClient
from models import RobotAction

ENV_URL = os.environ.get("ENV_URL", "http://localhost:7860")
API_BASE_URL = os.environ.get("API_BASE_URL", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

client = None
episode_state = None


def get_client():
    global client
    if client is None:
        client = WarehouseClient(base_url=ENV_URL)
    return client


def _direction_towards(fx, fy, tx, ty) -> str:
    if abs(tx - fx) >= abs(ty - fy):
        return "right" if tx > fx else "left"
    return "up" if ty > fy else "down"


def get_greedy_action(obs) -> RobotAction:
    rx, ry = obs.robot_position
    if obs.carrying_package is None:
        undelivered = [p for p in obs.packages if not p["delivered"]]
        if not undelivered:
            return RobotAction(direction="up", action="no_op")
        target = min(
            undelivered,
            key=lambda p: abs(p["position"][0] - rx) + abs(p["position"][1] - ry),
        )
        tx, ty = target["position"]
        if [rx, ry] == [tx, ty]:
            return RobotAction(direction="up", action="pick")
        return RobotAction(
            direction=_direction_towards(rx, ry, tx, ty),
            action="move",
        )
    else:
        if [rx, ry] == [0, 0]:
            return RobotAction(direction="up", action="deliver")
        return RobotAction(
            direction=_direction_towards(rx, ry, 0, 0),
            action="move",
        )


def render_grid(obs):
    """Render the warehouse grid as an image."""
    grid_size = obs.grid_size
    cell_size = 40
    img = (
        np.ones((grid_size * cell_size, grid_size * cell_size, 3), dtype=np.uint8) * 240
    )

    obstacles = set(tuple(o) for o in obs.obstacles)
    delivery_zone = (0, 0)
    robot_pos = tuple(obs.robot_position)
    carrying = obs.carrying_package

    for r in range(grid_size):
        for c in range(grid_size):
            y1, x1 = r * cell_size, c * cell_size
            y2, x2 = y1 + cell_size, x1 + cell_size

            if (r, c) in obstacles:
                img[y1:y2, x1:x2] = [80, 80, 80]
            elif (r, c) == delivery_zone:
                img[y1:y2, x1:x2] = [100, 200, 100]
            else:
                img[y1:y2, x1:x2] = [240, 240, 240]

            for pkg in obs.packages:
                if not pkg["delivered"] and tuple(pkg["position"]) == (r, c):
                    img[y1 + 5 : y2 - 5, x1 + 5 : x2 - 5] = [255, 100, 100]

            if (r, c) == robot_pos:
                color = [50, 150, 255] if carrying is None else [255, 200, 0]
                img[y1 + 3 : y2 - 3, x1 + 3 : x2 - 3] = color

    return img


def get_status_text(obs):
    """Generate human-readable status."""
    lines = []
    lines.append(f"Robot Position: {obs.robot_position}")
    lines.append(f"Carrying: {obs.carrying_package or 'Nothing'}")
    lines.append(f"Delivered: {obs.delivered_count}/{obs.total_packages}")
    lines.append(f"Steps Remaining: {obs.steps_remaining}")
    lines.append(f"Message: {obs.message}")

    if obs.done:
        score = (
            obs.delivered_count / obs.total_packages if obs.total_packages > 0 else 0
        )
        lines.append(f"\n*** EPISODE ENDED ***")
        lines.append(f"Final Score: {score:.2f}")

    return "\n".join(lines)


def reset_episode(task_level, agent_type):
    """Start a new episode."""
    global episode_state
    c = get_client()
    obs = c.reset(options={"task_level": task_level})
    episode_state = {
        "obs": obs,
        "task_level": task_level,
        "agent_type": agent_type,
        "step_count": 0,
        "total_reward": 0.0,
        "log": [],
    }
    img = render_grid(obs)
    status = get_status_text(obs)
    log = f"[START] Episode started — {task_level.upper()} | Agent: {agent_type}"
    return img, status, log


def step_episode():
    """Execute one step of the current episode."""
    global episode_state
    if episode_state is None:
        return None, "No active episode. Click 'New Episode' first.", ""
    if episode_state["obs"].done:
        return (
            render_grid(episode_state["obs"]),
            get_status_text(episode_state["obs"]),
            "Episode already ended.",
        )

    c = get_client()
    obs = episode_state["obs"]
    agent_type = episode_state["agent_type"]

    if agent_type == "greedy":
        action = get_greedy_action(obs)
    else:
        action = get_greedy_action(obs)

    obs = c.step(action)
    episode_state["obs"] = obs
    episode_state["step_count"] += 1
    episode_state["total_reward"] += obs.reward if obs.reward else 0.0

    step_log = (
        f"[STEP {episode_state['step_count']}] "
        f"Action: {action.direction}/{action.action} | "
        f"Pos: {obs.robot_position} | "
        f"Reward: {obs.reward} | "
        f"Delivered: {obs.delivered_count}/{obs.total_packages}"
    )
    episode_state["log"].append(step_log)

    img = render_grid(obs)
    status = get_status_text(obs)
    log = "\n".join(episode_state["log"][-20:])

    return img, status, log


def run_full_episode(task_level, agent_type):
    """Run an entire episode automatically."""
    global episode_state
    c = get_client()
    obs = c.reset(options={"task_level": task_level})
    step_count = 0
    total_reward = 0.0
    log_lines = []

    log_lines.append(f"[START] Episode — {task_level.upper()} | Agent: {agent_type}")

    while not obs.done:
        if obs.carrying_package is None:
            undelivered = [p for p in obs.packages if not p["delivered"]]
            if not undelivered:
                action = RobotAction(direction="up", action="no_op")
            else:
                target = min(
                    undelivered,
                    key=lambda p: (
                        abs(p["position"][0] - obs.robot_position[0])
                        + abs(p["position"][1] - obs.robot_position[1])
                    ),
                )
                tx, ty = target["position"]
                if [obs.robot_position[0], obs.robot_position[1]] == [tx, ty]:
                    action = RobotAction(direction="up", action="pick")
                else:
                    action = RobotAction(
                        direction=_direction_towards(
                            obs.robot_position[0], obs.robot_position[1], tx, ty
                        ),
                        action="move",
                    )
        else:
            if [obs.robot_position[0], obs.robot_position[1]] == [0, 0]:
                action = RobotAction(direction="up", action="deliver")
            else:
                action = RobotAction(
                    direction=_direction_towards(
                        obs.robot_position[0], obs.robot_position[1], 0, 0
                    ),
                    action="move",
                )

        obs = c.step(action)
        step_count += 1
        total_reward += obs.reward if obs.reward else 0.0

        log_lines.append(
            f"[STEP {step_count}] {action.direction}/{action.action} | "
            f"Pos: {obs.robot_position} | Reward: {obs.reward}"
        )

    score = obs.delivered_count / obs.total_packages if obs.total_packages > 0 else 0.0
    log_lines.append(
        f"\n[END] Score: {score:.2f} | Delivered: {obs.delivered_count}/{obs.total_packages}"
    )

    episode_state = {
        "obs": obs,
        "task_level": task_level,
        "agent_type": agent_type,
        "step_count": step_count,
        "total_reward": total_reward,
        "log": log_lines,
    }

    img = render_grid(obs)
    status = get_status_text(obs)
    log = "\n".join(log_lines)

    return img, status, log


def run_all_tasks():
    """Run all three difficulty levels and show results."""
    c = get_client()
    results = []

    for task in ["easy", "medium", "hard"]:
        obs = c.reset(options={"task_level": task})
        step_count = 0
        total_reward = 0.0

        while not obs.done:
            if obs.carrying_package is None:
                undelivered = [p for p in obs.packages if not p["delivered"]]
                if not undelivered:
                    action = RobotAction(direction="up", action="no_op")
                else:
                    target = min(
                        undelivered,
                        key=lambda p: (
                            abs(p["position"][0] - obs.robot_position[0])
                            + abs(p["position"][1] - obs.robot_position[1])
                        ),
                    )
                    tx, ty = target["position"]
                    if [obs.robot_position[0], obs.robot_position[1]] == [tx, ty]:
                        action = RobotAction(direction="up", action="pick")
                    else:
                        action = RobotAction(
                            direction=_direction_towards(
                                obs.robot_position[0], obs.robot_position[1], tx, ty
                            ),
                            action="move",
                        )
            else:
                if [obs.robot_position[0], obs.robot_position[1]] == [0, 0]:
                    action = RobotAction(direction="up", action="deliver")
                else:
                    action = RobotAction(
                        direction=_direction_towards(
                            obs.robot_position[0], obs.robot_position[1], 0, 0
                        ),
                        action="move",
                    )

            obs = c.step(action)
            step_count += 1
            total_reward += obs.reward if obs.reward else 0.0

        score = (
            obs.delivered_count / obs.total_packages if obs.total_packages > 0 else 0.0
        )
        results.append(
            f"{task.upper()}: Score={score:.2f}, Delivered={obs.delivered_count}/{obs.total_packages}, Steps={step_count}"
        )

    return "\n".join(results)


with gr.Blocks(title="Smart Warehouse Simulator", theme=gr.themes.Soft()) as app:
    gr.Markdown("# Smart Warehouse Simulator")
    gr.Markdown(
        "AI agent navigates a grid warehouse, picks packages, and delivers them under time deadlines."
    )

    with gr.Row():
        with gr.Column(scale=2):
            grid_output = gr.Image(label="Warehouse Grid", type="numpy")
        with gr.Column(scale=1):
            status_output = gr.Textbox(label="Status", lines=10)
            log_output = gr.Textbox(label="Episode Log", lines=15)

    with gr.Row():
        task_level = gr.Dropdown(
            choices=["easy", "medium", "hard"],
            value="easy",
            label="Task Level",
        )
        agent_type = gr.Dropdown(
            choices=["greedy"],
            value="greedy",
            label="Agent Type",
        )

    with gr.Row():
        reset_btn = gr.Button("New Episode")
        step_btn = gr.Button("Step")
        run_btn = gr.Button("Run Full Episode")
        benchmark_btn = gr.Button("Run All Tasks (Benchmark)")

    benchmark_output = gr.Textbox(label="Benchmark Results", lines=5)

    reset_btn.click(
        reset_episode,
        inputs=[task_level, agent_type],
        outputs=[grid_output, status_output, log_output],
    )
    step_btn.click(step_episode, outputs=[grid_output, status_output, log_output])
    run_btn.click(
        run_full_episode,
        inputs=[task_level, agent_type],
        outputs=[grid_output, status_output, log_output],
    )
    benchmark_btn.click(run_all_tasks, outputs=[benchmark_output])

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7861)

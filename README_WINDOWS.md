# Windows Setup Guide

## Prerequisites
- Python 3.11+ installed (download from python.org)
- Add Python to PATH during installation

## Setup Virtual Environment

1. Open **Command Prompt** or **PowerShell**

2. Create and activate venv:
```cmd
cd C:\path\to\warehouse_simulator
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```cmd
pip install -r requirements.txt
```

## Running the Project

1. **Start the environment server** (in one terminal):
```cmd
venv\Scripts\python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

2. **Run the agent** (in a second terminal):
```cmd
venv\Scripts\activate
python inference.py
```

## Troubleshooting

- If you get `Permission denied` errors, run PowerShell as Administrator
- For firewall prompts, allow Python through when prompted
- Use `python` instead of `python3` on Windows

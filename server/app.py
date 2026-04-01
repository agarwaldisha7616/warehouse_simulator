import sys, os
# Add /app/server to path → finds environment.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Add /app to path → finds models.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openenv.core.env_server import create_fastapi_app
from environment import SmartWarehouseEnv
from models import RobotAction, RobotObservation

app = create_fastapi_app(SmartWarehouseEnv, RobotAction, RobotObservation)
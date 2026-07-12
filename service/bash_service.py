import os
import subprocess
from utils.logger import get_logger

logger = get_logger(__name__)

def run_command(command: str) -> subprocess.CompletedProcess[str]:
    logger.info("Running command")
    os.makedirs("/tmp/workspace", exist_ok=True)
    result = subprocess.run(
        command, shell=True, text=True, capture_output=True,
        cwd="/tmp/workspace",
    )
    logger.info("Command exited with code %s", result.returncode)
    return result

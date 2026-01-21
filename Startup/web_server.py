import subprocess
from pathlib import Path

STARTUP_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = STARTUP_DIR.parent / "frontend"

subprocess.run(
    ["cmd.exe", "/c", "npx", "vite"],
    cwd=str(FRONTEND_DIR),
    check=True
)

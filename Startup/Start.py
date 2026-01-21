import os
import sys
import subprocess
from pathlib import Path

ENV_PATH = Path("config.env")
STARTUP_DIR = Path(__file__).resolve().parent
REQUIRED_KEYS = ["WEB_PIN", "SMB_PIN", "PREFERENCE"]  # PREFERENCE: web | smb | both

def load_env_file():
    """Load config.env into os.environ (simple KEY=VALUE lines)."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

def save_env_file():
    """Write required keys back to config.env."""
    lines = ["# Auto-generated config for simulation"]
    for k in REQUIRED_KEYS:
        lines.append(f"{k}={os.environ[k]}")
    ENV_PATH.write_text("\n".join(lines) + "\n")

def ensure_config():
    """If env vars exist, do nothing. Otherwise ask user and set them."""
    missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
    if not missing:
        return

    print("Missing config:", ", ".join(missing))
    print("Let’s set it once. This will be saved to config.env\n")

    # Pins (just numbers for now; later they map to GPIO pins)
    web_pin = input("Enter WEB_PIN (example 17): ").strip() or "17"
    smb_pin = input("Enter SMB_PIN (example 27): ").strip() or "27"

    # Preference
    print("\nPreference options: web | smb | both")
    pref = input("Enter PREFERENCE: ").strip().lower() or "web"
    if pref not in ("web", "smb", "both"):
        print("Invalid preference; defaulting to 'web'")
        pref = "web"

    os.environ["WEB_PIN"] = web_pin
    os.environ["SMB_PIN"] = smb_pin
    os.environ["PREFERENCE"] = pref

    save_env_file()
    print("\nSaved configuration to config.env\n")

def run_script(script_name: str):
    script_path = STARTUP_DIR / script_name
    print(f"\n[START] Running: {script_path}")
    subprocess.run([sys.executable, str(script_path), "start"], check=True)
    print(f"[DONE] {script_name}\n")

def main():
    load_env_file()
    ensure_config()

    pref = os.environ["PREFERENCE"]
    print(f"Using config: WEB_PIN={os.environ['WEB_PIN']} SMB_PIN={os.environ['SMB_PIN']} PREFERENCE={pref}")

    if pref == "web":
        run_script("web_server.py")
    elif pref == "smb":
        run_script("smb_server.py")
    elif pref == "both":
        run_script("smb_server.py")
        run_script("web_server.py")
        

if __name__ == "__main__":
    main()

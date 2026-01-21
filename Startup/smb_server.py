import os
import sys
import subprocess
from pathlib import Path

# ---------- Config ----------
SHARE_NAME = os.environ.get("SMB_SHARE_NAME", "MyNASShare")
SHARE_DIR = Path(os.environ.get("SMB_SHARE_DIR", r"C:\MyNAS\shared")).resolve()
HIDDEN_DIR_NAME = os.environ.get("SMB_HIDDEN_DIR", ".hidden")
HIDDEN_DIR = SHARE_DIR / HIDDEN_DIR_NAME

# ---------- Helpers ----------
def ensure_dirs():
    SHARE_DIR.mkdir(parents=True, exist_ok=True)
    HIDDEN_DIR.mkdir(parents=True, exist_ok=True)

def set_hidden_windows(path: Path):
    # No manual "C:\" prefix — use the absolute path as-is
    subprocess.run(["cmd.exe", "/c", "attrib", "+h", str(path)], check=False)

def ps(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        text=True,
        capture_output=True
    )

# ---------- Windows SMB Share Control (reliable) ----------
def win_create_share():
    # Remove existing share (if any), then create fresh pointing to SHARE_DIR
    remove_cmd = f'Remove-SmbShare -Name "{SHARE_NAME}" -Force -ErrorAction SilentlyContinue'
    create_cmd = f'New-SmbShare -Name "{SHARE_NAME}" -Path "{SHARE_DIR}" -FullAccess "Everyone"'

    ps(remove_cmd)
    r = ps(create_cmd)

    if r.returncode != 0:
        print("PowerShell output:")
        print((r.stdout or "").strip())
        print((r.stderr or "").strip())
        print("\nFAILED to create SMB share. Run PowerShell as Administrator.")
        sys.exit(r.returncode)

def win_delete_share():
    remove_cmd = f'Remove-SmbShare -Name "{SHARE_NAME}" -Force -ErrorAction SilentlyContinue'
    r = ps(remove_cmd)
    if r.returncode == 0:
        print("SMB share removed (if it existed).")
    else:
        print((r.stdout or "").strip())
        print((r.stderr or "").strip())
        print("FAILED to remove share (run as Administrator).")

def win_status_share():
    status_cmd = f'Get-SmbShare -Name "{SHARE_NAME}" | Select-Object Name,Path | Format-Table -AutoSize'
    r = ps(status_cmd)
    out = (r.stdout or "").strip()
    if out:
        print(out)
    else:
        print("Windows SMB share status: not found")
        print((r.stderr or "").strip())

def print_instructions():
    print("\n=== SMB READY ===")
    print(rf"Open File Explorer and go to: \\localhost\{SHARE_NAME}")
    print(f"Share backing folder (local): {SHARE_DIR}")

    print("\nHidden folder:")
    print(f" - Local path: {HIDDEN_DIR}")
    print(rf" - Through SMB: \\localhost\{SHARE_NAME}\{HIDDEN_DIR_NAME}")

    print("\nIf you don’t see the hidden folder in File Explorer:")
    print("  File Explorer → View → Show → Hidden items (turn ON)")
    print("================================\n")

# ---------- Main ----------
def main():
    if os.name != "nt":
        print("This SMB script is currently implemented for Windows dev.")
        sys.exit(1)

    action = (sys.argv[1].lower() if len(sys.argv) > 1 else "start")

    if action in ("start", "up"):
        ensure_dirs()
        set_hidden_windows(HIDDEN_DIR)
        win_create_share()
        print_instructions()

    elif action in ("stop", "down"):
        win_delete_share()

    elif action == "status":
        win_status_share()

    elif action == "restart":
        win_delete_share()
        ensure_dirs()
        set_hidden_windows(HIDDEN_DIR)
        win_create_share()
        print_instructions()

    else:
        print("Usage: py smb_server.py [start|stop|restart|status]")
        sys.exit(2)

if __name__ == "__main__":
    main()

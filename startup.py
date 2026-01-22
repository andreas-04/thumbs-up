import os
import sys
import subprocess
import threading
from pathlib import Path

ENV_PATH = Path("config.env")
STARTUP_DIR = Path(__file__).resolve().parent
REQUIRED_KEYS_BASE = ["PREFERENCE"]  # PREFERENCE: web | smb | both
REQUIRED_KEYS_WEB = ["WEB_PIN"]
REQUIRED_KEYS_SMB = ["SMB_GUEST_USER", "SMB_GUEST_PASSWORD"]

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
    """Write configuration back to config.env."""
    lines = ["# Auto-generated config for ThumbsUp"]
    
    # Always save preference
    if "PREFERENCE" in os.environ:
        lines.append(f"PREFERENCE={os.environ['PREFERENCE']}")
    
    # Save web-specific config
    pref = os.environ.get("PREFERENCE", "")
    if pref in ("web", "both") and "WEB_PIN" in os.environ:
        lines.append(f"WEB_PIN={os.environ['WEB_PIN']}")
    
    # Save SMB-specific config
    if pref in ("smb", "both"):
        if "SMB_GUEST_USER" in os.environ:
            lines.append(f"SMB_GUEST_USER={os.environ['SMB_GUEST_USER']}")
        if "SMB_GUEST_PASSWORD" in os.environ:
            lines.append(f"SMB_GUEST_PASSWORD={os.environ['SMB_GUEST_PASSWORD']}")
    
    ENV_PATH.write_text("\n".join(lines) + "\n")

def ensure_config():
    """If env vars exist, do nothing. Otherwise ask user and set them."""
    # Check if preference exists
    if not os.environ.get("PREFERENCE"):
        print("Let's configure ThumbsUp. This will be saved to config.env\n")
        
        # Ask preference first
        print("Preference options:")
        print("  web  - Web interface only (requires PIN)")
        print("  smb  - SMB file sharing only (requires credentials)")
        print("  both - Both web and SMB services")
        print()
        
        pref = ""
        while not pref or pref not in ("web", "smb", "both"):
            pref = input("Enter PREFERENCE: ").strip().lower()
            if not pref:
                print("Preference is required. Please enter a value.")
            elif pref not in ("web", "smb", "both"):
                print("Invalid preference. Must be: web, smb, or both")
        
        os.environ["PREFERENCE"] = pref
        print()
    else:
        pref = os.environ["PREFERENCE"]
    
    # Ask for web PIN if web service is enabled
    if pref in ("web", "both") and not os.environ.get("WEB_PIN"):
        print("Web service configuration:")
        web_pin = ""
        while not web_pin:
            web_pin = input("Create an integer web PIN: ").strip()
            if not web_pin:
                print("PIN is required. Please enter a value.")
        
        os.environ["WEB_PIN"] = web_pin
        print()
    
    # Ask for SMB credentials if SMB service is enabled
    if pref in ("smb", "both"):
        if not os.environ.get("SMB_GUEST_USER"):
            print("SMB service configuration:")
            smb_user = input("SMB username (default: guest): ").strip() or "guest"
            os.environ["SMB_GUEST_USER"] = smb_user
        
        if not os.environ.get("SMB_GUEST_PASSWORD"):
            smb_pass = input("SMB password (default: guest): ").strip() or "guest"
            os.environ["SMB_GUEST_PASSWORD"] = smb_pass
            print()
    
    save_env_file()
    print("[OK] Configuration saved to config.env\n")

def reset_credentials():
    """Reset all credentials and preferences."""
    if ENV_PATH.exists():
        print("Current configuration found in config.env")
        confirm = input("Are you sure you want to reset all credentials? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("Reset cancelled.")
            return
        
        # Backup old config
        backup_path = ENV_PATH.with_suffix(".env.backup")
        ENV_PATH.rename(backup_path)
        print(f"[OK] Old config backed up to {backup_path}")
    
    # Clear environment variables
    for key in ["PREFERENCE", "WEB_PIN", "SMB_GUEST_USER", "SMB_GUEST_PASSWORD"]:
        os.environ.pop(key, None)
    
    print("[OK] Credentials reset")
    print("\nRunning configuration setup...\n")
    
    # Run config setup
    ensure_config()
    print("[OK] New credentials configured successfully!\n")

def install_service():
    """Install and enable the systemd service."""
    service_file = STARTUP_DIR / "thumbsup.service"
    service_dest = Path("/etc/systemd/system/thumbsup.service")
    
    if not service_file.exists():
        print("Error: thumbsup.service file not found!")
        sys.exit(1)
    
    # Check if running with sudo
    if os.geteuid() != 0:
        print("Error: This command requires sudo privileges.")
        print("Please run: sudo python3 startup.py setup-service")
        sys.exit(1)
    
    # Update service file with current paths
    service_content = service_file.read_text()
    service_content = service_content.replace("/home/pi/thumbs-up", str(STARTUP_DIR))
    service_content = service_content.replace("User=pi", f"User={os.getenv('SUDO_USER', 'pi')}")
    
    # Write to systemd directory
    service_dest.write_text(service_content)
    print(f"[OK] Copied service file to {service_dest}")
    
    # Reload systemd, enable and start service
    try:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        print("[OK] Reloaded systemd daemon")
        
        subprocess.run(["systemctl", "enable", "thumbsup.service"], check=True)
        print("[OK] Enabled thumbsup.service (will start on boot)")
        
        subprocess.run(["systemctl", "start", "thumbsup.service"], check=True)
        print("[OK] Started thumbsup.service")
        
        print("\n[OK] Service installation complete!")
        print("\nUseful commands:")
        print("  sudo systemctl status thumbsup.service  - Check service status")
        print("  sudo journalctl -u thumbsup.service -f  - View logs")
        print("  sudo systemctl restart thumbsup.service - Restart service")
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to configure systemd service: {e}")
        sys.exit(1)

def start_web_server():
    """Start the web server using the start_webserver.sh script."""
    start_script = STARTUP_DIR / "backend" / "apiv2" / "start_webserver.sh"
    
    if not start_script.exists():
        print(f"Error: Web server start script not found at {start_script}")
        sys.exit(1)
    
    # Make script executable
    start_script.chmod(0o755)
    
    print(f"[WEB] Starting web server...")
    print()
    
    # Run the start script with current environment (includes ADMIN_PIN)
    try:
        subprocess.run(["bash", str(start_script)], 
                      cwd=start_script.parent,
                      env=os.environ.copy(),
                      check=True)
    except KeyboardInterrupt:
        print("\n\nWeb server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Web server exited with error: {e}")
        sys.exit(1)

def start_smb_server():
    """Start the SMB server with default guest admin access."""
    start_script = STARTUP_DIR / "backend" / "apiv2" / "start_smb.sh"
    
    if not start_script.exists():
        print(f"Error: SMB server start script not found at {start_script}")
        sys.exit(1)
    
    # Make script executable
    start_script.chmod(0o755)
    
    print(f"[SMB] Starting SMB server...")
    print()
    
    # Run the start script with current environment
    try:
        subprocess.run(["bash", str(start_script)], 
                      cwd=start_script.parent,
                      env=os.environ.copy(),
                      check=True)
    except KeyboardInterrupt:
        print("\n\nSMB server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: SMB server exited with error: {e}")
        sys.exit(1)

def start_both_servers():
    """Start both web and SMB servers in parallel threads."""
    print("Starting both web and SMB servers in parallel...\n")
    
    # Create threads for each server
    web_thread = threading.Thread(target=start_web_server, name="WebServer", daemon=True)
    smb_thread = threading.Thread(target=start_smb_server, name="SMBServer", daemon=True)
    
    # Start both threads
    web_thread.start()
    smb_thread.start()
    
    print("[OK] Both services started")
    print("   Press Ctrl+C to stop all servers\n")
    
    try:
        # Keep main thread alive and wait for threads
        web_thread.join()
        smb_thread.join()
    except KeyboardInterrupt:
        print("\n\nStopping all servers...")
        print("[OK] Services stopped")

def load_apiv2_env():
    """Load backend/apiv2/.env.example and set ADMIN_PIN from WEB_PIN."""
    apiv2_env_path = STARTUP_DIR / "backend" / "apiv2" / ".env.example"
    if apiv2_env_path.exists():
        for line in apiv2_env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            # Don't override ADMIN_PIN from .env.example, we'll set it from WEB_PIN
            if key != "ADMIN_PIN" and key not in os.environ:
                os.environ[key] = v.strip()
    
    # Set ADMIN_PIN from WEB_PIN
    if "WEB_PIN" in os.environ:
        os.environ["ADMIN_PIN"] = os.environ["WEB_PIN"]

def main():
    # Check for reset-credentials command
    if len(sys.argv) > 1 and sys.argv[1] == "reset-credentials":
        load_env_file()
        reset_credentials()
        return
    
    # Check for setup-service command
    if len(sys.argv) > 1 and sys.argv[1] == "setup-service":
        # First ensure config exists
        load_env_file()
        if not ENV_PATH.exists():
            print("Running initial setup before installing service...\n")
            ensure_config()
        install_service()
        return
    
    load_env_file()
    ensure_config()
    
    load_apiv2_env()

    pref = os.environ["PREFERENCE"]
    
    # Display config (mask sensitive info)
    print(f"Using config: PREFERENCE={pref}")
    if pref in ("web", "both"):
        print(f"  WEB_PIN: {'*' * len(os.environ.get('WEB_PIN', ''))}")
    if pref in ("smb", "both"):
        print(f"  SMB_USER: {os.environ.get('SMB_GUEST_USER', 'guest')}")
        print(f"  SMB_PASS: {'*' * len(os.environ.get('SMB_GUEST_PASSWORD', ''))}")
    print()

    if pref == "web":
        start_web_server()
    elif pref == "smb":
        start_smb_server()
    elif pref == "both":
        start_both_servers()
        

if __name__ == "__main__":
    main()

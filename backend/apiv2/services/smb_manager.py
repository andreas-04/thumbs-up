#!/usr/bin/env python3
"""
SMB Manager for ThumbsUp
Manages Samba configuration and service lifecycle with default guest admin access.
"""

import os
import subprocess
import tempfile
import socket
from pathlib import Path
from typing import Optional


class SMBManager:
    """Manages Samba server configuration and lifecycle."""
    
    # Default guest/admin credentials (can be overridden via env vars)
    DEFAULT_GUEST_USER = "guest"
    DEFAULT_GUEST_PASSWORD = "guest"
    
    def __init__(self, storage_path: str, service_name: str = "ThumbsUp", 
                 port: int = None, workgroup: str = "WORKGROUP"):
        """
        Initialize SMB Manager.
        
        Args:
            storage_path: Path to shared storage directory
            service_name: Service name for mDNS and share description
            port: SMB port (default 445, or 4450 for WSL/testing)
            workgroup: Windows workgroup name
        """
        self.storage_path = Path(storage_path).resolve()
        self.service_name = service_name
        
        # Auto-detect port: use 4450 for WSL, 445 for native Linux
        if port is None:
            # Check if running in WSL
            try:
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        port = 4450  # WSL detected
                    else:
                        port = 445   # Native Linux
            except:
                port = 445  # Default to standard port
        
        self.port = port
        self.workgroup = workgroup
        
        # Get server hostname/IP
        self.hostname = socket.gethostname()
        # Add .local for mDNS/Avahi resolution
        if not self.hostname.endswith('.local'):
            self.mdns_hostname = f"{self.hostname}.local"
        else:
            self.mdns_hostname = self.hostname
        
        try:
            self.ip_address = socket.gethostbyname(self.hostname)
        except:
            self.ip_address = '127.0.0.1'
        
        # Get credentials from env or use defaults
        self.guest_user = os.getenv('SMB_GUEST_USER', self.DEFAULT_GUEST_USER)
        self.guest_password = os.getenv('SMB_GUEST_PASSWORD', self.DEFAULT_GUEST_PASSWORD)
        
        # Configuration paths
        self.config_dir = Path(__file__).parent / "smb_config"
        self.config_file = self.config_dir / "smb.conf"
        self.pid_file = self.config_dir / "smbd.pid"
        
        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def generate_smb_config(self) -> str:
        """
        Generate Samba configuration with guest admin access.
        
        Returns:
            Path to generated config file
        """
        config_content = f"""# ThumbsUp SMB Configuration
# Auto-generated - DO NOT EDIT MANUALLY

[global]
    # Server identity
    workgroup = {self.workgroup}
    server string = {self.service_name}
    netbios name = THUMBSUP
    
    # Security settings
    security = user
    map to guest = never
    passdb backend = tdbsam
    
    # SMB3 with encryption
    min protocol = SMB3
    smb encrypt = desired
    
    # Performance and compatibility
    socket options = TCP_NODELAY IPTOS_LOWDELAY SO_RCVBUF=131072 SO_SNDBUF=131072
    read raw = yes
    write raw = yes
    max xmit = 65535
    
    # Logging
    log level = 1
    log file = {self.config_dir}/smb.log
    max log size = 1000
    
    # Disable printing
    load printers = no
    printing = bsd
    printcap name = /dev/null
    disable spoolss = yes
    
    # Port configuration (non-standard port for WSL compatibility)
    smb ports = {self.port}
    
    # Guest account mapping
    guest account = {self.guest_user}

[thumbsup]
    comment = {self.service_name} - Full Access Storage
    path = {self.storage_path}
    
    # Full read/write access for authenticated users
    valid users = {self.guest_user}
    read only = no
    writable = yes
    browseable = yes
    
    # Permissions
    create mask = 0644
    directory mask = 0755
    force user = {os.getenv('USER', 'nobody')}
    
    # Enable recycle bin (optional - can be disabled)
    vfs objects = recycle
    recycle:repository = .recycle
    recycle:keeptree = yes
    recycle:versions = yes
"""
        
        self.config_file.write_text(config_content)
        return str(self.config_file)
    
    def create_guest_user(self) -> bool:
        """
        Create the guest admin user with Samba password.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"Setting up SMB user: {self.guest_user}")
            
            # First, check if system user exists, create if not
            user_check = subprocess.run(['id', self.guest_user], 
                                       capture_output=True, text=True)
            
            if user_check.returncode != 0:
                # User doesn't exist, create it as a system user (no login)
                print(f"Creating system user: {self.guest_user}")
                create_user = subprocess.run(
                    ['useradd', '-r', '-s', '/usr/sbin/nologin', self.guest_user],
                    capture_output=True, text=True
                )
                
                if create_user.returncode != 0:
                    print(f"Warning: Could not create system user: {create_user.stderr}")
                    print(f"   Continuing anyway, Samba may work without system user...")
            
            # Now add Samba user
            process = subprocess.Popen(
                ['smbpasswd', '-a', '-s', self.guest_user],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send password twice (new password + confirmation)
            stdout, stderr = process.communicate(
                input=f"{self.guest_password}\n{self.guest_password}\n"
            )
            
            if process.returncode == 0:
                print(f"[OK] SMB user '{self.guest_user}' configured")
                
                # Enable the user
                subprocess.run(
                    ['smbpasswd', '-e', self.guest_user],
                    check=False,
                    capture_output=True
                )
                return True
            else:
                print(f"WARNING: Could not create SMB user: {stderr}")
                print(f"   System may not be configured correctly")
                return False
                
        except FileNotFoundError:
            print("⚠ Warning: smbpasswd not found. Please install Samba:")
            print("   Ubuntu/Debian: sudo apt-get install samba")
            print("   macOS: brew install samba")
            return False
        except Exception as e:
            print(f"⚠ Warning: Error creating SMB user: {e}")
            return False
    
    def start_service(self) -> Optional[subprocess.Popen]:
        """
        Start the Samba service (smbd).
        
        Returns:
            Process object if started successfully, None otherwise
        """
        # Generate fresh config
        config_path = self.generate_smb_config()
        print(f"[OK] Generated SMB config: {config_path}")
        
        # Create guest user
        self.create_guest_user()
        
        try:
            # Try to start smbd in foreground mode with our config
            print(f"Starting SMB service on port {self.port}...")
            
            process = subprocess.Popen(
                [
                    'smbd',
                    '--foreground',
                    '--no-process-group',
                    '--configfile', str(self.config_file),
                    '--debuglevel', '1',
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            
            # Check if still running
            if process.poll() is None:
                print(f"[OK] SMB service started (PID: {process.pid})")
                
                # Display connection info with correct port
                if self.port == 445:
                    print(f"[OK] Share available at: smb://{self.mdns_hostname}/thumbsup")
                    print(f"  Or use IP: smb://{self.ip_address}/thumbsup")
                else:
                    print(f"[OK] Share available at: smb://{self.mdns_hostname}:{self.port}/thumbsup")
                    print(f"  Or use IP: smb://{self.ip_address}:{self.port}/thumbsup")
                    print(f"  (Using port {self.port} - WSL/Testing mode)")
                
                print(f"  Username: {self.guest_user}")
                print(f"  Password: {self.guest_password}")
                self.pid_file.write_text(str(process.pid))
                return process
            else:
                stdout, _ = process.communicate()
                print(f"ERROR: SMB service failed to start")
                print(f"   Output: {stdout}")
                return None
                
        except FileNotFoundError:
            print("ERROR: 'smbd' command not found")
            print("   Please install Samba:")
            print("   Ubuntu/Debian: sudo apt-get install samba")
            print("   macOS: brew install samba")
            return None
        except Exception as e:
            print(f"ERROR: Error starting SMB service: {e}")
            return None
    
    def stop_service(self):
        """Stop the Samba service."""
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                os.kill(pid, 15)  # SIGTERM
                print(f"[OK] SMB service stopped (PID: {pid})")
                self.pid_file.unlink()
            except (ValueError, ProcessLookupError, FileNotFoundError):
                pass
    
    def get_connection_info(self) -> dict:
        """
        Get connection information for clients.
        
        """
        # Build URL with port if non-standard
        if self.port == 445:
            url = f'smb://{self.mdns_hostname}/thumbsup'
            url_ip = f'smb://{self.ip_address}/thumbsup'
        else:
            url = f'smb://{self.mdns_hostname}:{self.port}/thumbsup'
            url_ip = f'smb://{self.ip_address}:{self.port}/thumbsup'
        
        return {
            'service_name': self.service_name,
            'share_name': 'thumbsup',
            'username': self.guest_user,
            'password': self.guest_password,
            'workgroup': self.workgroup,
            'hostname': self.hostname,
            'mdns_hostname': self.mdns_hostname,
            'ip_address': self.ip_address,
            'port': self.port,
            'url': url,
            'url_ip': url_ip,
            'storage_path': str(self.storage_path)
        }


if __name__ == "__main__":
    # Test the SMB manager
    import sys
    
    storage = Path(__file__).parent / "storage"
    manager = SMBManager(storage_path=str(storage))
    
    print("=== ThumbsUp SMB Manager Test ===\n")
    
    # Generate config
    config = manager.generate_smb_config()
    print(f"Config generated: {config}\n")
    
    # Show connection info
    info = manager.get_connection_info()
    print("Connection Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    print("\n[!] Note: Run with sudo to actually start the service")

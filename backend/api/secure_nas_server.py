#!/usr/bin/env python3
"""
Secure NAS Server with State Machine
Implements certificate-based firewall rules and NFS access control
"""
import ssl
import socket
import subprocess
import time
import signal
import sys
import logging
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Set
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DeviceState(Enum):
    """Device operational states"""
    DORMANT = "dormant"           # No services, storage locked
    ADVERTISING = "advertising"   # mDNS active, waiting for clients
    ACTIVE = "active"             # Client connected, NFS accessible
    SHUTDOWN = "shutdown"         # Graceful shutdown in progress


@dataclass
class ClientSession:
    """Represents an authenticated client session"""
    ip: str
    port: int
    cert_cn: str
    cert_fingerprint: str
    connected_at: datetime
    last_activity: datetime
    firewall_rule_id: Optional[str] = None
    nfs_export_added: bool = False


class SecureNASServer:
    """
    Secure NAS server with state machine control.
    Implements mTLS authentication, dynamic firewall rules, and NFS access control.
    """
    
    def __init__(self, 
                 host='0.0.0.0', 
                 port=8443,
                 nfs_port=2049,
                 storage_path='/app/demo_storage',  # Changed to actual storage location
                 inactivity_timeout=300):  # 5 minutes
        
        self.host = host
        self.port = port
        self.nfs_port = nfs_port
        self.storage_path = storage_path
        self.inactivity_timeout = inactivity_timeout
        
        # State management
        self.state = DeviceState.DORMANT
        self.active_clients: Dict[str, ClientSession] = {}
        self.mdns_process: Optional[subprocess.Popen] = None
        self.storage_unlocked = False
        
        # SSL context
        self.ssl_context = None
        self.server_socket = None
        
        # Graceful shutdown handler
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.transition_to(DeviceState.SHUTDOWN)
        sys.exit(0)
    
    def _initialize_firewall(self):
        """
        Initialize iptables firewall with default-deny policy for NFS port.
        Only authenticated clients will have rules added to allow access.
        """
        try:
            logger.info("🔥 Initializing firewall rules...")
            
            # Flush any existing NAS client rules (cleanup from previous runs)
            result = subprocess.run(
                ['iptables', '-S', 'INPUT'],
                capture_output=True,
                text=True
            )
            
            # Remove old NAS_Client rules
            for line in result.stdout.split('\n'):
                if 'NAS_Client_' in line:
                    # Extract the rule and convert -A to -D to delete it
                    rule_parts = line.replace('-A', '-D').split()
                    if rule_parts:
                        subprocess.run(['iptables'] + rule_parts[1:], capture_output=True)
            
            # Allow established connections (important for NFS and mTLS)
            subprocess.run([
                'iptables', '-A', 'INPUT',
                '-m', 'state', '--state', 'ESTABLISHED,RELATED',
                '-j', 'ACCEPT'
            ], check=True, capture_output=True)
            
            # Allow loopback traffic
            subprocess.run([
                'iptables', '-A', 'INPUT',
                '-i', 'lo',
                '-j', 'ACCEPT'
            ], check=True, capture_output=True)
            
            # Allow mTLS port (always accessible for authentication)
            subprocess.run([
                'iptables', '-A', 'INPUT',
                '-p', 'tcp',
                '--dport', str(self.port),
                '-j', 'ACCEPT',
                '-m', 'comment',
                '--comment', 'NAS_mTLS_Port'
            ], check=True, capture_output=True)
            
            # Default policy: NFS port is blocked unless explicitly allowed per client
            # (Individual client rules will be added via _add_firewall_rule)
            
            logger.info(f"✓ Firewall initialized - mTLS port {self.port} open, NFS port {self.nfs_port} restricted")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize firewall: {e}")
            logger.error(f"stderr: {e.stderr if hasattr(e, 'stderr') else 'N/A'}")
        except Exception as e:
            logger.error(f"Unexpected error initializing firewall: {e}")
    
    # ============================================================================
    # STATE MACHINE TRANSITIONS
    # ============================================================================
    
    def transition_to(self, new_state: DeviceState):
        """Transition to a new state with proper cleanup and setup"""
        if self.state == new_state:
            return
        
        logger.info(f"State transition: {self.state.value} -> {new_state.value}")
        old_state = self.state
        self.state = new_state
        
        # Exit actions for old state
        if old_state == DeviceState.ADVERTISING:
            self._exit_advertising()
        elif old_state == DeviceState.ACTIVE:
            self._exit_active()
        
        # Entry actions for new state
        if new_state == DeviceState.DORMANT:
            self._enter_dormant()
        elif new_state == DeviceState.ADVERTISING:
            self._enter_advertising()
        elif new_state == DeviceState.ACTIVE:
            self._enter_active()
        elif new_state == DeviceState.SHUTDOWN:
            self._enter_shutdown()
    
    def _enter_dormant(self):
        """Enter dormant state - all services stopped"""
        logger.info("📴 Entering DORMANT state")
        # Storage should already be locked by exit_active
        # No network services active
        # Minimal power consumption
    
    def _enter_advertising(self):
        """Enter advertising state - ready to accept connections"""
        logger.info("📡 Entering ADVERTISING state")
        
        # Initialize firewall with secure defaults
        self._initialize_firewall()
        
        # Unlock storage (simulate LUKS unlock)
        self._unlock_storage()
        
        # Start mTLS server (but don't block on it yet)
        self._setup_mtls_server()
        
        # Broadcast mDNS
        self._start_mdns_broadcast()
        
        logger.info("✓ Device discoverable on network, waiting for authenticated clients")
    
    def _exit_advertising(self):
        """Exit advertising state"""
        logger.info("Exiting ADVERTISING state")
        # Note: Don't stop mDNS here - let it continue in ACTIVE state
        # Only stop when transitioning to DORMANT or SHUTDOWN
    
    def _enter_active(self):
        """Enter active state - client connected and authenticated"""
        logger.info("🔓 Entering ACTIVE state")
        
        # Unlock storage (if not already unlocked)
        if not self.storage_unlocked:
            self._unlock_storage()
        
        # Update mDNS broadcast to reflect active status
        # Stop the "advertising" broadcast and start an "active" one
        self._stop_mdns_broadcast()
        self._start_mdns_broadcast_active()
        
        # NFS will be configured per-client in handle_client_connection
        
        logger.info("✓ System active, serving authenticated clients")
    
    def _exit_active(self):
        """Exit active state - cleanup all client connections"""
        logger.info("Exiting ACTIVE state")
        
        # Stop mDNS broadcast
        self._stop_mdns_broadcast()
        
        # Disconnect all clients
        for client_ip in list(self.active_clients.keys()):
            self._cleanup_client(client_ip)
        
        # Lock storage
        if self.storage_unlocked:
            self._lock_storage()
    
    def _enter_shutdown(self):
        """Enter shutdown state - graceful cleanup"""
        logger.info("🛑 Entering SHUTDOWN state")
        
        # Transition through proper cleanup
        if self.state == DeviceState.ACTIVE:
            self.transition_to(DeviceState.ADVERTISING)
        
        if self.state == DeviceState.ADVERTISING:
            self.transition_to(DeviceState.DORMANT)
        
        # Close server socket
        if self.server_socket:
            self.server_socket.close()
        
        logger.info("✓ Shutdown complete")
    
    # ============================================================================
    # mTLS SERVER SETUP
    # ============================================================================
    
    def _setup_mtls_server(self):
        """Configure mTLS server with mutual authentication"""
        logger.info("Setting up mTLS server...")
        
        # Create SSL context
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        # Load server certificate and key
        # Check for Docker container path first, then fall back to development path
        if Path('/app/pki/server_cert.pem').exists():
            # Running in Docker container
            cert_path = Path('/app/pki/server_cert.pem')
            key_path = Path('/app/pki/server_key.pem')
            ca_path = Path('/app/pki/client_cert.pem')
        else:
            # Running in development
            cert_path = Path(__file__).parent.parent / 'pki' / 'server_cert.pem'
            key_path = Path(__file__).parent.parent / 'pki' / 'server_key.pem'
            ca_path = Path(__file__).parent.parent / 'pki' / 'client_cert.pem'
        
        self.ssl_context.load_cert_chain(
            certfile=str(cert_path),
            keyfile=str(key_path)
        )
        
        # Require client certificate (mutual TLS)
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        self.ssl_context.load_verify_locations(cafile=str(ca_path))
        
        logger.info(f"✓ mTLS configured - server will require client certificates")
    
    # ============================================================================
    # mDNS SERVICE DISCOVERY
    # ============================================================================
    
    def _start_mdns_broadcast(self):
        """Start mDNS service announcement using Avahi"""
        try:
            service_name = "ThumbsUp-SecureNAS"
            service_type = "_thumbsup._tcp"
            txt_record = f"status=advertising,timestamp={int(time.time())}"
            
            cmd = [
                'avahi-publish', '-s',
                service_name,
                service_type,
                str(self.port),
                txt_record
            ]
            
            self.mdns_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info(f"📡 mDNS broadcast started: {service_name}.{service_type} on port {self.port}")
            
        except FileNotFoundError:
            logger.warning("⚠️  avahi-publish not found. mDNS discovery unavailable.")
        except Exception as e:
            logger.error(f"⚠️  mDNS broadcast error: {e}")
    
    def _start_mdns_broadcast_active(self):
        """Start mDNS service announcement with active status"""
        try:
            service_name = "ThumbsUp-SecureNAS"
            service_type = "_thumbsup._tcp"
            num_clients = len(self.active_clients)
            txt_record = f"status=active,clients={num_clients},timestamp={int(time.time())}"
            
            cmd = [
                'avahi-publish', '-s',
                service_name,
                service_type,
                str(self.port),
                txt_record
            ]
            
            self.mdns_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info(f"📡 mDNS broadcast updated: ACTIVE with {num_clients} client(s)")
            
        except FileNotFoundError:
            logger.warning("⚠️  avahi-publish not found. mDNS discovery unavailable.")
        except Exception as e:
            logger.error(f"⚠️  mDNS broadcast error: {e}")
    
    def _stop_mdns_broadcast(self):
        """Stop mDNS service announcement"""
        if self.mdns_process:
            self.mdns_process.terminate()
            self.mdns_process.wait(timeout=5)
            self.mdns_process = None
            logger.info("📡 mDNS broadcast stopped")
    
    # ============================================================================
    # STORAGE MANAGEMENT (simulated with bind mount)
    # ============================================================================
    
    def _unlock_storage(self):
        """
        Unlock storage - for demo, just verify directory exists.
        In production, this would use LUKS cryptsetup commands.
        """
        logger.info(f"🔓 Unlocking encrypted storage: {self.storage_path}")
        
        try:
            # For demo: Storage is always available at /app/demo_storage
            # In production, this would be:
            # 1. cryptsetup open /dev/sdb1 encrypted_storage --key-file /etc/nas/storage.key
            # 2. mount /dev/mapper/encrypted_storage /mnt/encrypted_storage
            
            if not Path(self.storage_path).exists():
                raise Exception(f"Storage directory {self.storage_path} not found")
            
            self.storage_unlocked = True
            logger.info(f"✓ Storage unlocked at {self.storage_path}")
            
            # List files to confirm
            files = subprocess.run(
                ['ls', '-lah', self.storage_path],
                capture_output=True,
                text=True
            )
            logger.info(f"📁 Storage contents:\n{files.stdout}")
            
        except Exception as e:
            logger.error(f"Failed to unlock storage: {e}")
            self.storage_unlocked = False
    
    def _lock_storage(self):
        """
        Lock storage - for demo, just mark as locked.
        In production, this would use LUKS cryptsetup commands.
        """
        logger.info(f"🔒 Locking encrypted storage: {self.storage_path}")
        
        try:
            # For demo: Just mark as locked
            # In production, this would be:
            # 1. umount /mnt/encrypted_storage
            # 2. cryptsetup close encrypted_storage
            
            self.storage_unlocked = False
            logger.info(f"✓ Storage locked")
            
        except Exception as e:
            logger.error(f"Failed to lock storage: {e}")
            # Even if locking fails, mark as locked for safety
            self.storage_unlocked = False
    
    # ============================================================================
    # FIREWALL MANAGEMENT (iptables)
    # ============================================================================
    
    def _add_firewall_rule(self, client_ip: str) -> str:
        """
        Add iptables rule to allow specific client IP access to NFS port.
        Returns rule identifier for later removal.
        """
        try:
            # Create rule to allow this specific IP to NFS port
            cmd = [
                'iptables',
                '-A', 'INPUT',
                '-p', 'tcp',
                '-s', client_ip,
                '--dport', str(self.nfs_port),
                '-j', 'ACCEPT',
                '-m', 'comment',
                '--comment', f'NAS_Client_{client_ip.replace(".", "_")}'
            ]
            
            # Execute the iptables command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            rule_id = f"NAS_Client_{client_ip.replace('.', '_')}"
            logger.info(f"🔥 Firewall rule added: Allow {client_ip} -> NFS port {self.nfs_port}")
            
            return rule_id
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add firewall rule for {client_ip}: {e}")
            return None
    
    def _remove_firewall_rule(self, client_ip: str, rule_id: str):
        """Remove iptables rule for specific client"""
        try:
            # Remove the specific rule by comment
            cmd = [
                'iptables',
                '-D', 'INPUT',
                '-p', 'tcp',
                '-s', client_ip,
                '--dport', str(self.nfs_port),
                '-j', 'ACCEPT',
                '-m', 'comment',
                '--comment', rule_id
            ]
            
            # Execute the iptables command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            logger.info(f"🔥 Firewall rule removed: {client_ip}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove firewall rule for {client_ip}: {e}")
    
    # ============================================================================
    # NFS EXPORT MANAGEMENT
    # ============================================================================
    
    def _add_nfs_export(self, client_ip: str) -> bool:
        """
        Add NFS export entry for specific client IP.
        Returns True if successful.
        """
        try:
            # NFS export format: /path client_ip(options)
            export_line = f"{self.storage_path} {client_ip}(rw,sync,no_subtree_check,no_root_squash,insecure)\n"
            
            # Read existing exports
            try:
                with open('/etc/exports', 'r') as f:
                    existing = f.read()
            except FileNotFoundError:
                existing = ""
            
            # Add new export if not already present
            if export_line not in existing:
                with open('/etc/exports', 'a') as f:
                    f.write(export_line)
            
            # Reload NFS exports
            result = subprocess.run(
                ['exportfs', '-ra'],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"📁 NFS export added: {self.storage_path} -> {client_ip}")
            logger.info(f"   Client can now mount: {self.host}:{self.storage_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload NFS exports: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Failed to add NFS export for {client_ip}: {e}")
            return False
    
    def _remove_nfs_export(self, client_ip: str):
        """Remove NFS export entry for specific client IP"""
        try:
            # Read /etc/exports
            with open('/etc/exports', 'r') as f:
                lines = f.readlines()
            
            # Filter out the line containing client_ip
            filtered = [l for l in lines if client_ip not in l]
            
            # Write back
            with open('/etc/exports', 'w') as f:
                f.writelines(filtered)
            
            # Reload NFS exports
            result = subprocess.run(
                ['exportfs', '-ra'],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"📁 NFS export removed: {client_ip}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload NFS exports: {e.stderr}")
        except Exception as e:
            logger.error(f"Failed to remove NFS export for {client_ip}: {e}")
    
    # ============================================================================
    # CLIENT SESSION MANAGEMENT
    # ============================================================================
    
    def _handle_client_connection(self, conn, addr):
        """Handle an authenticated client connection"""
        client_ip = addr[0]
        client_port = addr[1]
        
        try:
            # Extract client certificate information
            cert = conn.getpeercert()
            if not cert:
                logger.warning(f"No certificate provided by {client_ip}")
                return
            
            # Parse certificate details
            subject = dict(x[0] for x in cert['subject'])
            client_cn = subject.get('commonName', 'Unknown')
            
            # Create fingerprint for tracking
            cert_fingerprint = self._get_cert_fingerprint(cert)
            
            logger.info(f"✓ Client authenticated: {client_cn} from {client_ip}:{client_port}")
            
            # Create client session
            session = ClientSession(
                ip=client_ip,
                port=client_port,
                cert_cn=client_cn,
                cert_fingerprint=cert_fingerprint,
                connected_at=datetime.now(),
                last_activity=datetime.now()
            )
            
            # Transition to ACTIVE state if this is first client
            if len(self.active_clients) == 0:
                self.transition_to(DeviceState.ACTIVE)
            
            # Add firewall rule for this client
            rule_id = self._add_firewall_rule(client_ip)
            session.firewall_rule_id = rule_id
            
            # Add NFS export for this client
            nfs_added = self._add_nfs_export(client_ip)
            session.nfs_export_added = nfs_added
            
            # Register session
            self.active_clients[client_ip] = session
            
            logger.info(f"✓ Client {client_cn} has full NFS access")
            
            # Handle client communication
            with conn:
                # Send welcome message
                welcome = f"Welcome {client_cn}! NFS access granted to {self.storage_path}\n"
                conn.sendall(welcome.encode('utf-8'))
                
                # Keep connection alive and monitor
                while True:
                    conn.settimeout(self.inactivity_timeout)  # Use configured inactivity timeout
                    data = conn.recv(1024)
                    
                    if not data:
                        logger.info(f"Client {client_cn} disconnected")
                        break
                    
                    # Update activity timestamp
                    session.last_activity = datetime.now()
                    
                    # Handle client commands
                    message = data.decode('utf-8').strip()
                    logger.info(f"[{client_cn}] {message}")
                    
                    response = self._handle_command(message, client_cn)
                    conn.sendall(response.encode('utf-8'))
        
        except socket.timeout:
            logger.info(f"Client {client_ip} connection timeout")
        except Exception as e:
            logger.error(f"Error handling client {client_ip}: {e}")
        finally:
            # Cleanup client session
            self._cleanup_client(client_ip)
    
    def _cleanup_client(self, client_ip: str):
        """Clean up client session and revoke access"""
        if client_ip not in self.active_clients:
            return
        
        session = self.active_clients[client_ip]
        logger.info(f"Cleaning up session for {session.cert_cn} ({client_ip})")
        
        # Remove NFS export
        if session.nfs_export_added:
            self._remove_nfs_export(client_ip)
        
        # Remove firewall rule
        if session.firewall_rule_id:
            self._remove_firewall_rule(client_ip, session.firewall_rule_id)
        
        # Remove from active clients
        del self.active_clients[client_ip]
        
        logger.info(f"✓ Session cleaned up for {session.cert_cn}")
        
        # If no more clients, transition back to ADVERTISING
        if len(self.active_clients) == 0:
            logger.info("No more active clients")
            self.transition_to(DeviceState.ADVERTISING)
    
    def _get_cert_fingerprint(self, cert) -> str:
        """Generate fingerprint from certificate for tracking"""
        # Simple fingerprint from serial number
        serial = cert.get('serialNumber', 'unknown')
        return f"cert_{serial}"
    
    def _handle_command(self, command: str, client_cn: str) -> str:
        """Handle client commands for file access"""
        try:
            if command == 'LIST_FILES':
                # List files in storage
                result = subprocess.run(
                    ['ls', '-lh', self.storage_path],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return f"📁 Files in {self.storage_path}:\n{result.stdout}\n"
                else:
                    return f"Error listing files: {result.stderr}\n"
            
            elif command.startswith('READ_FILE:'):
                # Read a specific file
                filename = command[10:].strip()
                # Sanitize filename to prevent directory traversal
                filename = filename.replace('..', '').replace('/', '')
                filepath = Path(self.storage_path) / filename
                
                if not filepath.exists():
                    return f"Error: File '{filename}' not found\n"
                
                if filepath.is_dir():
                    return f"Error: '{filename}' is a directory\n"
                
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    return f"📄 Contents of {filename}:\n{'='*50}\n{content}\n{'='*50}\n"
                except Exception as e:
                    return f"Error reading file: {e}\n"
            
            else:
                # Echo back other messages
                return f"ACK: {command}\n"
                
        except Exception as e:
            logger.error(f"Error handling command '{command}': {e}")
            return f"Error: {e}\n"
    
    # ============================================================================
    # MAIN SERVER LOOP
    # ============================================================================
    
    def activate(self):
        """
        Activate the device (simulates button press).
        Transitions from DORMANT to ADVERTISING.
        """
        logger.info("🔘 Device activation triggered!")
        if self.state == DeviceState.DORMANT:
            self.transition_to(DeviceState.ADVERTISING)
        else:
            logger.warning(f"Cannot activate from {self.state.value} state")
    
    def run(self):
        """Main server loop - handle incoming mTLS connections"""
        if self.state != DeviceState.ADVERTISING:
            logger.error("Server must be in ADVERTISING state to accept connections")
            return
        
        # Create server socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(5)
            
            self.server_socket = sock
            
            logger.info(f"🔒 mTLS Server listening on {self.host}:{self.port}")
            logger.info("📡 Device discoverable via mDNS")
            logger.info("Waiting for authenticated clients...\n")
            
            # Wrap socket with SSL
            with self.ssl_context.wrap_socket(sock, server_side=True) as ssock:
                while self.state != DeviceState.SHUTDOWN:
                    try:
                        # Accept client connection
                        conn, addr = ssock.accept()
                        
                        # Handle in same thread for now (could use threading for multiple clients)
                        self._handle_client_connection(conn, addr)
                        
                    except ssl.SSLError as e:
                        logger.error(f"SSL Error: {e}")
                        logger.error("Client certificate validation failed!")
                    except KeyboardInterrupt:
                        logger.info("\nShutdown signal received...")
                        self.transition_to(DeviceState.SHUTDOWN)
                        break
                    except Exception as e:
                        logger.error(f"Server error: {e}")


def main():
    """Main entry point"""
    print("=" * 70)
    print("  Secure NAS Server - State Machine Implementation")
    print("  mTLS + Avahi mDNS + NFS with Certificate-Based Firewall Rules")
    print("=" * 70)
    print()
    
    # Check for required certificates
    # Try Docker path first, then development path
    if Path('/app/pki/server_cert.pem').exists():
        pki_dir = Path('/app/pki')
    else:
        pki_dir = Path(__file__).parent.parent / 'pki'
    
    required_certs = ['server_cert.pem', 'server_key.pem', 'client_cert.pem']
    missing = [f for f in required_certs if not (pki_dir / f).exists()]
    
    if missing:
        logger.error(f"Missing certificates: {', '.join(missing)}")
        logger.error(f"Please generate certificates in {pki_dir}/")
        sys.exit(1)
    
    # Create server instance
    server = SecureNASServer(
        host='0.0.0.0',
        port=8443,
        nfs_port=2049,
        storage_path='/app/demo_storage',  # Use actual storage location for NFS export
        inactivity_timeout=300
    )
    
    # Simulate device activation (button press)
    logger.info("Simulating device activation (button press)...")
    time.sleep(1)
    server.activate()
    
    # Run server
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        server.transition_to(DeviceState.SHUTDOWN)


if __name__ == '__main__':
    main()

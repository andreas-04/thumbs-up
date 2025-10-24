#!/usr/bin/env python3
"""
Secure NAS Server - Clean Refactored Version

A certificate-based secure NAS with state machine control.
Features: mTLS authentication, dynamic firewall, NFS exports, mDNS discovery.

Architecture:
- state_machine.py: Device state management
- firewall.py: iptables access control
- nfs.py: NFS export management
- mdns_service.py: Avahi service discovery
- storage.py: Encrypted storage operations
"""
import ssl
import socket
import subprocess
import time
import signal
import sys
import logging
from pathlib import Path
from typing import Tuple, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager

# Import our clean modules
from state_machine import DeviceState, StateMachine
from firewall import Firewall
from nfs import NFS
from mdns_service import MDNSService
from storage import Storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# CLIENT SESSION MANAGEMENT
# ============================================================================

@dataclass
class ClientSession:
    """Represents an authenticated client session."""
    ip: str
    port: int
    cert_cn: str
    cert_fingerprint: str
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class ClientSessions:
    """
    Manages client sessions with automatic access control.
    
    Coordinates firewall and NFS access for authenticated clients.
    """
    
    def __init__(self, firewall_manager, nfs_manager, storage_manager):
        self.firewall = firewall_manager
        self.nfs = nfs_manager
        self.storage = storage_manager
        self._sessions: Dict[str, ClientSession] = {}
    
    @property
    def active_count(self) -> int:
        """Get number of active clients."""
        return len(self._sessions)
    
    @property
    def has_clients(self) -> bool:
        """Check if any clients are connected."""
        return self.active_count > 0
    
    def get_session(self, client_ip: str) -> Optional[ClientSession]:
        """Get session by client IP."""
        return self._sessions.get(client_ip)
    
    @contextmanager
    def client_access(self, client_ip: str, client_port: int, cert: dict):
        """
        Context manager for client session with automatic access control.
        
        Grants firewall and NFS access on entry, cleans up on exit.
        """
        session = self._create_session(client_ip, client_port, cert)
        
        # Use nested context managers for automatic cleanup
        with self.firewall.allow_client(client_ip), \
             self.nfs.export_for_client(client_ip):
            
            logger.info(f"✓ Client {session.cert_cn} has full access")
            
            try:
                yield session
            finally:
                self._remove_session(client_ip)
    
    def update_activity(self, client_ip: str) -> None:
        """Update last activity timestamp for a client."""
        if session := self._sessions.get(client_ip):
            session.last_activity = datetime.now()
    
    def handle_command(self, command: str, client_cn: str) -> str:
        """
        Handle client commands for file access.
        
        Supports:
        - LIST_FILES: List storage contents
        - READ_FILE:<filename>: Read specific file
        """
        try:
            if command == 'LIST_FILES':
                return self._list_files()
            
            elif command.startswith('READ_FILE:'):
                filename = command[10:].strip()
                return self._read_file(filename)
            
            else:
                return f"ACK: {command}\n"
                
        except Exception as e:
            logger.error(f"Error handling command '{command}': {e}")
            return f"Error: {e}\n"
    
    def _create_session(self, client_ip: str, client_port: int, cert: dict) -> ClientSession:
        """Create a new client session from certificate info."""
        # Parse certificate details
        subject = dict(x[0] for x in cert['subject'])
        client_cn = subject.get('commonName', 'Unknown')
        cert_fingerprint = f"cert_{cert.get('serialNumber', 'unknown')}"
        
        logger.info(f"✓ Client authenticated: {client_cn} from {client_ip}:{client_port}")
        
        # Create and register session
        session = ClientSession(
            ip=client_ip,
            port=client_port,
            cert_cn=client_cn,
            cert_fingerprint=cert_fingerprint
        )
        
        self._sessions[client_ip] = session
        return session
    
    def _remove_session(self, client_ip: str) -> None:
        """Remove client session."""
        if session := self._sessions.pop(client_ip, None):
            logger.info(f"✓ Session closed for {session.cert_cn}")
    
    def _list_files(self) -> str:
        """List files in storage."""
        storage_path = self.storage.path
        result = subprocess.run(
            ['ls', '-lh', str(storage_path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return f"📁 Files in {storage_path}:\n{result.stdout}\n"
        else:
            return f"Error listing files: {result.stderr}\n"
    
    def _read_file(self, filename: str) -> str:
        """Read a specific file from storage."""
        # Sanitize filename to prevent directory traversal
        filename = filename.replace('..', '').replace('/', '')
        filepath = self.storage.path / filename
        
        if not filepath.exists():
            return f"Error: File '{filename}' not found\n"
        
        if filepath.is_dir():
            return f"Error: '{filename}' is a directory\n"
        
        try:
            content = filepath.read_text()
            return f"📄 Contents of {filename}:\n{'='*50}\n{content}\n{'='*50}\n"
        except Exception as e:
            return f"Error reading file: {e}\n"


# ============================================================================
# MAIN SERVER CLASS
# ============================================================================

class SecureNASServer:
    """
    Main coordinator for the Secure NAS server.
    
    Orchestrates all components and manages their lifecycle through
    a clean state machine pattern.
    """
    
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8443,
        nfs_port: int = 2049,
        storage_path: str = '/app/demo_storage',
        inactivity_timeout: int = 300
    ):
        self.host = host
        self.port = port
        self.inactivity_timeout = inactivity_timeout
        
        # Initialize all components
        self.state_machine = StateMachine()
        self.firewall = Firewall(mtls_port=port, nfs_port=nfs_port)
        self.nfs = NFS(storage_path=storage_path)
        self.mdns = MDNSService(port=port)
        self.storage = Storage(storage_path=storage_path)
        self.sessions = ClientSessions(self.firewall, self.nfs, self.storage)
        
        # SSL and network
        self.ssl_context: ssl.SSLContext = None
        self.server_socket: socket.socket = None
        
        # Register state transition callbacks
        self._register_state_callbacks()
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
    
    # ========================================================================
    # STATE MACHINE CALLBACKS
    # ========================================================================
    
    def _register_state_callbacks(self) -> None:
        """Register all state entry/exit callbacks using clean decorator pattern."""
        
        @self.state_machine.on_enter(DeviceState.DORMANT)
        def enter_dormant():
            logger.info("📴 DORMANT - All services stopped")
        
        @self.state_machine.on_enter(DeviceState.ADVERTISING)
        def enter_advertising():
            logger.info("📡 ADVERTISING - Waiting for clients")
            self.firewall.initialize()
            self.storage.unlock()
            self._setup_ssl_context()
            self.mdns.start_advertising()
            logger.info("✓ Device discoverable, ready for connections")
        
        @self.state_machine.on_exit(DeviceState.ADVERTISING)
        def exit_advertising():
            logger.info("Exiting ADVERTISING state")
        
        @self.state_machine.on_enter(DeviceState.ACTIVE)
        def enter_active():
            logger.info("🔓 ACTIVE - Serving clients")
            if not self.storage.is_unlocked:
                self.storage.unlock()
            self.mdns.start_active(self.sessions.active_count)
            logger.info("✓ System active")
        
        @self.state_machine.on_exit(DeviceState.ACTIVE)
        def exit_active():
            logger.info("Exiting ACTIVE state")
            self.mdns.stop()
            # Sessions are cleaned up individually via context managers
            if self.storage.is_unlocked:
                self.storage.lock()
        
        @self.state_machine.on_enter(DeviceState.SHUTDOWN)
        def enter_shutdown():
            logger.info("🛑 SHUTDOWN - Cleaning up")
            self._perform_shutdown()
    
    def _handle_shutdown_signal(self, signum: int, frame) -> None:
        """Handle OS shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.state_machine.transition_to(DeviceState.SHUTDOWN)
        sys.exit(0)
    
    def _perform_shutdown(self) -> None:
        """Perform graceful shutdown sequence."""
        # Transition through states for proper cleanup
        current = self.state_machine.state
        
        if current == DeviceState.ACTIVE:
            self.state_machine.transition_to(DeviceState.ADVERTISING)
        
        if self.state_machine.state == DeviceState.ADVERTISING:
            self.state_machine.transition_to(DeviceState.DORMANT)
        
        # Close server socket
        if self.server_socket:
            self.server_socket.close()
        
        logger.info("✓ Shutdown complete")
    
    # ========================================================================
    # SSL/TLS CONFIGURATION
    # ========================================================================
    
    def _setup_ssl_context(self) -> None:
        """Configure mTLS with client certificate validation."""
        logger.info("Setting up mTLS server...")
        
        # Create SSL context for server
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        # Load certificates
        cert_path, key_path, ca_path = self._get_certificate_paths()
        self.ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        
        # Require and validate client certificates
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        self.ssl_context.load_verify_locations(cafile=str(ca_path))
        
        logger.info("✓ mTLS configured - mutual authentication enabled")
    
    def _get_certificate_paths(self) -> Tuple[Path, Path, Path]:
        """Get certificate paths for Docker or development environment."""
        # Try Docker path first
        if Path('/app/pki/server_cert.pem').exists():
            base = Path('/app/pki')
        else:
            # Development path
            base = Path(__file__).parent.parent / 'pki'
        
        return (
            base / 'server_cert.pem',
            base / 'server_key.pem',
            base / 'client_cert.pem'
        )
    
    # ========================================================================
    # CLIENT CONNECTION HANDLING
    # ========================================================================
    
    def _handle_client_connection(self, conn: ssl.SSLSocket, addr: Tuple[str, int]) -> None:
        """Handle an authenticated client connection with automatic resource management."""
        client_ip, client_port = addr
        
        try:
            # Validate client certificate
            cert = conn.getpeercert()
            if not cert:
                logger.warning(f"No certificate from {client_ip}")
                return
            
            # Transition to ACTIVE on first client
            if not self.sessions.has_clients:
                self.state_machine.transition_to(DeviceState.ACTIVE)
            
            # Use context manager for automatic access control
            with self.sessions.client_access(client_ip, client_port, cert) as session:
                self._communicate_with_client(conn, session)
        
        except socket.timeout:
            logger.info(f"Client {client_ip} timeout")
        except Exception as e:
            logger.error(f"Error with client {client_ip}: {e}", exc_info=True)
        finally:
            # Transition back to ADVERTISING if no more clients
            if not self.sessions.has_clients:
                logger.info("No more clients - back to advertising")
                self.state_machine.transition_to(DeviceState.ADVERTISING)
    
    def _communicate_with_client(self, conn: ssl.SSLSocket, session) -> None:
        """Handle client communication protocol."""
        with conn:
            # Send welcome message
            mount_info = self.nfs.get_mount_info(self.host)
            welcome = f"Welcome {session.cert_cn}! NFS: {mount_info}\n"
            conn.sendall(welcome.encode('utf-8'))
            
            # Message loop
            conn.settimeout(self.inactivity_timeout)
            while True:
                data = conn.recv(1024)
                if not data:
                    logger.info(f"Client {session.cert_cn} disconnected")
                    break
                
                # Update activity and handle command
                self.sessions.update_activity(session.ip)
                message = data.decode('utf-8').strip()
                logger.info(f"[{session.cert_cn}] {message}")
                
                response = self.sessions.handle_command(message, session.cert_cn)
                conn.sendall(response.encode('utf-8'))
    
    # ========================================================================
    # SERVER LIFECYCLE
    # ========================================================================
    
    def activate(self) -> None:
        """Activate the device (simulates physical button press)."""
        logger.info("👍 Device activation triggered!")
        
        if self.state_machine.is_state(DeviceState.DORMANT):
            self.state_machine.transition_to(DeviceState.ADVERTISING)
        else:
            logger.warning(f"Cannot activate from {self.state_machine.state.name}")
    
    def run(self) -> None:
        """Main server loop - accept and handle client connections."""
        if not self.state_machine.is_state(DeviceState.ADVERTISING):
            logger.error("Must be in ADVERTISING state to accept connections")
            return
        
        # Create and bind server socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(5)
            
            self.server_socket = sock
            
            logger.info(f"🔒 mTLS Server listening on {self.host}:{self.port}")
            logger.info("📡 Discoverable via mDNS")
            logger.info("Waiting for authenticated clients...\n")
            
            # Wrap with SSL and accept connections
            with self.ssl_context.wrap_socket(sock, server_side=True) as secure_sock:
                while not self.state_machine.is_state(DeviceState.SHUTDOWN):
                    try:
                        conn, addr = secure_sock.accept()
                        self._handle_client_connection(conn, addr)
                        
                    except ssl.SSLError as e:
                        logger.error(f"SSL Error: {e}")
                        logger.error("Client certificate validation failed")
                    except KeyboardInterrupt:
                        logger.info("\nKeyboard interrupt - shutting down...")
                        self.state_machine.transition_to(DeviceState.SHUTDOWN)
                        break
                    except Exception as e:
                        logger.error(f"Server error: {e}", exc_info=True)


def main() -> None:
    """Main entry point."""
    print("=" * 70)
    print("  Secure NAS Server - Clean Architecture")
    print("  mTLS + mDNS + NFS + Certificate-Based Firewall")
    print("=" * 70)
    print()
    
    # Verify certificates exist
    try:
        server = SecureNASServer()
        cert_path, key_path, ca_path = server._get_certificate_paths()
        
        missing = [p for p in [cert_path, key_path, ca_path] if not p.exists()]
        if missing:
            logger.error(f"Missing certificates: {[str(p) for p in missing]}")
            logger.error("Please generate certificates in PKI directory")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        sys.exit(1)
    
    # Create and start server
    server = SecureNASServer(
        host='0.0.0.0',
        port=8443,
        nfs_port=2049,
        storage_path='/app/demo_storage',
        inactivity_timeout=300
    )
    
    # Simulate device activation (physical button press)
    logger.info("Simulating device activation (button press)...")
    time.sleep(1)
    server.activate()
    
    # Run server
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        server.state_machine.transition_to(DeviceState.SHUTDOWN)


if __name__ == '__main__':
    main()

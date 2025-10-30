#!/usr/bin/env python3
"""
Secure NAS Server - Clean Refactored Version

A certificate-based secure NAS with state machine control.
Features: mTLS authentication, dynamic firewall, NFS exports, mDNS discovery.

Architecture:
- server.py: Device state management
- firewall.py: iptables access control
- nfs.py: NFS export management
- mdns_service.py: Avahi service discovery
- storage.py: Encrypted storage operations
"""
import ssl
import socket
import time
import signal
import sys
import logging
from pathlib import Path
from typing import Tuple, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager
from enum import Enum, auto

# Import our clean modules
from pkg.firewall import Firewall
from pkg.nfs import NFS
from pkg.mdns import MDNS
from pkg.storage import Storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DeviceState(Enum):
    """Device operational states."""

    DORMANT = auto()
    ADVERTISING = auto()
    ACTIVE = auto()
    SHUTDOWN = auto()


@dataclass
class ClientSession:
    """Represents an authenticated client session."""
    ip: str
    port: int
    cert_cn: str
    cert_fingerprint: str
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


# ============================================================================
# MAIN SERVER CLASS
# ============================================================================

@dataclass
class SecureNASServer:
    """Coordinates the Secure NAS server lifecycle."""

    host: str = '0.0.0.0'
    port: int = 8443
    nfs_port: int = 2049
    storage_path: Path = Path('/app/demo_storage')
    inactivity_timeout: int = 300

    firewall: Firewall = field(init=False)
    nfs: NFS = field(init=False)
    mdns: MDNS = field(init=False)
    storage: Storage = field(init=False)
    sessions: Dict[str, ClientSession] = field(default_factory=dict, init=False, repr=False)
    ssl_context: Optional[ssl.SSLContext] = field(default=None, init=False)
    server_socket: Optional[socket.socket] = field(default=None, init=False)
    state: DeviceState = field(default=DeviceState.DORMANT, init=False)
    _enter_handlers: Dict[DeviceState, Callable[[], None]] = field(default_factory=dict, init=False, repr=False)
    _exit_handlers: Dict[DeviceState, Callable[[], None]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        storage_path = Path(self.storage_path)
        self.storage_path = storage_path

        self.firewall = Firewall(mtls_port=self.port, nfs_port=self.nfs_port)
        self.nfs = NFS(storage_path=storage_path)
        self.mdns = MDNS(port=self.port)
        self.storage = Storage(storage_path=storage_path)
        self.sessions = {}

        self._register_state_handlers()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_shutdown_signal)

    # ====================================================================
    # SESSION MANAGEMENT HELPERS
    # ====================================================================

    @property
    def _active_client_count(self) -> int:
        return len(self.sessions)

    @property
    def _has_active_clients(self) -> bool:
        return bool(self.sessions)

    @contextmanager
    def _client_access(self, client_ip: str, client_port: int, cert: dict):
        session = self._create_session(client_ip, client_port, cert)

        with self.firewall.allow_client(client_ip), self.nfs.export_for_client(client_ip):
            logger.info(f"[NAS] Client {session.cert_cn} has full access")
            try:
                yield session
            finally:
                self._remove_session(client_ip)

    def _create_session(self, client_ip: str, client_port: int, cert: dict) -> ClientSession:
        subject = dict(x[0] for x in cert['subject'])
        client_cn = subject.get('commonName', 'Unknown')
        cert_fingerprint = f"cert_{cert.get('serialNumber', 'unknown')}"

        logger.info(f"[NAS] Client authenticated: {client_cn} from {client_ip}:{client_port}")

        session = ClientSession(
            ip=client_ip,
            port=client_port,
            cert_cn=client_cn,
            cert_fingerprint=cert_fingerprint
        )

        self.sessions[client_ip] = session
        return session

    def _remove_session(self, client_ip: str) -> None:
        if session := self.sessions.pop(client_ip, None):
            logger.info(f"[NAS] Client disconnected: {session.cert_cn}")

    def _update_client_activity(self, client_ip: str) -> None:
        if session := self.sessions.get(client_ip):
            session.last_activity = datetime.now()

    def _handle_command(self, command: str) -> str:
        if command in {'LIST_FILES', 'READ_FILE'} or command.startswith('READ_FILE:'):
            return "File operations are unsupported; mount the NFS share instead.\n"

        return f"ACK: {command}\n"
    
    # ========================================================================
    # STATE MACHINE HELPERS
    # ========================================================================

    def _register_state_handlers(self) -> None:
        """Configure enter/exit handlers for each device state."""

        self._enter_handlers = {
            DeviceState.DORMANT: self._enter_dormant,
            DeviceState.ADVERTISING: self._enter_advertising,
            DeviceState.ACTIVE: self._enter_active,
            DeviceState.SHUTDOWN: self._enter_shutdown,
        }

        self._exit_handlers = {
            DeviceState.ADVERTISING: self._exit_advertising,
            DeviceState.ACTIVE: self._exit_active,
        }

        # Fire initial state's entry hook so logs match previous behaviour.
        enter_handler = self._enter_handlers.get(self.state)
        if enter_handler:
            enter_handler()

    def is_state(self, state: DeviceState) -> bool:
        """Check if the device is currently in the given state."""

        return self.state == state

    def transition_to(self, new_state: DeviceState) -> None:
        """Transition to a new device state, invoking exit/enter hooks."""

        if self.state == new_state:
            return

        exit_handler = self._exit_handlers.get(self.state)
        if exit_handler:
            exit_handler()

        logger.info(f"[NAS] {new_state.name}")
        self.state = new_state

        enter_handler = self._enter_handlers.get(new_state)
        if enter_handler:
            enter_handler()

    # --------------------------------------------------------------------
    # State entry/exit handlers
    # --------------------------------------------------------------------

    def _enter_dormant(self) -> None:
        logger.info("[mDNS] Device dormant")

    def _enter_advertising(self) -> None:
        self.firewall.initialize()
        self.storage.unlock()
        self._setup_ssl_context()
        self.mdns.start_advertising()

    def _exit_advertising(self) -> None:
        self.mdns.stop()

    def _enter_active(self) -> None:
        if not self.storage.is_unlocked:
            self.storage.unlock()
        self.mdns.start_active(self._active_client_count)

    def _exit_active(self) -> None:
        self.mdns.stop()
        if self.storage.is_unlocked:
            self.storage.lock()

    def _enter_shutdown(self) -> None:
        self._perform_shutdown()
    
    def _handle_shutdown_signal(self, signum: int, frame) -> None:
        """Handle OS shutdown signals gracefully."""
        self.state = DeviceState.SHUTDOWN
    
    def _perform_shutdown(self) -> None:
        logger.info("[NAS] Performing shutdown...")
        
        # Transition through states for proper cleanup
        current = self.state

        if current == DeviceState.ACTIVE:
            self._exit_active()

        if current in (DeviceState.ACTIVE, DeviceState.ADVERTISING):
            self._exit_advertising()
        
    def ensure_certificates(self) -> None:
        """Validate expected certificate files exist."""
        missing = [path for path in self._get_certificate_paths() if not path.exists()]
        if missing:
            missing_str = ', '.join(str(path) for path in missing)
            raise FileNotFoundError(f"Missing certificates: {missing_str}")
    
    # ========================================================================
    # SSL/TLS CONFIGURATION
    # ========================================================================
    
    def _setup_ssl_context(self) -> None:
        """Configure mTLS with client certificate validation."""
        # Create SSL context for server
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        # Load certificates
        cert_path, key_path, ca_path = self._get_certificate_paths()
        self.ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        
        # Require and validate client certificates
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        self.ssl_context.load_verify_locations(cafile=str(ca_path))

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
                logger.warning(f"[mTLS] No certificate from {client_ip}")
                return
            
            # Transition to ACTIVE on first client
            if not self._has_active_clients:
                self.transition_to(DeviceState.ACTIVE)
            
            # Use context manager for automatic access control
            with self._client_access(client_ip, client_port, cert) as session:
                self._communicate_with_client(conn, session)
        
        except socket.timeout:
            logger.info(f"[NAS] Client {client_ip} timeout")
        except Exception as e:
            logger.error(f"[NAS] Error with client {client_ip}: {e}", exc_info=True)
        finally:
            # Transition back to ADVERTISING if no more clients
            if not self._has_active_clients:
                self.transition_to(DeviceState.ADVERTISING)
    
    def _communicate_with_client(self, conn: ssl.SSLSocket, session) -> None:
        """Handle client communication protocol."""
        with conn:
            # Send welcome message
            mount_info = self.nfs.get_mount_info(self.host)
            welcome = f"Welcome {session.cert_cn}!\n"
            conn.sendall(welcome.encode('utf-8'))
            
            # Message loop
            conn.settimeout(self.inactivity_timeout)
            while True:
                data = conn.recv(1024)
                if not data:
                    logger.info(f"[NAS] Client {session.cert_cn} disconnected")
                    break
                
                # Update activity and handle command
                self._update_client_activity(session.ip)
                message = data.decode('utf-8').strip()
                logger.info(f"[{session.cert_cn}] {message}")
                
                response = self._handle_command(message)
                conn.sendall(response.encode('utf-8'))
    
    # ========================================================================
    # SERVER LIFECYCLE
    # ========================================================================
    
    def activate(self) -> None:
        if self.is_state(DeviceState.DORMANT):
            self.transition_to(DeviceState.ADVERTISING)
        else:
            logger.warning(f"[NAS] Cannot activate from {self.state.name}")
    
    def run(self) -> None:
        """Main server loop - accept and handle client connections."""
        if not self.is_state(DeviceState.ADVERTISING):
            logger.error("[NAS] Must be in ADVERTISING state to accept connections")
            return
        
        # Create and bind server socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(5)
            
            self.server_socket = sock
            
            logger.info(f"[mTLS] Server listening on {self.host}:{self.port}")
            
            # Wrap with SSL and accept connections
            with self.ssl_context.wrap_socket(sock, server_side=True) as secure_sock:
                secure_sock.settimeout(1.0)
                self._accept_loop(secure_sock)
            
            # Clean up after accept loop exits
            self.server_socket = None

    def _accept_loop(self, secure_sock: ssl.SSLSocket) -> None:
        """Accept incoming TLS connections until shutdown."""
        while not self.is_state(DeviceState.SHUTDOWN):
            try:
                conn, addr = secure_sock.accept()
                self._handle_client_connection(conn, addr)

            except ssl.SSLError as exc:
                logger.error(f"[mTLS] Client certificate validation failed:\n{exc}")
            except socket.timeout:
                continue
            except OSError:
                # Socket closed during shutdown
                if self.is_state(DeviceState.SHUTDOWN):
                    break
                raise
            except KeyboardInterrupt:
                logger.info("\n[NAS] Keyboard interrupt - shutting down...")
                self.transition_to(DeviceState.SHUTDOWN)
                break
            except Exception as exc:
                logger.error(f"[NAS] Server error: {exc}", exc_info=True)


def main() -> None:
    try:
        server = SecureNASServer()
        server.ensure_certificates()
    except Exception as exc:
        logger.error(f"[NAS] Initialization error: {exc}")
        sys.exit(1)
    
    # Simulate device activation (physical button press)
    logger.info("[NAS] Attempting to activate device, simulating button press...")
    time.sleep(1)
    server.activate()
    
    # Run server
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("\n[NAS] Keyboard interrupt received")
    except Exception as exc:
        logger.error(f"[NAS] Fatal error: {exc}", exc_info=True)
    finally:
        # Ensure final shutdown
        if not server.is_state(DeviceState.SHUTDOWN):
            server.transition_to(DeviceState.SHUTDOWN)
        sys.exit(0)


if __name__ == '__main__':
    main()

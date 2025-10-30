#!/usr/bin/env python3
"""
Secure NAS Client
Discovers and connects to Secure NAS server using Avahi mDNS and mTLS authentication
"""
import ssl
import socket
import sys
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class SecureNASClient:
    """Minimal client for connecting to the Secure NAS server."""

    KEEPALIVE_INTERVAL = 120  # seconds between keepalive pings
    KEEPALIVE_TIMEOUT = 5     # seconds to wait for ACK

    def __init__(self, host: Optional[str] = None, port: int = 8443):
        self.host = host
        self.port = port
        self.ssl_context: Optional[ssl.SSLContext] = None
        self.mount_point = Path('/mnt/nas')
        self._mounted = False
    
    def discover_server(self, service_name="_thumbsup._tcp", timeout=10):
        """
        Discover Secure NAS server using Avahi/mDNS
        
        Args:
            service_name: The mDNS service type to search for
            timeout: How long to wait for discovery (seconds)
        
        Returns:
            tuple: (hostname, port) or (None, None) if not found
        """
        logger.info(f"🔍 Discovering server via mDNS ({service_name})...")
        
        try:
            # Use avahi-browse to discover the service
            # -t: terminate after discovering
            # -r: resolve the service
            # -p: parseable output
            result = subprocess.run(
                ['avahi-browse', '-t', '-r', '-p', service_name],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                logger.error(f"avahi-browse failed: {result.stderr}")
                return None, None
            
            # Parse the output
            # Format: =;interface;protocol;name;type;domain;hostname;address;port;txt
            for line in result.stdout.split('\n'):
                if line.startswith('='):
                    parts = line.split(';')
                    if len(parts) >= 9:
                        hostname = parts[6]  # hostname
                        address = parts[7]   # IP address
                        port = parts[8]      # port
                        txt_records = parts[9] if len(parts) > 9 else ""
                        
                        logger.info(f"✓ Found server: {hostname} at {address}:{port}")
                        
                        # Parse TXT records if present
                        if txt_records:
                            txt_dict = {}
                            for record in txt_records.strip('"').split('" "'):
                                if '=' in record:
                                    key, value = record.split('=', 1)
                                    txt_dict[key] = value
                            
                            status = txt_dict.get('status', 'unknown')
                            logger.info(f"  Status: {status}")
                            if 'clients' in txt_dict:
                                logger.info(f"  Connected clients: {txt_dict['clients']}")
                        
                        return address, int(port)
            
            logger.warning("No server found via mDNS")
            return None, None
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Discovery timeout after {timeout} seconds")
            return None, None
        except FileNotFoundError:
            logger.error("avahi-browse not found. Install avahi-utils package.")
            return None, None
        except Exception as e:
            logger.error(f"Discovery error: {e}")
            return None, None

        
    def setup_mtls(self):
        """Configure mTLS with client certificate"""
        # Create SSL context for client
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        
        # Load client certificate and key
        # Check for Docker container path first, then fall back to development path
        if Path('/app/pki/client_cert.pem').exists():
            # Running in Docker container
            cert_path = Path('/app/pki/client_cert.pem')
            key_path = Path('/app/pki/client_key.pem')
            ca_path = Path('/app/pki/server_cert.pem')
        else:
            # Running in development
            pki_dir = Path(__file__).parent.parent / 'pki'
            cert_path = pki_dir / 'client_cert.pem'
            key_path = pki_dir / 'client_key.pem'
            ca_path = pki_dir / 'server_cert.pem'
        
        # Load client certificate for mutual authentication
        self.ssl_context.load_cert_chain(
            certfile=str(cert_path),
            keyfile=str(key_path)
        )
        
        # Verify server certificate
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        self.ssl_context.load_verify_locations(cafile=str(ca_path))
        
        logger.info("✓ mTLS configured with client certificate")
    
    def connect(self) -> bool:
        """Connect to the Secure NAS server and keep the session alive."""
        # Discover server if host not specified
        if not self.host:
            discovered_host, discovered_port = self.discover_server()
            if not discovered_host:
                logger.error("❌ Could not discover server via mDNS")
                logger.info("Make sure the server is running and advertising via Avahi")
                return False
            self.host = discovered_host
            if discovered_port:
                self.port = discovered_port
        
        logger.info(f"Connecting to Secure NAS at {self.host}:{self.port}...")
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                with self.ssl_context.wrap_socket(sock, server_hostname=self.host) as ssock:
                    ssock.connect((self.host, self.port))

                    logger.info("✓ Connected successfully!")

                    if cert := ssock.getpeercert():
                        subject = dict(x[0] for x in cert['subject'])
                        server_cn = subject.get('commonName', 'Unknown')
                        logger.info(f"  Server CN: {server_cn}")

                    welcome = ssock.recv(1024).decode('utf-8')
                    logger.info(f"  Server: {welcome.strip()}")

                    self._mounted = self.mount_nfs_share()
                    logger.info("Session established. Press Ctrl+C to disconnect.")

                    self._session_loop(ssock)

        except ssl.SSLError as exc:
            logger.error(f"SSL Error: {exc}")
            logger.error("Certificate validation failed!")
            return False
        except ConnectionRefusedError:
            logger.error(f"Connection refused. Is the server running at {self.host}:{self.port}?")
            return False
        except KeyboardInterrupt:
            logger.info("Disconnecting...")
        except Exception as exc:
            logger.error(f"Connection error: {exc}")
            return False
        finally:
            if self._mounted:
                self.unmount_nfs_share()
                self._mounted = False
        
        return True
    
    def mount_nfs_share(self) -> bool:
        """Mount the NFS share locally."""
        try:
            logger.info("📁 Mounting NFS share...")

            subprocess.run(['mkdir', '-p', str(self.mount_point)], check=True)

            result = subprocess.run([
                'mount',
                '-t', 'nfs',
                '-o', 'vers=3,nolock',
                f'{self.host}:/app/demo_storage',
                str(self.mount_point)
            ], capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"✓ NFS share mounted at {self.mount_point}")
                return True

            logger.error(f"Failed to mount NFS: {result.stderr.strip()}")
            logger.info("Note: Mount requires SYS_ADMIN capability in container")
            return False

        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to mount NFS share: {exc}")
        except Exception as exc:
            logger.error(f"Error mounting NFS share: {exc}")

        return False

    def unmount_nfs_share(self) -> None:
        """Unmount the NFS share if it was mounted."""
        try:
            logger.info("Unmounting NFS share...")
            subprocess.run(['umount', str(self.mount_point)], capture_output=True)
            logger.info("✓ NFS share unmounted")
        except Exception as exc:
            logger.warning(f"Failed to unmount: {exc}")

    def _session_loop(self, ssock: ssl.SSLSocket) -> None:
        """Keep the TLS session alive with periodic keepalive messages."""
        try:
            while True:
                time.sleep(self.KEEPALIVE_INTERVAL)

                try:
                    ssock.sendall(b'PING\n')
                    ssock.settimeout(self.KEEPALIVE_TIMEOUT)
                    response = ssock.recv(4096)
                except socket.timeout:
                    logger.warning("Keepalive timed out; continuing")
                    continue
                finally:
                    ssock.settimeout(None)

                if not response:
                    logger.warning("Server closed the connection")
                    break

                logger.debug("Server response: %s", response.decode('utf-8').strip())

        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logger.error(f"Session error: {exc}")


def main():
    """Main entry point"""
    print("=" * 70)
    print("  Secure NAS Client - mDNS Discovery + mTLS Authentication")
    print("=" * 70)
    print()
    
    # Check for required certificates
    # Try Docker path first, then development path
    if Path('/app/pki/client_cert.pem').exists():
        pki_dir = Path('/app/pki')
    else:
        pki_dir = Path(__file__).parent.parent / 'pki'
    
    required_certs = ['client_cert.pem', 'client_key.pem', 'server_cert.pem']
    missing = [f for f in required_certs if not (pki_dir / f).exists()]
    
    if missing:
        logger.error(f"Missing certificates: {', '.join(missing)}")
        logger.error(f"Please generate certificates in {pki_dir}/")
        sys.exit(1)
    
    # Parse command line arguments
    # If host is provided, use it directly; otherwise discover via mDNS
    host = sys.argv[1] if len(sys.argv) > 1 else None
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8443
    
    if host:
        logger.info(f"Using specified host: {host}")
    else:
        logger.info("No host specified - will use mDNS discovery")
    
    # Create and connect client
    client = SecureNASClient(host=host, port=port)
    client.setup_mtls()
    
    # Connect to server
    if client.connect():
        logger.info("\nSession ended successfully")
    else:
        logger.error("Failed to connect to server")
        sys.exit(1)


if __name__ == '__main__':
    main()

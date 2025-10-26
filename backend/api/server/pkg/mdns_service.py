"""
mDNS Service Discovery for Secure NAS Server

Manages Avahi service announcements for network discovery.
"""
import subprocess
import time
import logging
import platform
from typing import Optional

logger = logging.getLogger(__name__)


class MDNSService:
    """
    Manages mDNS service discovery using Avahi.
    
    Broadcasts service availability and current status.
    """
    
    def __init__(
        self,
        service_name: str = "ThumbsUp-SecureNAS",
        service_type: str = "_thumbsup._tcp",
        port: int = 8443
    ):
        self.service_name = service_name
        self.service_type = service_type
        self.port = port
        self._process: Optional[subprocess.Popen] = None
    
    @property
    def is_broadcasting(self) -> bool:
        """Check if mDNS is currently broadcasting."""
        return self._process is not None and self._process.poll() is None
    
    def start_advertising(self) -> None:
        """Start broadcasting in advertising mode (waiting for clients)."""
        self.stop()
        
        txt_record = f"status=advertising,timestamp={int(time.time())}"
        self._start_broadcast(txt_record)
        
        logger.info(f"📡 mDNS: Broadcasting (advertising)")
    
    def start_active(self, num_clients: int = 0) -> None:
        """Start broadcasting in active mode (serving clients)."""
        self.stop()
        
        txt_record = f"status=active,clients={num_clients},timestamp={int(time.time())}"
        self._start_broadcast(txt_record)
        
        logger.info(f"📡 mDNS: Broadcasting (active, {num_clients} clients)")
    
    def stop(self) -> None:
        """Stop mDNS broadcast."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None
    
    def _start_broadcast(self, txt_record: str) -> None:
        """Start Avahi broadcast with given TXT record."""
        try:
            # Prefer the platform-native mDNS publisher where available:
            # - On macOS (Darwin) use the built-in `dns-sd -R` command
            # - On other systems (Linux/Raspbian) use avahi-publish
            system = platform.system()
            if system == 'Darwin':
                # dns-sd -R <Name> <Type> <Domain> <Port> [TXT...]
                cmd = [
                    'dns-sd', '-R',
                    self.service_name,
                    self.service_type,
                    'local',
                    str(self.port),
                    txt_record
                ]
            else:
                cmd = [
                    'avahi-publish', '-s',
                    self.service_name,
                    self.service_type,
                    str(self.port),
                    txt_record
                ]
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
        except FileNotFoundError:
            logger.warning("⚠️  avahi-publish not found - mDNS unavailable")
        except Exception as e:
            logger.error(f"⚠️  mDNS broadcast error: {e}")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.stop()

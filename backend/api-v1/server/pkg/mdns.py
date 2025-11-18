"""
mDNS Service Discovery for Secure NAS Server

Manages Avahi service announcements for network discovery.
"""
import subprocess
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Manages mDNS service discovery using Avahi.
# Broadcasts service availability and current status.
class MDNS:
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
        # Is mDNS currently broadcasting?
        return self._process is not None and self._process.poll() is None
    
    def start_advertising(self) -> None:
        # cleanup any existing broadcasts
        self.stop()
        txt_record = f"status=advertising,timestamp={int(time.time())}"
        self._start_broadcast(txt_record)
    
    def start_active(self, num_clients: int = 0) -> None:
        # cleanup any existing broadcasts
        self.stop()
        txt_record = f"status=active,clients={num_clients},timestamp={int(time.time())}"
        self._start_broadcast(txt_record)
    
    def stop(self) -> None:
        # Stop mDNS broadcast.
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None

    # Start Avahi broadcast with given TXT record.
    def _start_broadcast(self, txt_record: str) -> None:
        try:
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
            logger.warning("Error: avahi-publish not found - mDNS unavailable")
        except Exception as e:
            logger.error(f"mDNS broadcast exception: {e}")
    
    def __del__(self):
        # Cleanup on deletion.
        self.stop()

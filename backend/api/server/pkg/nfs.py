"""
NFS for Secure NAS Server

Copyright (c) 2025 Thumbs-Up Team
SPDX-License-Identifier: BSD-3-Clause

Manages NFS export configuration for authenticated clients.
"""
import subprocess
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


class NFS:
    """
    Manages NFS exports for authenticated clients.
    
    Provides context manager for automatic cleanup of client exports.
    """
    
    def __init__(self, storage_path: str = '/app/demo_storage'):
        self.storage_path = storage_path
        self.exports_file = Path('/etc/exports')
    
    @property
    def mount_point(self) -> str:
        """Get the mount point path for clients."""
        return self.storage_path
    
    @contextmanager
    def export_for_client(self, client_ip: str) -> Iterator[None]:
        """
        Context manager to temporarily export NFS to a client.
        
        Usage:
            with nfs.export_for_client('192.168.1.100'):
                # Client can mount NFS here
                pass
            # Export automatically removed
        """
        success = self._add_export(client_ip)
        try:
            yield
        finally:
            if success:
                self._remove_export(client_ip)
    
    def get_mount_info(self, server_host: str) -> str:
        """Get mount command information for clients."""
        return f"{server_host}:{self.storage_path}"
    
    def _add_export(self, client_ip: str) -> bool:
        """Add NFS export entry for specific client IP."""
        try:
            export_line = (
                f"{self.storage_path} {client_ip}"
                f"(rw,sync,no_subtree_check,no_root_squash,insecure)\n"
            )
            
            # Read existing exports
            existing = self._read_exports()
            
            # Add if not already present
            if export_line not in existing:
                with open(self.exports_file, 'a') as f:
                    f.write(export_line)
            
            # Reload NFS exports
            subprocess.run(
                ['exportfs', '-ra'],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"📁 NFS: Exported {self.storage_path} → {client_ip}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload NFS exports: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Failed to add NFS export for {client_ip}: {e}")
            return False
    
    def _remove_export(self, client_ip: str) -> None:
        """Remove NFS export entry for specific client IP."""
        try:
            # Read and filter exports
            lines = self.exports_file.read_text().splitlines(keepends=True)
            filtered = [line for line in lines if client_ip not in line]
            
            # Write back
            self.exports_file.write_text(''.join(filtered))
            
            # Reload NFS exports
            subprocess.run(
                ['exportfs', '-ra'],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"📁 NFS: Removed export for {client_ip}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload NFS exports: {e.stderr}")
        except Exception as e:
            logger.error(f"Failed to remove NFS export for {client_ip}: {e}")
    
    def _read_exports(self) -> str:
        """Read existing exports file."""
        try:
            return self.exports_file.read_text()
        except FileNotFoundError:
            return ""

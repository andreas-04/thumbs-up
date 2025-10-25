"""
Firewall for Secure NAS Server

Copyright (c) 2025 Thumbs-Up Team
SPDX-License-Identifier: BSD-3-Clause

Manages iptables rules for certificate-based NFS access control.
"""
import subprocess
import logging
from contextlib import contextmanager
from typing import Optional, Iterator

logger = logging.getLogger(__name__)


class Firewall:
    """
    Manages iptables firewall rules for NFS access control.
    
    Provides context manager for automatic cleanup of client rules.
    """
    
    def __init__(self, mtls_port: int = 8443, nfs_port: int = 2049):
        self.mtls_port = mtls_port
        self.nfs_port = nfs_port
    
    def initialize(self) -> None:
        """Initialize firewall with default-deny policy for NFS port."""
        logger.info("🔥 Initializing firewall rules...")
        
        try:
            # Cleanup old rules from previous runs
            self._cleanup_old_nas_rules()
            
            # Allow established connections
            self._add_rule([
                '-m', 'state', '--state', 'ESTABLISHED,RELATED',
                '-j', 'ACCEPT'
            ])
            
            # Allow loopback
            self._add_rule(['-i', 'lo', '-j', 'ACCEPT'])
            
            # Allow mTLS port
            self._add_rule([
                '-p', 'tcp', '--dport', str(self.mtls_port),
                '-j', 'ACCEPT',
                '-m', 'comment', '--comment', 'NAS_mTLS_Port'
            ])
            
            logger.info(f"✓ Firewall initialized - mTLS:{self.mtls_port} open, "
                       f"NFS:{self.nfs_port} restricted")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize firewall: {e}")
            raise
    
    @contextmanager
    def allow_client(self, client_ip: str) -> Iterator[str]:
        """
        Context manager to temporarily allow client access to NFS.
        
        Usage:
            with firewall.allow_client('192.168.1.100') as rule_id:
                # Client has access here
                pass
            # Access automatically revoked
        """
        rule_id = self._add_client_rule(client_ip)
        try:
            yield rule_id
        finally:
            if rule_id:
                self._remove_client_rule(client_ip, rule_id)
    
    def _add_client_rule(self, client_ip: str) -> Optional[str]:
        """Add iptables rule for specific client."""
        try:
            rule_id = f"NAS_Client_{client_ip.replace('.', '_')}"
            
            self._add_rule([
                '-p', 'tcp',
                '-s', client_ip,
                '--dport', str(self.nfs_port),
                '-j', 'ACCEPT',
                '-m', 'comment', '--comment', rule_id
            ])
            
            logger.info(f"🔥 Firewall: Allow {client_ip} → NFS:{self.nfs_port}")
            return rule_id
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add firewall rule for {client_ip}: {e}")
            return None
    
    def _remove_client_rule(self, client_ip: str, rule_id: str) -> None:
        """Remove iptables rule for specific client."""
        try:
            self._delete_rule([
                '-p', 'tcp',
                '-s', client_ip,
                '--dport', str(self.nfs_port),
                '-j', 'ACCEPT',
                '-m', 'comment', '--comment', rule_id
            ])
            
            logger.info(f"🔥 Firewall: Revoked {client_ip}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove firewall rule for {client_ip}: {e}")
    
    def _cleanup_old_nas_rules(self) -> None:
        """Remove old NAS client rules from previous runs."""
        try:
            result = subprocess.run(
                ['iptables', '-S', 'INPUT'],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.split('\n'):
                if 'NAS_Client_' in line:
                    rule_parts = line.replace('-A', '-D').split()
                    if rule_parts:
                        subprocess.run(
                            ['iptables'] + rule_parts[1:],
                            capture_output=True,
                            check=False  # Don't fail if rule doesn't exist
                        )
        except Exception as e:
            logger.warning(f"Error cleaning old rules: {e}")
    
    def _add_rule(self, args: list) -> None:
        """Add an iptables INPUT rule."""
        subprocess.run(
            ['iptables', '-A', 'INPUT'] + args,
            capture_output=True,
            check=True
        )
    
    def _delete_rule(self, args: list) -> None:
        """Delete an iptables INPUT rule."""
        subprocess.run(
            ['iptables', '-D', 'INPUT'] + args,
            capture_output=True,
            check=True
        )

"""
Firewall for Secure NAS Server

Manages iptables rules for certificate-based NFS access control.
"""
import subprocess
import logging
from contextlib import contextmanager
from typing import Optional, Iterator

logger = logging.getLogger(__name__)

# Manages iptables firewall rules for NFS access control 
# and provides a context manager for automatic cleanup of rules.
class Firewall:
    """
    Manages iptables firewall rules for NFS access control.
    
    Provides context manager for automatic cleanup of client rules.
    """
    
    def __init__(self, mtls_port: int = 8443, nfs_port: int = 2049):
        self.mtls_port = mtls_port
        self.nfs_port = nfs_port
    
    # Initialize firewall with default-deny policy for NFS port.
    def initialize(self) -> None:
        try:
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
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize firewall: {e}")
            raise
    
    @contextmanager
    def allow_client(self, client_ip: str) -> Iterator[str]:
        rule_id = self._add_client_rule(client_ip)
        try:
            yield rule_id
        finally:
            if rule_id:
                self._remove_client_rule(client_ip, rule_id)

    # Add iptables rule for specific client
    def _add_client_rule(self, client_ip: str) -> Optional[str]:
        try:
            rule_id = f"NAS_Client_{client_ip.replace('.', '_')}"
            
            self._add_rule([
                '-p', 'tcp',
                '-s', client_ip,
                '--dport', str(self.nfs_port),
                '-j', 'ACCEPT',
                '-m', 'comment', '--comment', rule_id
            ])
            return rule_id
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add firewall rule for {client_ip}: {e}")
            return None
    
    # Remove iptables rule for specific client
    def _remove_client_rule(self, client_ip: str, rule_id: str) -> None:
        try:
            self._delete_rule([
                '-p', 'tcp',
                '-s', client_ip,
                '--dport', str(self.nfs_port),
                '-j', 'ACCEPT',
                '-m', 'comment', '--comment', rule_id
            ])
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove firewall rule for {client_ip}: {e}")

    # Remove old NAS client rules from previous runs.
    def _cleanup_old_nas_rules(self) -> None:
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
            logger.warning(f"Exception occured when cleaning old rules: {e}")

    # Add an iptables INPUT rule.
    def _add_rule(self, args: list) -> None:
        subprocess.run(
            ['iptables', '-A', 'INPUT'] + args,
            capture_output=True,
            check=True
        )
        
    # Delete an iptables INPUT rule.
    def _delete_rule(self, args: list) -> None:
        subprocess.run(
            ['iptables', '-D', 'INPUT'] + args,
            capture_output=True,
            check=True
        )

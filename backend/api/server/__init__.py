"""
Secure NAS Server Package

Clean, modular implementation of a certificate-based secure NAS server.

Components:
- Firewall: iptables access control with context managers
- NFS: Dynamic NFS export management
- mDNS Service: Avahi service discovery and broadcasting
- Storage: Encrypted storage operations (LUKS)
"""


from .pkg.firewall import Firewall
from .pkg.nfs import NFS
from .pkg.mdns import MDNS
from .pkg.storage import Storage
from .server import SecureNASServer, DeviceState

__version__ = '2.0.0'
__all__ = [
    'SecureNASServer',
    'DeviceState',
    'Firewall',
    'NFS',
    'MDNS',
    'Storage',
]

"""
Secure NAS Server Package

Copyright (c) 2025 Thumbs-Up Team
SPDX-License-Identifier: BSD-3-Clause

Modular implementation of a certificate-based NAS server.

Components:
- State Machine: Device state management with callbacks
- Firewall: iptables access control with context managers
- NFS: Dynamic NFS export management
- mDNS Service: Avahi service discovery and broadcasting
- Storage: Encrypted storage operations (LUKS)

Example:
    from server import SecureNASServer
    
    server = SecureNASServer(host='0.0.0.0', port=8443)
    server.activate()
    server.run()
"""


from .pkg.state_machine import DeviceState, StateMachine
from .pkg.firewall import Firewall
from .pkg.nfs import NFS
from .pkg.mdns_service import MDNSService
from .pkg.storage import Storage

__version__ = '2.0.0'
__all__ = [
    'DeviceState',
    'StateMachine',
    'Firewall',
    'NFS',
    'MDNSService',
    'Storage',
]

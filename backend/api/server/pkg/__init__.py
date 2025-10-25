"""
Package containing core server components.

Copyright (c) 2025 Thumbs-Up Team
SPDX-License-Identifier: BSD-3-Clause

Modules:
- firewall: iptables access control
- mdns_service: Avahi service discovery
- nfs: NFS export management
- state_machine: Device state management
- storage: Encrypted storage operations
"""

__all__ = [
    'firewall',
    'mdns_service',
    'nfs',
    'state_machine',
    'storage',
]

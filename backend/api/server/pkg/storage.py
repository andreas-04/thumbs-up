"""
Storage for Secure NAS Server

Copyright (c) 2025 Thumbs-Up Team
SPDX-License-Identifier: BSD-3-Clause

Manages encrypted storage operations (LUKS in production, demo mode for testing).
"""
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Storage:
    """
    Manages encrypted storage operations.
    
    In production: LUKS encryption/decryption
    In demo: Simple availability check
    """
    
    def __init__(self, storage_path: str = '/app/demo_storage'):
        self.storage_path = Path(storage_path)
        self._is_unlocked = False
    
    @property
    def is_unlocked(self) -> bool:
        """Check if storage is currently unlocked."""
        return self._is_unlocked
    
    @property
    def path(self) -> Path:
        """Get storage path."""
        return self.storage_path
    
    def unlock(self) -> bool:
        """
        Unlock encrypted storage.
        
        Production: cryptsetup open /dev/sdb1 encrypted_storage
        Demo: Verify directory exists
        """
        logger.info(f"🔓 Unlocking storage: {self.storage_path}")
        
        try:
            # Demo mode: Just verify directory exists
            # Production would use:
            # subprocess.run(['cryptsetup', 'open', '/dev/sdb1', 'encrypted_storage'])
            # subprocess.run(['mount', '/dev/mapper/encrypted_storage', str(self.storage_path)])
            
            if not self.storage_path.exists():
                raise FileNotFoundError(f"Storage path {self.storage_path} not found")
            
            self._is_unlocked = True
            logger.info(f"✓ Storage unlocked")
            
            # Log contents for verification
            self._log_contents()
            return True
            
        except Exception as e:
            logger.error(f"Failed to unlock storage: {e}")
            self._is_unlocked = False
            return False
    
    def lock(self) -> bool:
        """
        Lock encrypted storage.
        
        Production: umount and cryptsetup close
        Demo: Mark as locked
        """
        logger.info(f"🔒 Locking storage: {self.storage_path}")
        
        try:
            # Demo mode: Just mark as locked
            # Production would use:
            # subprocess.run(['umount', str(self.storage_path)])
            # subprocess.run(['cryptsetup', 'close', 'encrypted_storage'])
            
            self._is_unlocked = False
            logger.info(f"✓ Storage locked")
            return True
            
        except Exception as e:
            logger.error(f"Failed to lock storage: {e}")
            # Mark as locked anyway for safety
            self._is_unlocked = False
            return False
    
    def _log_contents(self) -> None:
        """Log storage contents for verification."""
        try:
            result = subprocess.run(
                ['ls', '-lah', str(self.storage_path)],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"📁 Storage contents:\n{result.stdout}")
        except Exception as e:
            logger.debug(f"Could not list storage contents: {e}")

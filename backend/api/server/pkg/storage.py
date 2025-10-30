"""Storage helpers for the Secure NAS server."""
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, storage_path: str = '/app/demo_storage'):
        self.storage_path = Path(storage_path)
        self._is_unlocked = False
    
    @property
    def is_unlocked(self) -> bool:
        return self._is_unlocked
    
    @property
    def path(self) -> Path:
        return self.storage_path
    
    def unlock(self) -> bool:
        try:
            if not self.storage_path.exists():
                raise FileNotFoundError(f"Storage path {self.storage_path} not found")

            self._is_unlocked = True
            return True

        except Exception as exc:
            logger.error(f"Failed to unlock storage: {exc}")
            self._is_unlocked = False
            return False
    
    def lock(self) -> bool:
        try:
            self._is_unlocked = False
            return True

        except Exception as exc:
            logger.error(f"Failed to lock storage: {exc}")
            self._is_unlocked = False
            return False
    

"""
State Machine for Secure NAS Server

Clean, Pythonic state management with callback-based transitions.
"""
from enum import Enum, auto
from typing import Callable, Dict, List
import logging

logger = logging.getLogger(__name__)


class DeviceState(Enum):
    """Device operational states."""
    DORMANT = auto()        # No services, storage locked
    ADVERTISING = auto()    # mDNS active, waiting for clients
    ACTIVE = auto()         # Client connected, NFS accessible
    SHUTDOWN = auto()       # Graceful shutdown in progress


class StateMachine:
    """
    Manages device state transitions with clean callback pattern.
    
    Each state can have entry and exit callbacks that are executed
    during transitions.
    """
    
    def __init__(self, initial_state: DeviceState = DeviceState.DORMANT):
        self._state = initial_state
        self._enter_callbacks: Dict[DeviceState, List[Callable]] = {
            state: [] for state in DeviceState
        }
        self._exit_callbacks: Dict[DeviceState, List[Callable]] = {
            state: [] for state in DeviceState
        }
    
    @property
    def state(self) -> DeviceState:
        """Get current state."""
        return self._state
    
    def is_state(self, state: DeviceState) -> bool:
        """Check if currently in given state."""
        return self._state == state
    
    def on_enter(self, state: DeviceState) -> Callable:
        """
        Decorator to register entry callback for a state.
        
        Usage:
            @state_machine.on_enter(DeviceState.ACTIVE)
            def setup_active_state():
                # Setup logic here
                pass
        """
        def decorator(func: Callable) -> Callable:
            self._enter_callbacks[state].append(func)
            return func
        return decorator
    
    def on_exit(self, state: DeviceState) -> Callable:
        """
        Decorator to register exit callback for a state.
        
        Usage:
            @state_machine.on_exit(DeviceState.ACTIVE)
            def cleanup_active_state():
                # Cleanup logic here
                pass
        """
        def decorator(func: Callable) -> Callable:
            self._exit_callbacks[state].append(func)
            return func
        return decorator
    
    def transition_to(self, new_state: DeviceState) -> None:
        """
        Transition to a new state.
        
        Executes exit callbacks for old state, updates state,
        then executes entry callbacks for new state.
        """
        if self._state == new_state:
            logger.debug(f"Already in {new_state.name} state")
            return
        
        old_state = self._state
        logger.info(f"State transition: {old_state.name} → {new_state.name}")
        
        # Execute exit callbacks
        self._execute_callbacks(self._exit_callbacks[old_state], 
                               f"exit {old_state.name}")
        
        # Update state
        self._state = new_state
        
        # Execute entry callbacks
        self._execute_callbacks(self._enter_callbacks[new_state],
                               f"enter {new_state.name}")
    
    def _execute_callbacks(self, callbacks: List[Callable], context: str) -> None:
        """Execute a list of callbacks with error handling."""
        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in {context} callback: {e}", exc_info=True)

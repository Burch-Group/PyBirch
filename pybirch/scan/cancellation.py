"""
Cancellation Token for PyBirch scan execution.

This module provides a thread-safe cancellation mechanism for long-running
scan operations. The CancellationToken can be used to signal abort requests
from any thread and checked by worker threads.

Usage:
    from pybirch.scan.cancellation import CancellationToken, CancellationError
    
    token = CancellationToken()
    
    # In worker thread:
    while not token.is_cancelled:
        token.check()  # Raises CancellationError if cancelled
        do_work()
    
    # In main thread:
    token.cancel()  # Signal cancellation
    token.cancel("User requested abort")  # With reason
"""

from __future__ import annotations
from threading import Event, Lock
from typing import Optional, Callable, List, Any
from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CancellationError(Exception):
    """Exception raised when an operation is cancelled."""
    
    def __init__(self, reason: str = "Operation was cancelled"):
        self.reason = reason
        super().__init__(reason)


class CancellationType(Enum):
    """Types of cancellation."""
    
    NONE = auto()        # Not cancelled
    SOFT = auto()        # Graceful cancellation (finish current item)
    HARD = auto()        # Immediate cancellation (stop ASAP)
    TIMEOUT = auto()     # Cancelled due to timeout


@dataclass
class CancellationInfo:
    """Information about a cancellation event."""
    
    type: CancellationType
    reason: str
    timestamp: datetime
    source: Optional[str] = None


class CancellationToken:
    """
    Thread-safe cancellation token for cooperative cancellation.
    
    This token provides a standard pattern for signaling cancellation
    across threads. Workers periodically check the token and stop
    gracefully when cancelled.
    
    Attributes:
        is_cancelled: Whether cancellation has been requested.
        is_pause_requested: Whether pause has been requested.
        reason: The reason for cancellation (if any).
        
    Thread Safety:
        All public methods are thread-safe.
    """
    
    def __init__(self, name: str = ""):
        """
        Initialize a new cancellation token.
        
        Args:
            name: Optional name for logging purposes.
        """
        self._name = name
        self._cancelled = Event()
        self._paused = Event()
        self._lock = Lock()
        self._info: Optional[CancellationInfo] = None
        self._callbacks: List[Callable[[CancellationInfo], None]] = []
    
    @property
    def name(self) -> str:
        """Get the token name."""
        return self._name
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled.is_set()
    
    @property
    def is_pause_requested(self) -> bool:
        """Check if pause has been requested."""
        return self._paused.is_set()
    
    @property
    def reason(self) -> str:
        """Get the cancellation reason."""
        with self._lock:
            return self._info.reason if self._info else ""
    
    @property
    def info(self) -> Optional[CancellationInfo]:
        """Get full cancellation information."""
        with self._lock:
            return self._info
    
    def cancel(
        self,
        reason: str = "Operation was cancelled",
        cancellation_type: CancellationType = CancellationType.SOFT,
        source: Optional[str] = None
    ) -> None:
        """
        Request cancellation.
        
        Args:
            reason: Human-readable reason for cancellation.
            cancellation_type: Type of cancellation (soft or hard).
            source: Source of the cancellation request.
        """
        with self._lock:
            if self._cancelled.is_set():
                return  # Already cancelled
            
            self._info = CancellationInfo(
                type=cancellation_type,
                reason=reason,
                timestamp=datetime.now(),
                source=source
            )
            self._cancelled.set()
            self._paused.clear()  # Unpause if paused
            
            logger.info(f"Cancellation requested: {reason} (type={cancellation_type.name})")
            
            # Call registered callbacks
            for callback in self._callbacks:
                try:
                    callback(self._info)
                except Exception as e:
                    logger.error(f"Cancellation callback error: {e}")
    
    def cancel_hard(self, reason: str = "Immediate cancellation requested") -> None:
        """Request immediate cancellation."""
        self.cancel(reason, CancellationType.HARD)
    
    def pause(self) -> None:
        """Request pause (without cancelling)."""
        with self._lock:
            if not self._cancelled.is_set():
                self._paused.set()
                logger.info(f"Pause requested for token '{self._name}'")
    
    def resume(self) -> None:
        """Resume from pause."""
        with self._lock:
            self._paused.clear()
            logger.info(f"Resume requested for token '{self._name}'")
    
    def check(self, throw_on_cancel: bool = True) -> bool:
        """
        Check if cancellation or pause is requested.
        
        Args:
            throw_on_cancel: If True, raises CancellationError when cancelled.
            
        Returns:
            True if cancelled, False otherwise.
            
        Raises:
            CancellationError: If cancelled and throw_on_cancel is True.
        """
        if self._cancelled.is_set():
            if throw_on_cancel:
                raise CancellationError(self.reason)
            return True
        return False
    
    def wait_if_paused(self, timeout: Optional[float] = None) -> bool:
        """
        Block if pause is requested until resumed or cancelled.
        
        Args:
            timeout: Maximum time to wait (None = wait forever).
            
        Returns:
            True if resumed, False if cancelled.
        """
        while self._paused.is_set() and not self._cancelled.is_set():
            # Poll periodically to check cancellation
            self._paused.wait(timeout=timeout or 0.1)
            if timeout is not None:
                break
        return not self._cancelled.is_set()
    
    def wait_for_cancellation(self, timeout: Optional[float] = None) -> bool:
        """
        Block until cancellation is requested.
        
        Args:
            timeout: Maximum time to wait (None = wait forever).
            
        Returns:
            True if cancelled, False if timeout elapsed.
        """
        return self._cancelled.wait(timeout=timeout)
    
    def reset(self) -> None:
        """
        Reset the token to non-cancelled state.
        
        Warning: Use with caution - only reset when no workers are active.
        """
        with self._lock:
            self._cancelled.clear()
            self._paused.clear()
            self._info = None
            logger.debug(f"Token '{self._name}' reset")
    
    def register_callback(
        self,
        callback: Callable[[CancellationInfo], None]
    ) -> None:
        """
        Register a callback to be called when cancellation occurs.
        
        Args:
            callback: Function to call with CancellationInfo.
        """
        with self._lock:
            self._callbacks.append(callback)
    
    def unregister_callback(
        self,
        callback: Callable[[CancellationInfo], None]
    ) -> None:
        """
        Remove a previously registered callback.
        
        Args:
            callback: The callback to remove.
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def create_child(self, name: str = "") -> 'CancellationToken':
        """
        Create a child token that is cancelled when this token is cancelled.
        
        Args:
            name: Name for the child token.
            
        Returns:
            A new CancellationToken linked to this one.
        """
        child = CancellationToken(name or f"{self._name}_child")
        
        def propagate_cancel(info: CancellationInfo):
            child.cancel(info.reason, info.type, f"parent:{self._name}")
        
        self.register_callback(propagate_cancel)
        return child
    
    def __enter__(self) -> 'CancellationToken':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - does not suppress exceptions."""
        return False
    
    def __repr__(self) -> str:
        status = "cancelled" if self.is_cancelled else ("paused" if self.is_pause_requested else "active")
        return f"CancellationToken(name='{self._name}', status={status})"


class CancellationTokenSource:
    """
    Factory for creating and managing related cancellation tokens.
    
    This provides a pattern for managing multiple tokens that should
    be cancelled together.
    """
    
    def __init__(self, name: str = ""):
        """
        Initialize the token source.
        
        Args:
            name: Name prefix for created tokens.
        """
        self._name = name
        self._tokens: List[CancellationToken] = []
        self._lock = Lock()
    
    def create_token(self, name: str = "") -> CancellationToken:
        """
        Create a new token managed by this source.
        
        Args:
            name: Optional name for the token.
            
        Returns:
            A new CancellationToken.
        """
        token = CancellationToken(name or f"{self._name}_{len(self._tokens)}")
        with self._lock:
            self._tokens.append(token)
        return token
    
    def cancel_all(self, reason: str = "All operations cancelled") -> None:
        """
        Cancel all tokens created by this source.
        
        Args:
            reason: Reason for cancellation.
        """
        with self._lock:
            for token in self._tokens:
                if not token.is_cancelled:
                    token.cancel(reason)
    
    def reset_all(self) -> None:
        """Reset all tokens."""
        with self._lock:
            for token in self._tokens:
                token.reset()
    
    @property
    def any_cancelled(self) -> bool:
        """Check if any token is cancelled."""
        with self._lock:
            return any(t.is_cancelled for t in self._tokens)
    
    @property
    def all_cancelled(self) -> bool:
        """Check if all tokens are cancelled."""
        with self._lock:
            return all(t.is_cancelled for t in self._tokens) if self._tokens else False

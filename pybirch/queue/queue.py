from pybirch.scan.measurements import Measurement
import numpy as np
import pandas as pd
import time
import os
from pybirch.scan.movements import Movement
import wandb
from pybirch.scan.scan import Scan, ScanSettings
from pymeasure.instruments import Instrument
from pymeasure.experiment import Results, Procedure
import pickle
from threading import Thread, Event, Lock
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from enum import Enum, auto
from typing import Callable, Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import queue
import traceback
import copy


class ScanState(Enum):
    """State of a scan in the queue."""
    QUEUED = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    ABORTED = auto()
    FAILED = auto()


class QueueState(Enum):
    """State of the queue itself."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()


class ExecutionMode(Enum):
    """How to execute scans."""
    SERIAL = auto()
    PARALLEL = auto()


@dataclass
class LogEntry:
    """A structured log entry from a scan."""
    timestamp: datetime
    scan_id: str
    scan_name: str
    level: str  # INFO, WARNING, ERROR, DEBUG
    message: str
    data: Optional[Dict[str, Any]] = None

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] [{self.level}] [{self.scan_name}] {self.message}"


@dataclass 
class ScanHandle:
    """A handle to track and control an individual scan."""
    scan: Scan
    state: ScanState = ScanState.QUEUED
    thread: Optional[Thread] = None
    future: Optional[Future] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[Exception] = None
    progress: float = 0.0  # 0.0 to 1.0
    
    def __getstate__(self):
        """Get state for pickling - exclude unpickleable thread/future."""
        state = self.__dict__.copy()
        state['thread'] = None
        state['future'] = None
        return state
    
    def __setstate__(self, state):
        """Set state when unpickling."""
        self.__dict__.update(state)
    
    @property
    def scan_id(self) -> str:
        return f"{self.scan.scan_settings.project_name}_{self.scan.scan_settings.scan_name}"
    
    @property
    def duration(self) -> Optional[float]:
        """Duration in seconds."""
        if self.start_time is None:
            return None
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    def is_active(self) -> bool:
        return self.state in (ScanState.RUNNING, ScanState.PAUSED)
    
    def is_finished(self) -> bool:
        return self.state in (ScanState.COMPLETED, ScanState.ABORTED, ScanState.FAILED)


class Queue:
    """A queue class to manage scans in the PyBirch framework.
    
    Features:
    - Execute scans in serial or parallel mode
    - Thread-safe operations for UI compatibility
    - Pause, resume, abort, restart individual scans or entire queue
    - Real-time logging with callbacks
    - Progress tracking
    """

    def __init__(self, QID: str, scans: Optional[List[Scan]] = None, max_parallel_scans: int = 4):
        self.QID = QID
        self._scan_handles: List[ScanHandle] = []
        self._state = QueueState.IDLE
        self._execution_mode = ExecutionMode.SERIAL
        self._max_parallel_scans = max_parallel_scans
        
        # Metadata storage for queue info (project_name, material, substrate, user_fields, etc.)
        self.metadata: dict = {}
        
        # Thread safety
        self._lock = Lock()
        self._stop_event = Event()
        self._pause_event = Event()
        self._pause_event.set()  # Not paused by default
        
        # Execution
        self._executor: Optional[ThreadPoolExecutor] = None
        self._execution_thread: Optional[Thread] = None
        
        # Logging
        self._log_queue: queue.Queue[LogEntry] = queue.Queue()
        self._log_callbacks: List[Callable[[LogEntry], None]] = []
        self._log_history: deque[LogEntry] = deque(maxlen=10000)
        
        # Progress callback
        self._progress_callbacks: List[Callable[[str, float], None]] = []
        self._state_callbacks: List[Callable[[str, ScanState], None]] = []
        
        # Add initial scans
        if scans:
            for scan in scans:
                self.enqueue(scan)
    
    def __getstate__(self):
        """Get state for pickling - exclude unpickleable objects."""
        state = self.__dict__.copy()
        # Clear callbacks as they may contain unpickleable objects (locks, sockets)
        state['_log_callbacks'] = []
        state['_progress_callbacks'] = []
        state['_state_callbacks'] = []
        # Clear threading objects
        state['_executor'] = None
        state['_execution_thread'] = None
        state['_lock'] = None
        state['_log_queue'] = None
        state['_stop_event'] = None
        state['_pause_event'] = None
        return state
    
    def __setstate__(self, state):
        """Set state when unpickling."""
        self.__dict__.update(state)
        # Reinitialize threading objects
        import threading
        import queue as queue_module
        self._lock = threading.RLock()
        self._log_queue = queue_module.Queue()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        # Ensure callback lists exist
        if '_log_callbacks' not in self.__dict__:
            self._log_callbacks = []
        if '_progress_callbacks' not in self.__dict__:
            self._progress_callbacks = []
        if '_state_callbacks' not in self.__dict__:
            self._state_callbacks = []

    # ==================== Core Queue Operations ====================

    @property
    def scans(self) -> List[Scan]:
        """Get list of all scans (for backwards compatibility)."""
        with self._lock:
            return [h.scan for h in self._scan_handles]
    
    @property
    def state(self) -> QueueState:
        return self._state
    
    @property
    def execution_mode(self) -> ExecutionMode:
        return self._execution_mode
    
    @execution_mode.setter
    def execution_mode(self, mode: ExecutionMode):
        if self._state == QueueState.RUNNING:
            raise RuntimeError("Cannot change execution mode while queue is running")
        self._execution_mode = mode

    def enqueue(self, scan: Scan) -> ScanHandle:
        """Add a scan to the queue."""
        with self._lock:
            handle = ScanHandle(scan=scan, state=ScanState.QUEUED)
            self._scan_handles.append(handle)
            self._log(handle.scan_id, scan.scan_settings.scan_name, "INFO", 
                     f"Scan enqueued: {scan.scan_settings.scan_name}")
            return handle

    def dequeue(self, index: int = 0) -> Scan:
        """Remove and return a scan from the queue."""
        with self._lock:
            if index < 0 or index >= len(self._scan_handles):
                raise IndexError("Queue index out of range")
            handle = self._scan_handles[index]
            if handle.is_active():
                raise RuntimeError("Cannot dequeue an active scan. Abort it first.")
            removed = self._scan_handles.pop(index)
            self._log(removed.scan_id, removed.scan.scan_settings.scan_name, "INFO",
                     f"Scan dequeued: {removed.scan.scan_settings.scan_name}")
            return removed.scan

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._scan_handles) == 0

    def size(self) -> int:
        with self._lock:
            return len(self._scan_handles)
    
    def clear(self):
        """Clear all non-active scans from the queue."""
        with self._lock:
            self._scan_handles = [h for h in self._scan_handles if h.is_active()]
            self._log("queue", self.QID, "INFO", "Queue cleared of inactive scans")

    def get_handle(self, index: int) -> ScanHandle:
        """Get a scan handle by index."""
        with self._lock:
            return self._scan_handles[index]
    
    def get_handle_by_id(self, scan_id: str) -> Optional[ScanHandle]:
        """Get a scan handle by scan ID."""
        with self._lock:
            for handle in self._scan_handles:
                if handle.scan_id == scan_id:
                    return handle
            return None

    def get_handles_by_state(self, state: ScanState) -> List[ScanHandle]:
        """Get all handles with a specific state."""
        with self._lock:
            return [h for h in self._scan_handles if h.state == state]

    def move_scan(self, from_index: int, to_index: int):
        """Move a scan to a different position in the queue."""
        with self._lock:
            if from_index < 0 or from_index >= len(self._scan_handles):
                raise IndexError("from_index out of range")
            if to_index < 0 or to_index >= len(self._scan_handles):
                raise IndexError("to_index out of range")
            handle = self._scan_handles.pop(from_index)
            self._scan_handles.insert(to_index, handle)

    def replace_scan(self, index: int, scan: Scan) -> ScanHandle:
        """Replace a scan at a specific index with a new scan.
        
        Args:
            index: The index of the scan to replace
            scan: The new Scan object to use
            
        Returns:
            The updated ScanHandle
            
        Raises:
            IndexError: If index is out of range
            RuntimeError: If the scan at that index is currently running
        """
        with self._lock:
            if index < 0 or index >= len(self._scan_handles):
                raise IndexError("Queue index out of range")
            handle = self._scan_handles[index]
            if handle.state == ScanState.RUNNING:
                raise RuntimeError("Cannot replace a running scan")
            # Update the scan reference in the handle
            handle.scan = scan
            self._log(handle.scan_id, scan.scan_settings.scan_name, "INFO",
                     f"Scan replaced: {scan.scan_settings.scan_name}")
            return handle

    # ==================== Execution Control ====================

    def start(self, indices: Optional[List[int]] = None, mode: Optional[ExecutionMode] = None):
        """Start executing scans.
        
        Args:
            indices: List of scan indices to execute. If None, execute all queued scans.
            mode: Execution mode (SERIAL or PARALLEL). If None, use current mode.
        """
        if self._state == QueueState.RUNNING:
            raise RuntimeError("Queue is already running")
        
        if mode is not None:
            self._execution_mode = mode
        
        self._stop_event.clear()
        self._pause_event.set()
        self._state = QueueState.RUNNING
        
        # Determine which scans to run
        with self._lock:
            if indices is None:
                # Run all queued scans
                scans_to_run = [h for h in self._scan_handles if h.state == ScanState.QUEUED]
            else:
                scans_to_run = [self._scan_handles[i] for i in indices 
                               if 0 <= i < len(self._scan_handles) 
                               and self._scan_handles[i].state == ScanState.QUEUED]
        
        if not scans_to_run:
            self._state = QueueState.IDLE
            self._log("queue", self.QID, "WARNING", "No queued scans to execute")
            return
        
        self._log("queue", self.QID, "INFO", 
                 f"Starting queue execution ({self._execution_mode.name}) with {len(scans_to_run)} scans")
        
        # Start execution in background thread
        self._execution_thread = Thread(
            target=self._execute_scans,
            args=(scans_to_run,),
            name=f"Queue_{self.QID}_executor",
            daemon=True
        )
        self._execution_thread.start()

    def _execute_scans(self, handles: List[ScanHandle]):
        """Internal method to execute scans (runs in background thread)."""
        try:
            if self._execution_mode == ExecutionMode.SERIAL:
                self._execute_serial(handles)
            else:
                self._execute_parallel(handles)
        except Exception as e:
            self._log("queue", self.QID, "ERROR", f"Queue execution error: {str(e)}")
        finally:
            self._state = QueueState.IDLE
            self._log("queue", self.QID, "INFO", "Queue execution finished")

    def _execute_serial(self, handles: List[ScanHandle]):
        """Execute scans one at a time."""
        for handle in handles:
            if self._stop_event.is_set():
                break
            
            # Wait if paused
            self._pause_event.wait()
            
            if self._stop_event.is_set():
                break
            
            self._run_single_scan(handle)

    def _execute_parallel(self, handles: List[ScanHandle]):
        """Execute scans in parallel."""
        with ThreadPoolExecutor(max_workers=self._max_parallel_scans, 
                               thread_name_prefix="scan_worker_") as executor:
            self._executor = executor
            futures = {}
            
            for handle in handles:
                if self._stop_event.is_set():
                    break
                future = executor.submit(self._run_single_scan, handle)
                futures[future] = handle
                handle.future = future
            
            # Wait for all to complete
            for future in as_completed(futures):
                handle = futures[future]
                try:
                    future.result()
                except Exception as e:
                    self._log(handle.scan_id, handle.scan.scan_settings.scan_name, 
                             "ERROR", f"Scan failed: {str(e)}")
            
            self._executor = None

    def _run_single_scan(self, handle: ScanHandle):
        """Run a single scan with full lifecycle management."""
        scan = handle.scan
        scan_name = scan.scan_settings.scan_name
        scan_id = handle.scan_id
        
        try:
            # Update state
            handle.state = ScanState.RUNNING
            handle.start_time = datetime.now()
            scan.scan_settings.status = "Running"
            self._notify_state_change(scan_id, ScanState.RUNNING)
            self._log(scan_id, scan_name, "INFO", "Scan started")
            
            # Startup phase
            self._log(scan_id, scan_name, "INFO", "Initializing scan...")
            scan.startup()
            self._log(scan_id, scan_name, "INFO", "Scan initialization complete")
            
            # Execute with pause/stop checking
            self._execute_scan_with_control(handle)
            
            # Check final state
            if scan._stop_event.is_set():
                if handle.state != ScanState.PAUSED:
                    handle.state = ScanState.ABORTED
                    scan.scan_settings.status = "Aborted"
                    self._log(scan_id, scan_name, "WARNING", "Scan aborted by user")
            else:
                handle.state = ScanState.COMPLETED
                scan.scan_settings.status = "Completed"
                self._log(scan_id, scan_name, "INFO", "Scan completed successfully")
            
        except Exception as e:
            handle.state = ScanState.FAILED
            handle.error = e
            scan.scan_settings.status = "Failed"
            self._log(scan_id, scan_name, "ERROR", f"Scan failed: {str(e)}\n{traceback.format_exc()}")
        
        finally:
            handle.end_time = datetime.now()
            try:
                scan.shutdown()
                self._log(scan_id, scan_name, "INFO", "Scan shutdown complete")
            except Exception as e:
                self._log(scan_id, scan_name, "ERROR", f"Error during shutdown: {str(e)}")
            
            self._notify_state_change(scan_id, handle.state)
            handle.progress = 1.0
            self._notify_progress(scan_id, 1.0)

    def _execute_scan_with_control(self, handle: ScanHandle):
        """Execute scan with pause/stop control integration."""
        scan = handle.scan
        
        # Store original stop event check
        original_stop_check = lambda: (
            self._stop_event.is_set() or 
            scan._stop_event.is_set() or
            not self._pause_event.is_set()
        )
        
        # Execute the scan
        scan.execute()

    # ==================== Scan Control Operations ====================

    def pause(self, scan_id: Optional[str] = None):
        """Pause execution.
        
        Args:
            scan_id: If provided, pause specific scan. Otherwise pause entire queue.
        """
        if scan_id:
            handle = self.get_handle_by_id(scan_id)
            if handle and handle.state == ScanState.RUNNING:
                handle.scan._stop_event.set()
                handle.state = ScanState.PAUSED
                handle.scan.scan_settings.status = "Paused"
                self._notify_state_change(scan_id, ScanState.PAUSED)
                self._log(scan_id, handle.scan.scan_settings.scan_name, "INFO", "Scan paused")
        else:
            self._pause_event.clear()
            self._state = QueueState.PAUSED
            # Pause all running scans
            for handle in self._scan_handles:
                if handle.state == ScanState.RUNNING:
                    handle.scan._stop_event.set()
                    handle.state = ScanState.PAUSED
                    handle.scan.scan_settings.status = "Paused"
                    self._notify_state_change(handle.scan_id, ScanState.PAUSED)
            self._log("queue", self.QID, "INFO", "Queue paused")

    def resume(self, scan_id: Optional[str] = None):
        """Resume execution.
        
        Args:
            scan_id: If provided, resume specific scan. Otherwise resume entire queue.
        """
        if scan_id:
            handle = self.get_handle_by_id(scan_id)
            if handle and handle.state == ScanState.PAUSED:
                handle.scan._stop_event.clear()
                handle.state = ScanState.RUNNING
                handle.scan.scan_settings.status = "Running"
                self._notify_state_change(scan_id, ScanState.RUNNING)
                self._log(scan_id, handle.scan.scan_settings.scan_name, "INFO", "Scan resumed")
                # Re-execute scan in new thread if in serial mode
                if self._execution_mode == ExecutionMode.SERIAL:
                    Thread(target=self._run_single_scan, args=(handle,), daemon=True).start()
        else:
            self._pause_event.set()
            self._state = QueueState.RUNNING
            # Resume all paused scans
            for handle in self._scan_handles:
                if handle.state == ScanState.PAUSED:
                    handle.scan._stop_event.clear()
                    handle.state = ScanState.RUNNING
                    handle.scan.scan_settings.status = "Running"
                    self._notify_state_change(handle.scan_id, ScanState.RUNNING)
                    # Re-execute in serial mode
                    if self._execution_mode == ExecutionMode.SERIAL:
                        Thread(target=self._run_single_scan, args=(handle,), daemon=True).start()
            self._log("queue", self.QID, "INFO", "Queue resumed")

    def abort(self, scan_id: Optional[str] = None):
        """Abort execution.
        
        Args:
            scan_id: If provided, abort specific scan. Otherwise abort entire queue.
        """
        if scan_id:
            handle = self.get_handle_by_id(scan_id)
            if handle and handle.is_active():
                handle.scan._stop_event.set()
                handle.state = ScanState.ABORTED
                handle.scan.scan_settings.status = "Aborted"
                self._notify_state_change(scan_id, ScanState.ABORTED)
                self._log(scan_id, handle.scan.scan_settings.scan_name, "WARNING", "Scan aborted")
        else:
            self._stop_event.set()
            self._pause_event.set()  # Unblock any waiting
            self._state = QueueState.STOPPING
            # Abort all active scans
            for handle in self._scan_handles:
                if handle.is_active():
                    handle.scan._stop_event.set()
                    handle.state = ScanState.ABORTED
                    handle.scan.scan_settings.status = "Aborted"
                    self._notify_state_change(handle.scan_id, ScanState.ABORTED)
            self._log("queue", self.QID, "WARNING", "Queue aborted")

    def restart(self, scan_id: str):
        """Restart a scan (reset and re-queue).
        
        Args:
            scan_id: The ID of the scan to restart.
        """
        handle = self.get_handle_by_id(scan_id)
        if not handle:
            raise ValueError(f"No scan found with ID: {scan_id}")
        
        if handle.is_active():
            raise RuntimeError("Cannot restart an active scan. Abort it first.")
        
        # Reset the scan state
        handle.state = ScanState.QUEUED
        handle.scan.scan_settings.status = "Queued"
        handle.start_time = None
        handle.end_time = None
        handle.error = None
        handle.progress = 0.0
        handle.scan._stop_event.clear()
        handle.scan.current_item = None
        
        # Reset instrument runtime states in the tree
        for item in handle.scan.scan_settings.scan_tree.get_all_instrument_items():
            item._runtime_initialized = False
            item.reset_indices()
        
        self._notify_state_change(scan_id, ScanState.QUEUED)
        self._log(scan_id, handle.scan.scan_settings.scan_name, "INFO", "Scan reset and re-queued")

    def stop_queue(self):
        """Stop the queue execution gracefully after current scans finish."""
        self._stop_event.set()
        self._state = QueueState.STOPPING
        self._log("queue", self.QID, "INFO", "Queue stopping (waiting for active scans)")

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all scans to complete.
        
        Args:
            timeout: Maximum time to wait in seconds. None for infinite.
            
        Returns:
            True if completed, False if timed out.
        """
        if self._execution_thread:
            self._execution_thread.join(timeout=timeout)
            return not self._execution_thread.is_alive()
        return True

    # ==================== Logging System ====================

    def _log(self, scan_id: str, scan_name: str, level: str, message: str, data: Optional[Dict] = None):
        """Internal logging method."""
        entry = LogEntry(
            timestamp=datetime.now(),
            scan_id=scan_id,
            scan_name=scan_name,
            level=level,
            message=message,
            data=data
        )
        
        # Add to history
        self._log_history.append(entry)
        
        # Put in queue for async processing
        self._log_queue.put(entry)
        
        # Notify callbacks
        for callback in self._log_callbacks:
            try:
                callback(entry)
            except Exception:
                pass  # Don't let callback errors affect logging

    def add_log_callback(self, callback: Callable[[LogEntry], None]):
        """Add a callback to receive log entries in real-time."""
        self._log_callbacks.append(callback)

    def remove_log_callback(self, callback: Callable[[LogEntry], None]):
        """Remove a log callback."""
        if callback in self._log_callbacks:
            self._log_callbacks.remove(callback)

    def get_logs(self, scan_id: Optional[str] = None, level: Optional[str] = None, limit: Optional[int] = None) -> List[LogEntry]:
        """Get log entries with optional filtering.
        
        Args:
            scan_id: Filter by scan ID
            level: Filter by log level
            limit: Maximum number of entries to return
        """
        logs = list(self._log_history)
        
        if scan_id:
            logs = [l for l in logs if l.scan_id == scan_id]
        if level:
            logs = [l for l in logs if l.level == level]
        if limit:
            logs = logs[-limit:]
        
        return logs

    def clear_logs(self):
        """Clear log history."""
        self._log_history.clear()

    # ==================== Progress & State Callbacks ====================

    def add_progress_callback(self, callback: Callable[[str, float], None]):
        """Add callback for progress updates. Receives (scan_id, progress 0.0-1.0)."""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[str, float], None]):
        """Remove a progress callback."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def _notify_progress(self, scan_id: str, progress: float):
        """Notify progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(scan_id, progress)
            except Exception:
                pass

    def add_state_callback(self, callback: Callable[[str, ScanState], None]):
        """Add callback for state changes. Receives (scan_id, new_state)."""
        self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[str, ScanState], None]):
        """Remove a state callback."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    def _notify_state_change(self, scan_id: str, state: ScanState):
        """Notify state callbacks."""
        for callback in self._state_callbacks:
            try:
                callback(scan_id, state)
            except Exception:
                pass

    # ==================== Status & Info ====================

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive queue status."""
        with self._lock:
            return {
                "queue_id": self.QID,
                "state": self._state.name,
                "execution_mode": self._execution_mode.name,
                "total_scans": len(self._scan_handles),
                "scans_by_state": {
                    state.name: len([h for h in self._scan_handles if h.state == state])
                    for state in ScanState
                },
                "scans": [
                    {
                        "id": h.scan_id,
                        "name": h.scan.scan_settings.scan_name,
                        "state": h.state.name,
                        "progress": h.progress,
                        "duration": h.duration,
                        "error": str(h.error) if h.error else None
                    }
                    for h in self._scan_handles
                ]
            }

    def __len__(self) -> int:
        return self.size()

    def __iter__(self):
        return iter(self.scans)

    # ==================== Serialization ====================

    def serialize(self) -> dict:
        """Serialize the queue to a dictionary."""
        with self._lock:
            return {
                "QID": self.QID,
                "execution_mode": self._execution_mode.name,
                "max_parallel_scans": self._max_parallel_scans,
                "scans": [
                    {
                        "scan_settings": h.scan.scan_settings.serialize(),
                        "owner": h.scan.owner,
                        "sample_id": h.scan.sample_id,
                        "state": h.state.name,
                        "progress": h.progress
                    }
                    for h in self._scan_handles
                ]
            }

    @classmethod
    def deserialize(cls, data: dict) -> 'Queue':
        """Deserialize a queue from a dictionary."""
        queue = cls(
            QID=data["QID"],
            max_parallel_scans=data.get("max_parallel_scans", 4)
        )
        queue._execution_mode = ExecutionMode[data.get("execution_mode", "SERIAL")]
        
        # Note: Full scan deserialization requires instrument objects to be reconstructed
        # This provides the structure, actual instrument pairing happens separately
        
        return queue

    def save(self, filepath: str):
        """Save the queue to a pickle file."""
        with open(filepath, 'wb') as f:
            pickle.dump(self.serialize(), f)

    @classmethod
    def load(cls, filepath: str) -> 'Queue':
        """Load a queue from a pickle file."""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            return cls.deserialize(data)

    def __repr__(self) -> str:
        return f"Queue(QID='{self.QID}', scans={self.size()}, state={self._state.name})"

    def __str__(self) -> str:
        lines = [f"Queue '{self.QID}' ({self._state.name})"]
        for i, handle in enumerate(self._scan_handles):
            lines.append(f"  [{i}] {handle.scan.scan_settings.scan_name}: {handle.state.name}")
        return "\n".join(lines)


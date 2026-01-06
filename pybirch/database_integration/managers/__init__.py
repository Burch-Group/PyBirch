"""Managers module for database integration."""

from .scan_manager import ScanManager
from .queue_manager import QueueManager
from .equipment_manager import EquipmentManager

# DataManager requires pandas - import conditionally
try:
    from .data_manager import DataManager
except ImportError:
    DataManager = None  # Will be None if pandas not available

__all__ = ['ScanManager', 'QueueManager', 'EquipmentManager', 'DataManager']

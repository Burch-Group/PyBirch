# Copyright (C) 2025
# Instrument Configuration Manager for PyBirch
"""
Manages persistent storage and retrieval of instrument configurations.
Handles saving/loading of adapter manager and instrument selection states.
Provides smart reconnection handling for temporarily disconnected instruments.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Default config path
DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent / "config" / "default" / "instruments"


class InstrumentConfigManager:
    """
    Manages persistent storage of instrument configurations.
    
    Features:
    - Saves adapter mappings and instrument selections
    - Tracks connection history for smart reconnection
    - Preserves configurations for temporarily disconnected instruments
    """
    
    CONFIG_FILENAME = "instrument_config.json"
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory for storing configuration files.
                       Defaults to config/default/instruments/
        """
        if config_dir is None:
            self.config_dir = DEFAULT_CONFIG_DIR
        else:
            self.config_dir = Path(config_dir)
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_path = self.config_dir / self.CONFIG_FILENAME
        
    def save_config(self, data: Dict[str, Any]) -> bool:
        """
        Save instrument configuration to file.
        
        Args:
            data: Configuration data containing:
                - adapter_manager: Adapter manager serialized data
                - instrument_selector: Instrument selector serialized data
                - splitter_sizes: UI splitter sizes
                - connection_history: Historical connection data
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add metadata
            save_data = {
                'version': '1.0',
                'saved_at': datetime.now().isoformat(),
                'data': data
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, default=self._json_serializer)
            
            return True
        except Exception as e:
            print(f"Error saving instrument config: {e}")
            return False
    
    def load_config(self) -> Optional[Dict[str, Any]]:
        """
        Load instrument configuration from file.
        
        Returns:
            Configuration data dict or None if file doesn't exist/error
        """
        if not self.config_path.exists():
            return None
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            return save_data.get('data', {})
        except Exception as e:
            print(f"Error loading instrument config: {e}")
            return None
    
    def config_exists(self) -> bool:
        """Check if a saved configuration exists."""
        return self.config_path.exists()
    
    def get_last_saved_time(self) -> Optional[str]:
        """Get the timestamp of the last saved configuration."""
        if not self.config_path.exists():
            return None
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            return save_data.get('saved_at')
        except Exception:
            return None
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for non-serializable objects."""
        if hasattr(obj, '__name__'):
            # It's a class - store its name
            return {'__class_name__': obj.__name__}
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)
    
    def update_connection_history(self, adapter: str, connected: bool, 
                                   instrument_name: str = "", nickname: str = "") -> Dict[str, Any]:
        """
        Update connection history for an adapter.
        
        Args:
            adapter: Adapter string (e.g., "COM3", "GPIB0::1::INSTR")
            connected: Whether the adapter is currently connected
            instrument_name: Name of the assigned instrument
            nickname: User-defined nickname
        
        Returns:
            Updated history entry for the adapter
        """
        config = self.load_config() or {}
        history = config.get('connection_history', {})
        
        now = datetime.now().isoformat()
        
        if adapter not in history:
            history[adapter] = {
                'first_seen': now,
                'last_seen': now,
                'last_connected': now if connected else None,
                'instrument_name': instrument_name,
                'nickname': nickname,
                'connection_count': 1 if connected else 0
            }
        else:
            entry = history[adapter]
            entry['last_seen'] = now
            if connected:
                entry['last_connected'] = now
                entry['connection_count'] = entry.get('connection_count', 0) + 1
            if instrument_name:
                entry['instrument_name'] = instrument_name
            if nickname:
                entry['nickname'] = nickname
        
        config['connection_history'] = history
        self.save_config(config)
        
        return history[adapter]
    
    def get_connection_history(self, adapter: str) -> Optional[Dict[str, Any]]:
        """Get connection history for a specific adapter."""
        config = self.load_config() or {}
        history = config.get('connection_history', {})
        return history.get(adapter)
    
    def get_all_known_adapters(self) -> List[Dict[str, Any]]:
        """
        Get list of all historically known adapters with their configurations.
        
        Returns:
            List of adapter configurations including offline ones
        """
        config = self.load_config() or {}
        history = config.get('connection_history', {})
        
        adapters = []
        for adapter_str, entry in history.items():
            adapters.append({
                'adapter': adapter_str,
                'instrument_name': entry.get('instrument_name', ''),
                'nickname': entry.get('nickname', ''),
                'last_connected': entry.get('last_connected'),
                'first_seen': entry.get('first_seen'),
                'connection_count': entry.get('connection_count', 0)
            })
        
        return adapters
    
    def delete_config(self) -> bool:
        """Delete the saved configuration file."""
        try:
            if self.config_path.exists():
                self.config_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting config: {e}")
            return False


# Singleton instance for global access
_config_manager_instance: Optional[InstrumentConfigManager] = None


def get_config_manager() -> InstrumentConfigManager:
    """Get the global instrument config manager instance."""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = InstrumentConfigManager()
    return _config_manager_instance

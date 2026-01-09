"""
Instrument Factory
==================
Factory for creating instrument instances from database drivers.

This module provides dynamic class creation from database-stored source code,
enabling browser-based instrument creation and per-computer discovery.

Usage:
    from pybirch.Instruments.factory import InstrumentFactory
    
    # Create class from driver
    driver = db_service.get_driver(driver_id)
    instrument_class = InstrumentFactory.create_class_from_driver(driver)
    
    # Create instance with adapter
    instance = InstrumentFactory.create_instance(driver, adapter='GPIB::8::INSTR')
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Type
import warnings
import logging

logger = logging.getLogger(__name__)


class InstrumentFactory:
    """Factory for creating instrument instances from database drivers.
    
    Can be used as a class with classmethods for one-off operations, or
    instantiated with a DatabaseService for database-backed operations.
    """
    
    # Class-level cache of compiled classes by driver ID
    _class_cache: Dict[int, type] = {}
    
    # Class-level cache of driver versions for invalidation
    _version_cache: Dict[int, int] = {}
    
    def __init__(self, db_service=None):
        """Initialize the factory with optional database service.
        
        Args:
            db_service: DatabaseService instance for loading drivers
        """
        self.db_service = db_service
    
    def get_available_drivers(self) -> List[Dict]:
        """Get all available instrument drivers from the database.
        
        Returns:
            List of driver dictionaries
        """
        if not self.db_service:
            logger.warning("No database service configured for InstrumentFactory")
            return []
        
        try:
            drivers = self.db_service.get_drivers()
            return drivers if drivers else []
        except Exception as e:
            logger.error(f"Failed to get drivers: {e}")
            return []
    
    def get_driver_by_id(self, driver_id: int) -> Optional[Dict]:
        """Get a specific instrument driver by ID.
        
        Args:
            driver_id: The driver ID
            
        Returns:
            driver dictionary or None
        """
        if not self.db_service:
            return None
        
        try:
            return self.db_service.get_driver(driver_id)
        except Exception as e:
            logger.error(f"Failed to get driver {driver_id}: {e}")
            return None
    
    def get_driver_by_name_or_class(self, name: str) -> Optional[Dict]:
        """Get a specific instrument driver by class name.
        
        Args:
            name: The class name
            
        Returns:
            driver dictionary or None
        """
        if not self.db_service:
            return None
        
        try:
            return self.db_service.get_driver_by_name(name)
        except Exception as e:
            logger.error(f"Failed to get driver '{name}': {e}")
            return None
    
    @classmethod
    def get_base_class_map(cls) -> Dict[str, type]:
        """Get mapping of base class names to actual classes.
        
        Returns:
            Dictionary mapping class name strings to class types
        """
        from pybirch.scan.measurements import Measurement, VisaMeasurement
        from pybirch.scan.movements import Movement, VisaMovement
        
        base_map = {
            'Measurement': Measurement,
            'VisaMeasurement': VisaMeasurement,
            'Movement': Movement,
            'VisaMovement': VisaMovement,
        }
        
        # Try to import new base classes
        try:
            from pybirch.Instruments.base import (
                BaseMeasurementInstrument,
                BaseMovementInstrument,
                FakeMeasurementInstrument,
                FakeMovementInstrument,
                VisaBaseMeasurementInstrument,
                VisaBaseMovementInstrument,
                InstrumentSettingsMixin,
            )
            base_map.update({
                'BaseMeasurementInstrument': BaseMeasurementInstrument,
                'BaseMovementInstrument': BaseMovementInstrument,
                'FakeMeasurementInstrument': FakeMeasurementInstrument,
                'FakeMovementInstrument': FakeMovementInstrument,
                'VisaBaseMeasurementInstrument': VisaBaseMeasurementInstrument,
                'VisaBaseMovementInstrument': VisaBaseMovementInstrument,
                'InstrumentSettingsMixin': InstrumentSettingsMixin,
            })
        except ImportError:
            pass
        
        return base_map
    
    @classmethod
    def create_namespace(cls) -> Dict[str, Any]:
        """Create namespace for executing instrument code.
        
        Returns:
            Dictionary with common imports available
        """
        import time
        import math
        
        namespace = {
            # Common imports
            'np': np,
            'numpy': np,
            'pd': pd,
            'pandas': pd,
            'time': time,
            'math': math,
            
            # Type hints
            'Dict': Dict,
            'List': list,
            'Optional': Optional,
            'Any': Any,
            'Type': Type,
            
            # Built-ins
            '__builtins__': __builtins__,
        }
        
        # Add base classes
        namespace.update(cls.get_base_class_map())
        
        return namespace
    
    @classmethod
    def create_class_from_driver(cls, driver: Dict) -> type:
        """Dynamically create a Python class from database driver.
        
        Args:
            driver: Driver record as dictionary with:
                - id: driver ID
                - name: Class name
                - source_code: Python source code
                - base_class: Base class name
                - version: Version number
        
        Returns:
            The dynamically created instrument class
        
        Raises:
            ValueError: If driver is invalid
            SyntaxError: If source code has syntax errors
            NameError: If base class not found
        """
        if not driver:
            raise ValueError("driver cannot be empty")
        
        driver_id = driver.get('id')
        class_name = driver.get('name')
        source_code = driver.get('source_code')
        version = driver.get('version', 1)
        
        if not class_name:
            raise ValueError("driver must have 'name' field")
        if not source_code:
            raise ValueError("driver must have 'source_code' field")
        
        # Check cache
        if driver_id:
            cached_version = cls._version_cache.get(driver_id)
            if cached_version == version and driver_id in cls._class_cache:
                return cls._class_cache[driver_id]
        
        # Create namespace with imports and base classes
        namespace = cls.create_namespace()
        
        # Compile and execute the source code
        try:
            exec(source_code, namespace)
        except SyntaxError as e:
            raise SyntaxError(f"Syntax error in instrument '{class_name}': {e}")
        except NameError as e:
            raise NameError(f"Name error in instrument '{class_name}': {e}")
        
        # Find the class in the namespace
        if class_name not in namespace:
            # Try to find any class that was defined
            defined_classes = [
                name for name, obj in namespace.items()
                if isinstance(obj, type) and obj.__module__ == '__main__'
            ]
            if defined_classes:
                raise ValueError(
                    f"Class '{class_name}' not found in source code. "
                    f"Found: {defined_classes}"
                )
            else:
                raise ValueError(
                    f"No class found in source code for '{class_name}'"
                )
        
        instrument_class = namespace[class_name]
        
        # Validate it's actually a class
        if not isinstance(instrument_class, type):
            raise ValueError(f"'{class_name}' is not a class")
        
        # Store metadata on the class
        instrument_class._driver_id = driver_id
        instrument_class._driver_version = version
        
        # Cache it
        if driver_id:
            cls._class_cache[driver_id] = instrument_class
            cls._version_cache[driver_id] = version
        
        return instrument_class
    
    @classmethod
    def create_instance(
        cls,
        driver: Dict,
        adapter: str = '',
        name: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Create an instrument instance from a driver.
        
        Args:
            driver: Driver record as dictionary
            adapter: VISA address or connection string
            name: Optional name override (uses display_name by default)
            **kwargs: Additional arguments passed to constructor
        
        Returns:
            Instrument instance
        """
        instrument_class = cls.create_class_from_driver(driver)
        
        # Determine name to use
        instance_name = name or driver.get('display_name') or driver.get('name')
        
        # Create instance
        try:
            instance = instrument_class(name=instance_name, **kwargs)
        except TypeError:
            # Some classes might not accept name in constructor
            try:
                instance = instrument_class(instance_name, **kwargs)
            except TypeError:
                instance = instrument_class(**kwargs)
                instance.name = instance_name
        
        # Set adapter
        if adapter:
            instance.adapter = adapter
        
        # Store reference to driver
        instance._driver_id = driver.get('id')
        instance._driver_version = driver.get('version', 1)
        
        return instance
    
    @classmethod
    def invalidate_cache(cls, driver_id: Optional[int] = None):
        """Invalidate the class cache.
        
        Args:
            driver_id: Specific driver to invalidate, or None for all
        """
        if driver_id:
            cls._class_cache.pop(driver_id, None)
            cls._version_cache.pop(driver_id, None)
        else:
            cls._class_cache.clear()
            cls._version_cache.clear()
    
    @classmethod
    def validate_source_code(cls, source_code: str, class_name: str) -> Dict:
        """Validate instrument source code without creating an instance.
        
        Args:
            source_code: Python source code to validate
            class_name: Expected class name
        
        Returns:
            Dictionary with:
                - valid: bool - whether code is valid
                - errors: list - any errors found
                - warnings: list - any warnings
                - class_info: dict - extracted class info if valid
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'class_info': None,
        }
        
        # Check syntax
        try:
            compile(source_code, '<instrument>', 'exec')
        except SyntaxError as e:
            result['errors'].append(f"Syntax error at line {e.lineno}: {e.msg}")
            return result
        
        # Try to execute
        namespace = cls.create_namespace()
        
        try:
            exec(source_code, namespace)
        except Exception as e:
            result['errors'].append(f"Execution error: {type(e).__name__}: {e}")
            return result
        
        # Find the class
        if class_name not in namespace:
            result['errors'].append(f"Class '{class_name}' not found in source code")
            return result
        
        instrument_class = namespace[class_name]
        
        if not isinstance(instrument_class, type):
            result['errors'].append(f"'{class_name}' is not a class")
            return result
        
        # Check inheritance
        base_classes = cls.get_base_class_map()
        valid_bases = set(base_classes.values())
        
        has_valid_base = any(
            issubclass(instrument_class, base)
            for base in valid_bases
            if isinstance(base, type)
        )
        
        if not has_valid_base:
            result['warnings'].append(
                f"Class '{class_name}' does not inherit from a known instrument base class"
            )
        
        # Extract class info
        instrument_type = None
        for base in instrument_class.__mro__:
            base_name = base.__name__
            if 'Measurement' in base_name:
                instrument_type = 'measurement'
                break
            elif 'Movement' in base_name:
                instrument_type = 'movement'
                break
        
        result['class_info'] = {
            'name': class_name,
            'instrument_type': instrument_type,
            'base_classes': [b.__name__ for b in instrument_class.__bases__],
            'docstring': instrument_class.__doc__,
        }
        
        result['valid'] = len(result['errors']) == 0
        return result


# Convenience function for getting computer info
def get_computer_info() -> Dict[str, str]:
    """Get identifying information about this computer.
    
    Returns:
        Dictionary with:
            - computer_name: hostname
            - computer_id: MAC address as string
            - username: OS username
    """
    import socket
    import uuid
    import os
    
    return {
        'computer_name': socket.gethostname(),
        'computer_id': str(uuid.getnode()),  # MAC address as int, converted to string
        'username': os.getenv('USERNAME') or os.getenv('USER') or '',
    }

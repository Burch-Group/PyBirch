"""
Equipment Manager
=================
Manages the integration between PyBirch instruments and the database.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Type

try:
    from database.services import DatabaseService
    from database.models import Equipment
except ImportError:
    DatabaseService = None
    Equipment = None


class EquipmentManager:
    """
    Manages instrument registration and status tracking in the database.
    
    This class bridges PyBirch instrument objects with database Equipment records,
    handling registration, status updates, and settings persistence.
    """
    
    def __init__(self, db_service: 'DatabaseService'):
        """
        Initialize the EquipmentManager.
        
        Args:
            db_service: Database service instance for persistence operations
        """
        self.db = db_service
        self._registered_instruments: Dict[str, int] = {}  # Maps instrument name to db_id
    
    def register_instrument(
        self,
        instrument: Any,
        lab_id: Optional[int] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a PyBirch instrument in the database.
        
        Args:
            instrument: PyBirch instrument object (Measurement or Movement)
            lab_id: Database lab ID (optional)
            location: Physical location of the instrument
            
        Returns:
            Dictionary with created/updated equipment data
        """
        # Determine equipment type
        equipment_type = self._get_equipment_type(instrument)
        
        # Get instrument properties
        name = getattr(instrument, 'name', instrument.__class__.__name__)
        adapter = getattr(instrument, 'adapter', '')
        pybirch_class = instrument.__class__.__name__
        
        # Check if already registered
        existing = self.db.get_equipment_by_name(name) if hasattr(self.db, 'get_equipment_by_name') else None
        
        if existing:
            # Update existing record
            update_data = {
                'adapter': adapter,
                'pybirch_class': pybirch_class,
                'status': 'available' if getattr(instrument, 'status', False) else 'disconnected',
            }
            if lab_id:
                update_data['lab_id'] = lab_id
            if location:
                update_data['location'] = location
            
            equipment = self.db.update_equipment(existing['id'], update_data)
            self._registered_instruments[name] = existing['id']
            return equipment
        
        # Create new record
        data = {
            'name': name,
            'equipment_type': equipment_type,
            'pybirch_class': pybirch_class,
            'adapter': adapter,
            'lab_id': lab_id,
            'location': location,
            'status': 'available' if getattr(instrument, 'status', False) else 'disconnected',
            'specifications': self._get_specifications(instrument),
        }
        
        equipment = self.db.create_equipment(data)
        self._registered_instruments[name] = equipment['id']
        
        return equipment
    
    def update_status(
        self,
        instrument_name: str,
        status: str,
        error_message: Optional[str] = None,
        current_settings: Optional[Dict] = None,
    ) -> bool:
        """
        Update instrument status.
        
        Args:
            instrument_name: Name of the instrument
            status: New status ('available', 'in_use', 'disconnected', 'error', 'maintenance')
            error_message: Error message if status is 'error'
            current_settings: Current instrument settings
            
        Returns:
            True if successful, False otherwise
        """
        db_id = self._registered_instruments.get(instrument_name)
        if not db_id:
            return False
        
        update_data = {'status': status}
        
        # If we have InstrumentStatus tracking
        if hasattr(self.db, 'update_instrument_status'):
            return self.db.update_instrument_status(
                db_id, 
                status, 
                error_message=error_message,
                current_settings=current_settings
            )
        
        # Otherwise just update equipment
        result = self.db.update_equipment(db_id, update_data)
        return result is not None
    
    def set_connected(self, instrument_name: str) -> bool:
        """Mark an instrument as connected."""
        return self.update_status(instrument_name, 'available')
    
    def set_disconnected(self, instrument_name: str) -> bool:
        """Mark an instrument as disconnected."""
        return self.update_status(instrument_name, 'disconnected')
    
    def set_in_use(self, instrument_name: str) -> bool:
        """Mark an instrument as in use."""
        return self.update_status(instrument_name, 'in_use')
    
    def set_error(self, instrument_name: str, error_message: str) -> bool:
        """Mark an instrument as having an error."""
        return self.update_status(instrument_name, 'error', error_message=error_message)
    
    def save_settings(self, instrument_name: str, settings: Dict[str, Any]) -> bool:
        """
        Save instrument settings to database.
        
        Args:
            instrument_name: Name of the instrument
            settings: Settings dictionary
            
        Returns:
            True if successful, False otherwise
        """
        db_id = self._registered_instruments.get(instrument_name)
        if not db_id:
            return False
        
        # Store settings in specifications JSON field
        result = self.db.update_equipment(db_id, {
            'specifications': settings
        })
        return result is not None
    
    def get_saved_settings(self, instrument_name: str) -> Optional[Dict[str, Any]]:
        """
        Get saved settings for an instrument.
        
        Args:
            instrument_name: Name of the instrument
            
        Returns:
            Settings dictionary or None
        """
        db_id = self._registered_instruments.get(instrument_name)
        if not db_id:
            return None
        
        equipment = self.db.get_equipment(db_id)
        if equipment:
            return equipment.get('specifications')
        return None
    
    def get_equipment(self, instrument_name: str) -> Optional[Dict[str, Any]]:
        """Get equipment data from database."""
        db_id = self._registered_instruments.get(instrument_name)
        if db_id:
            return self.db.get_equipment(db_id)
        
        # Try to find by name
        if hasattr(self.db, 'get_equipment_by_name'):
            return self.db.get_equipment_by_name(instrument_name)
        return None
    
    def get_instruments_by_type(self, equipment_type: str) -> List[Dict[str, Any]]:
        """Get all instruments of a specific type."""
        return self.db.get_equipment(equipment_type=equipment_type)[0]
    
    def discover_instruments(self, setup_module: Any) -> List[Dict[str, Any]]:
        """
        Discover and register all instruments from a setup module.
        
        Args:
            setup_module: PyBirch setup module containing instrument definitions
            
        Returns:
            List of registered equipment dictionaries
        """
        registered = []
        
        # Look for measurement instruments
        if hasattr(setup_module, 'measurement_instruments'):
            for instr in setup_module.measurement_instruments:
                try:
                    equipment = self.register_instrument(instr)
                    registered.append(equipment)
                except Exception as e:
                    print(f"Failed to register measurement instrument: {e}")
        
        # Look for movement instruments
        if hasattr(setup_module, 'movement_instruments'):
            for instr in setup_module.movement_instruments:
                try:
                    equipment = self.register_instrument(instr)
                    registered.append(equipment)
                except Exception as e:
                    print(f"Failed to register movement instrument: {e}")
        
        return registered
    
    def _get_equipment_type(self, instrument: Any) -> str:
        """Determine equipment type from instrument class."""
        class_name = instrument.__class__.__name__.lower()
        base_classes = [c.__name__.lower() for c in instrument.__class__.__mro__]
        
        if 'measurement' in class_name or any('measurement' in b for b in base_classes):
            return 'measurement'
        elif 'movement' in class_name or any('movement' in b for b in base_classes):
            return 'movement'
        else:
            return 'other'
    
    def _get_specifications(self, instrument: Any) -> Dict[str, Any]:
        """Extract specifications from instrument."""
        specs = {}
        
        # Get data columns for measurement instruments
        if hasattr(instrument, 'data_columns'):
            specs['data_columns'] = list(instrument.data_columns) if hasattr(instrument.data_columns, '__iter__') else []
        
        if hasattr(instrument, 'data_units'):
            specs['data_units'] = list(instrument.data_units) if hasattr(instrument.data_units, '__iter__') else []
        
        # Get position info for movement instruments
        if hasattr(instrument, 'position_column'):
            specs['position_column'] = instrument.position_column
        
        if hasattr(instrument, 'position_units'):
            specs['position_units'] = instrument.position_units
        
        # Get current settings if available
        if hasattr(instrument, 'settings'):
            try:
                specs['default_settings'] = instrument.settings
            except Exception:
                pass
        
        return specs

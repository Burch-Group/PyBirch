"""
Unit Tests for Instrument drivers Feature

Tests cover:
- InstrumentFactory: dynamic class creation, validation, caching
- DatabaseService: CRUD for instrument drivers and computer bindings
- get_computer_info: computer identification utility

Run with: pytest tests/test_drivers.py -v
"""

import sys
import os
import logging
import pytest

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from database.services import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_measurement_code():
    """Sample measurement instrument source code."""
    return '''
from pybirch.scan.measurements import Measurement
import numpy as np

class TestMeasurementInstrument(Measurement):
    """A test measurement instrument."""
    
    def __init__(self, name="TestMeasurement"):
        super().__init__(name=name)
        self.data_columns = ["voltage", "current"]
        self.data_units = ["V", "A"]
        self._last_value = 0.0
    
    def connect(self):
        self.status = True
        return True
    
    def measure(self):
        self._last_value = np.random.random()
        return {"voltage": self._last_value, "current": self._last_value * 0.1}
    
    def shutdown(self):
        self.status = False
'''


@pytest.fixture
def sample_movement_code():
    """Sample movement instrument source code."""
    return '''
from pybirch.scan.movements import Movement

class TestMovementInstrument(Movement):
    """A test movement instrument."""
    
    def __init__(self, name="TestMovement"):
        super().__init__(name=name)
        self._position = 0.0
        self.min_position = -100.0
        self.max_position = 100.0
    
    @property
    def position(self):
        return self._position
    
    @position.setter
    def position(self, value):
        if self.min_position <= value <= self.max_position:
            self._position = value
        else:
            raise ValueError(f"Position {value} out of range")
    
    def connect(self):
        self.status = True
        return True
    
    def shutdown(self):
        self.status = False
'''


@pytest.fixture
def invalid_syntax_code():
    """Code with syntax errors."""
    return '''
class BrokenInstrument(Measurement):
    def __init__(self
        # Missing closing parenthesis
        pass
'''


@pytest.fixture
def missing_class_code():
    """Code that doesn't define the expected class."""
    return '''
from pybirch.scan.measurements import Measurement

class WrongClassName(Measurement):
    pass
'''


@pytest.fixture
def sample_driver(sample_measurement_code):
    """A sample instrument driver dictionary."""
    return {
        'id': 1,
        'name': 'TestMeasurementInstrument',
        'display_name': 'Test Measurement',
        'description': 'A test instrument',
        'instrument_type': 'measurement',
        'source_code': sample_measurement_code,
        'base_class': 'Measurement',
        'version': 1,
        'is_public': True,
    }


@pytest.fixture(scope='function')
def db_service():
    """Create a DatabaseService with an in-memory database."""
    # Use in-memory database to avoid file locking issues on Windows
    # The :memory: database is faster and doesn't need cleanup
    db_url = 'sqlite:///:memory:'
    service = DatabaseService(db_url)
    
    yield service


@pytest.fixture
def sample_lab(db_service):
    """Create a sample lab for testing."""
    lab = db_service.create_lab({
        'name': 'Test Lab',
        'code': 'TEST',
        'university': 'Test University',
        'department': 'Test Department',
    })
    return lab


# =============================================================================
# InstrumentFactory Tests
# =============================================================================

class TestInstrumentFactory:
    """Tests for InstrumentFactory."""
    
    def test_create_class_from_driver_measurement(self, sample_driver):
        """Test creating a measurement class from driver."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        # Clear cache first
        InstrumentFactory.invalidate_cache()
        
        instrument_class = InstrumentFactory.create_class_from_driver(sample_driver)
        
        assert instrument_class is not None
        assert instrument_class.__name__ == 'TestMeasurementInstrument'
        assert hasattr(instrument_class, '_driver_id')
        assert instrument_class._driver_id == 1
        
    def test_create_class_from_driver_movement(self, sample_movement_code):
        """Test creating a movement class from driver."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        driver = {
            'id': 2,
            'name': 'TestMovementInstrument',
            'source_code': sample_movement_code,
            'version': 1,
        }
        
        instrument_class = InstrumentFactory.create_class_from_driver(driver)
        
        assert instrument_class is not None
        assert instrument_class.__name__ == 'TestMovementInstrument'
    
    def test_create_instance(self, sample_driver):
        """Test creating an instrument instance from driver."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        instance = InstrumentFactory.create_instance(
            sample_driver,
            name="My Test Instrument"
        )
        
        assert instance is not None
        assert instance.name == "My Test Instrument"
        assert hasattr(instance, '_driver_id')
        
    def test_create_instance_with_adapter(self, sample_driver):
        """Test creating an instance with adapter address."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        instance = InstrumentFactory.create_instance(
            sample_driver,
            adapter="GPIB0::8::INSTR"
        )
        
        assert instance.adapter == "GPIB0::8::INSTR"
    
    def test_class_cache(self, sample_driver):
        """Test that class caching works correctly."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # First creation
        class1 = InstrumentFactory.create_class_from_driver(sample_driver)
        
        # Second creation should return cached class
        class2 = InstrumentFactory.create_class_from_driver(sample_driver)
        
        assert class1 is class2  # Same object (cached)
        
    def test_cache_invalidation_by_version(self, sample_driver):
        """Test that cache is invalidated when version changes."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # First creation
        class1 = InstrumentFactory.create_class_from_driver(sample_driver)
        
        # Update version
        sample_driver['version'] = 2
        
        # Should create new class due to version change
        class2 = InstrumentFactory.create_class_from_driver(sample_driver)
        
        # Different objects (cache invalidated by version change)
        # Note: They might be equal in content but cache should detect version change
        assert InstrumentFactory._version_cache.get(1) == 2
    
    def test_invalidate_cache_specific(self, sample_driver, sample_movement_code):
        """Test invalidating specific cache entry."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # Create two classes
        InstrumentFactory.create_class_from_driver(sample_driver)
        InstrumentFactory.create_class_from_driver({
            'id': 2,
            'name': 'TestMovementInstrument',
            'source_code': sample_movement_code,
            'version': 1,
        })
        
        assert 1 in InstrumentFactory._class_cache
        assert 2 in InstrumentFactory._class_cache
        
        # Invalidate only first
        InstrumentFactory.invalidate_cache(driver_id=1)
        
        assert 1 not in InstrumentFactory._class_cache
        assert 2 in InstrumentFactory._class_cache
    
    def test_invalidate_cache_all(self, sample_driver, sample_movement_code):
        """Test invalidating entire cache."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # Create two classes
        InstrumentFactory.create_class_from_driver(sample_driver)
        InstrumentFactory.create_class_from_driver({
            'id': 2,
            'name': 'TestMovementInstrument',
            'source_code': sample_movement_code,
            'version': 1,
        })
        
        # Invalidate all
        InstrumentFactory.invalidate_cache()
        
        assert len(InstrumentFactory._class_cache) == 0
        assert len(InstrumentFactory._version_cache) == 0
    
    def test_create_class_empty_driver(self):
        """Test error handling for empty driver."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        with pytest.raises(ValueError, match="driver cannot be empty"):
            InstrumentFactory.create_class_from_driver(None)
    
    def test_create_class_missing_name(self, sample_measurement_code):
        """Test error handling for missing name."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        driver = {
            'source_code': sample_measurement_code,
        }
        
        with pytest.raises(ValueError, match="must have 'name' field"):
            InstrumentFactory.create_class_from_driver(driver)
    
    def test_create_class_missing_source_code(self):
        """Test error handling for missing source code."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        driver = {
            'name': 'TestInstrument',
        }
        
        with pytest.raises(ValueError, match="must have 'source_code' field"):
            InstrumentFactory.create_class_from_driver(driver)
    
    def test_create_class_syntax_error(self, invalid_syntax_code):
        """Test error handling for syntax errors."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        driver = {
            'name': 'BrokenInstrument',
            'source_code': invalid_syntax_code,
        }
        
        with pytest.raises(SyntaxError):
            InstrumentFactory.create_class_from_driver(driver)
    
    def test_create_class_wrong_class_name(self, missing_class_code):
        """Test error handling for wrong class name."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        driver = {
            'name': 'ExpectedClassName',
            'source_code': missing_class_code,
        }
        
        with pytest.raises(ValueError, match="No class found in source code"):
            InstrumentFactory.create_class_from_driver(driver)


class TestInstrumentFactoryValidation:
    """Tests for InstrumentFactory.validate_source_code."""
    
    def test_validate_valid_code(self, sample_measurement_code):
        """Test validation of valid source code."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        result = InstrumentFactory.validate_source_code(
            sample_measurement_code,
            'TestMeasurementInstrument'
        )
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
        assert result['class_info'] is not None
        assert result['class_info']['name'] == 'TestMeasurementInstrument'
        assert result['class_info']['instrument_type'] == 'measurement'
    
    def test_validate_movement_code(self, sample_movement_code):
        """Test validation identifies movement type."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        result = InstrumentFactory.validate_source_code(
            sample_movement_code,
            'TestMovementInstrument'
        )
        
        assert result['valid'] is True
        assert result['class_info']['instrument_type'] == 'movement'
    
    def test_validate_syntax_error(self, invalid_syntax_code):
        """Test validation catches syntax errors."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        result = InstrumentFactory.validate_source_code(
            invalid_syntax_code,
            'BrokenInstrument'
        )
        
        assert result['valid'] is False
        assert len(result['errors']) > 0
        assert 'Syntax error' in result['errors'][0]
    
    def test_validate_wrong_class_name(self, sample_measurement_code):
        """Test validation catches missing class."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        result = InstrumentFactory.validate_source_code(
            sample_measurement_code,
            'WrongClassName'
        )
        
        assert result['valid'] is False
        assert 'WrongClassName' in result['errors'][0] or 'not found' in result['errors'][0].lower()
    
    def test_validate_no_base_class_warning(self):
        """Test validation warns about missing base class."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        code = '''
class StandaloneInstrument:
    def __init__(self):
        pass
'''
        result = InstrumentFactory.validate_source_code(code, 'StandaloneInstrument')
        
        assert result['valid'] is True  # Still valid, just warning
        assert len(result['warnings']) > 0
        assert 'does not inherit' in result['warnings'][0]


class TestGetComputerInfo:
    """Tests for get_computer_info utility."""
    
    def test_get_computer_info_returns_dict(self):
        """Test that get_computer_info returns expected keys."""
        from pybirch.Instruments.factory import get_computer_info
        
        info = get_computer_info()
        
        assert isinstance(info, dict)
        assert 'computer_name' in info
        assert 'computer_id' in info
        assert 'username' in info
    
    def test_get_computer_info_hostname_not_empty(self):
        """Test that hostname is populated."""
        from pybirch.Instruments.factory import get_computer_info
        
        info = get_computer_info()
        
        assert info['computer_name']  # Not empty
        assert isinstance(info['computer_name'], str)
    
    def test_get_computer_info_computer_id_not_empty(self):
        """Test that computer_id (MAC) is populated."""
        from pybirch.Instruments.factory import get_computer_info
        
        info = get_computer_info()
        
        assert info['computer_id']  # Not empty
        assert isinstance(info['computer_id'], str)


# =============================================================================
# DatabaseService Instrument driver Tests
# =============================================================================

class TestDatabaseServiceDrivers:
    """Tests for DatabaseService instrument driver CRUD."""
    
    def test_create_driver(self, db_service, sample_measurement_code):
        """Test creating an instrument driver."""
        data = {
            'name': 'MyTestInstrument',
            'display_name': 'My Test Instrument',
            'description': 'A test instrument for unit tests',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'is_public': True,
            'created_by': 'test_user',
        }
        
        result = db_service.create_driver(data)
        
        assert result is not None
        assert result['id'] is not None
        assert result['name'] == 'MyTestInstrument'
        assert result['display_name'] == 'My Test Instrument'
        assert result['version'] == 1
    
    def test_get_driver(self, db_service, sample_measurement_code):
        """Test retrieving an instrument driver."""
        # Create first
        created = db_service.create_driver({
            'name': 'GetTestInstrument',
            'display_name': 'Get Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Retrieve
        result = db_service.get_driver(created['id'])
        
        assert result is not None
        assert result['id'] == created['id']
        assert result['name'] == 'GetTestInstrument'
    
    def test_get_driver_by_name(self, db_service, sample_measurement_code):
        """Test retrieving driver by name."""
        db_service.create_driver({
            'name': 'NamedInstrument',
            'display_name': 'Named Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        result = db_service.get_driver_by_name('NamedInstrument')
        
        assert result is not None
        assert result['name'] == 'NamedInstrument'
    
    def test_get_drivers_list(self, db_service, sample_measurement_code, sample_movement_code):
        """Test retrieving list of drivers."""
        # Create multiple
        db_service.create_driver({
            'name': 'ListInstrument1',
            'display_name': 'List Test 1',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        db_service.create_driver({
            'name': 'ListInstrument2',
            'display_name': 'List Test 2',
            'instrument_type': 'movement',
            'source_code': sample_movement_code,
            'base_class': 'Movement',
        })
        
        # Get all
        results = db_service.get_drivers()
        
        assert len(results) >= 2
    
    def test_get_drivers_filter_by_type(self, db_service, sample_measurement_code, sample_movement_code):
        """Test filtering drivers by type."""
        db_service.create_driver({
            'name': 'FilterMeasurement',
            'display_name': 'Filter Meas',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        db_service.create_driver({
            'name': 'FilterMovement',
            'display_name': 'Filter Mov',
            'instrument_type': 'movement',
            'source_code': sample_movement_code,
            'base_class': 'Movement',
        })
        
        # Filter by type
        measurements = db_service.get_drivers(instrument_type='measurement')
        movements = db_service.get_drivers(instrument_type='movement')
        
        measurement_names = [d['name'] for d in measurements]
        movement_names = [d['name'] for d in movements]
        
        assert 'FilterMeasurement' in measurement_names
        assert 'FilterMovement' not in measurement_names
        assert 'FilterMovement' in movement_names
    
    def test_update_driver(self, db_service, sample_measurement_code):
        """Test updating an instrument driver."""
        # Create
        created = db_service.create_driver({
            'name': 'UpdateInstrument',
            'display_name': 'Original Name',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Update without source change - version stays the same
        updated = db_service.update_driver(
            created['id'],
            {'display_name': 'Updated Name', 'description': 'New description'},
            change_summary='Updated display name',
            updated_by='test_user'
        )
        
        assert updated['display_name'] == 'Updated Name'
        assert updated['description'] == 'New description'
        assert updated['version'] == 1  # Version NOT incremented without source change
    
    def test_update_driver_source_code(self, db_service, sample_measurement_code):
        """Test that updating source code increments version."""
        # Create
        created = db_service.create_driver({
            'name': 'VersionUpdateInstrument',
            'display_name': 'Version Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Update with source code change
        new_source = sample_measurement_code + "\n# Modified version"
        updated = db_service.update_driver(
            created['id'],
            {'source_code': new_source},
            change_summary='Changed source code',
        )
        
        assert updated['version'] == 2  # Version incremented on source change
    
    def test_delete_driver(self, db_service, sample_measurement_code):
        """Test deleting an instrument driver."""
        # Create
        created = db_service.create_driver({
            'name': 'DeleteInstrument',
            'display_name': 'Delete Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Delete
        result = db_service.delete_driver(created['id'])
        
        assert result is True
        
        # Verify deleted
        retrieved = db_service.get_driver(created['id'])
        assert retrieved is None
    
    def test_get_driver_versions(self, db_service, sample_measurement_code):
        """Test retrieving version history."""
        # Create
        created = db_service.create_driver({
            'name': 'VersionedInstrument',
            'display_name': 'Version Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Update source code to create new versions
        db_service.update_driver(
            created['id'],
            {'source_code': sample_measurement_code + '\n# Version 2'},
            change_summary='First update'
        )
        db_service.update_driver(
            created['id'],
            {'source_code': sample_measurement_code + '\n# Version 3'},
            change_summary='Second update'
        )
        
        # Get versions - should have initial + 2 updates = 3 versions
        versions = db_service.get_driver_versions(created['id'])
        
        assert len(versions) >= 3


# =============================================================================
# DatabaseService Computer Binding Tests
# =============================================================================

class TestDatabaseServiceBindings:
    """Tests for DatabaseService computer binding CRUD."""
    
    @pytest.fixture
    def instrument_for_binding(self, db_service, sample_measurement_code, sample_lab):
        """Create an instrument to bind to."""
        # Create driver first
        driver = db_service.create_driver({
            'name': 'BindingTestInstrument',
            'display_name': 'Binding Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Create instrument instance
        instrument = db_service.create_instrument_for_driver(
            driver['id'],
            {
                'name': 'Test Device #1',
                'adapter': 'GPIB0::8::INSTR',
                'serial_number': 'SN12345',
                'lab_id': sample_lab['id'],
            }
        )
        
        return instrument
    
    def test_bind_instrument_to_computer(self, db_service, instrument_for_binding):
        """Test creating a computer binding."""
        result = db_service.bind_instrument_to_computer(
            instrument_id=instrument_for_binding['id'],
            computer_name='TESTPC-01',
            computer_id='123456789012',
            username='testuser',
            adapter='GPIB0::8::INSTR',
            adapter_type='GPIB',
            is_primary=True,
        )
        
        assert result is not None
        assert result['id'] is not None
        assert result['computer_name'] == 'TESTPC-01'
        assert result['is_primary'] is True
    
    def test_get_computer_bindings_by_computer(self, db_service, instrument_for_binding):
        """Test retrieving bindings by computer name."""
        # Create binding
        db_service.bind_instrument_to_computer(
            instrument_id=instrument_for_binding['id'],
            computer_name='LABPC-01',
            is_primary=True,
        )
        
        # Get bindings
        bindings = db_service.get_computer_bindings(computer_name='LABPC-01')
        
        assert len(bindings) >= 1
        assert bindings[0]['computer_name'] == 'LABPC-01'
    
    def test_get_computer_bindings_by_instrument(self, db_service, instrument_for_binding):
        """Test retrieving bindings by instrument ID."""
        # Create bindings to multiple computers
        db_service.bind_instrument_to_computer(
            instrument_id=instrument_for_binding['id'],
            computer_name='PC-A',
            is_primary=True,
        )
        db_service.bind_instrument_to_computer(
            instrument_id=instrument_for_binding['id'],
            computer_name='PC-B',
            is_primary=False,
        )
        
        # Get bindings for instrument
        bindings = db_service.get_computer_bindings(
            instrument_id=instrument_for_binding['id']
        )
        
        assert len(bindings) >= 2
    
    def test_delete_computer_binding(self, db_service, instrument_for_binding):
        """Test deleting a computer binding."""
        # Create binding
        binding = db_service.bind_instrument_to_computer(
            instrument_id=instrument_for_binding['id'],
            computer_name='DELETE-PC',
            is_primary=True,
        )
        
        # Delete
        result = db_service.delete_computer_binding(binding['id'])
        
        assert result is True
    
    def test_get_driver_ids_for_computer(self, db_service, sample_measurement_code, sample_lab):
        """Test getting driver IDs bound to a computer."""
        # Create driver
        driver = db_service.create_driver({
            'name': 'ComputerFilterInstrument',
            'display_name': 'Computer Filter Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'is_public': False,  # Not public - should only appear if bound
        })
        
        # Create instrument
        instrument = db_service.create_instrument_for_driver(
            driver['id'],
            {'name': 'Filter Device', 'lab_id': sample_lab['id']}
        )
        
        # Initially, computer should not see this driver
        ids_before = db_service.get_driver_ids_for_computer(
            computer_name='FILTER-PC',
            include_public=False
        )
        assert driver['id'] not in ids_before
        
        # Bind to computer
        db_service.bind_instrument_to_computer(
            instrument_id=instrument['id'],
            computer_name='FILTER-PC',
        )
        
        # Now computer should see the driver
        ids_after = db_service.get_driver_ids_for_computer(
            computer_name='FILTER-PC',
            include_public=False
        )
        assert driver['id'] in ids_after
    
    def test_get_driver_ids_includes_public(self, db_service, sample_measurement_code):
        """Test that public drivers are included."""
        # Create public driver
        public_def = db_service.create_driver({
            'name': 'PublicInstrument',
            'display_name': 'Public Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'is_public': True,
        })
        
        # Get IDs for any computer with include_public=True
        ids = db_service.get_driver_ids_for_computer(
            computer_name='ANY-PC',
            include_public=True
        )
        
        assert public_def['id'] in ids


# =============================================================================
# DatabaseService Instrument Instance Tests
# =============================================================================

class TestDatabaseServiceInstances:
    """Tests for DatabaseService instrument instance operations."""
    
    def test_create_instrument_for_driver(self, db_service, sample_measurement_code, sample_lab):
        """Test creating an instrument instance for a driver."""
        # Create driver
        driver = db_service.create_driver({
            'name': 'InstanceTestInstrument',
            'display_name': 'Instance Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'manufacturer': 'TestCorp',
        })
        
        # Create instance
        instrument = db_service.create_instrument_for_driver(
            driver['id'],
            {
                'name': 'Instance #1',
                'adapter': 'GPIB0::4::INSTR',
                'serial_number': 'ABC123',
                'lab_id': sample_lab['id'],
            }
        )
        
        assert instrument is not None
        assert instrument['name'] == 'Instance #1'
        assert instrument['driver_id'] == driver['id']
        assert instrument['pybirch_class'] == 'InstanceTestInstrument'
        assert instrument['manufacturer'] == 'TestCorp'  # Inherited from driver
    
    def test_get_instruments_by_driver(self, db_service, sample_measurement_code, sample_lab):
        """Test getting all instruments for a driver."""
        # Create driver
        driver = db_service.create_driver({
            'name': 'MultiInstanceInstrument',
            'display_name': 'Multi Instance Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Create multiple instances
        db_service.create_instrument_for_driver(
            driver['id'],
            {'name': 'Device A', 'adapter': 'GPIB0::1::INSTR', 'lab_id': sample_lab['id']}
        )
        db_service.create_instrument_for_driver(
            driver['id'],
            {'name': 'Device B', 'adapter': 'GPIB0::2::INSTR', 'lab_id': sample_lab['id']}
        )
        
        # Get all instruments for this driver
        instruments = db_service.get_instruments_by_driver(
            driver['id'],
            include_bindings=False
        )
        
        assert len(instruments) == 2
        names = [i['name'] for i in instruments]
        assert 'Device A' in names
        assert 'Device B' in names
    
    def test_get_instruments_by_driver_with_bindings(self, db_service, sample_measurement_code, sample_lab):
        """Test getting instruments with their bindings."""
        # Create driver
        driver = db_service.create_driver({
            'name': 'BindingListInstrument',
            'display_name': 'Binding List Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Create instrument
        instrument = db_service.create_instrument_for_driver(
            driver['id'],
            {'name': 'Bound Device', 'lab_id': sample_lab['id']}
        )
        
        # Add bindings
        db_service.bind_instrument_to_computer(
            instrument_id=instrument['id'],
            computer_name='BINDING-PC-1',
        )
        db_service.bind_instrument_to_computer(
            instrument_id=instrument['id'],
            computer_name='BINDING-PC-2',
        )
        
        # Get instruments with bindings
        instruments = db_service.get_instruments_by_driver(
            driver['id'],
            include_bindings=True
        )
        
        assert len(instruments) == 1
        assert 'computer_bindings' in instruments[0]
        assert len(instruments[0]['computer_bindings']) == 2


# =============================================================================
# Integration Tests
# =============================================================================

class TestDriverIntegration:
    """Integration tests for the full workflow."""
    
    def test_full_workflow(self, db_service, sample_measurement_code, sample_lab):
        """Test complete workflow: create driver -> create instance -> bind -> discover."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # 1. Create driver (name must match class name in source code)
        driver = db_service.create_driver({
            'name': 'TestMeasurementInstrument',  # Must match class in sample_measurement_code
            'display_name': 'Workflow Test',
            'description': 'Integration test instrument',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'is_public': False,
        })
        
        assert driver['id'] is not None
        
        # 2. Create instrument instance
        instrument = db_service.create_instrument_for_driver(
            driver['id'],
            {
                'name': 'Lab Voltmeter #1',
                'serial_number': 'WF-001',
                'lab_id': sample_lab['id'],
            }
        )
        
        assert instrument['driver_id'] == driver['id']
        
        # 3. Bind to computer (adapter is stored on the binding, not the instrument)
        binding = db_service.bind_instrument_to_computer(
            instrument_id=instrument['id'],
            computer_name='WORKFLOW-PC',
            adapter='GPIB0::8::INSTR',
            is_primary=True,
        )
        
        assert binding['computer_name'] == 'WORKFLOW-PC'
        assert binding['adapter'] == 'GPIB0::8::INSTR'
        
        # 4. Verify discovery
        driver_ids = db_service.get_driver_ids_for_computer(
            computer_name='WORKFLOW-PC',
            include_public=False
        )
        
        assert driver['id'] in driver_ids
        
        # 5. Create class from driver
        driver_data = db_service.get_driver(driver['id'])
        instrument_class = InstrumentFactory.create_class_from_driver(driver_data)
        
        assert instrument_class.__name__ == 'TestMeasurementInstrument'
        
        # 6. Create instance using adapter from binding
        instance = InstrumentFactory.create_instance(
            driver_data,
            adapter=binding['adapter'],
            name=instrument['name']
        )
        
        assert instance.name == 'Lab Voltmeter #1'
        assert instance.adapter == 'GPIB0::8::INSTR'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

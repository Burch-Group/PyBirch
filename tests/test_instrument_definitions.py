"""
Unit Tests for Instrument Definitions Feature

Tests cover:
- InstrumentFactory: dynamic class creation, validation, caching
- DatabaseService: CRUD for instrument definitions and computer bindings
- get_computer_info: computer identification utility

Run with: pytest tests/test_instrument_definitions.py -v
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
def sample_definition(sample_measurement_code):
    """A sample instrument definition dictionary."""
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


# =============================================================================
# InstrumentFactory Tests
# =============================================================================

class TestInstrumentFactory:
    """Tests for InstrumentFactory."""
    
    def test_create_class_from_definition_measurement(self, sample_definition):
        """Test creating a measurement class from definition."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        # Clear cache first
        InstrumentFactory.invalidate_cache()
        
        instrument_class = InstrumentFactory.create_class_from_definition(sample_definition)
        
        assert instrument_class is not None
        assert instrument_class.__name__ == 'TestMeasurementInstrument'
        assert hasattr(instrument_class, '_definition_id')
        assert instrument_class._definition_id == 1
        
    def test_create_class_from_definition_movement(self, sample_movement_code):
        """Test creating a movement class from definition."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        definition = {
            'id': 2,
            'name': 'TestMovementInstrument',
            'source_code': sample_movement_code,
            'version': 1,
        }
        
        instrument_class = InstrumentFactory.create_class_from_definition(definition)
        
        assert instrument_class is not None
        assert instrument_class.__name__ == 'TestMovementInstrument'
    
    def test_create_instance(self, sample_definition):
        """Test creating an instrument instance from definition."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        instance = InstrumentFactory.create_instance(
            sample_definition,
            name="My Test Instrument"
        )
        
        assert instance is not None
        assert instance.name == "My Test Instrument"
        assert hasattr(instance, '_definition_id')
        
    def test_create_instance_with_adapter(self, sample_definition):
        """Test creating an instance with adapter address."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        instance = InstrumentFactory.create_instance(
            sample_definition,
            adapter="GPIB0::8::INSTR"
        )
        
        assert instance.adapter == "GPIB0::8::INSTR"
    
    def test_class_cache(self, sample_definition):
        """Test that class caching works correctly."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # First creation
        class1 = InstrumentFactory.create_class_from_definition(sample_definition)
        
        # Second creation should return cached class
        class2 = InstrumentFactory.create_class_from_definition(sample_definition)
        
        assert class1 is class2  # Same object (cached)
        
    def test_cache_invalidation_by_version(self, sample_definition):
        """Test that cache is invalidated when version changes."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # First creation
        class1 = InstrumentFactory.create_class_from_definition(sample_definition)
        
        # Update version
        sample_definition['version'] = 2
        
        # Should create new class due to version change
        class2 = InstrumentFactory.create_class_from_definition(sample_definition)
        
        # Different objects (cache invalidated by version change)
        # Note: They might be equal in content but cache should detect version change
        assert InstrumentFactory._version_cache.get(1) == 2
    
    def test_invalidate_cache_specific(self, sample_definition, sample_movement_code):
        """Test invalidating specific cache entry."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # Create two classes
        InstrumentFactory.create_class_from_definition(sample_definition)
        InstrumentFactory.create_class_from_definition({
            'id': 2,
            'name': 'TestMovementInstrument',
            'source_code': sample_movement_code,
            'version': 1,
        })
        
        assert 1 in InstrumentFactory._class_cache
        assert 2 in InstrumentFactory._class_cache
        
        # Invalidate only first
        InstrumentFactory.invalidate_cache(definition_id=1)
        
        assert 1 not in InstrumentFactory._class_cache
        assert 2 in InstrumentFactory._class_cache
    
    def test_invalidate_cache_all(self, sample_definition, sample_movement_code):
        """Test invalidating entire cache."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # Create two classes
        InstrumentFactory.create_class_from_definition(sample_definition)
        InstrumentFactory.create_class_from_definition({
            'id': 2,
            'name': 'TestMovementInstrument',
            'source_code': sample_movement_code,
            'version': 1,
        })
        
        # Invalidate all
        InstrumentFactory.invalidate_cache()
        
        assert len(InstrumentFactory._class_cache) == 0
        assert len(InstrumentFactory._version_cache) == 0
    
    def test_create_class_empty_definition(self):
        """Test error handling for empty definition."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        with pytest.raises(ValueError, match="Definition cannot be empty"):
            InstrumentFactory.create_class_from_definition(None)
    
    def test_create_class_missing_name(self, sample_measurement_code):
        """Test error handling for missing name."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        definition = {
            'source_code': sample_measurement_code,
        }
        
        with pytest.raises(ValueError, match="must have 'name' field"):
            InstrumentFactory.create_class_from_definition(definition)
    
    def test_create_class_missing_source_code(self):
        """Test error handling for missing source code."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        definition = {
            'name': 'TestInstrument',
        }
        
        with pytest.raises(ValueError, match="must have 'source_code' field"):
            InstrumentFactory.create_class_from_definition(definition)
    
    def test_create_class_syntax_error(self, invalid_syntax_code):
        """Test error handling for syntax errors."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        definition = {
            'name': 'BrokenInstrument',
            'source_code': invalid_syntax_code,
        }
        
        with pytest.raises(SyntaxError):
            InstrumentFactory.create_class_from_definition(definition)
    
    def test_create_class_wrong_class_name(self, missing_class_code):
        """Test error handling for wrong class name."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        definition = {
            'name': 'ExpectedClassName',
            'source_code': missing_class_code,
        }
        
        with pytest.raises(ValueError, match="No class found in source code"):
            InstrumentFactory.create_class_from_definition(definition)


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
# DatabaseService Instrument Definition Tests
# =============================================================================

class TestDatabaseServiceDefinitions:
    """Tests for DatabaseService instrument definition CRUD."""
    
    def test_create_instrument_definition(self, db_service, sample_measurement_code):
        """Test creating an instrument definition."""
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
        
        result = db_service.create_instrument_definition(data)
        
        assert result is not None
        assert result['id'] is not None
        assert result['name'] == 'MyTestInstrument'
        assert result['display_name'] == 'My Test Instrument'
        assert result['version'] == 1
    
    def test_get_instrument_definition(self, db_service, sample_measurement_code):
        """Test retrieving an instrument definition."""
        # Create first
        created = db_service.create_instrument_definition({
            'name': 'GetTestInstrument',
            'display_name': 'Get Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Retrieve
        result = db_service.get_instrument_definition(created['id'])
        
        assert result is not None
        assert result['id'] == created['id']
        assert result['name'] == 'GetTestInstrument'
    
    def test_get_instrument_definition_by_name(self, db_service, sample_measurement_code):
        """Test retrieving definition by name."""
        db_service.create_instrument_definition({
            'name': 'NamedInstrument',
            'display_name': 'Named Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        result = db_service.get_instrument_definition_by_name('NamedInstrument')
        
        assert result is not None
        assert result['name'] == 'NamedInstrument'
    
    def test_get_instrument_definitions_list(self, db_service, sample_measurement_code, sample_movement_code):
        """Test retrieving list of definitions."""
        # Create multiple
        db_service.create_instrument_definition({
            'name': 'ListInstrument1',
            'display_name': 'List Test 1',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        db_service.create_instrument_definition({
            'name': 'ListInstrument2',
            'display_name': 'List Test 2',
            'instrument_type': 'movement',
            'source_code': sample_movement_code,
            'base_class': 'Movement',
        })
        
        # Get all
        results = db_service.get_instrument_definitions()
        
        assert len(results) >= 2
    
    def test_get_instrument_definitions_filter_by_type(self, db_service, sample_measurement_code, sample_movement_code):
        """Test filtering definitions by type."""
        db_service.create_instrument_definition({
            'name': 'FilterMeasurement',
            'display_name': 'Filter Meas',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        db_service.create_instrument_definition({
            'name': 'FilterMovement',
            'display_name': 'Filter Mov',
            'instrument_type': 'movement',
            'source_code': sample_movement_code,
            'base_class': 'Movement',
        })
        
        # Filter by type
        measurements = db_service.get_instrument_definitions(instrument_type='measurement')
        movements = db_service.get_instrument_definitions(instrument_type='movement')
        
        measurement_names = [d['name'] for d in measurements]
        movement_names = [d['name'] for d in movements]
        
        assert 'FilterMeasurement' in measurement_names
        assert 'FilterMovement' not in measurement_names
        assert 'FilterMovement' in movement_names
    
    def test_update_instrument_definition(self, db_service, sample_measurement_code):
        """Test updating an instrument definition."""
        # Create
        created = db_service.create_instrument_definition({
            'name': 'UpdateInstrument',
            'display_name': 'Original Name',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Update without source change - version stays the same
        updated = db_service.update_instrument_definition(
            created['id'],
            {'display_name': 'Updated Name', 'description': 'New description'},
            change_summary='Updated display name',
            updated_by='test_user'
        )
        
        assert updated['display_name'] == 'Updated Name'
        assert updated['description'] == 'New description'
        assert updated['version'] == 1  # Version NOT incremented without source change
    
    def test_update_instrument_definition_source_code(self, db_service, sample_measurement_code):
        """Test that updating source code increments version."""
        # Create
        created = db_service.create_instrument_definition({
            'name': 'VersionUpdateInstrument',
            'display_name': 'Version Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Update with source code change
        new_source = sample_measurement_code + "\n# Modified version"
        updated = db_service.update_instrument_definition(
            created['id'],
            {'source_code': new_source},
            change_summary='Changed source code',
        )
        
        assert updated['version'] == 2  # Version incremented on source change
    
    def test_delete_instrument_definition(self, db_service, sample_measurement_code):
        """Test deleting an instrument definition."""
        # Create
        created = db_service.create_instrument_definition({
            'name': 'DeleteInstrument',
            'display_name': 'Delete Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Delete
        result = db_service.delete_instrument_definition(created['id'])
        
        assert result is True
        
        # Verify deleted
        retrieved = db_service.get_instrument_definition(created['id'])
        assert retrieved is None
    
    def test_get_instrument_definition_versions(self, db_service, sample_measurement_code):
        """Test retrieving version history."""
        # Create
        created = db_service.create_instrument_definition({
            'name': 'VersionedInstrument',
            'display_name': 'Version Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Update source code to create new versions
        db_service.update_instrument_definition(
            created['id'],
            {'source_code': sample_measurement_code + '\n# Version 2'},
            change_summary='First update'
        )
        db_service.update_instrument_definition(
            created['id'],
            {'source_code': sample_measurement_code + '\n# Version 3'},
            change_summary='Second update'
        )
        
        # Get versions - should have initial + 2 updates = 3 versions
        versions = db_service.get_instrument_definition_versions(created['id'])
        
        assert len(versions) >= 3


# =============================================================================
# DatabaseService Computer Binding Tests
# =============================================================================

class TestDatabaseServiceBindings:
    """Tests for DatabaseService computer binding CRUD."""
    
    @pytest.fixture
    def instrument_for_binding(self, db_service, sample_measurement_code):
        """Create an instrument to bind to."""
        # Create definition first
        definition = db_service.create_instrument_definition({
            'name': 'BindingTestInstrument',
            'display_name': 'Binding Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Create instrument instance
        instrument = db_service.create_instrument_for_definition(
            definition['id'],
            {
                'name': 'Test Device #1',
                'adapter': 'GPIB0::8::INSTR',
                'serial_number': 'SN12345',
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
    
    def test_get_definition_ids_for_computer(self, db_service, sample_measurement_code):
        """Test getting definition IDs bound to a computer."""
        # Create definition
        definition = db_service.create_instrument_definition({
            'name': 'ComputerFilterInstrument',
            'display_name': 'Computer Filter Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'is_public': False,  # Not public - should only appear if bound
        })
        
        # Create instrument
        instrument = db_service.create_instrument_for_definition(
            definition['id'],
            {'name': 'Filter Device'}
        )
        
        # Initially, computer should not see this definition
        ids_before = db_service.get_definition_ids_for_computer(
            computer_name='FILTER-PC',
            include_public=False
        )
        assert definition['id'] not in ids_before
        
        # Bind to computer
        db_service.bind_instrument_to_computer(
            instrument_id=instrument['id'],
            computer_name='FILTER-PC',
        )
        
        # Now computer should see the definition
        ids_after = db_service.get_definition_ids_for_computer(
            computer_name='FILTER-PC',
            include_public=False
        )
        assert definition['id'] in ids_after
    
    def test_get_definition_ids_includes_public(self, db_service, sample_measurement_code):
        """Test that public definitions are included."""
        # Create public definition
        public_def = db_service.create_instrument_definition({
            'name': 'PublicInstrument',
            'display_name': 'Public Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'is_public': True,
        })
        
        # Get IDs for any computer with include_public=True
        ids = db_service.get_definition_ids_for_computer(
            computer_name='ANY-PC',
            include_public=True
        )
        
        assert public_def['id'] in ids


# =============================================================================
# DatabaseService Instrument Instance Tests
# =============================================================================

class TestDatabaseServiceInstances:
    """Tests for DatabaseService instrument instance operations."""
    
    def test_create_instrument_for_definition(self, db_service, sample_measurement_code):
        """Test creating an instrument instance for a definition."""
        # Create definition
        definition = db_service.create_instrument_definition({
            'name': 'InstanceTestInstrument',
            'display_name': 'Instance Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'manufacturer': 'TestCorp',
        })
        
        # Create instance
        instrument = db_service.create_instrument_for_definition(
            definition['id'],
            {
                'name': 'Instance #1',
                'adapter': 'GPIB0::4::INSTR',
                'serial_number': 'ABC123',
                'location': 'Room 101',
            }
        )
        
        assert instrument is not None
        assert instrument['name'] == 'Instance #1'
        assert instrument['definition_id'] == definition['id']
        assert instrument['pybirch_class'] == 'InstanceTestInstrument'
        assert instrument['manufacturer'] == 'TestCorp'  # Inherited from definition
    
    def test_get_instruments_by_definition(self, db_service, sample_measurement_code):
        """Test getting all instruments for a definition."""
        # Create definition
        definition = db_service.create_instrument_definition({
            'name': 'MultiInstanceInstrument',
            'display_name': 'Multi Instance Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Create multiple instances
        db_service.create_instrument_for_definition(
            definition['id'],
            {'name': 'Device A', 'adapter': 'GPIB0::1::INSTR'}
        )
        db_service.create_instrument_for_definition(
            definition['id'],
            {'name': 'Device B', 'adapter': 'GPIB0::2::INSTR'}
        )
        
        # Get all instruments for this definition
        instruments = db_service.get_instruments_by_definition(
            definition['id'],
            include_bindings=False
        )
        
        assert len(instruments) == 2
        names = [i['name'] for i in instruments]
        assert 'Device A' in names
        assert 'Device B' in names
    
    def test_get_instruments_by_definition_with_bindings(self, db_service, sample_measurement_code):
        """Test getting instruments with their bindings."""
        # Create definition
        definition = db_service.create_instrument_definition({
            'name': 'BindingListInstrument',
            'display_name': 'Binding List Test',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
        })
        
        # Create instrument
        instrument = db_service.create_instrument_for_definition(
            definition['id'],
            {'name': 'Bound Device'}
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
        instruments = db_service.get_instruments_by_definition(
            definition['id'],
            include_bindings=True
        )
        
        assert len(instruments) == 1
        assert 'computer_bindings' in instruments[0]
        assert len(instruments[0]['computer_bindings']) == 2


# =============================================================================
# Integration Tests
# =============================================================================

class TestInstrumentDefinitionIntegration:
    """Integration tests for the full workflow."""
    
    def test_full_workflow(self, db_service, sample_measurement_code):
        """Test complete workflow: create definition -> create instance -> bind -> discover."""
        from pybirch.Instruments.factory import InstrumentFactory
        
        InstrumentFactory.invalidate_cache()
        
        # 1. Create definition (name must match class name in source code)
        definition = db_service.create_instrument_definition({
            'name': 'TestMeasurementInstrument',  # Must match class in sample_measurement_code
            'display_name': 'Workflow Test',
            'description': 'Integration test instrument',
            'instrument_type': 'measurement',
            'source_code': sample_measurement_code,
            'base_class': 'Measurement',
            'is_public': False,
        })
        
        assert definition['id'] is not None
        
        # 2. Create instrument instance
        instrument = db_service.create_instrument_for_definition(
            definition['id'],
            {
                'name': 'Lab Voltmeter #1',
                'adapter': 'GPIB0::8::INSTR',
                'serial_number': 'WF-001',
            }
        )
        
        assert instrument['definition_id'] == definition['id']
        
        # 3. Bind to computer
        binding = db_service.bind_instrument_to_computer(
            instrument_id=instrument['id'],
            computer_name='WORKFLOW-PC',
            adapter='GPIB0::8::INSTR',
            is_primary=True,
        )
        
        assert binding['computer_name'] == 'WORKFLOW-PC'
        
        # 4. Verify discovery
        definition_ids = db_service.get_definition_ids_for_computer(
            computer_name='WORKFLOW-PC',
            include_public=False
        )
        
        assert definition['id'] in definition_ids
        
        # 5. Create class from definition
        definition_data = db_service.get_instrument_definition(definition['id'])
        instrument_class = InstrumentFactory.create_class_from_definition(definition_data)
        
        assert instrument_class.__name__ == 'TestMeasurementInstrument'
        
        # 6. Create instance
        instance = InstrumentFactory.create_instance(
            definition_data,
            adapter=instrument['adapter'],
            name=instrument['name']
        )
        
        assert instance.name == 'Lab Voltmeter #1'
        assert instance.adapter == 'GPIB0::8::INSTR'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

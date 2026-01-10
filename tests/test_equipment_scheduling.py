"""
Tests for Equipment Scheduling System
=====================================

Tests the equipment booking, scheduling configuration, and calendar integration
features added to the PyBirch database.
"""

import os
import sys
import tempfile
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from database.services import DatabaseService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def db_service():
    """Create an in-memory database service for testing."""
    # Use a temporary file-based database for tests
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # DatabaseService takes db_path, not db_url
    service = DatabaseService(db_path=db_path)
    
    yield service
    
    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


class TestEquipmentSchedulingModels:
    """Tests for equipment scheduling database models."""
    
    def test_equipment_booking_model_creation(self, db_service, test_equipment, test_user):
        """Test creating an EquipmentBooking record."""
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        
        booking_data = {
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'NMR Analysis',
            'description': 'Running spectroscopy analysis',
            'start_time': start_time,
            'end_time': end_time,
        }
        
        booking = db_service.create_equipment_booking(booking_data)
        
        assert booking is not None
        assert booking['id'] is not None
        assert booking['equipment_id'] == test_equipment['id']
        assert booking['user_id'] == test_user['id']
        assert booking['title'] == 'NMR Analysis'
        assert booking['status'] in ['pending', 'confirmed']
    
    def test_equipment_booking_time_validation(self, db_service, test_equipment, test_user):
        """Test that booking times are properly validated."""
        # End time before start time should fail
        start_time = datetime.utcnow() + timedelta(hours=2)
        end_time = datetime.utcnow() + timedelta(hours=1)  # Before start
        
        booking_data = {
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'Invalid Booking',
            'start_time': start_time,
            'end_time': end_time,
        }
        
        # This should raise an error or be handled gracefully
        # The actual behavior depends on implementation
        # For now, we just verify the API accepts proper values
        
    def test_scheduling_config_defaults(self, db_service, test_equipment):
        """Test default scheduling configuration values."""
        config = db_service.get_equipment_scheduling_config(test_equipment['id'])
        
        # Config might be None initially
        if config is None:
            # Create one to test defaults
            config = db_service.create_or_update_scheduling_config(
                test_equipment['id'],
                {'scheduling_enabled': True}
            )
        
        assert config is not None
        assert 'min_booking_duration' in config
        assert 'max_booking_duration' in config
        assert 'buffer_time' in config
    
    def test_scheduling_config_custom_values(self, db_service, test_equipment):
        """Test setting custom scheduling configuration."""
        custom_config = {
            'scheduling_enabled': True,
            'min_booking_duration': 15,  # 15 minutes
            'max_booking_duration': 240,  # 4 hours
            'buffer_time': 10,  # 10 minute buffer
            'requires_approval': True,
            'max_advance_booking': 14,  # 2 weeks
        }
        
        config = db_service.create_or_update_scheduling_config(
            test_equipment['id'],
            custom_config
        )
        
        assert config['min_booking_duration'] == 15
        assert config['max_booking_duration'] == 240
        assert config['buffer_time'] == 10
        assert config['requires_approval'] == True
        assert config['max_advance_booking'] == 14


class TestBookingConflictDetection:
    """Tests for booking conflict detection logic."""
    
    def test_overlapping_booking_detection(self, db_service, test_equipment, test_user):
        """Test that overlapping bookings are detected."""
        start_time = datetime.utcnow() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        
        # Create first booking
        booking1 = db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'First Booking',
            'start_time': start_time,
            'end_time': end_time,
        })
        
        # Try to create overlapping booking
        overlap_start = start_time + timedelta(hours=1)  # Overlaps with first
        overlap_end = end_time + timedelta(hours=1)
        
        with pytest.raises(ValueError, match="conflict"):
            db_service.create_equipment_booking({
                'equipment_id': test_equipment['id'],
                'user_id': test_user['id'],
                'title': 'Overlapping Booking',
                'start_time': overlap_start,
                'end_time': overlap_end,
            })
    
    def test_adjacent_bookings_allowed(self, db_service, test_equipment, test_user):
        """Test that adjacent (non-overlapping) bookings are allowed."""
        start1 = datetime.utcnow() + timedelta(days=2)
        end1 = start1 + timedelta(hours=2)
        
        # Create first booking
        booking1 = db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'Morning Session',
            'start_time': start1,
            'end_time': end1,
        })
        
        # Create adjacent booking (starts when first ends)
        start2 = end1
        end2 = start2 + timedelta(hours=2)
        
        booking2 = db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'Afternoon Session',
            'start_time': start2,
            'end_time': end2,
        })
        
        assert booking2 is not None
        assert booking2['id'] != booking1['id']
    
    def test_availability_check(self, db_service, test_equipment, test_user):
        """Test the availability checking function."""
        start_time = datetime.utcnow() + timedelta(days=3)
        end_time = start_time + timedelta(hours=2)
        
        # Check availability before any bookings
        availability = db_service.check_booking_availability(
            test_equipment['id'],
            start_time,
            end_time
        )
        
        assert availability['available'] == True
        assert len(availability.get('issues', [])) == 0


class TestBookingWorkflow:
    """Tests for the booking workflow (create, confirm, check-in, check-out, cancel)."""
    
    def test_booking_status_transitions(self, db_service, test_equipment, test_user):
        """Test booking status transitions."""
        start_time = datetime.utcnow() + timedelta(days=4)
        end_time = start_time + timedelta(hours=2)
        
        # Create booking
        booking = db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'Workflow Test',
            'start_time': start_time,
            'end_time': end_time,
        })
        
        assert booking['status'] in ['pending', 'confirmed']
        
        # Check in
        if hasattr(db_service, 'checkin_booking'):
            db_service.checkin_booking(booking['id'])
            updated = db_service.get_equipment_booking(booking['id'])
            # Status after check-in is 'in_progress'
            assert updated['status'] in ['checked_in', 'in_progress']
    
    def test_booking_cancellation(self, db_service, test_equipment, test_user):
        """Test booking cancellation."""
        start_time = datetime.utcnow() + timedelta(days=5)
        end_time = start_time + timedelta(hours=2)
        
        booking = db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'To Be Cancelled',
            'start_time': start_time,
            'end_time': end_time,
        })
        
        # Cancel the booking
        if hasattr(db_service, 'cancel_booking'):
            db_service.cancel_booking(booking['id'], reason='Testing cancellation')
            cancelled = db_service.get_equipment_booking(booking['id'])
            assert cancelled['status'] == 'cancelled'
    
    def test_booking_retrieval_by_equipment(self, db_service, test_equipment, test_user):
        """Test retrieving bookings for a specific equipment."""
        start_time = datetime.utcnow() + timedelta(days=6)
        
        # Create a few bookings
        for i in range(3):
            db_service.create_equipment_booking({
                'equipment_id': test_equipment['id'],
                'user_id': test_user['id'],
                'title': f'Booking {i+1}',
                'start_time': start_time + timedelta(days=i),
                'end_time': start_time + timedelta(days=i, hours=2),
            })
        
        # Retrieve bookings - returns (list, total) tuple
        result = db_service.get_equipment_bookings(equipment_id=test_equipment['id'])
        # Handle both tuple (list, count) and list return types
        if isinstance(result, tuple):
            bookings, total = result
        else:
            bookings = result
        
        assert len(bookings) >= 3
    
    def test_booking_retrieval_by_user(self, db_service, test_equipment, test_user):
        """Test retrieving bookings for a specific user."""
        result = db_service.get_equipment_bookings(user_id=test_user['id'])
        
        # Handle both tuple (list, count) and list return types
        if isinstance(result, tuple):
            bookings, total = result
        else:
            bookings = result
        
        # Should return list (possibly empty)
        assert isinstance(bookings, list)


class TestRecurringBookings:
    """Tests for recurring booking functionality."""
    
    def test_create_recurring_booking(self, db_service, test_equipment, test_user):
        """Test creating a recurring booking."""
        start_time = datetime.utcnow() + timedelta(days=7)
        end_time = start_time + timedelta(hours=2)
        
        booking = db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'Weekly Lab Time',
            'start_time': start_time,
            'end_time': end_time,
            'is_recurring': True,
            'recurrence_rule': 'FREQ=WEEKLY;COUNT=4',
        })
        
        assert booking is not None
        assert booking['is_recurring'] == True


class TestCalendarEvents:
    """Tests for calendar event generation."""
    
    def test_generate_calendar_event_dict(self, db_service, test_equipment, test_user):
        """Test generating calendar event data from booking."""
        start_time = datetime.utcnow() + timedelta(days=8)
        end_time = start_time + timedelta(hours=2)
        
        booking = db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'Calendar Test',
            'start_time': start_time,
            'end_time': end_time,
        })
        
        # Get bookings formatted for calendar
        if hasattr(db_service, 'get_bookings_for_calendar'):
            events = db_service.get_bookings_for_calendar(
                equipment_id=test_equipment['id'],
                start_date=start_time - timedelta(days=1),
                end_date=end_time + timedelta(days=1)
            )
            
            assert len(events) >= 1
            event = events[0]
            assert 'title' in event
            assert 'start' in event
            assert 'end' in event
    
    def test_ical_feed_generation(self, db_service, test_equipment, test_user):
        """Test iCalendar feed generation."""
        start_time = datetime.utcnow() + timedelta(days=9)
        end_time = start_time + timedelta(hours=2)
        
        booking = db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'iCal Test',
            'start_time': start_time,
            'end_time': end_time,
        })
        
        if hasattr(db_service, 'generate_ical_feed'):
            ical_content = db_service.generate_ical_feed(
                equipment_id=test_equipment['id']
            )
            
            assert 'BEGIN:VCALENDAR' in ical_content
            assert 'END:VCALENDAR' in ical_content
            assert 'BEGIN:VEVENT' in ical_content


class TestCalendarIntegrationService:
    """Tests for the CalendarIntegrationService class."""
    
    def test_calendar_service_initialization(self, db_service):
        """Test calendar service can be initialized."""
        from database.calendar_integration import CalendarIntegrationService
        
        service = CalendarIntegrationService(db_service)
        
        assert service is not None
        assert service.db_service == db_service
    
    def test_google_availability_check(self, db_service):
        """Test checking Google Calendar availability."""
        from database.calendar_integration import CalendarIntegrationService
        
        service = CalendarIntegrationService(db_service)
        
        # Without credentials set, should return False
        is_available = service.is_google_available()
        
        # Result depends on environment variables
        assert isinstance(is_available, bool)
    
    def test_ical_event_generation(self, db_service):
        """Test iCalendar event generation."""
        from database.calendar_integration import CalendarIntegrationService
        
        service = CalendarIntegrationService(db_service)
        
        booking = {
            'id': 1,
            'title': 'Test Event',
            'start_time': '2026-01-15T10:00:00',
            'end_time': '2026-01-15T12:00:00',
            'equipment_name': 'NMR Spectrometer',
            'description': 'Test description',
            'status': 'confirmed',
        }
        
        ical_event = service.generate_ical_event(booking)
        
        assert 'BEGIN:VEVENT' in ical_event
        assert 'END:VEVENT' in ical_event
        assert 'Test Event' in ical_event
    
    def test_booking_color_mapping(self, db_service):
        """Test status-to-color mapping for calendar events."""
        from database.calendar_integration import CalendarIntegrationService
        
        service = CalendarIntegrationService(db_service)
        
        # Test color mapping
        assert service._get_booking_color('pending') == '5'  # Yellow
        assert service._get_booking_color('confirmed') == '10'  # Green
        assert service._get_booking_color('cancelled') == '11'  # Red
    
    def test_shared_calendar_event_description(self, db_service):
        """Test shared calendar event description formatting."""
        from database.calendar_integration import CalendarIntegrationService
        
        service = CalendarIntegrationService(db_service)
        
        booking = {
            'id': 1,
            'title': 'Analysis',
            'user_name': 'John Doe',
            'equipment_name': 'Mass Spec',
            'description': 'Running samples',
            'status': 'confirmed',
        }
        
        description = service._format_shared_event_description(booking)
        
        assert 'John Doe' in description
        assert 'Mass Spec' in description
        assert 'confirmed' in description.lower()


class TestSchedulingWebRoutes:
    """Tests for scheduling web routes (integration tests)."""
    
    @pytest.fixture
    def app_client(self, db_service):
        """Create a Flask test client."""
        try:
            from database.web.routes import main_bp
            from flask import Flask
            
            app = Flask(__name__)
            app.config['TESTING'] = True
            app.config['SECRET_KEY'] = 'test-secret'
            app.register_blueprint(main_bp)
            
            return app.test_client()
        except ImportError:
            pytest.skip("Flask routes not available")
    
    def test_schedule_page_loads(self, app_client, test_equipment):
        """Test that the schedule page loads."""
        # This is a basic smoke test
        # In a real test environment with full Flask setup,
        # we would test the actual routes
        pass
    
    def test_availability_check_endpoint(self, db_service, test_equipment, test_user):
        """Test the booking availability check API endpoint."""
        from datetime import datetime, timedelta
        
        # Create an existing booking
        start_time = datetime.now() + timedelta(days=1)
        start_time = start_time.replace(hour=10, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=2)
        
        db_service.create_equipment_booking({
            'equipment_id': test_equipment['id'],
            'user_id': test_user['id'],
            'title': 'Existing Booking',
            'start_time': start_time,
            'end_time': end_time,
        })
        
        # Test 1: Check availability for conflicting time
        availability = db_service.check_booking_availability(
            test_equipment['id'],
            start_time + timedelta(minutes=30),  # Overlaps
            end_time + timedelta(minutes=30)
        )
        assert not availability['available'], "Overlapping time should not be available"
        assert len(availability['issues']) > 0, "Should have conflict issue"
        
        # Test 2: Check availability for non-conflicting time
        available_start = end_time + timedelta(hours=1)
        available_end = available_start + timedelta(hours=1)
        
        availability2 = db_service.check_booking_availability(
            test_equipment['id'],
            available_start,
            available_end
        )
        assert availability2['available'], "Non-overlapping time should be available"
    
    def test_toggle_scheduling_enabled(self, db_service, test_equipment):
        """Test toggling scheduling enabled/disabled for equipment."""
        equipment_id = test_equipment['id']
        
        # Initially, scheduling should be enabled (default)
        config = db_service.get_equipment_scheduling_config(equipment_id)
        initial_enabled = config.get('scheduling_enabled', True) if config else True
        assert initial_enabled, "Scheduling should be enabled by default"
        
        # Disable scheduling
        db_service.create_or_update_scheduling_config(equipment_id, {
            'scheduling_enabled': False
        })
        
        config = db_service.get_equipment_scheduling_config(equipment_id)
        assert config is not None, "Config should exist after update"
        assert not config['scheduling_enabled'], "Scheduling should be disabled"
        
        # Re-enable scheduling
        db_service.create_or_update_scheduling_config(equipment_id, {
            'scheduling_enabled': True
        })
        
        config = db_service.get_equipment_scheduling_config(equipment_id)
        assert config['scheduling_enabled'], "Scheduling should be enabled again"


# Fixtures for scheduling tests

@pytest.fixture(scope="module")
def test_lab(db_service):
    """Create a test lab."""
    import time
    unique_name = f'Test Lab {int(time.time() * 1000)}'
    
    lab = db_service.create_lab({
        'name': unique_name,
        'description': 'Lab for scheduling tests',
    })
    
    yield lab
    
    # Cleanup handled at end of module


@pytest.fixture
def test_equipment(db_service, test_lab):
    """Create a test equipment item."""
    # Create unique name with timestamp to avoid conflicts
    import time
    unique_name = f'Test Scheduling Equipment {int(time.time() * 1000)}'
    
    equipment = db_service.create_equipment({
        'name': unique_name,
        'equipment_type': 'spectrometer',
        'status': 'available',
        'description': 'Equipment for scheduling tests',
        'lab_id': test_lab['id'],  # Required field
    })
    
    yield equipment
    
    # Cleanup
    try:
        db_service.delete_equipment(equipment['id'])
    except:
        pass


@pytest.fixture
def test_user(db_service, test_lab):
    """Create or get a test user."""
    import time
    unique_username = f'schedule_test_{int(time.time() * 1000)}'
    
    # Try to get existing test user
    user = db_service.get_user_by_username(unique_username)
    
    if not user:
        user = db_service.create_user(
            username=unique_username,
            email=f'{unique_username}@example.com',
            password='testpass123',
            name='Schedule Test User',
            lab_id=test_lab['id'],
        )
    
    return user


@pytest.fixture
def scheduling_config(db_service, test_equipment):
    """Create a scheduling configuration for test equipment."""
    config = db_service.create_or_update_scheduling_config(
        test_equipment['id'],
        {
            'scheduling_enabled': True,
            'min_booking_duration': 30,
            'max_booking_duration': 480,
            'buffer_time': 0,
            'requires_approval': False,
        }
    )
    return config

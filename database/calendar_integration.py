"""
PyBirch Calendar Integration Module
===================================
Handles integration with Google Calendar, Microsoft Outlook, and other
calendar services for equipment scheduling.

Industry-standard approach using:
- OAuth 2.0 for authentication
- Google Calendar API v3
- Microsoft Graph API for Outlook
- iCalendar (RFC 5545) for universal compatibility
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json

# Google Calendar API imports
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    Credentials = None  # Placeholder for type hints

# Microsoft Graph API imports (optional)
try:
    import msal
    MICROSOFT_API_AVAILABLE = True
except ImportError:
    MICROSOFT_API_AVAILABLE = False


class CalendarIntegrationService:
    """
    Service for integrating with external calendar providers.
    
    Supports:
    - Google Calendar (including shared lab calendars)
    - Microsoft Outlook Calendar
    - Apple iCloud Calendar (via CalDAV)
    - Generic iCalendar export/import
    """
    
    # Google Calendar OAuth scopes
    # Full calendar access needed for creating/sharing lab calendars
    GOOGLE_SCOPES = [
        'https://www.googleapis.com/auth/calendar',  # Full calendar access for shared calendars
        'https://www.googleapis.com/auth/calendar.events',
    ]
    
    # Separate scopes for admin users who manage shared calendars
    GOOGLE_ADMIN_SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/calendar.settings.readonly',
    ]
    
    def __init__(self, db_service):
        """Initialize with database service for token storage."""
        self.db_service = db_service
        
        # Google OAuth configuration
        self.google_client_id = os.environ.get('GOOGLE_CALENDAR_CLIENT_ID')
        self.google_client_secret = os.environ.get('GOOGLE_CALENDAR_CLIENT_SECRET')
        
        # Microsoft OAuth configuration  
        self.microsoft_client_id = os.environ.get('MICROSOFT_CLIENT_ID')
        self.microsoft_client_secret = os.environ.get('MICROSOFT_CLIENT_SECRET')
    
    # ==================== Google Calendar ====================
    
    def is_google_available(self) -> bool:
        """Check if Google Calendar integration is available."""
        return (
            GOOGLE_API_AVAILABLE and 
            self.google_client_id and 
            self.google_client_secret
        )
    
    def get_google_auth_url(self, user_id: int, redirect_uri: str) -> str:
        """Get Google OAuth authorization URL."""
        if not self.is_google_available():
            raise ValueError("Google Calendar integration not configured")
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.google_client_id,
                    "client_secret": self.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=self.GOOGLE_SCOPES,
            redirect_uri=redirect_uri
        )
        
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=str(user_id)  # Store user_id in state for callback
        )
        
        return auth_url
    
    def handle_google_callback(self, user_id: int, authorization_code: str, redirect_uri: str) -> Dict:
        """Handle Google OAuth callback and store credentials."""
        if not self.is_google_available():
            raise ValueError("Google Calendar integration not configured")
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.google_client_id,
                    "client_secret": self.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=self.GOOGLE_SCOPES,
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(code=authorization_code)
        credentials = flow.credentials
        
        # Store credentials in database
        data = {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_expires_at': credentials.expiry,
            'is_active': True,
        }
        
        return self.db_service.create_or_update_calendar_integration(
            user_id, 'google', data
        )
    
    def get_google_credentials(self, user_id: int) -> Optional[Credentials]:
        """Get valid Google credentials for a user."""
        if not GOOGLE_API_AVAILABLE:
            return None
        
        integration = self.db_service.get_calendar_integration(user_id, 'google')
        if not integration:
            return None
        
        credentials = Credentials(
            token=integration.get('access_token'),
            refresh_token=integration.get('refresh_token'),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.google_client_id,
            client_secret=self.google_client_secret,
        )
        
        # Refresh if expired
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                # Update stored tokens
                self.db_service.create_or_update_calendar_integration(
                    user_id, 'google', {
                        'access_token': credentials.token,
                        'token_expires_at': credentials.expiry,
                    }
                )
            except Exception as e:
                # Token refresh failed, user needs to re-authenticate
                self.db_service.create_or_update_calendar_integration(
                    user_id, 'google', {
                        'is_active': False,
                        'last_error': str(e),
                    }
                )
                return None
        
        return credentials
    
    def get_google_calendars(self, user_id: int) -> List[Dict]:
        """Get list of user's Google Calendars."""
        credentials = self.get_google_credentials(user_id)
        if not credentials:
            return []
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            calendars = service.calendarList().list().execute()
            
            return [{
                'id': cal['id'],
                'name': cal['summary'],
                'primary': cal.get('primary', False),
                'access_role': cal.get('accessRole', 'reader'),
            } for cal in calendars.get('items', [])]
        except Exception as e:
            self.db_service.create_or_update_calendar_integration(
                user_id, 'google', {'last_error': str(e)}
            )
            return []
    
    def create_google_event(
        self, 
        user_id: int, 
        booking: Dict,
        calendar_id: str = 'primary'
    ) -> Optional[str]:
        """Create a Google Calendar event for a booking."""
        credentials = self.get_google_credentials(user_id)
        if not credentials:
            return None
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            event = {
                'summary': f"Equipment: {booking.get('equipment_name', 'Unknown')} - {booking['title']}",
                'description': booking.get('description', ''),
                'start': {
                    'dateTime': booking['start_time'],
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': booking['end_time'],
                    'timeZone': 'UTC',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
                'extendedProperties': {
                    'private': {
                        'pybirch_booking_id': str(booking['id']),
                        'pybirch_equipment_id': str(booking['equipment_id']),
                    }
                }
            }
            
            created_event = service.events().insert(
                calendarId=calendar_id, 
                body=event
            ).execute()
            
            # Update booking with Google event ID
            self.db_service.update_equipment_booking(
                booking['id'], 
                {'google_event_id': created_event['id']}
            )
            
            return created_event['id']
            
        except Exception as e:
            self.db_service.create_or_update_calendar_integration(
                user_id, 'google', {'last_error': str(e)}
            )
            return None
    
    def update_google_event(
        self,
        user_id: int,
        booking: Dict,
        calendar_id: str = 'primary'
    ) -> bool:
        """Update a Google Calendar event for a booking."""
        if not booking.get('google_event_id'):
            return False
        
        credentials = self.get_google_credentials(user_id)
        if not credentials:
            return False
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            event = {
                'summary': f"Equipment: {booking.get('equipment_name', 'Unknown')} - {booking['title']}",
                'description': booking.get('description', ''),
                'start': {
                    'dateTime': booking['start_time'],
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': booking['end_time'],
                    'timeZone': 'UTC',
                },
            }
            
            service.events().update(
                calendarId=calendar_id,
                eventId=booking['google_event_id'],
                body=event
            ).execute()
            
            return True
            
        except Exception as e:
            self.db_service.create_or_update_calendar_integration(
                user_id, 'google', {'last_error': str(e)}
            )
            return False
    
    def delete_google_event(
        self,
        user_id: int,
        google_event_id: str,
        calendar_id: str = 'primary'
    ) -> bool:
        """Delete a Google Calendar event."""
        credentials = self.get_google_credentials(user_id)
        if not credentials:
            return False
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            service.events().delete(
                calendarId=calendar_id,
                eventId=google_event_id
            ).execute()
            return True
        except Exception as e:
            return False
    
    # ==================== Shared Lab Calendars ====================
    
    def create_shared_calendar(
        self,
        admin_user_id: int,
        calendar_name: str,
        description: str = '',
        timezone: str = 'America/New_York'
    ) -> Optional[Dict]:
        """
        Create a new shared Google Calendar for equipment scheduling.
        
        This creates a secondary calendar in the admin user's account
        that can be shared with lab members.
        
        Args:
            admin_user_id: User ID of the calendar owner (typically a lab admin)
            calendar_name: Name for the new calendar (e.g., "Lab Equipment Schedule")
            description: Optional description
            timezone: Calendar timezone
            
        Returns:
            Dict with calendar info including 'id' for sharing/events
        """
        credentials = self.get_google_credentials(admin_user_id)
        if not credentials:
            return None
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            calendar = {
                'summary': calendar_name,
                'description': description or f'Equipment scheduling calendar managed by PyBirch',
                'timeZone': timezone,
            }
            
            created_calendar = service.calendars().insert(body=calendar).execute()
            
            return {
                'id': created_calendar['id'],
                'name': created_calendar['summary'],
                'description': created_calendar.get('description', ''),
                'timezone': created_calendar.get('timeZone', timezone),
            }
            
        except Exception as e:
            self.db_service.create_or_update_calendar_integration(
                admin_user_id, 'google', {'last_error': f'Failed to create calendar: {str(e)}'}
            )
            return None
    
    def share_calendar_with_user(
        self,
        admin_user_id: int,
        calendar_id: str,
        email: str,
        role: str = 'reader'
    ) -> bool:
        """
        Share a Google Calendar with another user.
        
        Args:
            admin_user_id: User ID of the calendar owner
            calendar_id: Google Calendar ID to share
            email: Email of user to share with
            role: Access level - 'reader', 'writer', or 'owner'
            
        Returns:
            True if sharing succeeded
        """
        credentials = self.get_google_credentials(admin_user_id)
        if not credentials:
            return False
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            acl_rule = {
                'scope': {
                    'type': 'user',
                    'value': email,
                },
                'role': role,  # 'reader', 'writer', 'owner'
            }
            
            service.acl().insert(calendarId=calendar_id, body=acl_rule).execute()
            return True
            
        except Exception as e:
            self.db_service.create_or_update_calendar_integration(
                admin_user_id, 'google', {'last_error': f'Failed to share calendar: {str(e)}'}
            )
            return False
    
    def share_calendar_with_domain(
        self,
        admin_user_id: int,
        calendar_id: str,
        domain: str,
        role: str = 'reader'
    ) -> bool:
        """
        Share a Google Calendar with everyone in a domain.
        
        Useful for sharing equipment calendars with all lab members
        in an organization (e.g., university.edu).
        
        Args:
            admin_user_id: User ID of the calendar owner
            calendar_id: Google Calendar ID to share
            domain: Domain to share with (e.g., 'university.edu')
            role: Access level - 'reader' or 'writer'
        """
        credentials = self.get_google_credentials(admin_user_id)
        if not credentials:
            return False
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            acl_rule = {
                'scope': {
                    'type': 'domain',
                    'value': domain,
                },
                'role': role,
            }
            
            service.acl().insert(calendarId=calendar_id, body=acl_rule).execute()
            return True
            
        except Exception as e:
            return False
    
    def make_calendar_public(
        self,
        admin_user_id: int,
        calendar_id: str,
        role: str = 'reader'
    ) -> bool:
        """
        Make a Google Calendar publicly visible.
        
        Args:
            admin_user_id: User ID of the calendar owner
            calendar_id: Google Calendar ID
            role: Public access level - typically 'reader' (view only)
        """
        credentials = self.get_google_credentials(admin_user_id)
        if not credentials:
            return False
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            # Make calendar publicly readable
            acl_rule = {
                'scope': {
                    'type': 'default',  # Public access
                },
                'role': role,
            }
            
            service.acl().insert(calendarId=calendar_id, body=acl_rule).execute()
            return True
            
        except Exception as e:
            return False
    
    def get_calendar_share_link(self, calendar_id: str, embed: bool = False) -> str:
        """
        Get a shareable link to view a Google Calendar.
        
        Args:
            calendar_id: Google Calendar ID
            embed: If True, return an embeddable iframe URL
            
        Returns:
            Public URL to view/embed the calendar
        """
        from urllib.parse import quote
        encoded_id = quote(calendar_id, safe='')
        
        if embed:
            return f"https://calendar.google.com/calendar/embed?src={encoded_id}"
        else:
            return f"https://calendar.google.com/calendar/u/0?cid={encoded_id}"
    
    def get_calendar_subscribers(
        self,
        admin_user_id: int,
        calendar_id: str
    ) -> List[Dict]:
        """
        Get list of users who have access to a shared calendar.
        
        Returns list of dicts with 'email', 'role', and 'type' keys.
        """
        credentials = self.get_google_credentials(admin_user_id)
        if not credentials:
            return []
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            acl_list = service.acl().list(calendarId=calendar_id).execute()
            
            return [{
                'id': rule['id'],
                'email': rule['scope'].get('value', ''),
                'type': rule['scope']['type'],  # 'user', 'domain', 'default'
                'role': rule['role'],
            } for rule in acl_list.get('items', [])]
            
        except Exception as e:
            return []
    
    def remove_calendar_access(
        self,
        admin_user_id: int,
        calendar_id: str,
        rule_id: str
    ) -> bool:
        """Remove a user's access to a shared calendar."""
        credentials = self.get_google_credentials(admin_user_id)
        if not credentials:
            return False
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            service.acl().delete(calendarId=calendar_id, ruleId=rule_id).execute()
            return True
        except Exception as e:
            return False
    
    def populate_shared_calendar(
        self,
        admin_user_id: int,
        calendar_id: str,
        bookings: List[Dict],
        clear_existing: bool = False
    ) -> Dict:
        """
        Populate a shared calendar with equipment bookings.
        
        Args:
            admin_user_id: User ID of the calendar owner
            calendar_id: Google Calendar ID to populate
            bookings: List of booking dicts to create as events
            clear_existing: If True, delete all existing PyBirch events first
            
        Returns:
            Dict with 'created', 'updated', 'failed' counts
        """
        credentials = self.get_google_credentials(admin_user_id)
        if not credentials:
            return {'created': 0, 'updated': 0, 'failed': 0, 'error': 'No credentials'}
        
        result = {'created': 0, 'updated': 0, 'failed': 0, 'skipped': 0}
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            # Optionally clear existing PyBirch events
            if clear_existing:
                self._clear_pybirch_events(service, calendar_id)
            
            # Get existing events to check for updates
            existing_events = self._get_pybirch_events(service, calendar_id)
            existing_by_booking_id = {
                e.get('extendedProperties', {}).get('private', {}).get('pybirch_booking_id'): e
                for e in existing_events
            }
            
            for booking in bookings:
                try:
                    booking_id_str = str(booking['id'])
                    
                    event_body = {
                        'summary': f"🔬 {booking.get('equipment_name', 'Equipment')}: {booking['title']}",
                        'description': self._format_shared_event_description(booking),
                        'start': {
                            'dateTime': booking['start_time'],
                            'timeZone': 'UTC',
                        },
                        'end': {
                            'dateTime': booking['end_time'],
                            'timeZone': 'UTC',
                        },
                        'colorId': self._get_booking_color(booking.get('status', 'pending')),
                        'transparency': 'opaque',
                        'extendedProperties': {
                            'private': {
                                'pybirch_booking_id': booking_id_str,
                                'pybirch_equipment_id': str(booking.get('equipment_id', '')),
                                'pybirch_user_id': str(booking.get('user_id', '')),
                            }
                        }
                    }
                    
                    if booking_id_str in existing_by_booking_id:
                        # Update existing event
                        existing = existing_by_booking_id[booking_id_str]
                        service.events().update(
                            calendarId=calendar_id,
                            eventId=existing['id'],
                            body=event_body
                        ).execute()
                        result['updated'] += 1
                    else:
                        # Create new event
                        created = service.events().insert(
                            calendarId=calendar_id,
                            body=event_body
                        ).execute()
                        
                        # Store the event ID in the booking for future sync
                        self.db_service.update_equipment_booking(
                            booking['id'],
                            {'google_event_id': created['id']}
                        )
                        result['created'] += 1
                        
                except Exception as e:
                    result['failed'] += 1
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _format_shared_event_description(self, booking: Dict) -> str:
        """Format description for shared calendar events."""
        lines = []
        
        if booking.get('user_name'):
            lines.append(f"👤 Booked by: {booking['user_name']}")
        
        if booking.get('description'):
            lines.append(f"\n📝 Purpose: {booking['description']}")
        
        lines.append(f"\n🔧 Equipment: {booking.get('equipment_name', 'Unknown')}")
        
        status = booking.get('status', 'pending')
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'cancelled': '❌',
            'checked_in': '🟢',
            'completed': '✔️',
        }.get(status, '❓')
        lines.append(f"\n{status_emoji} Status: {status.replace('_', ' ').title()}")
        
        lines.append(f"\n---\nManaged by PyBirch Equipment Scheduler")
        
        return ''.join(lines)
    
    def _get_booking_color(self, status: str) -> str:
        """Get Google Calendar color ID for booking status."""
        # Google Calendar color IDs: 1-11
        color_map = {
            'pending': '5',      # Yellow
            'confirmed': '10',   # Green
            'cancelled': '11',   # Red
            'checked_in': '2',   # Sage green
            'completed': '8',    # Gray
        }
        return color_map.get(status, '1')
    
    def _get_pybirch_events(self, service, calendar_id: str) -> List[Dict]:
        """Get all PyBirch-created events from a calendar."""
        try:
            events = service.events().list(
                calendarId=calendar_id,
                privateExtendedProperty='pybirch_booking_id',
                maxResults=2500,
                singleEvents=True,
            ).execute()
            return events.get('items', [])
        except Exception:
            return []
    
    def _clear_pybirch_events(self, service, calendar_id: str) -> int:
        """Delete all PyBirch-created events from a calendar."""
        events = self._get_pybirch_events(service, calendar_id)
        deleted = 0
        for event in events:
            try:
                service.events().delete(
                    calendarId=calendar_id,
                    eventId=event['id']
                ).execute()
                deleted += 1
            except Exception:
                pass
        return deleted
    
    def sync_booking_to_shared_calendar(
        self,
        admin_user_id: int,
        calendar_id: str,
        booking: Dict,
        delete: bool = False
    ) -> bool:
        """
        Sync a single booking to a shared calendar.
        
        Call this when a booking is created, updated, or cancelled.
        """
        credentials = self.get_google_credentials(admin_user_id)
        if not credentials:
            return False
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            if delete and booking.get('google_event_id'):
                service.events().delete(
                    calendarId=calendar_id,
                    eventId=booking['google_event_id']
                ).execute()
                return True
            
            event_body = {
                'summary': f"🔬 {booking.get('equipment_name', 'Equipment')}: {booking['title']}",
                'description': self._format_shared_event_description(booking),
                'start': {
                    'dateTime': booking['start_time'],
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': booking['end_time'],
                    'timeZone': 'UTC',
                },
                'colorId': self._get_booking_color(booking.get('status', 'pending')),
                'extendedProperties': {
                    'private': {
                        'pybirch_booking_id': str(booking['id']),
                        'pybirch_equipment_id': str(booking.get('equipment_id', '')),
                    }
                }
            }
            
            if booking.get('google_event_id'):
                # Update existing event
                service.events().update(
                    calendarId=calendar_id,
                    eventId=booking['google_event_id'],
                    body=event_body
                ).execute()
            else:
                # Create new event
                created = service.events().insert(
                    calendarId=calendar_id,
                    body=event_body
                ).execute()
                
                self.db_service.update_equipment_booking(
                    booking['id'],
                    {'google_event_id': created['id']}
                )
            
            return True
            
        except Exception as e:
            return False
    
    # ==================== Microsoft Outlook ====================
    
    def is_microsoft_available(self) -> bool:
        """Check if Microsoft Calendar integration is available."""
        return (
            MICROSOFT_API_AVAILABLE and 
            self.microsoft_client_id and 
            self.microsoft_client_secret
        )
    
    def get_microsoft_auth_url(self, user_id: int, redirect_uri: str) -> str:
        """Get Microsoft OAuth authorization URL."""
        if not self.is_microsoft_available():
            raise ValueError("Microsoft Calendar integration not configured")
        
        authority = "https://login.microsoftonline.com/common"
        scopes = ["Calendars.ReadWrite", "User.Read"]
        
        app = msal.ConfidentialClientApplication(
            self.microsoft_client_id,
            authority=authority,
            client_credential=self.microsoft_client_secret,
        )
        
        auth_url = app.get_authorization_request_url(
            scopes,
            redirect_uri=redirect_uri,
            state=str(user_id)
        )
        
        return auth_url
    
    # ==================== iCalendar ====================
    
    def generate_ical_event(self, booking: Dict) -> str:
        """Generate iCalendar format for a single event."""
        uid = booking.get('ical_uid') or f"booking-{booking['id']}@pybirch"
        
        # Format datetimes
        dtstart = datetime.fromisoformat(booking['start_time'].replace('Z', '')).strftime('%Y%m%dT%H%M%SZ')
        dtend = datetime.fromisoformat(booking['end_time'].replace('Z', '')).strftime('%Y%m%dT%H%M%SZ')
        dtstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        
        summary = f"{booking.get('equipment_name', 'Equipment')}: {booking['title']}"
        description = booking.get('description', '')
        
        # Escape special characters
        summary = summary.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;')
        description = description.replace('\\', '\\\\').replace('\n', '\\n')
        
        lines = [
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{dtstamp}',
            f'DTSTART:{dtstart}',
            f'DTEND:{dtend}',
            f'SUMMARY:{summary}',
            f'DESCRIPTION:{description}',
            f'STATUS:{"CONFIRMED" if booking.get("status") == "confirmed" else "TENTATIVE"}',
            'END:VEVENT'
        ]
        
        return '\r\n'.join(lines)
    
    def parse_ical_rrule(self, rrule: str, start: datetime, max_occurrences: int = 52) -> List[datetime]:
        """Parse iCalendar RRULE and generate occurrence dates."""
        try:
            from dateutil.rrule import rrulestr
            rule = rrulestr(rrule, dtstart=start)
            return list(rule[:max_occurrences])
        except Exception:
            return [start]


# Global instance for use in routes
_calendar_service = None

def get_calendar_service(db_service=None):
    """Get or create the calendar integration service instance."""
    global _calendar_service
    if _calendar_service is None and db_service is not None:
        _calendar_service = CalendarIntegrationService(db_service)
    return _calendar_service

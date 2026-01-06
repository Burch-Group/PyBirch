"""
PyBirch URI Scheme Handler
==========================
Handles pybirch:// URI scheme for deep linking from browser to PyBirch application.

URI Format:
    pybirch://scan/<id>     - Open scan by database ID
    pybirch://queue/<id>    - Open queue by database ID  
    pybirch://sample/<id>   - Open sample by database ID

Usage:
    1. Register the URI scheme (run register_uri_scheme.py as admin)
    2. Click a pybirch:// link in browser
    3. Windows launches PyBirch with the URI as argument
    4. PyBirch parses the URI and loads the appropriate item
"""

import sys
import re
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote


@dataclass
class PyBirchURI:
    """Parsed PyBirch URI."""
    entity_type: str  # 'scan', 'queue', 'sample', etc.
    entity_id: int
    action: Optional[str] = None  # Future: 'edit', 'duplicate', etc.
    
    @property
    def is_valid(self) -> bool:
        return self.entity_type in ('scan', 'queue', 'sample', 'equipment', 'precursor')


def parse_pybirch_uri(uri: str) -> Optional[PyBirchURI]:
    """Parse a pybirch:// URI string.
    
    Args:
        uri: URI string like 'pybirch://scan/42' or 'pybirch://queue/123'
        
    Returns:
        PyBirchURI object if valid, None if invalid
    """
    if not uri:
        return None
    
    # Handle URL encoding
    uri = unquote(uri)
    
    # Parse the URI
    parsed = urlparse(uri)
    
    # Check scheme
    if parsed.scheme != 'pybirch':
        return None
    
    # The path format is: /<entity_type>/<id>
    # netloc might contain the entity_type depending on how Windows passes the URI
    path = parsed.netloc + parsed.path if parsed.netloc else parsed.path
    path = path.strip('/')
    
    parts = path.split('/')
    
    if len(parts) < 2:
        return None
    
    entity_type = parts[0].lower()
    
    try:
        entity_id = int(parts[1])
    except (ValueError, IndexError):
        return None
    
    action = parts[2] if len(parts) > 2 else None
    
    return PyBirchURI(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action
    )


def generate_uri(entity_type: str, entity_id: int, action: Optional[str] = None) -> str:
    """Generate a pybirch:// URI.
    
    Args:
        entity_type: Type of entity ('scan', 'queue', 'sample')
        entity_id: Database ID of the entity
        action: Optional action ('edit', etc.)
        
    Returns:
        URI string like 'pybirch://scan/42'
    """
    uri = f"pybirch://{entity_type}/{entity_id}"
    if action:
        uri += f"/{action}"
    return uri


class URIHandler:
    """
    Handler for PyBirch URI scheme.
    Integrates with PyBirch Qt application to load items from URIs.
    """
    
    def __init__(self, app=None):
        """Initialize the URI handler.
        
        Args:
            app: Optional PyBirch Qt application instance
        """
        self.app = app
        self._callbacks = {}
    
    def register_callback(self, entity_type: str, callback):
        """Register a callback for an entity type.
        
        Args:
            entity_type: Type of entity ('scan', 'queue', 'sample')
            callback: Function to call with entity_id when URI is received
        """
        self._callbacks[entity_type] = callback
    
    def handle_uri(self, uri: str) -> bool:
        """Handle a pybirch:// URI.
        
        Args:
            uri: URI string to handle
            
        Returns:
            True if handled successfully, False otherwise
        """
        parsed = parse_pybirch_uri(uri)
        
        if not parsed or not parsed.is_valid:
            print(f"Invalid PyBirch URI: {uri}")
            return False
        
        callback = self._callbacks.get(parsed.entity_type)
        
        if callback:
            try:
                callback(parsed.entity_id, parsed.action)
                return True
            except Exception as e:
                print(f"Error handling URI {uri}: {e}")
                return False
        else:
            print(f"No handler registered for entity type: {parsed.entity_type}")
            return False
    
    def handle_command_line(self, args: list = None) -> bool:
        """Check command line arguments for URI.
        
        Args:
            args: Command line arguments (defaults to sys.argv)
            
        Returns:
            True if a URI was found and handled
        """
        if args is None:
            args = sys.argv[1:]
        
        for arg in args:
            if arg.startswith('pybirch://'):
                return self.handle_uri(arg)
        
        return False


# Singleton instance
_uri_handler: Optional[URIHandler] = None


def get_uri_handler() -> URIHandler:
    """Get the global URI handler instance."""
    global _uri_handler
    if _uri_handler is None:
        _uri_handler = URIHandler()
    return _uri_handler


def setup_uri_handler_for_qt(main_window):
    """Set up URI handler callbacks for PyBirch Qt application.
    
    This function should be called after the main window is created.
    It registers callbacks that will load scans/queues/samples when
    pybirch:// links are clicked.
    
    Args:
        main_window: The PyBirch main window instance
    """
    handler = get_uri_handler()
    
    def handle_scan(scan_id: int, action: Optional[str] = None):
        """Load a scan by ID."""
        print(f"Opening scan {scan_id}")
        # This would integrate with PyBirch's scan loading
        # main_window.load_scan_from_database(scan_id)
        pass
    
    def handle_queue(queue_id: int, action: Optional[str] = None):
        """Load a queue by ID."""
        print(f"Opening queue {queue_id}")
        # This would integrate with PyBirch's queue loading
        # main_window.load_queue_from_database(queue_id)
        pass
    
    def handle_sample(sample_id: int, action: Optional[str] = None):
        """Load a sample by ID."""
        print(f"Opening sample {sample_id}")
        # This would integrate with PyBirch's sample management
        # main_window.show_sample_details(sample_id)
        pass
    
    handler.register_callback('scan', handle_scan)
    handler.register_callback('queue', handle_queue)
    handler.register_callback('sample', handle_sample)
    
    # Check if launched with a URI
    handler.handle_command_line()
    
    return handler


if __name__ == '__main__':
    # Test URI parsing
    test_uris = [
        'pybirch://scan/42',
        'pybirch://queue/123',
        'pybirch://sample/1/edit',
        'pybirch://invalid',
        'http://example.com',
    ]
    
    print("Testing URI parsing:")
    for uri in test_uris:
        result = parse_pybirch_uri(uri)
        print(f"  {uri} -> {result}")

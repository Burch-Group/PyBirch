"""
PyBirch Database Web Application
================================
Flask application factory for the database browser with WebSocket support.
"""

import os
from typing import Optional, Any
from dotenv import load_dotenv
from flask import Flask
from flask_dance.contrib.google import make_google_blueprint
from markupsafe import Markup, escape
from database.services import get_db_service

# Load environment variables from .env file
load_dotenv()

# Allow OAuth over HTTP for local development (required for testing)
# WARNING: Remove this in production! Production MUST use HTTPS
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Optional Flask-SocketIO support
try:
    from flask_socketio import SocketIO
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    SocketIO = None

# Global SocketIO instance
socketio = None

# Global ScanUpdateServer instance for WebSocket broadcasts
scan_update_server = None


def get_scan_update_server():
    """Get the global ScanUpdateServer instance for WebSocket broadcasts.
    
    Returns:
        ScanUpdateServer instance or None if not initialized
    """
    return scan_update_server


def create_app(db_path: Optional[str] = None, enable_socketio: bool = True) -> Flask:
    """Create and configure the Flask application.
    
    Args:
        db_path: Optional path to SQLite database.
        enable_socketio: Enable Flask-SocketIO for real-time features (default True).
        
    Returns:
        Configured Flask application.
    """
    global socketio
    
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pybirch-dev-key-change-in-production')
    app.config['DB_PATH'] = db_path
    
    # Google OAuth Configuration
    app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    
    # Only enable OAuth if credentials are configured
    if app.config['GOOGLE_OAUTH_CLIENT_ID'] and app.config['GOOGLE_OAUTH_CLIENT_SECRET']:
        google_bp = make_google_blueprint(
            client_id=app.config['GOOGLE_OAUTH_CLIENT_ID'],
            client_secret=app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
            scope=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile'],
            redirect_to='main.google_login'
        )
        app.register_blueprint(google_bp, url_prefix='/oauth')
        app.config['GOOGLE_OAUTH_ENABLED'] = True
    else:
        app.config['GOOGLE_OAUTH_ENABLED'] = False
    
    # Initialize database service
    with app.app_context():
        get_db_service(db_path)
    
    # Register blueprints
    from database.web.routes import main_bp, api_bp
    from database.web.api_v1 import api_v1_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(api_v1_bp)  # Registered at /api/v1/ (prefix defined in blueprint)
    
    # Context processor for templates
    @app.context_processor
    def utility_processor():
        from flask import session
        
        # Get site-wide filter values from session
        filter_lab_id = session.get('filter_lab_id')
        filter_project_id = session.get('filter_project_id')
        
        # Get labs and projects for filter dropdowns
        db = get_db_service()
        filter_labs = db.get_labs_simple_list() if db else []
        filter_projects = db.get_projects_simple_list() if db else []
        
        # Get filter display names
        filter_lab_name = None
        filter_project_name = None
        if filter_lab_id:
            lab = next((l for l in filter_labs if l.get('id') == filter_lab_id), None)
            filter_lab_name = lab.get('name') if lab else None
        if filter_project_id:
            proj = next((p for p in filter_projects if p.get('id') == filter_project_id), None)
            filter_project_name = proj.get('name') if proj else None
        
        has_active_filter = bool(filter_lab_id or filter_project_id)
        
        return {
            'app_name': 'PyBirch Database',
            'filter_labs': filter_labs,
            'filter_projects': filter_projects,
            'filter_lab_id': filter_lab_id,
            'filter_project_id': filter_project_id,
            'filter_lab_name': filter_lab_name,
            'filter_project_name': filter_project_name,
            'has_active_filter': has_active_filter,
        }
    
    # Custom template filter for newline to <br> conversion
    @app.template_filter('nl2br')
    def nl2br_filter(value):
        """Convert newlines to HTML <br> tags."""
        if value is None:
            return ''
        return Markup(escape(value).replace('\n', '<br>\n'))
    
    # Initialize Flask-SocketIO if available and enabled
    if enable_socketio and SOCKETIO_AVAILABLE:
        socketio = SocketIO(
            app,
            async_mode='threading',
            cors_allowed_origins='*',
            ping_interval=25,
            ping_timeout=120
        )
        app.config['SOCKETIO_ENABLED'] = True
        
        # Register WebSocket event handlers
        _register_socketio_handlers(socketio)
        
        # Create global ScanUpdateServer for broadcasting from PyBirch GUI
        global scan_update_server
        try:
            from pybirch.database_integration.sync import ScanUpdateServer
            scan_update_server = ScanUpdateServer(socketio)
            scan_update_server.register_handlers()
            app.config['SCAN_UPDATE_SERVER'] = scan_update_server
            print("[WebSocket] ScanUpdateServer initialized for GUI integration")
        except ImportError:
            print("[WebSocket] Warning: Could not create ScanUpdateServer (pybirch not available)")
    else:
        app.config['SOCKETIO_ENABLED'] = False
    
    return app


def _register_socketio_handlers(socketio: Any):
    """Register WebSocket event handlers for real-time updates."""
    if not SOCKETIO_AVAILABLE:
        return
    from flask_socketio import emit, join_room, leave_room
    from datetime import datetime
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        emit('connected', {
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat(),
            'message': 'Connected to PyBirch real-time updates'
        })
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        pass
    
    @socketio.on('subscribe_scan')
    def handle_subscribe_scan(data):
        """Subscribe to updates for a specific scan."""
        scan_id = data.get('scan_id')
        if scan_id:
            join_room(f'scan_{scan_id}')
            emit('subscribed', {'type': 'scan', 'id': scan_id})
    
    @socketio.on('unsubscribe_scan')
    def handle_unsubscribe_scan(data):
        """Unsubscribe from scan updates."""
        scan_id = data.get('scan_id')
        if scan_id:
            leave_room(f'scan_{scan_id}')
    
    @socketio.on('subscribe_queue')
    def handle_subscribe_queue(data):
        """Subscribe to updates for a specific queue."""
        queue_id = data.get('queue_id')
        if queue_id:
            join_room(f'queue_{queue_id}')
            emit('subscribed', {'type': 'queue', 'id': queue_id})
    
    @socketio.on('unsubscribe_queue')
    def handle_unsubscribe_queue(data):
        """Unsubscribe from queue updates."""
        queue_id = data.get('queue_id')
        if queue_id:
            leave_room(f'queue_{queue_id}')
    
    @socketio.on('subscribe_instruments')
    def handle_subscribe_instruments():
        """Subscribe to instrument status updates."""
        join_room('instruments')
        emit('subscribed', {'type': 'instruments'})
    
    @socketio.on('subscribe_queues')
    def handle_subscribe_queues():
        """Subscribe to all queue status updates (for dashboard)."""
        join_room('all_queues')
        join_room('all_updates')
        emit('subscribed', {'type': 'queues'})
    
    @socketio.on('unsubscribe_queues')
    def handle_unsubscribe_queues():
        """Unsubscribe from all queue updates."""
        leave_room('all_queues')
    
    @socketio.on('subscribe_scans')
    def handle_subscribe_scans():
        """Subscribe to all scan status updates (for dashboard)."""
        join_room('all_scans')
        join_room('all_updates')
        emit('subscribed', {'type': 'scans'})
    
    @socketio.on('unsubscribe_scans')
    def handle_unsubscribe_scans():
        """Unsubscribe from all scan updates."""
        leave_room('all_scans')
    
    @socketio.on('subscribe_all')
    def handle_subscribe_all():
        """Subscribe to all updates."""
        join_room('all_updates')
        emit('subscribed', {'type': 'all'})
    
    # ===== Client-to-Server Event Handlers =====
    # These handle events from PyBirch GUI clients and rebroadcast them
    # to web dashboard clients for cross-process communication
    
    @socketio.on('client_scan_status')
    def handle_client_scan_status(data):
        """
        Handle scan status from PyBirch GUI client and rebroadcast.
        
        Args:
            data: Dict with scan_id, status, progress, message, etc.
        """
        scan_id = data.get('scan_id')
        if scan_id:
            # Broadcast to scan-specific room
            emit('scan_status', data, room=f'scan_{scan_id}')
            # Broadcast to all_scans room (for dashboard subscribed to all scans)
            emit('scan_status', data, room='all_scans')
            # Also broadcast to all_updates room
            emit('scan_status', data, room='all_updates')
            print(f"[WS Server] Relayed scan status: {scan_id} - {data.get('status')}")
    
    @socketio.on('client_queue_status')
    def handle_client_queue_status(data):
        """
        Handle queue status from PyBirch GUI client and rebroadcast.
        
        Args:
            data: Dict with queue_id, status, total_scans, completed_scans, etc.
        """
        queue_id = data.get('queue_id')
        if queue_id:
            # Broadcast to queue-specific room
            emit('queue_status', data, room=f'queue_{queue_id}')
            # Broadcast to all_queues room (for dashboard subscribed to all queues)
            emit('queue_status', data, room='all_queues')
            # Also broadcast to all_updates room
            emit('queue_status', data, room='all_updates')
            print(f"[WS Server] Relayed queue status: {queue_id} - {data.get('status')}")
    
    @socketio.on('client_data_point')
    def handle_client_data_point(data):
        """
        Handle data point from PyBirch GUI client and rebroadcast.
        
        Args:
            data: Dict with scan_id, measurement_name, data, sequence_index, etc.
        """
        scan_id = data.get('scan_id')
        if scan_id:
            # Broadcast to scan-specific room
            emit('data_point', data, room=f'scan_{scan_id}')
            # Also broadcast to all_updates room  
            emit('data_point', data, room='all_updates')
    
    @socketio.on('client_log_entry')
    def handle_client_log_entry(data):
        """
        Handle log entry from PyBirch GUI client and rebroadcast.
        
        Args:
            data: Dict with queue_id, level, message, scan_id, etc.
        """
        queue_id = data.get('queue_id')
        if queue_id:
            # Broadcast to queue-specific room
            emit('log_entry', data, room=f'queue_{queue_id}')
            # Also broadcast to all_updates room
            emit('log_entry', data, room='all_updates')


def get_socketio():
    """Get the global SocketIO instance."""
    return socketio


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='PyBirch Database Web Server')
    parser.add_argument('--host', default='127.0.0.1', 
                        help='Host to bind to (use 0.0.0.0 for network access)')
    parser.add_argument('--port', type=int, default=5002,
                        help='Port to run on')
    parser.add_argument('--network', action='store_true',
                        help='Enable network access (shortcut for --host 0.0.0.0)')
    args = parser.parse_args()
    
    host = '0.0.0.0' if args.network else args.host
    
    app = create_app()
    
    if host == '0.0.0.0':
        import socket
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        print(f"\n{'='*50}")
        print(f"  PyBirch Database Server")
        print(f"{'='*50}")
        print(f"  Local:   http://127.0.0.1:{args.port}")
        print(f"  Network: http://{local_ip}:{args.port}")
        if SOCKETIO_AVAILABLE:
            print(f"  WebSocket: Enabled")
        else:
            print(f"  WebSocket: Disabled (install flask-socketio)")
        print(f"{'='*50}\n")
    
    # Run with SocketIO if available, otherwise use standard Flask
    if SOCKETIO_AVAILABLE and socketio is not None:
        socketio.run(app, debug=True, host=host, port=args.port)
    else:
        app.run(debug=True, host=host, port=args.port)

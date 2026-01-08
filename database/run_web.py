#!/usr/bin/env python
"""
PyBirch Database Web Server
===========================
Entry point for running the Flask-based database browser.

Usage:
    python database/run_web.py              # Start on default port 5000
    python database/run_web.py --port 8080  # Start on custom port
    python database/run_web.py --debug      # Enable debug mode
    python database/run_web.py --kill       # Kill existing server on port
    python database/run_web.py --restart    # Kill existing and restart

The web interface will be available at http://localhost:5000
"""

import os
import sys
import argparse
import webbrowser
import socket
import signal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def kill_server_on_port(port: int) -> bool:
    """Kill any process using the specified port.
    
    Returns True if a process was killed, False otherwise.
    """
    import subprocess
    
    if sys.platform == 'win32':
        # Windows: use netstat and taskkill
        try:
            # Find PID using the port
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'TCP'],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            subprocess.run(['taskkill', '/PID', pid, '/F'], 
                                         capture_output=True)
                            print(f"  Killed process {pid} using port {port}")
                            return True
                        except Exception:
                            pass
        except Exception as e:
            print(f"  Warning: Could not check for existing server: {e}")
    else:
        # Unix-like: use lsof and kill
        try:
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True
            )
            
            if result.stdout.strip():
                for pid in result.stdout.strip().split('\n'):
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"  Killed process {pid} using port {port}")
                        return True
                    except Exception:
                        pass
        except Exception as e:
            print(f"  Warning: Could not check for existing server: {e}")
    
    return False


def is_port_in_use(port: int) -> bool:
    """Check if a port is currently in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Run the PyBirch Database Web Server"
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=5000,
        help='Port to run the server on (default: 5000)'
    )
    parser.add_argument(
        '--host', '-H',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug mode with auto-reload'
    )
    parser.add_argument(
        '--db-path',
        default=None,
        help='Path to SQLite database file (default: database/pybirch.db)'
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not open browser automatically'
    )
    parser.add_argument(
        '--kill', '-k',
        action='store_true',
        help='Kill any existing server on the port and exit'
    )
    parser.add_argument(
        '--restart', '-r',
        action='store_true',
        help='Kill any existing server on the port before starting'
    )
    
    args = parser.parse_args()
    
    # Handle --kill flag (just kill and exit)
    if args.kill:
        if is_port_in_use(args.port):
            killed = kill_server_on_port(args.port)
            if killed:
                print(f"Server on port {args.port} has been stopped.")
            else:
                print(f"Could not kill server on port {args.port}.")
        else:
            print(f"No server running on port {args.port}.")
        return
    
    # Handle --restart flag (kill existing before starting)
    if args.restart or is_port_in_use(args.port):
        if is_port_in_use(args.port):
            print(f"  Port {args.port} is in use, attempting to kill existing server...")
            kill_server_on_port(args.port)
            import time
            time.sleep(1)  # Give it a moment to release the port
    
    # Determine database path
    if args.db_path:
        db_path = args.db_path
    else:
        db_path = str(Path(__file__).parent / 'pybirch.db')
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║           PyBirch Database Web Server                    ║
╚══════════════════════════════════════════════════════════╝

  Database: {db_path}
  Server:   http://{args.host}:{args.port}
  Debug:    {'Enabled' if args.debug else 'Disabled'}

  Press Ctrl+C to stop the server.
""")
    
    # Import and create the Flask app
    from database.web import create_app
    from database.web.app import socketio
    app = create_app(db_path=db_path)
    
    # Open browser (only if not in debug mode's second process)
    if not args.no_browser and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        url = f"http://{args.host}:{args.port}"
        print(f"  Opening browser to {url}...")
        webbrowser.open(url)
    
    # Run the server with SocketIO if available, otherwise use standard Flask
    if socketio is not None:
        print("  WebSocket support: Enabled")
        socketio.run(
            app,
            host=args.host,
            port=args.port,
            debug=args.debug
        )
    else:
        print("  WebSocket support: Disabled (flask-socketio not installed)")
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug
        )


if __name__ == '__main__':
    main()

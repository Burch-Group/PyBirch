#!/usr/bin/env python
"""
PyBirch Database Web Server
===========================
Entry point for running the Flask-based database browser.

Usage:
    python database/run_web.py              # Start on default port 5000
    python database/run_web.py --port 8080  # Start on custom port
    python database/run_web.py --debug      # Enable debug mode

The web interface will be available at http://localhost:5000
"""

import os
import sys
import argparse
import webbrowser
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


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
    
    args = parser.parse_args()
    
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
    app = create_app(db_path=db_path)
    
    # Open browser (only if not in debug mode's second process)
    if not args.no_browser and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        url = f"http://{args.host}:{args.port}"
        print(f"  Opening browser to {url}...")
        webbrowser.open(url)
    
    # Run the server
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == '__main__':
    main()

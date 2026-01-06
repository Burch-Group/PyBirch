"""
PyBirch Database Web Application
================================
Flask application factory for the database browser.
"""

import os
from dotenv import load_dotenv
from flask import Flask
from flask_dance.contrib.google import make_google_blueprint
from database.services import get_db_service

# Load environment variables from .env file
load_dotenv()

# Allow OAuth over HTTP for local development (required for testing)
# WARNING: Remove this in production! Production MUST use HTTPS
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


def create_app(db_path: str = None) -> Flask:
    """Create and configure the Flask application.
    
    Args:
        db_path: Optional path to SQLite database.
        
    Returns:
        Configured Flask application.
    """
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
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Context processor for templates
    @app.context_processor
    def utility_processor():
        return {
            'app_name': 'PyBirch Database',
        }
    
    return app


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
        print(f"{'='*50}\n")
    
    app.run(debug=True, host=host, port=args.port)

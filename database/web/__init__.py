"""
PyBirch Database Web UI Package
===============================
Flask-based web interface for browsing the PyBirch database.
"""

from database.web.app import create_app

__all__ = ['create_app']

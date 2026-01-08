"""
PyBirch API Client
==================
Lightweight HTTP client for communicating with the PyBirch Database server.

This module provides a clean interface for PyBirch instruments and experiments
to interact with the database without requiring direct database access.

Example usage:
    from pybirch.api_client import PyBirchClient
    
    client = PyBirchClient("http://localhost:5000")
    
    # Create a scan
    scan = client.scans.create({
        "sample_id": 1,
        "scan_type": "IV Curve"
    })
    
    # Submit measurement data
    client.measurements.create_data(
        measurement_id=scan["measurement_id"],
        points=[{"values": {"voltage": v, "current": i}} for v, i in data]
    )
"""

from .client import PyBirchClient
from .exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    ConnectionError,
)

__all__ = [
    'PyBirchClient',
    'APIError',
    'AuthenticationError', 
    'NotFoundError',
    'ValidationError',
    'ConnectionError',
]

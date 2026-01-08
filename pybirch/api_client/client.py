"""
PyBirch API Client
==================
Main client class for interacting with the PyBirch Database REST API.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    ConnectionError,
    ServerError,
)

logger = logging.getLogger(__name__)


class ResourceEndpoint:
    """Base class for API resource endpoints."""
    
    def __init__(self, client: 'PyBirchClient', resource_name: str):
        self.client = client
        self.resource_name = resource_name
        self.base_path = f"/{resource_name}"
    
    def list(
        self,
        page: int = 1,
        per_page: int = 20,
        **filters
    ) -> Dict[str, Any]:
        """List resources with optional filtering and pagination.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            **filters: Additional filter parameters
            
        Returns:
            Dict with 'data', 'meta' keys containing items and pagination info
        """
        params = {'page': page, 'per_page': per_page, **filters}
        return self.client.get(self.base_path, params=params)
    
    def get(self, resource_id: int) -> Dict[str, Any]:
        """Get a single resource by ID.
        
        Args:
            resource_id: Resource ID
            
        Returns:
            Resource data as dictionary
        """
        return self.client.get(f"{self.base_path}/{resource_id}")
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new resource.
        
        Args:
            data: Resource data
            
        Returns:
            Created resource data
        """
        return self.client.post(self.base_path, json=data)
    
    def update(self, resource_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing resource.
        
        Args:
            resource_id: Resource ID
            data: Updated resource data
            
        Returns:
            Updated resource data
        """
        return self.client.patch(f"{self.base_path}/{resource_id}", json=data)
    
    def delete(self, resource_id: int) -> Dict[str, Any]:
        """Delete a resource.
        
        Args:
            resource_id: Resource ID
            
        Returns:
            Deletion confirmation
        """
        return self.client.request('DELETE', f"{self.base_path}/{resource_id}")


class ScansEndpoint(ResourceEndpoint):
    """Endpoint for scan operations with additional measurement methods."""
    
    def __init__(self, client: 'PyBirchClient'):
        super().__init__(client, 'scans')
    
    def update_status(
        self,
        scan_id: int,
        status: str,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update scan status.
        
        Args:
            scan_id: Scan ID
            status: New status ('pending', 'running', 'completed', 'failed', 'aborted')
            started_at: ISO timestamp when scan started
            completed_at: ISO timestamp when scan completed
            error_message: Error message if scan failed
            
        Returns:
            Updated scan data
        """
        data = {'status': status}
        if started_at:
            data['started_at'] = started_at
        if completed_at:
            data['completed_at'] = completed_at
        if error_message:
            data['error_message'] = error_message
        
        return self.client.patch(f"{self.base_path}/{scan_id}/status", json=data)
    
    def get_measurements(self, scan_id: int) -> List[Dict[str, Any]]:
        """Get measurement objects for a scan.
        
        Args:
            scan_id: Scan ID
            
        Returns:
            List of measurement objects
        """
        response = self.client.get(f"{self.base_path}/{scan_id}/measurements")
        return response.get('data', response)
    
    def create_measurement(
        self,
        scan_id: int,
        name: str,
        data_type: str = 'float',
        unit: Optional[str] = None,
        instrument_name: Optional[str] = None,
        columns: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a measurement object for a scan.
        
        Args:
            scan_id: Scan ID
            name: Measurement name (e.g., "IV_Curve", "Temperature")
            data_type: Data type ('float', 'int', 'array', 'json')
            unit: Measurement unit (e.g., 'V', 'A', 'K')
            instrument_name: Name of the instrument
            columns: Column names for array data
            description: Measurement description
            
        Returns:
            Created measurement object data
        """
        data = {
            'name': name,
            'data_type': data_type,
        }
        if unit:
            data['unit'] = unit
        if instrument_name:
            data['instrument_name'] = instrument_name
        if columns:
            data['columns'] = columns
        if description:
            data['description'] = description
        
        return self.client.post(f"{self.base_path}/{scan_id}/measurements", json=data)


class MeasurementsEndpoint:
    """Endpoint for measurement data operations."""
    
    def __init__(self, client: 'PyBirchClient'):
        self.client = client
    
    def get_data(self, measurement_id: int) -> List[Dict[str, Any]]:
        """Get data points for a measurement.
        
        Args:
            measurement_id: Measurement object ID
            
        Returns:
            List of data points
        """
        response = self.client.get(f"/measurements/{measurement_id}/data")
        return response.get('data', response)
    
    def create_data(
        self,
        measurement_id: int,
        points: List[Dict[str, Any]],
        batch_size: int = 5000
    ) -> Dict[str, Any]:
        """Submit data points for a measurement.
        
        Automatically batches large submissions to avoid request size limits.
        
        Args:
            measurement_id: Measurement object ID
            points: List of data point dictionaries, each with 'values' key
            batch_size: Maximum points per request (default 5000)
            
        Returns:
            Summary of created data points
        """
        total_created = 0
        
        # Process in batches
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            result = self.client.post(
                f"/measurements/{measurement_id}/data",
                json={'points': batch}
            )
            total_created += result.get('data', {}).get('count', len(batch))
        
        return {'count': total_created, 'measurement_id': measurement_id}


class QueuesEndpoint(ResourceEndpoint):
    """Endpoint for queue operations.
    
    Queues are parent containers for scans. A queue can have multiple
    child scans that are executed as part of the queue.
    """
    
    def __init__(self, client: 'PyBirchClient'):
        super().__init__(client, 'queues')
    
    def update_status(self, queue_id: int, status: str) -> Dict[str, Any]:
        """Update queue status.
        
        Args:
            queue_id: Queue ID
            status: New status
            
        Returns:
            Updated queue data
        """
        return self.client.patch(
            f"{self.base_path}/{queue_id}/status",
            json={'status': status}
        )
    
    def get_scans(
        self,
        queue_id: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Get scans belonging to a queue (children).
        
        Scans are children of queues - each scan in a queue is
        executed as part of that queue's workflow.
        
        Args:
            queue_id: Parent queue ID
            search: Search term for scan name/ID
            status: Filter by scan status
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Paginated list of scans belonging to this queue
        """
        params = {'page': page, 'per_page': per_page}
        if search:
            params['search'] = search
        if status:
            params['status'] = status
        return self.client.get(f"{self.base_path}/{queue_id}/scans", params=params)


class PyBirchClient:
    """
    Client for the PyBirch Database REST API.
    
    Provides a clean interface for PyBirch instruments and experiments
    to interact with the database server.
    
    Example:
        client = PyBirchClient("http://localhost:5000", api_key="your-key")
        
        # List samples
        samples = client.samples.list(lab_id=1)
        
        # Create a scan
        scan = client.scans.create({
            "sample_id": 1,
            "scan_type": "IV Curve"
        })
        
        # Create measurement and submit data
        measurement = client.scans.create_measurement(
            scan_id=scan['data']['id'],
            name="IV_Curve",
            unit="A"
        )
        client.measurements.create_data(
            measurement_id=measurement['data']['id'],
            points=[{"values": {"voltage": v, "current": i}} for v, i in data]
        )
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        retries: int = 3,
        verify_ssl: bool = True,
    ):
        """Initialize the PyBirch API client.
        
        Args:
            base_url: API server base URL. Defaults to PYBIRCH_API_URL env var
                     or http://localhost:5000
            api_key: API key for authentication. Defaults to PYBIRCH_API_KEY env var
            timeout: Request timeout in seconds
            retries: Number of retries for failed requests
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url or os.environ.get('PYBIRCH_API_URL', 'http://localhost:5000')
        self.api_url = urljoin(self.base_url, '/api/v1')
        self.api_key = api_key or os.environ.get('PYBIRCH_API_KEY')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Set default headers
        if self.api_key:
            self.session.headers['Authorization'] = f'Bearer {self.api_key}'
        self.session.headers['Content-Type'] = 'application/json'
        self.session.headers['Accept'] = 'application/json'
        
        # Initialize resource endpoints
        self.labs = ResourceEndpoint(self, 'labs')
        self.projects = ResourceEndpoint(self, 'projects')
        self.samples = ResourceEndpoint(self, 'samples')
        self.equipment = ResourceEndpoint(self, 'equipment')
        self.precursors = ResourceEndpoint(self, 'precursors')
        self.procedures = ResourceEndpoint(self, 'procedures')
        self.instruments = ResourceEndpoint(self, 'instruments')
        self.fabrication_runs = ResourceEndpoint(self, 'fabrication-runs')
        
        # Specialized endpoints
        self.scans = ScansEndpoint(self)
        self.queues = QueuesEndpoint(self)
        self.measurements = MeasurementsEndpoint(self)
    
    def _build_url(self, path: str) -> str:
        """Build full URL from path."""
        if path.startswith('/'):
            path = path[1:]
        return f"{self.api_url}/{path}"
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        try:
            data = response.json()
        except ValueError:
            data = {'message': response.text}
        
        if response.status_code == 200 or response.status_code == 201:
            return data
        
        # Extract error info
        error_info = data.get('error', {})
        message = error_info.get('message', data.get('message', 'Unknown error'))
        code = error_info.get('code', 'ERROR')
        details = error_info.get('details', {})
        
        # Map to appropriate exception
        if response.status_code == 401:
            raise AuthenticationError(message, code, response.status_code, details)
        elif response.status_code == 404:
            raise NotFoundError(message, code, response.status_code, details)
        elif response.status_code == 400 or response.status_code == 422:
            raise ValidationError(message, code, response.status_code, details)
        elif response.status_code >= 500:
            raise ServerError(message, code, response.status_code, details)
        else:
            raise APIError(message, code, response.status_code, details)
    
    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make an API request.
        
        Args:
            method: HTTP method (GET, POST, PATCH, PUT, DELETE)
            path: API path (relative to /api/v1)
            params: Query parameters
            json: JSON body data
            **kwargs: Additional arguments passed to requests
            
        Returns:
            Response data as dictionary
            
        Raises:
            APIError: On API errors
            ConnectionError: On connection errors
        """
        url = self._build_url(path)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                timeout=self.timeout,
                verify=self.verify_ssl,
                **kwargs
            )
            return self._handle_response(response)
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"Failed to connect to API server at {self.base_url}: {e}",
                code="CONNECTION_ERROR"
            )
        except requests.exceptions.Timeout as e:
            raise ConnectionError(
                f"Request timed out after {self.timeout}s: {e}",
                code="TIMEOUT"
            )
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {e}", code="REQUEST_ERROR")
    
    def get(self, path: str, params: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make a GET request."""
        return self.request('GET', path, params=params, **kwargs)
    
    def post(self, path: str, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make a POST request."""
        return self.request('POST', path, json=json, **kwargs)
    
    def patch(self, path: str, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make a PATCH request."""
        return self.request('PATCH', path, json=json, **kwargs)
    
    def put(self, path: str, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make a PUT request."""
        return self.request('PUT', path, json=json, **kwargs)
    
    def health_check(self) -> Dict[str, Any]:
        """Check API server health.
        
        Returns:
            Health check response with status and version
        """
        return self.get('/health')
    
    def search(self, query: str) -> Dict[str, Any]:
        """Global search across all entities.
        
        Args:
            query: Search query string
            
        Returns:
            Search results grouped by entity type
        """
        return self.get('/search', params={'q': query})
    
    def __repr__(self) -> str:
        auth_status = "authenticated" if self.api_key else "anonymous"
        return f"<PyBirchClient({self.base_url}, {auth_status})>"

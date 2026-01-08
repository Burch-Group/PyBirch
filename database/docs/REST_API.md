# PyBirch REST API v1 Documentation

## Overview

The PyBirch Database provides a REST API for programmatic access to laboratory data. This API enables PyBirch instruments, experiments, and external applications to interact with the database without direct database access.

**Base URL:** `http://localhost:5000/api/v1`

**API Version:** v1

## Authentication

The API supports two authentication methods:

### 1. API Key (Recommended)

Include your API key in the `Authorization` header:

```
Authorization: Bearer your-api-key
```

Or use the `X-API-Key` header:

```
X-API-Key: your-api-key
```

### 2. Session Cookie

For web clients, session authentication via cookies is also supported.

**Note:** Some endpoints work without authentication (read-only access), while write operations require authentication.

## Response Format

### Successful Response

```json
{
  "success": true,
  "data": {
    // Resource data
  },
  "meta": {
    // Pagination info (for list endpoints)
    "total": 100,
    "page": 1,
    "per_page": 20,
    "pages": 5
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "details": {}
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource does not exist |
| `AUTH_REQUIRED` | 401 | Authentication required |
| `INVALID_INPUT` | 400 | Request body missing or invalid |
| `MISSING_FIELDS` | 400 | Required fields not provided |
| `DUPLICATE_ID` | 409 | Resource with same ID already exists |
| `QUERY_ERROR` | 500 | Database query failed |
| `CREATE_ERROR` | 500 | Failed to create resource |
| `UPDATE_ERROR` | 500 | Failed to update resource |
| `DELETE_ERROR` | 500 | Failed to delete resource |

## Pagination

List endpoints support pagination via query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number (1-indexed) |
| `per_page` | int | 20 | Items per page (max 100) |

---

## Quick Reference

| Resource | GET (list) | GET (single) | POST | PATCH/PUT | DELETE |
|----------|------------|--------------|------|-----------|--------|
| Labs | ✅ | ✅ | ✅ | ✅ | ✅ |
| Projects | ✅ | ✅ | ✅ | ✅ | ✅ |
| Samples | ✅ | ✅ | ✅ | ✅ | ✅ |
| Equipment | ✅ | ✅ | ✅ | ✅ | ✅ |
| Instruments | ✅ | ✅ | ✅ | ✅ | ✅ |
| Precursors | ✅ | ✅ | ✅ | ✅ | ✅ |
| Procedures | ✅ | ✅ | ✅ | ✅ | ✅* |
| Queues | ✅ | ✅ | ✅ | ✅ | ✅ |
| Scans | ✅ | ✅ | ✅ | ✅ | ✅ |
| Fabrication Runs | ✅ | ✅ | ✅ | ✅ | - |

*Soft delete (marks as inactive)

---

## Endpoints

### Health Check

#### `GET /api/v1/health`

Check API server health.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2026-01-06T20:00:00.000Z",
    "version": "v1"
  }
}
```

---

### Labs

#### `GET /api/v1/labs`

List all labs with optional filtering.

**Query Parameters:**
- `search` (string) - Filter by name
- `page` (int) - Page number
- `per_page` (int) - Items per page

#### `GET /api/v1/labs/{id}`

Get a single lab by ID.

#### `POST /api/v1/labs` 🔒

Create a new lab. **Requires authentication.**

**Request Body:**
```json
{
  "name": "Materials Science Lab",
  "description": "Main research lab",
  "location": "Building A, Room 101"
}
```

#### `PATCH /api/v1/labs/{id}` 🔒

Update a lab. **Requires authentication.**

#### `DELETE /api/v1/labs/{id}` 🔒

Delete a lab. **Requires authentication.**

---

### Projects

#### `GET /api/v1/projects`

List all projects with optional filtering.

**Query Parameters:**
- `search` (string) - Filter by name
- `lab_id` (int) - Filter by lab
- `status` (string) - Filter by status
- `page`, `per_page` - Pagination

#### `GET /api/v1/projects/{id}`
#### `POST /api/v1/projects` 🔒
#### `PATCH /api/v1/projects/{id}` 🔒
#### `DELETE /api/v1/projects/{id}` 🔒

---

### Samples

#### `GET /api/v1/samples`

List samples with optional filtering.

**Query Parameters:**
- `search` (string) - Filter by name or sample_id
- `status` (string) - Filter by status
- `lab_id` (int) - Filter by lab
- `project_id` (int) - Filter by project
- `page`, `per_page` - Pagination

#### `GET /api/v1/samples/{id}`

Get a single sample with full details.

#### `POST /api/v1/samples` 🔒

Create a new sample. **Requires authentication.**

**Request Body:**
```json
{
  "sample_id": "SAMPLE-001",
  "name": "Test Sample",
  "substrate": "Silicon",
  "project_id": 1,
  "lab_id": 1
}
```

**Required fields:** `sample_id`

#### `PATCH /api/v1/samples/{id}` 🔒
#### `DELETE /api/v1/samples/{id}` 🔒

---

### Scans

Scans are children of queues. When a queue is executed, it runs a series of scans.
Each scan belongs to a parent queue and contains measurement data.

#### `GET /api/v1/scans`

List scans with optional filtering.

**Query Parameters:**
- `search` (string) - Filter by scan_id or notes
- `status` (string) - Filter by status (`pending`, `running`, `completed`, `failed`, `aborted`)
- `sample_id` (int) - Filter by sample
- `queue_id` (int) - Filter by parent queue (scans belonging to a specific queue)
- `lab_id` (int) - Filter by lab
- `project_id` (int) - Filter by project
- `page`, `per_page` - Pagination

**Example - Get scans for a specific queue:**
```bash
# Get all scans belonging to queue #3
curl "http://localhost:5000/api/v1/scans?queue_id=3"

# Or use the nested endpoint
curl "http://localhost:5000/api/v1/queues/3/scans"
```

#### `GET /api/v1/scans/{id}`

Get a single scan with full details.

#### `POST /api/v1/scans` 🔒

Create a new scan. **Requires authentication.**

**Request Body:**
```json
{
  "sample_id": 1,
  "queue_id": 1,
  "scan_type": "IV Curve",
  "parameters": {
    "voltage_start": -1.0,
    "voltage_end": 1.0,
    "voltage_step": 0.01
  },
  "notes": "Initial characterization"
}
```

**Note:** The `queue_id` field links this scan to its parent queue.

#### `PATCH /api/v1/scans/{id}` 🔒

Update a scan.

#### `PATCH /api/v1/scans/{id}/status` 🔒

Update scan status. **Requires authentication.**

**Request Body:**
```json
{
  "status": "completed",
  "started_at": "2026-01-06T20:00:00.000Z",
  "completed_at": "2026-01-06T20:30:00.000Z",
  "error_message": null
}
```

Valid statuses: `pending`, `running`, `completed`, `failed`, `aborted`

#### `DELETE /api/v1/scans/{id}` 🔒

---

### Measurements

#### `GET /api/v1/scans/{scan_id}/measurements`

Get all measurement objects for a scan.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "scan_id": 1,
      "name": "IV_Curve",
      "data_type": "float",
      "unit": "A",
      "instrument_name": "Keithley 2400",
      "columns": ["voltage", "current"]
    }
  ]
}
```

#### `POST /api/v1/scans/{scan_id}/measurements` 🔒

Create a measurement object for a scan. **Requires authentication.**

**Request Body:**
```json
{
  "name": "IV_Curve",
  "data_type": "float",
  "unit": "A",
  "instrument_name": "Keithley 2400",
  "columns": ["voltage", "current"],
  "description": "Current-voltage measurement"
}
```

**Required fields:** `name`

#### `GET /api/v1/measurements/{measurement_id}/data`

Get data points for a measurement.

#### `POST /api/v1/measurements/{measurement_id}/data` 🔒

Submit data points for a measurement (bulk insert). **Requires authentication.**

**Request Body:**
```json
{
  "points": [
    {"values": {"voltage": -1.0, "current": -0.001}, "sequence_index": 0},
    {"values": {"voltage": -0.5, "current": -0.0005}, "sequence_index": 1},
    {"values": {"voltage": 0.0, "current": 0.0}, "sequence_index": 2},
    {"values": {"voltage": 0.5, "current": 0.0005}, "sequence_index": 3},
    {"values": {"voltage": 1.0, "current": 0.001}, "sequence_index": 4}
  ]
}
```

**Limits:**
- Maximum **10,000 points** per request
- For larger datasets, use multiple requests

**Response:**
```json
{
  "success": true,
  "data": {
    "count": 5,
    "measurement_id": 1
  }
}
```

---

### Queues

Queues are parent containers for scans. A queue represents an execution session
that can contain multiple child scans.

#### `GET /api/v1/queues`

List queues with optional filtering.

**Query Parameters:**
- `search` (string) - Filter by name
- `status` (string) - Filter by status
- `lab_id` (int) - Filter by lab
- `project_id` (int) - Filter by project
- `page`, `per_page` - Pagination

#### `GET /api/v1/queues/{id}`

Get a single queue by ID. **Includes child scans** in the response.

**Response includes:**
- Queue details
- `sample` - Associated sample (if any)
- `scans` - List of child scans belonging to this queue

#### `GET /api/v1/queues/{id}/scans`

List scans belonging to a queue (children of the queue).

**Query Parameters:**
- `search` (string) - Filter by scan name/ID
- `status` (string) - Filter by status
- `page`, `per_page` - Pagination

**Example:**
```bash
# Get all scans in queue #5
curl "http://localhost:5000/api/v1/queues/5/scans"
```

#### `POST /api/v1/queues` 🔒
#### `PATCH /api/v1/queues/{id}` 🔒

#### `PATCH /api/v1/queues/{id}/status` 🔒

Update queue status. **Requires authentication.**

**Request Body:**
```json
{
  "status": "running"
}
```

#### `DELETE /api/v1/queues/{id}` 🔒

---

### Equipment

#### `GET /api/v1/equipment`

List equipment with optional filtering.

**Query Parameters:**
- `search` (string) - Filter by name, manufacturer, model, description
- `status` (string) - Filter by status
- `type` (string) - Filter by equipment type
- `lab_id` (int) - Filter by lab
- `page`, `per_page` - Pagination

#### `GET /api/v1/equipment/{id}`
#### `POST /api/v1/equipment` 🔒
#### `PATCH /api/v1/equipment/{id}` 🔒
#### `DELETE /api/v1/equipment/{id}` 🔒

---

### Instruments

#### `GET /api/v1/instruments`

List instruments with optional filtering.

**Query Parameters:**
- `search` (string) - Filter by name, manufacturer, model, or pybirch_class
- `type` (string) - Filter by instrument type
- `status` (string) - Filter by status
- `lab_id` (int) - Filter by lab
- `page`, `per_page` - Pagination

#### `GET /api/v1/instruments/{id}`
#### `POST /api/v1/instruments` 🔒
#### `PATCH /api/v1/instruments/{id}` 🔒
#### `DELETE /api/v1/instruments/{id}` 🔒

---

### Precursors

#### `GET /api/v1/precursors`

**Query Parameters:**
- `search` (string) - Filter by name
- `type` (string) - Filter by precursor type
- `lab_id` (int) - Filter by lab
- `project_id` (int) - Filter by project
- `page`, `per_page` - Pagination

#### `GET /api/v1/precursors/{id}`
#### `POST /api/v1/precursors` 🔒
#### `PATCH /api/v1/precursors/{id}` 🔒
#### `DELETE /api/v1/precursors/{id}` 🔒

---

### Procedures

#### `GET /api/v1/procedures`

**Query Parameters:**
- `search` (string) - Filter by name or description
- `type` (string) - Filter by procedure type
- `lab_id` (int) - Filter by lab
- `project_id` (int) - Filter by project
- `page`, `per_page` - Pagination

#### `GET /api/v1/procedures/{id}`
#### `POST /api/v1/procedures` 🔒
#### `PATCH /api/v1/procedures/{id}` 🔒
#### `DELETE /api/v1/procedures/{id}` 🔒

**Note:** Deleting a procedure performs a soft delete (sets `is_active=false`).

---

### Fabrication Runs

#### `GET /api/v1/fabrication-runs`

List fabrication runs with optional filtering.

**Query Parameters:**
- `sample_id` (int) - Filter by sample
- `procedure_id` (int) - Filter by procedure
- `status` (string) - Filter by status
- `page`, `per_page` - Pagination

#### `GET /api/v1/fabrication-runs/{id}`
#### `POST /api/v1/fabrication-runs` 🔒

**Required fields:** `sample_id`, `procedure_id`

#### `PATCH /api/v1/fabrication-runs/{id}` 🔒

---

### Search

#### `GET /api/v1/search`

Global search across all entities.

**Query Parameters:**
- `q` (string, required) - Search query

**Response:**
```json
{
  "success": true,
  "data": {
    "samples": [...],
    "scans": [...],
    "queues": [...],
    "equipment": [...],
    "instruments": [...],
    "precursors": [...],
    "procedures": [...]
  }
}
```

---

## Python Client

A Python client library is available for easy API access. See [pybirch/api_client/](../../pybirch/api_client/) for full documentation.

### Quick Start

```python
from pybirch.api_client import PyBirchClient

# Initialize client (uses environment variables by default)
# PYBIRCH_API_URL=http://localhost:5000
# PYBIRCH_API_KEY=your-api-key (optional)
client = PyBirchClient()

# Or specify directly
client = PyBirchClient(
    base_url="http://localhost:5000",
    api_key="your-api-key"
)

# Health check
health = client.health_check()
print(f"Server status: {health['data']['status']}")

# List samples
result = client.samples.list(lab_id=1, page=1, per_page=50)
samples = result['data']
print(f"Found {result['meta']['total']} samples")

# Get single sample
sample = client.samples.get(sample_id=1)

# Create sample
new_sample = client.samples.create({
    "sample_id": "SAMPLE-001",
    "name": "Test Sample"
})

# Create scan with measurements
scan = client.scans.create({
    "sample_id": 1,
    "scan_type": "IV Curve"
})

measurement = client.scans.create_measurement(
    scan_id=scan['data']['id'],
    name="IV_Curve",
    unit="A",
    columns=["voltage", "current"]
)

# Submit data (auto-batched for large datasets)
data = [(v, v**2 * 0.001) for v in range(-100, 101)]  # Example data
client.measurements.create_data(
    measurement_id=measurement['data']['id'],
    points=[{"values": {"voltage": v/100, "current": i}} for v, i in data]
)

# Update scan status
client.scans.update_status(scan['data']['id'], status="completed")

# Global search
results = client.search("silicon")
```

### Exception Handling

```python
from pybirch.api_client import (
    PyBirchClient,
    APIError,
    NotFoundError,
    AuthenticationError,
    ValidationError,
    ConnectionError
)

client = PyBirchClient()

try:
    sample = client.samples.get(999)
except NotFoundError as e:
    print(f"Sample not found: {e.message}")
except AuthenticationError as e:
    print(f"Auth failed: {e.message}")
except ValidationError as e:
    print(f"Invalid data: {e.message}, details: {e.details}")
except ConnectionError as e:
    print(f"Cannot connect to server: {e.message}")
except APIError as e:
    print(f"API error [{e.code}]: {e.message}")
```

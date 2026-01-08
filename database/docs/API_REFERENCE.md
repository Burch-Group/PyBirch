# PyBirch Database API Reference

Complete API reference for the PyBirch Database module.

## Table of Contents

- [DatabaseService](#databaseservice)
- [Models](#models)
- [Session Management](#session-management)
- [Web Routes](#web-routes)

---

## DatabaseService

The main service class for all database operations.

### Constructor

```python
DatabaseService(db_path: Optional[str] = None)
```

**Parameters:**
- `db_path` - Path to SQLite database file or SQLAlchemy connection URL. If `None`, uses default `database/pybirch.db`.

**Example:**
```python
from database.services import DatabaseService

# Default database
db = DatabaseService()

# Custom path
db = DatabaseService("/path/to/mydb.db")

# PostgreSQL
db = DatabaseService("postgresql://user:pass@localhost/pybirch")
```

---

### Dashboard Methods

#### get_dashboard_stats

```python
get_dashboard_stats() -> Dict[str, Any]
```

Get statistics for the dashboard.

**Returns:** Dictionary with counts and recent activity:

```python
{
    'samples': {'total': int, 'active': int},
    'scans': {'total': int, 'completed': int, 'running': int},
    'queues': {'total': int, 'active': int},
    'instruments': {'total': int, 'available': int},
    'equipment': {'total': int, 'operational': int},
    'precursors': {'total': int},
    'procedures': {'total': int, 'active': int},
    'labs': {'total': int, 'active': int},
    'projects': {'total': int, 'active': int},
    'issues': {'total': int, 'open': int, 'in_progress': int},
    'recent_scans': List[Dict],
    'recent_samples': List[Dict],
    'open_issues': List[Dict],
    'open_equipment_issues': List[Dict],
}
```

---

### Lab Methods

#### get_labs

```python
get_labs(
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

Get paginated list of labs.

**Parameters:**
- `search` - Search term for name, university, department
- `page` - Page number (1-indexed)
- `per_page` - Items per page

**Returns:** Tuple of (labs list, total count)

#### get_lab

```python
get_lab(lab_id: int) -> Optional[Dict]
```

Get a single lab by ID.

**Returns:** Lab dictionary or `None` if not found.

**Lab Dictionary Structure:**
```python
{
    'id': int,
    'name': str,
    'code': Optional[str],
    'university': Optional[str],
    'department': Optional[str],
    'description': Optional[str],
    'address': Optional[str],
    'website': Optional[str],
    'email': Optional[str],
    'phone': Optional[str],
    'is_active': bool,
    'member_count': int,
    'project_count': int,
    'created_at': str,  # ISO format
}
```

#### create_lab

```python
create_lab(data: Dict[str, Any]) -> Dict
```

Create a new lab.

**Parameters:**
- `data` - Dictionary with lab fields

**Returns:** Created lab dictionary.

#### update_lab

```python
update_lab(lab_id: int, data: Dict) -> Optional[Dict]
```

Update an existing lab.

**Returns:** Updated lab dictionary or `None` if not found.

#### delete_lab

```python
delete_lab(lab_id: int) -> bool
```

Delete a lab.

**Returns:** `True` if deleted, `False` if not found.

---

### Lab Member Methods

#### get_lab_members

```python
get_lab_members(
    lab_id: int,
    role: Optional[str] = None,
    page: int = 1,
    per_page: int = 50
) -> Tuple[List[Dict], int]
```

Get members of a lab.

#### add_lab_member

```python
add_lab_member(lab_id: int, data: Dict) -> Dict
```

Add a member to a lab.

**Data Fields:**
- `name` (required) - Member name
- `email` - Email address
- `role` - One of: `principal_investigator`, `administrator`, `member`, `student`, `visiting`
- `title` - Job title
- `notes` - Additional notes

#### update_lab_member

```python
update_lab_member(member_id: int, data: Dict) -> Optional[Dict]
```

#### remove_lab_member

```python
remove_lab_member(member_id: int) -> bool
```

---

### Project Methods

#### get_projects

```python
get_projects(
    search: Optional[str] = None,
    status: Optional[str] = None,
    lab_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

**Status Values:** `planning`, `active`, `paused`, `completed`, `archived`

#### get_project

```python
get_project(project_id: int) -> Optional[Dict]
```

**Project Dictionary Structure:**
```python
{
    'id': int,
    'name': str,
    'code': Optional[str],
    'description': Optional[str],
    'status': str,
    'start_date': Optional[str],
    'end_date': Optional[str],
    'funding_source': Optional[str],
    'grant_number': Optional[str],
    'budget': Optional[float],
    'goals': Optional[str],
    'lab_id': Optional[int],
    'lab_name': Optional[str],
    'member_count': int,
    'sample_count': int,
    'created_at': str,
}
```

#### create_project / update_project / delete_project

Standard CRUD signatures.

---

### Sample Methods

#### get_samples

```python
get_samples(
    search: Optional[str] = None,
    status: Optional[str] = None,
    material: Optional[str] = None,
    lab_id: Optional[int] = None,
    project_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

**Status Values:** `active`, `consumed`, `archived`

#### get_sample

```python
get_sample(sample_id: int) -> Optional[Dict]
```

**Sample Dictionary Structure:**
```python
{
    'id': int,
    'sample_id': str,  # User-friendly ID
    'name': Optional[str],
    'material': Optional[str],
    'sample_type': Optional[str],
    'substrate': Optional[str],
    'dimensions': Optional[Dict],
    'status': str,
    'storage_location': Optional[str],
    'description': Optional[str],
    'lab_id': Optional[int],
    'lab_name': Optional[str],
    'project_id': Optional[int],
    'project_name': Optional[str],
    'parent_sample_id': Optional[int],
    'created_at': str,
    'created_by': Optional[str],
    'scan_count': int,
    'fabrication_run_count': int,
}
```

#### create_sample

```python
create_sample(data: Dict[str, Any]) -> Dict
```

**Required Fields:**
- `sample_id` - Unique identifier string

#### update_sample / delete_sample

Standard CRUD signatures.

---

### Equipment Methods

#### get_equipment_list

```python
get_equipment_list(
    search: Optional[str] = None,
    status: Optional[str] = None,
    equipment_type: Optional[str] = None,
    lab_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

**Status Values:** `operational`, `maintenance`, `offline`, `retired`

**Equipment Types:** `glovebox`, `chamber`, `lithography`, `furnace`, `other`

#### get_equipment

```python
get_equipment(equipment_id: int) -> Optional[Dict]
```

**Equipment Dictionary Structure:**
```python
{
    'id': int,
    'name': str,
    'equipment_type': Optional[str],
    'description': Optional[str],
    'manufacturer': Optional[str],
    'model': Optional[str],
    'serial_number': Optional[str],
    'location': Optional[str],
    'room': Optional[str],
    'status': str,
    'owner_id': Optional[int],
    'owner_name': Optional[str],
    'lab_id': Optional[int],
    'lab_name': Optional[str],
    'purchase_date': Optional[str],
    'warranty_expiration': Optional[str],
    'last_maintenance_date': Optional[str],
    'next_maintenance_date': Optional[str],
    'specifications': Optional[Dict],
    'documentation_url': Optional[str],
    'issue_count': int,
    'open_issue_count': int,
}
```

#### create_equipment / update_equipment / delete_equipment

Standard CRUD signatures.

---

### Equipment Issue Methods

#### get_equipment_issues

```python
get_equipment_issues(
    equipment_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    assignee_id: Optional[int] = None,
    reporter_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

**Status Values:** `open`, `in_progress`, `resolved`, `closed`, `wont_fix`

**Priority Values:** `low`, `medium`, `high`, `critical`

**Category Values:** `malfunction`, `maintenance`, `safety`, `consumables`, `other`

#### get_equipment_issue

```python
get_equipment_issue(issue_id: int) -> Optional[Dict]
```

#### create_equipment_issue

```python
create_equipment_issue(data: Dict[str, Any]) -> Dict
```

**Required Fields:**
- `equipment_id` - Equipment ID
- `title` - Issue title

**Optional Fields:**
- `description`, `category`, `priority`, `status`
- `reporter_id`, `assignee_id`
- `error_message`, `steps_to_reproduce`

#### update_equipment_issue

```python
update_equipment_issue(issue_id: int, data: Dict) -> Optional[Dict]
```

---

### Instrument Methods

#### get_instruments

```python
get_instruments(
    search: Optional[str] = None,
    status: Optional[str] = None,
    instrument_type: Optional[str] = None,
    lab_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

**Status Values:** `available`, `in_use`, `maintenance`, `retired`

**Instrument Types:** `movement`, `measurement`, `fabrication`

#### get_instrument

```python
get_instrument(instrument_id: int) -> Optional[Dict]
```

**Instrument Dictionary Structure:**
```python
{
    'id': int,
    'name': str,
    'instrument_type': Optional[str],
    'pybirch_class': Optional[str],
    'manufacturer': Optional[str],
    'model': Optional[str],
    'serial_number': Optional[str],
    'adapter': Optional[str],  # VISA address
    'location': Optional[str],
    'status': str,
    'lab_id': Optional[int],
    'equipment_id': Optional[int],
    'calibration_date': Optional[str],
    'next_calibration_date': Optional[str],
    'specifications': Optional[Dict],
}
```

---

### Precursor Methods

#### get_precursors

```python
get_precursors(
    search: Optional[str] = None,
    status: Optional[str] = None,
    lab_id: Optional[int] = None,
    project_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

**Status Values:** `new`, `in_use`, `low`, `empty`, `expired`

#### get_precursor

```python
get_precursor(precursor_id: int) -> Optional[Dict]
```

**Precursor Dictionary Structure:**
```python
{
    'id': int,
    'name': str,
    'chemical_formula': Optional[str],
    'cas_number': Optional[str],
    'supplier': Optional[str],
    'lot_number': Optional[str],
    'purity': Optional[float],
    'state': Optional[str],  # solid, liquid, gas, solution
    'status': str,
    'concentration': Optional[float],
    'concentration_unit': Optional[str],
    'storage_conditions': Optional[str],
    'expiration_date': Optional[str],
    'safety_info': Optional[str],
    'lab_id': Optional[int],
    'project_id': Optional[int],
}
```

---

### Procedure Methods

#### get_procedures

```python
get_procedures(
    search: Optional[str] = None,
    procedure_type: Optional[str] = None,
    lab_id: Optional[int] = None,
    project_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

#### get_procedure

```python
get_procedure(procedure_id: int) -> Optional[Dict]
```

**Procedure Dictionary Structure:**
```python
{
    'id': int,
    'name': str,
    'procedure_type': Optional[str],
    'version': str,
    'description': Optional[str],
    'steps': Optional[List[Dict]],
    'parameters': Optional[Dict],
    'estimated_duration_minutes': Optional[int],
    'safety_requirements': Optional[str],
    'is_active': bool,
    'lab_id': Optional[int],
    'project_id': Optional[int],
    'equipment': List[Dict],  # Linked equipment
    'precursors': List[Dict],  # Linked precursors
    'created_by': Optional[str],
    'created_at': str,
}
```

---

### Scan & Queue Methods

#### get_scans

```python
get_scans(
    sample_id: Optional[int] = None,
    queue_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

**Status Values:** `pending`, `running`, `paused`, `completed`, `failed`, `aborted`

#### get_scan

```python
get_scan(scan_id: int) -> Optional[Dict]
```

#### get_queues

```python
get_queues(
    sample_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]
```

#### get_queue

```python
get_queue(queue_id: int) -> Optional[Dict]
```

---

### User Methods

#### get_user

```python
get_user(user_id: int) -> Optional[Dict]
```

#### get_user_by_email

```python
get_user_by_email(email: str) -> Optional[Dict]
```

#### get_user_by_google_id

```python
get_user_by_google_id(google_id: str) -> Optional[Dict]
```

#### create_user

```python
create_user(data: Dict[str, Any]) -> Dict
```

#### update_user

```python
update_user(user_id: int, data: Dict) -> Optional[Dict]
```

---

### Search Methods

#### search_all

```python
search_all(
    query: str,
    entity_types: Optional[List[str]] = None,
    lab_id: Optional[int] = None,
    project_id: Optional[int] = None,
    limit_per_type: int = 10
) -> Dict[str, List[Dict]]
```

Search across all entity types.

**Parameters:**
- `query` - Search string
- `entity_types` - List of types to search: `samples`, `equipment`, `precursors`, `procedures`, `scans`, `queues`
- `lab_id` - Filter by lab
- `project_id` - Filter by project
- `limit_per_type` - Max results per entity type

**Returns:**
```python
{
    'samples': [...],
    'equipment': [...],
    'precursors': [...],
    'procedures': [...],
    'scans': [...],
    'queues': [...],
    'totals': {
        'samples': int,
        'equipment': int,
        ...
    }
}
```

---

### Pin Methods

#### toggle_pin

```python
toggle_pin(user_id: int, entity_type: str, entity_id: int) -> bool
```

Toggle pin status for an entity.

**Returns:** `True` if now pinned, `False` if unpinned.

#### get_user_pins

```python
get_user_pins(user_id: int, entity_type: Optional[str] = None) -> List[Dict]
```

Get user's pinned items.

#### is_pinned

```python
is_pinned(user_id: int, entity_type: str, entity_id: int) -> bool
```

Check if entity is pinned by user.

---

## Models

All models are defined in `database/models.py`. See [Database Models](DEVELOPER_GUIDE.md#database-models) in the Developer Guide for detailed documentation.

### Model Import

```python
from database.models import (
    Base,
    Lab, LabMember, Project, ProjectMember,
    User, UserPin,
    Sample, SamplePrecursor,
    Equipment, EquipmentImage, EquipmentIssue,
    Instrument,
    Precursor, PrecursorInventory,
    Procedure, ProcedureEquipment, ProcedurePrecursor,
    FabricationRun, FabricationRunEquipment, FabricationRunPrecursor,
    Queue, QueueLog, Scan, MeasurementDataPoint,
    Template, Issue, Tag, EntityTag,
)
```

---

## Session Management

### DatabaseManager

```python
from database.session import DatabaseManager, get_session, init_db

# Initialize database
init_db("sqlite:///path/to/db.sqlite")

# Get session context manager
with get_session() as session:
    samples = session.query(Sample).all()
```

### Thread Safety

The session manager uses `scoped_session` for thread-local sessions, making it safe for concurrent access from Flask and Qt.

---

## Web Routes

### Route Reference

| Route | Method | Handler | Description |
|-------|--------|---------|-------------|
| `/` | GET | `index` | Dashboard |
| `/login` | GET | `login` | Initiate OAuth |
| `/logout` | GET | `logout` | End session |
| `/profile` | GET, POST | `profile` | User profile |
| `/samples` | GET | `samples` | List samples |
| `/samples/<id>` | GET | `sample_detail` | Sample detail |
| `/samples/new` | GET, POST | `sample_new` | Create sample |
| `/samples/<id>/edit` | GET, POST | `sample_edit` | Edit sample |
| `/samples/<id>/delete` | POST | `sample_delete` | Delete sample |
| `/equipment` | GET | `equipment` | List equipment |
| `/equipment/<id>` | GET | `equipment_detail` | Equipment detail |
| `/equipment/<id>/issues` | GET | `equipment_issues` | Equipment issues |
| `/equipment/<id>/issues/new` | GET, POST | `equipment_issue_new` | Report issue |
| `/precursors` | GET | `precursors` | List precursors |
| `/procedures` | GET | `procedures` | List procedures |
| `/procedures/<id>/start` | GET, POST | `start_procedure` | Start fabrication |
| `/scans` | GET | `scans` | List scans |
| `/scans/<id>` | GET | `scan_detail` | Scan detail |
| `/queues` | GET | `queues` | List queues |
| `/queues/<id>` | GET | `queue_detail` | Queue detail |
| `/labs` | GET | `labs` | List labs |
| `/projects` | GET | `projects` | List projects |
| `/search` | GET | `search` | Simple search |
| `/search/advanced` | GET | `advanced_search` | Advanced search |
| `/api/pin` | POST | `toggle_pin_api` | Toggle pin (AJAX) |

---

*Last updated: January 2026*

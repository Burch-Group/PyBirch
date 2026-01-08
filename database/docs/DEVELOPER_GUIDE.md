# PyBirch Database Developer Guide

A comprehensive guide for developers working with the PyBirch Database module.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Models](#database-models)
4. [Services Layer](#services-layer)
5. [Web Interface](#web-interface)
6. [API Reference](#api-reference)
7. [Development Workflow](#development-workflow)
8. [Testing](#testing)

---

## Overview

PyBirch Database is a laboratory information management system (LIMS) built with SQLAlchemy ORM and Flask. It provides:

- **Data persistence** for PyBirch measurement sessions
- **Web-based UI** for browsing and managing laboratory data
- **REST-like routes** for CRUD operations
- **OAuth authentication** via Google
- **Integration hooks** for PyBirch Qt application
- **Database flexibility** with SQLite (development) or PostgreSQL (production)

### Key Design Principles

1. **Separation of Concerns**: Models → Services → Routes → Templates
2. **Thread Safety**: Session-per-request pattern for Flask/Qt compatibility
3. **Extensibility**: Template system for custom entity types
4. **Traceability**: Full audit trail for sample fabrication history

---

## Architecture

```
database/
├── models.py           # SQLAlchemy ORM models
├── services.py         # Business logic layer
├── session.py          # Database connection management
├── crud.py             # Legacy CRUD operations (deprecated)
├── extension.py        # PyBirch scan extension
├── run_web.py          # Web server entry point
├── utils.py            # Helper utilities
├── weather.py          # Weather API integration
├── uri_handler.py      # pybirch:// URI scheme
├── migrations/         # Database migrations
└── web/
    ├── app.py          # Flask application factory
    ├── routes.py       # URL route handlers
    ├── static/         # CSS, JS, images
    └── templates/      # Jinja2 HTML templates
```

### Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Flask     │     │  Services    │     │  SQLAlchemy │
│   Routes    │────▶│  Layer       │────▶│  Session    │
└─────────────┘     └──────────────┘     └─────────────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Jinja2    │     │  Dict        │     │  SQLite/    │
│   Templates │◀────│  Responses   │◀────│  PostgreSQL │
└─────────────┘     └──────────────┘     └─────────────┘
```

### Database Configuration

PyBirch supports both SQLite (default) and PostgreSQL:

| Database | Best For | Configuration |
|----------|----------|---------------|
| SQLite | Development, single-user, low concurrency | Default (no config needed) |
| PostgreSQL | Production, multi-user, high concurrency | Set `DATABASE_URL` env var |

**SQLite Optimizations** (automatic):
- WAL mode for better concurrent reads
- 64MB cache for faster queries
- 5 second busy timeout for lock contention

**PostgreSQL Connection Pooling** (automatic):
- 10 base connections with 20 overflow
- Connection health checks before use
- 1-hour connection recycling

---

## Database Models

All models inherit from `sqlalchemy.orm.DeclarativeBase` and are defined in `models.py`.

### Entity Relationship Diagram

```
┌─────────┐       ┌──────────┐       ┌─────────┐
│   Lab   │──────▶│  Project │◀──────│  Sample │
└─────────┘       └──────────┘       └─────────┘
     │                  │                  │
     ▼                  ▼                  ▼
┌─────────┐       ┌──────────┐       ┌─────────┐
│LabMember│       │Procedure │◀──────│Fab.Run  │
└─────────┘       └──────────┘       └─────────┘
                       │
                       ▼
              ┌──────────────┐
              │  Equipment   │
              │  Precursor   │
              └──────────────┘
```

### Core Models

#### Organizational Hierarchy

| Model | Description | Key Fields |
|-------|-------------|------------|
| `Lab` | Research laboratory | `name`, `university`, `department`, `is_active` |
| `LabMember` | Lab personnel | `name`, `email`, `role`, `title` |
| `Project` | Research project | `name`, `status`, `funding_source`, `lab_id` |
| `ProjectMember` | Project assignment | `project_id`, `lab_member_id`, `role` |

#### Sample Management

| Model | Description | Key Fields |
|-------|-------------|------------|
| `Sample` | Physical sample | `sample_id`, `material`, `status`, `lab_id`, `project_id` |
| `FabricationRun` | Procedure execution | `sample_id`, `procedure_id`, `status`, `actual_parameters` |
| `SamplePrecursor` | Junction table | `sample_id`, `precursor_id`, `quantity_used` |

#### Equipment & Instruments

| Model | Description | Key Fields |
|-------|-------------|------------|
| `Equipment` | Large equipment | `name`, `equipment_type`, `status`, `owner_id` |
| `Instrument` | PyBirch devices | `name`, `instrument_type`, `pybirch_class`, `adapter` |
| `EquipmentIssue` | Issue tracking | `equipment_id`, `title`, `priority`, `status` |

#### Measurement System

| Model | Description | Key Fields |
|-------|-------------|------------|
| `Queue` | Scan queue | `name`, `sample_id`, `status`, `execution_mode` |
| `Scan` | Single scan | `queue_id`, `scan_name`, `status`, `data_file` |
| `MeasurementDataPoint` | Raw data | `scan_id`, `point_index`, `raw_data` |

### Model Conventions

```python
class Sample(Base):
    """
    Physical samples on which scans are run.
    
    Attributes:
        id: Primary key (auto-increment)
        sample_id: User-friendly identifier (unique)
        material: Chemical composition
        status: Lifecycle state ('active', 'consumed', 'archived')
        created_at: Creation timestamp (auto-set)
        updated_at: Last modification (auto-updated)
    
    Relationships:
        lab: Parent Lab (many-to-one)
        project: Parent Project (many-to-one)
        scans: Associated Scans (one-to-many)
        fabrication_runs: Fabrication history (one-to-many)
    """
    __tablename__ = "samples"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # ... additional fields
```

### Status Enumerations

Models use string-based status fields for flexibility:

| Entity | Statuses |
|--------|----------|
| Sample | `active`, `consumed`, `archived` |
| Equipment | `operational`, `maintenance`, `offline`, `retired` |
| Instrument | `available`, `in_use`, `maintenance`, `retired` |
| Project | `planning`, `active`, `paused`, `completed`, `archived` |
| Issue | `open`, `in_progress`, `resolved`, `closed`, `wont_fix` |
| Queue/Scan | `pending`, `running`, `paused`, `completed`, `failed`, `aborted` |

---

## Services Layer

The `DatabaseService` class in `services.py` provides the business logic layer. It abstracts database operations and ensures thread-safe access.

### Initialization

```python
from database.services import DatabaseService

# Default: Uses DATABASE_URL env var, or SQLite in database folder
db = DatabaseService()

# Custom SQLite path
db = DatabaseService(db_path="/path/to/database.db")

# PostgreSQL (recommended for production)
db = DatabaseService(db_path="postgresql://user:pass@localhost:5432/pybirch")
```

**Environment Variable Configuration:**

```bash
# Set once, used automatically
export DATABASE_URL="postgresql://user:pass@localhost:5432/pybirch"

# Then just use default initialization
from database.services import DatabaseService
db = DatabaseService()  # Uses DATABASE_URL
```

### Session Management

The service uses context managers for transaction handling:

```python
class DatabaseService:
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for a series of operations."""
        with get_session() as session:
            yield session
```

### Service Method Patterns

All service methods follow consistent patterns:

#### Query Methods (GET)

```python
def get_samples(
    self,
    search: Optional[str] = None,
    status: Optional[str] = None,
    lab_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20
) -> Tuple[List[Dict], int]:
    """
    Get paginated list of samples with optional filtering.
    
    Args:
        search: Text search across name, sample_id, material
        status: Filter by status
        lab_id: Filter by lab
        page: Page number (1-indexed)
        per_page: Items per page
    
    Returns:
        Tuple of (samples list, total count)
    """
    with self.session_scope() as session:
        query = session.query(Sample)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(or_(
                Sample.name.ilike(search_term),
                Sample.sample_id.ilike(search_term),
                Sample.material.ilike(search_term)
            ))
        
        if status:
            query = query.filter(Sample.status == status)
            
        total = query.count()
        samples = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return [self._sample_to_dict(s) for s in samples], total
```

#### Single Entity Methods

```python
def get_sample(self, sample_id: int) -> Optional[Dict]:
    """Get a single sample by ID."""
    with self.session_scope() as session:
        sample = session.query(Sample).filter(Sample.id == sample_id).first()
        return self._sample_to_dict(sample) if sample else None
```

#### Create Methods

```python
def create_sample(self, data: Dict[str, Any]) -> Dict:
    """
    Create a new sample.
    
    Args:
        data: Dictionary with sample fields
        
    Returns:
        Created sample as dictionary
        
    Raises:
        IntegrityError: If sample_id already exists
    """
    with self.session_scope() as session:
        sample = Sample(**data)
        session.add(sample)
        session.flush()  # Get ID before commit
        return self._sample_to_dict(sample)
```

#### Update Methods

```python
def update_sample(self, sample_id: int, data: Dict) -> Optional[Dict]:
    """
    Update an existing sample.
    
    Args:
        sample_id: Database ID
        data: Fields to update
        
    Returns:
        Updated sample or None if not found
    """
    with self.session_scope() as session:
        sample = session.query(Sample).filter(Sample.id == sample_id).first()
        if not sample:
            return None
        
        for field, value in data.items():
            if hasattr(sample, field):
                setattr(sample, field, value)
        
        return self._sample_to_dict(sample)
```

#### Delete Methods

```python
def delete_sample(self, sample_id: int) -> bool:
    """
    Delete a sample.
    
    Args:
        sample_id: Database ID
        
    Returns:
        True if deleted, False if not found
    """
    with self.session_scope() as session:
        sample = session.query(Sample).filter(Sample.id == sample_id).first()
        if not sample:
            return False
        session.delete(sample)
        return True
```

### Dictionary Conversion

Models are converted to dictionaries for JSON serialization:

```python
def _sample_to_dict(self, sample: Sample) -> Dict:
    """Convert Sample model to dictionary."""
    return {
        'id': sample.id,
        'sample_id': sample.sample_id,
        'name': sample.name,
        'material': sample.material,
        'status': sample.status,
        'lab_id': sample.lab_id,
        'lab_name': sample.lab.name if sample.lab else None,
        'project_id': sample.project_id,
        'project_name': sample.project.name if sample.project else None,
        'created_at': sample.created_at.isoformat() if sample.created_at else None,
        # ... additional fields
    }
```

---

## Web Interface

The Flask web application is defined in `web/app.py` with routes in `web/routes.py`.

### Application Factory

```python
def create_app(config: Optional[Dict] = None) -> Flask:
    """
    Create and configure the Flask application.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get('database_url')
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    # Context processors
    @app.context_processor
    def inject_globals():
        return {
            'current_user': get_current_user(),
            'app_name': 'PyBirch Database',
        }
    
    return app
```

### Route Organization

Routes are organized by entity type:

```python
# Blueprint registration
main_bp = Blueprint('main', __name__)

# Dashboard
@main_bp.route('/')
def index():
    """Dashboard with statistics and recent activity."""
    
# Samples CRUD
@main_bp.route('/samples')
def samples():
    """List all samples with filtering."""
    
@main_bp.route('/samples/<int:sample_id>')
def sample_detail(sample_id):
    """View single sample details."""
    
@main_bp.route('/samples/new', methods=['GET', 'POST'])
def sample_new():
    """Create new sample form."""
    
@main_bp.route('/samples/<int:sample_id>/edit', methods=['GET', 'POST'])
def sample_edit(sample_id):
    """Edit existing sample."""
```

### URL Patterns

| Pattern | Method | Description |
|---------|--------|-------------|
| `/samples` | GET | List with pagination/filtering |
| `/samples/<id>` | GET | Detail view |
| `/samples/new` | GET, POST | Create form |
| `/samples/<id>/edit` | GET, POST | Edit form |
| `/samples/<id>/delete` | POST | Delete action |

### Template Structure

Templates use Jinja2 inheritance:

```
templates/
├── base.html              # Base layout with navigation
├── index.html             # Dashboard
├── samples.html           # Sample list
├── sample_detail.html     # Sample detail view
├── sample_form.html       # Create/edit form
└── ...
```

#### Base Template

```html
<!-- base.html -->
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}PyBirch Database{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">
            <a href="{{ url_for('main.index') }}">PyBirch Database</a>
        </div>
        <div class="nav-links">
            <a href="{{ url_for('main.samples') }}">Samples</a>
            <a href="{{ url_for('main.equipment') }}">Equipment</a>
            <!-- ... -->
        </div>
    </nav>
    
    <main class="content">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

### Authentication

Google OAuth is used for authentication:

```python
from authlib.integrations.flask_client import OAuth

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    # ...
)

@main_bp.route('/login')
def login():
    redirect_uri = url_for('main.auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@main_bp.route('/auth/callback')
def auth_callback():
    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()
    # Create or update user...
```

---

## API Reference

### DatabaseService Methods

#### Dashboard

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_dashboard_stats()` | - | `Dict` | Statistics for all entities |

#### Labs

| Method | Parameters | Returns |
|--------|------------|---------|
| `get_labs(search, page, per_page)` | Optional filters | `Tuple[List[Dict], int]` |
| `get_lab(lab_id)` | `int` | `Optional[Dict]` |
| `create_lab(data)` | `Dict` | `Dict` |
| `update_lab(lab_id, data)` | `int`, `Dict` | `Optional[Dict]` |
| `delete_lab(lab_id)` | `int` | `bool` |

#### Samples

| Method | Parameters | Returns |
|--------|------------|---------|
| `get_samples(search, status, lab_id, project_id, page, per_page)` | Filters | `Tuple[List[Dict], int]` |
| `get_sample(sample_id)` | `int` | `Optional[Dict]` |
| `create_sample(data)` | `Dict` | `Dict` |
| `update_sample(sample_id, data)` | `int`, `Dict` | `Optional[Dict]` |
| `delete_sample(sample_id)` | `int` | `bool` |

#### Equipment

| Method | Parameters | Returns |
|--------|------------|---------|
| `get_equipment_list(search, status, equipment_type, page, per_page)` | Filters | `Tuple[List[Dict], int]` |
| `get_equipment(equipment_id)` | `int` | `Optional[Dict]` |
| `create_equipment(data)` | `Dict` | `Dict` |
| `update_equipment(equipment_id, data)` | `int`, `Dict` | `Optional[Dict]` |

#### Procedures

| Method | Parameters | Returns |
|--------|------------|---------|
| `get_procedures(search, procedure_type, lab_id, page, per_page)` | Filters | `Tuple[List[Dict], int]` |
| `get_procedure(procedure_id)` | `int` | `Optional[Dict]` |
| `create_procedure(data)` | `Dict` | `Dict` |

#### Scans & Queues

| Method | Parameters | Returns |
|--------|------------|---------|
| `get_scans(sample_id, status, page, per_page)` | Filters | `Tuple[List[Dict], int]` |
| `get_scan(scan_id)` | `int` | `Optional[Dict]` |
| `create_scan(data)` | `Dict` | `Dict` |
| `update_scan_status(scan_id, status)` | `int`, `str` | `bool` |

---

## Development Workflow

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/Burch-Group/PyBirch.git
cd PyBirch

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -e .
pip install -r requirements-dev.txt
```

### Running the Development Server

```bash
# SQLite (default - no setup needed)
cd database
python run_web.py --debug --port 5000

# PostgreSQL (set environment variable first)
export DATABASE_URL="postgresql://user:pass@localhost:5432/pybirch"
python run_web.py --debug --port 5000
```

### Setting Up PostgreSQL

1. **Install PostgreSQL** (or use Docker):
   ```bash
   # Docker option
   docker run -d --name pybirch-postgres \
     -e POSTGRES_PASSWORD=pybirch \
     -e POSTGRES_DB=pybirch \
     -p 5432:5432 postgres:15
   ```

2. **Migrate existing data** (optional):
   ```bash
   python -m database.migrations.migrate_to_postgresql \
     --postgres-url "postgresql://postgres:pybirch@localhost:5432/pybirch"
   ```

3. **Set environment variable**:
   ```bash
   export DATABASE_URL="postgresql://postgres:pybirch@localhost:5432/pybirch"
   ```

### Database Migrations

When modifying models, create a database-agnostic migration:

```python
# migrations/add_new_column.py
"""Add new column to samples table."""

from sqlalchemy import text, inspect
from database.session import DatabaseManager


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if column exists (works with SQLite and PostgreSQL)."""
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    
    with db.session() as session:
        if not column_exists(inspector, 'samples', 'new_column'):
            session.execute(text('ALTER TABLE samples ADD COLUMN new_column TEXT'))
            session.commit()
            print('Added new_column to samples')
        else:
            print('new_column already exists')


def downgrade():
    db = DatabaseManager(create_tables=False)
    
    # PostgreSQL supports DROP COLUMN
    if db._is_postgresql:
        with db.session() as session:
            session.execute(text('ALTER TABLE samples DROP COLUMN IF EXISTS new_column'))
            session.commit()
    else:
        print('SQLite: Column remains but will be ignored')


if __name__ == '__main__':
    upgrade()
```

**Key Migration Tools:**

| Script | Purpose |
|--------|--------|
| `migrate_to_postgresql.py` | Full SQLite → PostgreSQL data migration |
| `add_equipment_columns.py` | Add equipment management columns |
| `add_lab_to_all_objects.py` | Add lab_id to all entities |

### Adding a New Entity

1. **Define the model** in `models.py`:

```python
class NewEntity(Base):
    __tablename__ = "new_entities"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ... fields
```

2. **Add service methods** in `services.py`:

```python
def get_new_entities(self, ...) -> Tuple[List[Dict], int]:
    ...

def get_new_entity(self, entity_id: int) -> Optional[Dict]:
    ...

def create_new_entity(self, data: Dict) -> Dict:
    ...

def _new_entity_to_dict(self, entity) -> Dict:
    ...
```

3. **Create routes** in `routes.py`:

```python
@main_bp.route('/new-entities')
def new_entities():
    ...

@main_bp.route('/new-entities/<int:entity_id>')
def new_entity_detail(entity_id):
    ...
```

4. **Create templates**:
   - `new_entities.html` (list view)
   - `new_entity_detail.html` (detail view)
   - `new_entity_form.html` (create/edit form)

---

## Testing

### Running Tests

```bash
pytest tests/test_database.py -v
```

### Test Structure

```python
# tests/test_database.py

import pytest
from database.services import DatabaseService

@pytest.fixture
def db_service():
    """Create in-memory database for testing."""
    return DatabaseService(db_path="sqlite:///:memory:")

def test_create_sample(db_service):
    """Test sample creation."""
    sample = db_service.create_sample({
        'sample_id': 'TEST-001',
        'material': 'Silicon',
        'status': 'active'
    })
    
    assert sample['sample_id'] == 'TEST-001'
    assert sample['id'] is not None

def test_get_sample(db_service):
    """Test sample retrieval."""
    created = db_service.create_sample({
        'sample_id': 'TEST-002',
        'material': 'GaAs'
    })
    
    retrieved = db_service.get_sample(created['id'])
    
    assert retrieved is not None
    assert retrieved['material'] == 'GaAs'
```

---

## Appendix

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session encryption key | `dev-key` |
| `DATABASE_URL` | Database connection URL | SQLite in `database/pybirch.db` |
| `GOOGLE_CLIENT_ID` | OAuth client ID | - |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | - |
| `OPENWEATHER_API_KEY` | Weather API key | - |

**DATABASE_URL Format:**

```bash
# SQLite
DATABASE_URL="sqlite:///path/to/database.db"

# PostgreSQL
DATABASE_URL="postgresql://username:password@hostname:5432/database_name"

# PostgreSQL with SSL (cloud providers)
DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=require"
```

**Note:** Heroku-style `postgres://` URLs are automatically converted to `postgresql://`.

### URI Scheme

PyBirch supports a custom URI scheme for opening scans/queues:

```
pybirch://scan/{scan_id}
pybirch://queue/{queue_id}
```

Register the handler:

```bash
python -m database.register_uri_scheme
```

---

*Last updated: January 2026*

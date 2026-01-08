# PyBirch Database Architecture

This document describes the high-level architecture of the PyBirch Database module.

## System Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           PyBirch Application                               │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────┐              ┌─────────────────┐                     │
│  │   PyBirch Qt    │              │   Flask Web     │                     │
│  │   Application   │              │   Interface     │                     │
│  │                 │              │                 │                     │
│  │  - Scan Control │              │  - CRUD Forms   │                     │
│  │  - Queue Mgmt   │              │  - Dashboard    │                     │
│  │  - Instruments  │              │  - Search       │                     │
│  └────────┬────────┘              └────────┬────────┘                     │
│           │                                │                               │
│           └──────────────┬─────────────────┘                               │
│                          ▼                                                 │
│              ┌───────────────────────┐                                    │
│              │   DatabaseService     │                                    │
│              │   (services.py)       │                                    │
│              │                       │                                    │
│              │  - Business Logic     │                                    │
│              │  - Data Validation    │                                    │
│              │  - Query Building     │                                    │
│              └───────────┬───────────┘                                    │
│                          │                                                 │
│                          ▼                                                 │
│              ┌───────────────────────┐                                    │
│              │   Session Manager     │                                    │
│              │   (session.py)        │                                    │
│              │                       │                                    │
│              │  - Connection Pool    │                                    │
│              │  - Thread Safety      │                                    │
│              │  - Transactions       │                                    │
│              └───────────┬───────────┘                                    │
│                          │                                                 │
│                          ▼                                                 │
│              ┌───────────────────────┐                                    │
│              │   SQLAlchemy ORM      │                                    │
│              │   (models.py)         │                                    │
│              │                       │                                    │
│              │  - Model Definitions  │                                    │
│              │  - Relationships      │                                    │
│              │  - Indexes            │                                    │
│              └───────────┬───────────┘                                    │
│                          │                                                 │
└──────────────────────────┼─────────────────────────────────────────────────┘
                           │
                           ▼
              ┌───────────────────────┐
              │   SQLite / PostgreSQL │
              │                       │
              │   pybirch.db          │
              └───────────────────────┘
```

## Layer Responsibilities

### 1. Presentation Layer

#### Flask Web Interface (`web/`)

- **routes.py**: URL routing and request handling
- **templates/**: Jinja2 HTML templates
- **static/**: CSS, JavaScript, images

Responsibilities:
- Handle HTTP requests and responses
- Render HTML templates
- Form validation and CSRF protection
- Session management and authentication
- Flash messages for user feedback

#### PyBirch Qt Application

- Direct integration via `DatabaseService`
- Scan/Queue result persistence
- Equipment status updates

### 2. Business Logic Layer (`services.py`)

The `DatabaseService` class encapsulates all business operations:

```python
class DatabaseService:
    """
    High-level database service providing business operations.
    Thread-safe for use with Flask and Qt concurrently.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize with optional custom database path."""
        
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for operations."""
```

Responsibilities:
- Implement business rules
- Coordinate complex operations
- Convert models to dictionaries
- Handle pagination and filtering
- Aggregate related data

### 3. Data Access Layer (`session.py`)

The `DatabaseManager` class manages database connections:

```python
class DatabaseManager:
    """
    Manages database connections and sessions for PyBirch.
    
    Supports both SQLite (default) and PostgreSQL.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize engine and session factory."""
```

Responsibilities:
- Connection pooling
- Session lifecycle management
- Thread-local session scope
- Transaction boundaries

### 4. Domain Model Layer (`models.py`)

SQLAlchemy ORM models define the data structure:

```python
class Sample(Base):
    __tablename__ = "samples"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sample_id: Mapped[str] = mapped_column(String(100), unique=True)
    # ... fields and relationships
```

Responsibilities:
- Schema definition
- Relationship mapping
- Constraints and indexes
- Data type conversion

## Design Patterns

### Repository Pattern

The `DatabaseService` acts as a repository, abstracting data access:

```python
# Client code doesn't know about SQLAlchemy
samples, total = db.get_samples(status='active')

# Service handles all ORM operations internally
def get_samples(self, status=None, ...):
    with self.session_scope() as session:
        query = session.query(Sample)
        if status:
            query = query.filter(Sample.status == status)
        # ...
```

### Unit of Work

Sessions manage transactions as units of work:

```python
@contextmanager
def session_scope(self):
    with get_session() as session:
        yield session
        # Commit happens automatically on context exit
        # Rollback on exception
```

### Data Transfer Objects

Models are converted to dictionaries for transport:

```python
def _sample_to_dict(self, sample: Sample) -> Dict:
    return {
        'id': sample.id,
        'sample_id': sample.sample_id,
        'lab_name': sample.lab.name if sample.lab else None,
        # ...
    }
```

### Factory Pattern

Flask application uses factory pattern:

```python
def create_app(config: Optional[Dict] = None) -> Flask:
    app = Flask(__name__)
    # Configure and return app
    return app
```

## Data Model

### Entity Categories

#### Organizational

```
Lab ─────┬──── LabMember
         │
         └──── Project ──── ProjectMember
```

- Labs contain members and projects
- Projects belong to labs
- Members can be assigned to multiple projects

#### Resources

```
Equipment ────┬──── EquipmentImage
              ├──── EquipmentIssue
              └──── Instrument
                    
Precursor ────┬──── PrecursorInventory
              └──── (used by Procedures, Samples)
```

- Equipment represents large lab infrastructure
- Instruments are PyBirch-compatible devices
- Precursors are tracked materials

#### Workflow

```
Procedure ──── FabricationRun ──── Sample
    │              │
    ├─ ProcedureEquipment
    └─ ProcedurePrecursor
    
Sample ──── Queue ──── Scan ──── MeasurementDataPoint
```

- Procedures define fabrication steps
- FabricationRuns record procedure executions
- Samples link to scans and queues

### Key Relationships

| Relationship | Type | Description |
|-------------|------|-------------|
| Lab → LabMember | One-to-Many | Lab has members |
| Lab → Project | One-to-Many | Lab has projects |
| Project → Sample | One-to-Many | Project contains samples |
| Sample → Scan | One-to-Many | Sample has scans |
| Sample → FabricationRun | One-to-Many | Sample fabrication history |
| Procedure → FabricationRun | One-to-Many | Procedure executions |
| Equipment → EquipmentIssue | One-to-Many | Equipment issues |
| Queue → Scan | One-to-Many | Queue contains scans |

## Thread Safety

### Session Per Request

Flask uses a session-per-request pattern:

```python
@main_bp.before_request
def before_request():
    g.db = get_db_service()

@main_bp.teardown_request
def teardown_request(exception):
    # Session cleanup handled by context manager
    pass
```

### Scoped Sessions

SQLAlchemy's `scoped_session` provides thread-local sessions:

```python
self._scoped_session = scoped_session(self._session_factory)
```

This ensures each thread gets its own session, preventing race conditions.

### Qt Integration

The Qt application can safely use `DatabaseService` from any thread:

```python
# In a worker thread
def save_scan_results(scan_data):
    db = DatabaseService()  # Gets thread-local session
    db.create_scan(scan_data)
```

## Extension Points

### Templates

The generic `Template` model allows custom entity presets:

```python
class Template(Base):
    entity_type: Mapped[str]  # 'sample', 'precursor', etc.
    template_data: Mapped[dict]  # JSON blob of defaults
```

### Extra Data Fields

Models include JSON fields for extensibility:

```python
extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
specifications: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

### Tags

The tagging system allows flexible categorization:

```python
class Tag(Base):
    name: Mapped[str]
    category: Mapped[str]

class EntityTag(Base):
    tag_id: Mapped[int]
    entity_type: Mapped[str]
    entity_id: Mapped[int]
```

## Security

### Authentication

- Google OAuth 2.0 for user authentication
- Session-based auth with Flask-Login pattern
- CSRF protection on all forms

### Authorization

- Role-based access (admin, user, viewer)
- Lab/project membership controls
- Per-item guest access for sharing

### Data Protection

- Prepared statements prevent SQL injection
- Input sanitization in service layer
- Secure session cookies

## Performance Considerations

### Indexes

Strategic indexes for common queries:

```python
__table_args__ = (
    Index('idx_samples_status', 'status'),
    Index('idx_samples_created', 'created_at'),
    Index('idx_samples_lab', 'lab_id'),
)
```

### Eager Loading

Relationships loaded with queries to avoid N+1:

```python
query = session.query(Sample).options(
    joinedload(Sample.lab),
    joinedload(Sample.project)
)
```

### Pagination

All list queries support pagination:

```python
def get_samples(self, page=1, per_page=20):
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
```

## Deployment

### Development

```bash
python run_web.py --debug
```

Uses SQLite with WAL mode and Flask's development server.

### Production

```bash
# Set PostgreSQL connection
export DATABASE_URL="postgresql://user:pass@localhost:5432/pybirch"

# Run with production WSGI server
gunicorn -w 4 "database.web.app:create_app()"
```

### Database Selection

| Scenario | Database | Configuration |
|----------|----------|---------------|
| Local development | SQLite | Default (no config) |
| Single-user production | SQLite + WAL | Default (auto-enabled) |
| Multi-user / high concurrency | PostgreSQL | Set `DATABASE_URL` |
| Cloud deployment | PostgreSQL | Use managed service |

### SQLite Optimizations (Automatic)

```python
# Enabled automatically in session.py
PRAGMA journal_mode=WAL      # Write-Ahead Logging
PRAGMA synchronous=NORMAL    # Faster writes
PRAGMA cache_size=-64000     # 64MB cache
PRAGMA busy_timeout=5000     # 5 second lock timeout
```

### PostgreSQL Connection Pool (Automatic)

```python
# Configured in session.py for PostgreSQL
pool_size=10           # Base connections
max_overflow=20        # Extra connections under load
pool_pre_ping=True     # Health check before use
pool_recycle=3600      # Recycle connections hourly
```

### Migrating from SQLite to PostgreSQL

```bash
python -m database.migrations.migrate_to_postgresql \
    --postgres-url "postgresql://user:pass@localhost:5432/pybirch"
```

Recommended production setup:
- Use PostgreSQL for concurrent access
- Deploy behind nginx/Apache
- Enable HTTPS
- Set strong SECRET_KEY
- Use connection pooling (PgBouncer for very high load)

---

*Last updated: January 2026*

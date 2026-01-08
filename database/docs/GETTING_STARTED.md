# Getting Started with PyBirch Database

This guide will help you set up and start using the PyBirch Database module.

## Prerequisites

- Python 3.9 or higher
- pip package manager
- (Optional) PostgreSQL for production deployments
- (Optional) Google OAuth credentials for authentication

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/Burch-Group/PyBirch.git
cd PyBirch

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install PyBirch with dependencies
pip install -e .

# Install PostgreSQL driver (optional, for production)
pip install psycopg2-binary
```

### Dependencies

The database module requires:

```
sqlalchemy>=2.0
flask>=3.0
authlib
python-dotenv
requests           # For weather integration
psycopg2-binary    # For PostgreSQL (optional)
```

## Quick Start

### Starting the Web Server

The simplest way to start using PyBirch Database:

```bash
cd database
python run_web.py
```

This will:
1. Initialize the SQLite database (if not exists)
2. Start the Flask development server
3. Open your browser to http://127.0.0.1:5000

### Command Line Options

```bash
python run_web.py --help

Options:
  --port PORT      Port to run on (default: 5000)
  --host HOST      Host to bind to (default: 127.0.0.1)
  --debug          Enable debug mode
  --no-browser     Don't open browser automatically
  --db PATH        Path to database file
```

### Using the DatabaseService Directly

For programmatic access without the web interface:

```python
from database.services import DatabaseService

# Initialize service (uses default SQLite database)
db = DatabaseService()

# Create a lab
lab = db.create_lab({
    'name': 'Materials Science Lab',
    'university': 'Example University',
    'department': 'Physics'
})

# Create a project
project = db.create_project({
    'name': 'Thin Film Study',
    'lab_id': lab['id'],
    'status': 'active'
})

# Create a sample
sample = db.create_sample({
    'sample_id': 'TF-2026-001',
    'name': 'Silicon wafer #1',
    'material': 'Si',
    'lab_id': lab['id'],
    'project_id': project['id']
})

# Query samples
samples, total = db.get_samples(
    lab_id=lab['id'],
    status='active',
    page=1,
    per_page=20
)

print(f"Found {total} samples")
for s in samples:
    print(f"  - {s['sample_id']}: {s['material']}")
```

## Configuration

### Environment Variables

Create a `.env` file in the `database` directory:

```env
# Flask secret key (generate a random string)
SECRET_KEY=your-secret-key-here

# Database URL (optional, defaults to SQLite)
# SQLite (default):
DATABASE_URL=sqlite:///pybirch.db
# PostgreSQL (recommended for production):
DATABASE_URL=postgresql://user:password@localhost:5432/pybirch

# Google OAuth (optional, for authentication)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Weather API (optional, for fabrication run logging)
OPENWEATHER_API_KEY=your-api-key
```

### Database Selection

| Use Case | Database | Setup |
|----------|----------|-------|
| Development/Testing | SQLite | Default, no config needed |
| Single user | SQLite | Default with WAL mode (automatic) |
| Multi-user / Production | PostgreSQL | Set `DATABASE_URL` |

### Database Location

By default, the database is created at `database/pybirch.db`. To use a different location:

```python
from database.services import DatabaseService

# Default: Uses DATABASE_URL env var or SQLite
db = DatabaseService()

# Custom SQLite file path
db = DatabaseService(db_path="/path/to/mydata.db")

# PostgreSQL (recommended for production)
db = DatabaseService(db_path="postgresql://user:pass@localhost:5432/pybirch")
```

### Using PostgreSQL

1. **Start PostgreSQL** (Docker example):
   ```bash
   docker run -d --name pybirch-postgres \
     -e POSTGRES_PASSWORD=pybirch \
     -e POSTGRES_DB=pybirch \
     -p 5432:5432 postgres:15
   ```

2. **Set environment variable**:
   ```bash
   export DATABASE_URL="postgresql://postgres:pybirch@localhost:5432/pybirch"
   ```

3. **Migrate existing data** (optional):
   ```bash
   python -m database.migrations.migrate_to_postgresql \
     --postgres-url "postgresql://postgres:pybirch@localhost:5432/pybirch"
   ```

4. **Start the server**:
   ```bash
   python run_web.py
   ```

## First Steps

### 1. Create Your Lab

After starting the web server, navigate to **Labs** > **+ New Lab**:

- **Name**: Your lab's name
- **University**: Institution name
- **Department**: Department or school
- **Code**: Short identifier (e.g., "MSL")

### 2. Add Lab Members

Go to your lab's detail page and click **Add Member**:

- **Name**: Full name
- **Email**: Contact email
- **Role**: Principal Investigator, Administrator, Member, Student, or Visiting
- **Title**: Professor, Postdoc, PhD Student, etc.

### 3. Create a Project

Navigate to **Projects** > **+ New Project**:

- **Name**: Project title
- **Lab**: Select your lab
- **Status**: Planning, Active, Paused, Completed, or Archived
- **Description**: Project goals and scope

### 4. Register Equipment

Go to **Equipment** > **+ New Equipment**:

- **Name**: Equipment name
- **Type**: Glovebox, Chamber, Lithography, Furnace, or Other
- **Location**: Building/room
- **Status**: Operational, Maintenance, Offline, or Retired

### 5. Add Precursors

Navigate to **Precursors** > **+ New Precursor**:

- **Name**: Chemical name
- **Formula**: Chemical formula
- **CAS Number**: CAS registry number
- **Supplier**: Vendor name
- **Lot Number**: Batch identifier

### 6. Define Procedures

Go to **Procedures** > **+ New Procedure**:

- **Name**: Procedure title
- **Type**: Deposition, Annealing, Etching, etc.
- **Steps**: Step-by-step instructions (JSON format)
- **Equipment**: Link required equipment
- **Precursors**: Link required materials

### 7. Create Samples

Navigate to **Samples** > **+ New Sample**:

- **Sample ID**: Unique identifier (e.g., "ABC-2026-001")
- **Material**: Composition
- **Lab/Project**: Organization
- **Precursors**: Materials used

### 8. Track Fabrication

From a sample's detail page, click **Add Fabrication Run**:

- **Procedure**: Select the procedure used
- **Parameters**: Actual parameters (may differ from defaults)
- **Equipment**: Equipment used
- **Notes**: Observations

## Integration with PyBirch

### Scan Extension

The database extension automatically saves scan data:

```python
from pybirch.database_integration import enable_database_integration

# Enable database logging for scans
enable_database_integration()

# Now all scans will be saved to the database
```

### URI Scheme

Register the `pybirch://` URI scheme to open scans from external links:

```bash
python -m database.register_uri_scheme
```

This enables links like:
- `pybirch://scan/123` - Open scan #123
- `pybirch://queue/456` - Open queue #456

## User Authentication

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI: `http://localhost:5000/auth/callback`
6. Copy Client ID and Secret to your `.env` file

See [GOOGLE_OAUTH_SETUP.md](../web/GOOGLE_OAUTH_SETUP.md) for detailed instructions.

### User Roles

- **Admin**: Full access to all features
- **User**: Can create and edit entities
- **Viewer**: Read-only access

## Troubleshooting

### Database Locked Error

SQLite can only handle one write at a time. If you see "database is locked":

1. Close any other programs accessing the database
2. Ensure you're not running multiple server instances
3. Try restarting the server

### Missing Tables

If tables are missing, run migrations:

```python
from database.session import init_db
init_db()  # Creates all tables
```

### OAuth Not Working

1. Verify credentials in `.env`
2. Check redirect URI matches Google Console
3. Ensure `HTTPS` or `localhost` (Google requires secure origins)

## Next Steps

- Read the [Developer Guide](DEVELOPER_GUIDE.md) for detailed architecture
- See the [API Reference](API_REFERENCE.md) for all available methods
- Check [examples/](../../examples/) for integration examples

---

*Last updated: January 2026*

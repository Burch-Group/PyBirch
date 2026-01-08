# PyBirch GUI-to-Database Integration Plan

## Executive Summary

This document outlines the plan for saving scans and queues from the PyBirch Qt GUI to the PyBirch SQLite/PostgreSQL database. The existing infrastructure provides a solid foundation - database models (`Queue`, `Scan`), CRUD operations (`ScanCRUD`, `QueueCRUD`), and database extensions (`DatabaseExtension`, `QueueDatabaseExtension`) are already implemented. The primary work involves wiring the GUI actions to these existing database services.

---

## 1. Current State Analysis

### 1.1 What Already Exists

| Component | Location | Status |
|-----------|----------|--------|
| Database Models | `database/models.py` (lines 945-1100) | ✅ Complete |
| `Queue` Model | Fields: `queue_id`, `serialized_data`, `status`, `total_scans` | ✅ Ready |
| `Scan` Model | Fields: `scan_tree_data`, `status`, `from_pybirch_scan()` | ✅ Ready |
| CRUD Operations | `database/crud.py` (lines 444-720) | ✅ Complete |
| `ScanCRUD.from_pybirch()` | Converts PyBirch Scan → DB Scan | ✅ Ready |
| `QueueCRUD.from_pybirch()` | Converts PyBirch Queue → DB Queue | ✅ Ready |
| Session Management | `database/session.py` | ✅ Complete |
| `DatabaseExtension` | `database/extension.py` (lines 1-240) | ✅ For runtime scan data |
| `QueueDatabaseExtension` | `database/extension.py` (lines 276-378) | ✅ For queue tracking |

### 1.2 Current GUI Save/Load

| Feature | Current Implementation | Database Integration |
|---------|----------------------|---------------------|
| Save Queue | Pickle to file (`queue_bar.py:290`) | ❌ Not connected |
| Load Queue | Pickle from file (`queue_bar.py:298`) | ❌ Not connected |
| Save Scan | Via preset system (`preset_manager.py`) | ❌ Not connected |
| Auto-save tree | `scan_page.py:save_tree_to_scan()` | ❌ In-memory only |

---

## 2. Integration Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PyBirch Qt GUI                                │
├─────────────────────────────────────────────────────────────────────┤
│  QueuePage           ScanPage            QueueBar                   │
│  ├─ queue_list      ├─ scan_tree        ├─ save_button (💾)        │
│  └─ scan_pages      └─ scan_info        ├─ load_button (📂)        │
│                                          └─ db_button (🗄️) [NEW]    │
└───────────────┬─────────────┬──────────────────┬────────────────────┘
                │             │                  │
                ▼             ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     GUI Database Service (NEW)                       │
│  ├─ GUIDatabaseManager                                              │
│  │   ├─ save_queue_to_db(queue) → db_queue_id                       │
│  │   ├─ save_scan_to_db(scan) → db_scan_id                          │
│  │   ├─ load_queue_from_db(queue_id) → Queue                        │
│  │   ├─ load_scan_from_db(scan_id) → Scan                           │
│  │   ├─ list_saved_queues() → List[QueueSummary]                    │
│  │   └─ list_saved_scans() → List[ScanSummary]                      │
│  └─ DatabaseBrowserDialog (NEW)                                     │
│       ├─ Queue browser with search/filter                           │
│       └─ Scan browser with search/filter                            │
└───────────────┬─────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Existing Database Layer                          │
│  ├─ ScanCRUD, QueueCRUD (database/crud.py)                          │
│  ├─ DatabaseManager (database/session.py)                           │
│  └─ Models: Queue, Scan, Sample, Project (database/models.py)       │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Save Triggers

| Trigger | When | What to Save | Priority |
|---------|------|--------------|----------|
| **Manual Save** | User clicks 💾 | Current queue + all scans | P1 |
| **Auto-save Draft** | Every N minutes or on significant change | Queue state as draft | P2 |
| **Queue Start** | `queue.execute()` called | Queue record + all scan records | P1 |
| **Scan Complete** | After each scan finishes | Scan status + measurement data | P1 |
| **Queue Complete** | All scans finished | Final queue status | P1 |

---

## 3. Implementation Plan

### Phase 1: Core Integration (Week 1)

#### 3.1.1 Create GUI Database Service

**New File:** `GUI/services/database_service.py`

```python
"""
GUI Database Service
Provides a clean interface between the Qt GUI and the database layer.
"""
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime

from database.session import get_session, DatabaseManager
from database.crud import scan_crud, queue_crud, sample_crud
from database.models import Queue as QueueModel, Scan as ScanModel


@dataclass
class QueueSummary:
    """Summary data for queue list display."""
    db_id: int
    queue_id: str
    name: Optional[str]
    status: str
    total_scans: int
    completed_scans: int
    created_at: datetime
    updated_at: datetime


@dataclass  
class ScanSummary:
    """Summary data for scan list display."""
    db_id: int
    scan_id: str
    scan_name: Optional[str]
    project_name: Optional[str]
    status: str
    created_at: datetime


class GUIDatabaseService:
    """
    Service layer for GUI-database interactions.
    Thread-safe and designed for Qt signal/slot usage.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        self._db_manager = DatabaseManager.get_instance(
            database_url=database_url
        )
    
    def save_queue(self, pybirch_queue, name: Optional[str] = None, 
                   operator: Optional[str] = None) -> int:
        """
        Save a PyBirch Queue to the database.
        
        Returns:
            Database ID of the saved queue
        """
        with self._db_manager.session() as session:
            db_queue = queue_crud.from_pybirch(session, pybirch_queue)
            if name:
                db_queue.name = name
            db_queue.created_by = operator
            session.flush()
            return db_queue.id
    
    def save_scan(self, pybirch_scan, queue_db_id: Optional[int] = None,
                  operator: Optional[str] = None) -> int:
        """
        Save a PyBirch Scan to the database.
        
        Returns:
            Database ID of the saved scan
        """
        with self._db_manager.session() as session:
            db_scan = scan_crud.from_pybirch(
                session, pybirch_scan, queue_db_id=queue_db_id
            )
            db_scan.created_by = operator
            session.flush()
            return db_scan.id
    
    def load_queue(self, queue_id: str):
        """Load a queue from database by its queue_id."""
        with self._db_manager.session() as session:
            db_queue = queue_crud.get_by_queue_id(session, queue_id)
            if db_queue and db_queue.serialized_data:
                from pybirch.queue.queue import Queue
                return Queue.deserialize(db_queue.serialized_data)
        return None
    
    def list_queues(self, status: Optional[str] = None,
                    limit: int = 100) -> List[QueueSummary]:
        """List saved queues with optional filtering."""
        with self._db_manager.session() as session:
            filters = {"status": status} if status else None
            queues = queue_crud.get_all(session, filters=filters, limit=limit)
            return [
                QueueSummary(
                    db_id=q.id,
                    queue_id=q.queue_id,
                    name=q.name,
                    status=q.status,
                    total_scans=q.total_scans or 0,
                    completed_scans=q.completed_scans,
                    created_at=q.created_at,
                    updated_at=q.updated_at
                )
                for q in queues
            ]
    
    def list_scans(self, status: Optional[str] = None,
                   limit: int = 100) -> List[ScanSummary]:
        """List saved scans with optional filtering."""
        with self._db_manager.session() as session:
            filters = {"status": status} if status else None
            scans = scan_crud.get_all(session, filters=filters, limit=limit)
            return [
                ScanSummary(
                    db_id=s.id,
                    scan_id=s.scan_id,
                    scan_name=s.scan_name,
                    project_name=s.project_name,
                    status=s.status,
                    created_at=s.created_at
                )
                for s in scans
            ]
```

#### 3.1.2 Add Database Button to QueueBar

**Modify:** `GUI/widgets/queue_bar.py`

Add a new "Database" button (🗄️) between Save and Extensions:

```python
# Database button - database/storage icon
self.database_button = QtWidgets.QPushButton("🗄️")
self.database_button.setFont(QtGui.QFont("Segoe UI Emoji", 24))
self.database_button.setToolTip("Save/Load from database")
self.database_button.setFixedSize(64, 64)
```

Connect to a new dialog for database browsing.

#### 3.1.3 Create Database Browser Dialog

**New File:** `GUI/widgets/database_browser.py`

A dialog that allows users to:
- View saved queues and scans in a searchable table
- Filter by status, date range, project
- Load selected items back into the GUI
- Delete old entries
- View details/metadata

---

### Phase 2: Queue Bar Integration (Week 2)

#### 3.2.1 Update Save Button Behavior

**Option A: Save to Database by Default**
- Change 💾 to save to database instead of pickle
- Keep pickle option in "Save As..." submenu

**Option B: Dual-Save Dialog**
- Show dialog: "Save to: [Database] [File] [Both]"

**Recommendation:** Option A with a settings toggle

#### 3.2.2 Update Load Button Behavior

- First check database for recent queues
- Show database browser dialog
- Keep file load as secondary option

#### 3.2.3 Add Context Menu

Right-click on save/load buttons for additional options:
- Save to Database
- Save to File (Pickle)
- Save to Both
- Export as JSON

---

### Phase 3: Runtime Integration (Week 3)

#### 3.3.1 Auto-Save During Execution

Leverage existing `QueueDatabaseExtension`:

```python
# In QueuePage.on_queue_start():
from database.extension import QueueDatabaseExtension

def on_queue_start(self):
    # Create database extension for tracking
    self.db_extension = QueueDatabaseExtension(
        self.queue, 
        operator=self.get_current_operator()
    )
    
    # Add DatabaseExtension to each scan
    for scan in self.queue.scans:
        scan.scan_settings.extensions.append(
            DatabaseExtension(operator=self.get_current_operator())
        )
    
    self.queue.execute()
```

#### 3.3.2 Status Updates

- Update queue status in DB when paused/resumed/aborted
- Update individual scan status as they complete
- Show database sync indicator in GUI (✓ Saved)

---

### Phase 4: Advanced Features (Week 4)

#### 3.4.1 Draft Auto-Save

```python
class AutoSaveManager:
    """Periodically saves queue state as a draft."""
    
    def __init__(self, queue_page, interval_seconds=300):
        self.timer = QTimer()
        self.timer.timeout.connect(self._auto_save)
        self.timer.start(interval_seconds * 1000)
    
    def _auto_save(self):
        if self.queue_page.has_unsaved_changes():
            self.db_service.save_queue(
                self.queue_page.queue,
                status='draft'
            )
```

#### 3.4.2 History/Versioning

- Keep track of queue modifications
- Allow "Revert to saved" option
- Show diff between current and saved state

#### 3.4.3 Sample/Project Association

- Add dropdowns to associate queue with:
  - Sample (from `samples` table)
  - Project (from `projects` table)
  - Lab (from `labs` table)
- These are stored in the queue/scan records

---

## 4. File Changes Summary

### New Files to Create

| File | Purpose |
|------|---------|
| `GUI/services/__init__.py` | Services package init |
| `GUI/services/database_service.py` | GUI-database interface |
| `GUI/widgets/database_browser.py` | Database browser dialog |
| `tests/test_gui_database_service.py` | Unit tests |

### Files to Modify

| File | Changes |
|------|---------|
| `GUI/widgets/queue_bar.py` | Add database button, update save/load handlers |
| `GUI/windows/queue_page.py` | Initialize database service, connect signals |
| `GUI/windows/scan_page.py` | Optional: save scan to DB on changes |
| `database/crud.py` | Add any missing query methods |

---

## 5. Database Schema Mapping

### PyBirch Queue → Database Queue

| PyBirch Attribute | DB Column | Notes |
|-------------------|-----------|-------|
| `queue.QID` | `queue_id` | Unique identifier |
| `queue.execution_mode.name` | `execution_mode` | "SERIAL" or "PARALLEL" |
| `len(queue)` | `total_scans` | Count of scans |
| `queue.serialize()` | `serialized_data` | Full JSON serialization |
| (from GUI) | `name` | User-friendly name |
| (from GUI) | `created_by` | Operator name |

### PyBirch Scan → Database Scan

| PyBirch Attribute | DB Column | Notes |
|-------------------|-----------|-------|
| `scan.scan_settings.project_name` | `project_name` | |
| `scan.scan_settings.scan_name` | `scan_name` | |
| `scan.scan_settings.scan_type` | `scan_type` | |
| `scan.scan_settings.scan_tree.serialize()` | `scan_tree_data` | JSON |
| `scan.scan_settings.status` | `status` | |
| `scan.owner` | `created_by` | Operator |

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
# tests/test_gui_database_service.py

class TestGUIDatabaseService:
    """Tests for GUI database service."""
    
    def test_save_queue_creates_record(self, db_service, sample_queue):
        """Test that save_queue creates a database record."""
        db_id = db_service.save_queue(sample_queue, name="Test Queue")
        assert db_id > 0
        
    def test_load_queue_restores_state(self, db_service, sample_queue):
        """Test that load_queue restores the queue correctly."""
        db_service.save_queue(sample_queue)
        loaded = db_service.load_queue(sample_queue.QID)
        assert loaded.QID == sample_queue.QID
        assert len(loaded) == len(sample_queue)
    
    def test_list_queues_returns_summaries(self, db_service):
        """Test list_queues returns proper summaries."""
        summaries = db_service.list_queues(limit=10)
        assert isinstance(summaries, list)
```

### 6.2 Integration Tests

- Test full save → load cycle through GUI
- Test auto-save during queue execution
- Test database browser dialog interactions

### 6.3 Manual Testing Checklist

- [ ] Save empty queue to database
- [ ] Save queue with scans to database
- [ ] Load queue from database browser
- [ ] Run queue with database tracking enabled
- [ ] Verify scan data saved during execution
- [ ] Test with PostgreSQL (not just SQLite)

---

## 7. Implementation Order

### Week 1
1. ✅ Create `GUI/services/database_service.py`
2. ✅ Add basic unit tests
3. ✅ Add database button to `queue_bar.py`

### Week 2
4. Create `database_browser.py` dialog
5. Connect save button to database service
6. Connect load button to database browser

### Week 3
7. Add `QueueDatabaseExtension` to queue execution
8. Add `DatabaseExtension` to scan execution
9. Add status sync indicators

### Week 4
10. Implement auto-save drafts
11. Add sample/project association UI
12. Polish and documentation

---

## 8. Configuration Options

Add to `config/default/gui_settings.yaml`:

```yaml
database:
  enabled: true
  auto_save:
    enabled: true
    interval_seconds: 300
  save_mode: "database"  # "database", "file", "both"
  default_load_source: "database"  # "database", "file"
```

---

## 9. Error Handling

### Connection Errors
```python
try:
    db_service.save_queue(queue)
except DatabaseConnectionError:
    # Show warning, offer to save to file instead
    QMessageBox.warning(
        self, 
        "Database Unavailable",
        "Could not connect to database. Save to file instead?"
    )
```

### Serialization Errors
```python
try:
    queue.serialize()
except SerializationError as e:
    logger.error(f"Failed to serialize queue: {e}")
    # Notify user of problematic scan/instrument
```

---

## 10. Migration Notes

### For Existing Users
- Existing pickle files continue to work
- No data migration required
- Database is opt-in initially, can become default later

### Future Considerations
- Add "Import from pickle" feature to database browser
- Consider cloud sync options (PostgreSQL on Azure)
- Add export to common formats (JSON, CSV for measurement data)

---

## Appendix A: Relevant Code Locations

| Feature | File | Line |
|---------|------|------|
| Queue model | `database/models.py` | 945 |
| Scan model | `database/models.py` | 1021 |
| `Scan.from_pybirch_scan()` | `database/models.py` | 1079 |
| `ScanCRUD.from_pybirch()` | `database/crud.py` | 508 |
| `QueueCRUD.from_pybirch()` | `database/crud.py` | 692 |
| `DatabaseExtension` | `database/extension.py` | 19 |
| `QueueDatabaseExtension` | `database/extension.py` | 276 |
| `get_session()` | `database/session.py` | 254 |
| Current save handler | `GUI/widgets/queue_bar.py` | 290 |
| Current load handler | `GUI/widgets/queue_bar.py` | 298 |

---

*Document created: [Current Date]*
*Last updated: [Current Date]*
*Author: PyBirch Development Team*

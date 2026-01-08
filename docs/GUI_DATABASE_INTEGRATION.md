# GUI-Database Integration Plan

This document outlines the integration between the PyBirch scan GUI and the database web interface.

## Goals

1. **Persist scan/queue execution**: Scans and queues that have been (at least partially) run should save to the database along with their corresponding data items
2. **Sample selection from database**: The GUI should request sample ID from the database rather than manual material/substrate entry
3. **Browser launch links**: Launch links from the web interface should open the appropriate PyBirch scan or queue

---

## Phase 1: Database Models & API

### New Models

- [ ] Create `Scan` model in database
  - `id`: Primary key
  - `sample_id`: Foreign key to Sample
  - `name`: Scan name/title
  - `config_json`: Full scan configuration (serialized)
  - `status`: enum (pending, running, completed, aborted, error)
  - `started_at`: Timestamp
  - `completed_at`: Timestamp
  - `created_by`: User who created the scan
  - `notes`: Optional notes

- [ ] Create `Queue` model in database
  - `id`: Primary key
  - `name`: Queue name/title
  - `config_json`: Full queue configuration (serialized)
  - `status`: enum (pending, running, completed, aborted, error)
  - `current_scan_index`: Track progress through queue
  - `started_at`: Timestamp
  - `completed_at`: Timestamp
  - `created_by`: User who created the queue

- [ ] Create `ScanDataItem` model for measurement data
  - `id`: Primary key
  - `scan_id`: Foreign key to Scan
  - `timestamp`: When data point was recorded
  - `data_json`: Measurement values (flexible JSON storage)
  - `step_index`: Position in scan sequence

### API Endpoints

- [ ] `GET /api/scans` - List all scans
- [ ] `POST /api/scans` - Create new scan record
- [ ] `GET /api/scans/<id>` - Get scan details
- [ ] `PUT /api/scans/<id>` - Update scan (status, data)
- [ ] `DELETE /api/scans/<id>` - Delete scan

- [ ] `GET /api/queues` - List all queues
- [ ] `POST /api/queues` - Create new queue record
- [ ] `GET /api/queues/<id>` - Get queue details
- [ ] `PUT /api/queues/<id>` - Update queue
- [ ] `DELETE /api/queues/<id>` - Delete queue

- [ ] `GET /api/samples/list` - Simple list for GUI dropdown (id, sample_id, name)

---

## Phase 2: GUI Sample Selection

### Replace Material/Substrate Fields

- [ ] Remove manual material and substrate text fields from scan info page
- [ ] Add sample ID dropdown/selector widget
- [ ] Implement sample search with autocomplete (queries `/api/samples/list`)
- [ ] Display selected sample details preview (material, substrate, project)
- [ ] Store sample database ID in scan configuration

### Offline Mode

- [ ] Detect when database is unavailable
- [ ] Fall back to manual entry mode with warning
- [ ] Queue sample linkage for when connection restored

---

## Phase 3: Scan/Queue Persistence

### Scan Lifecycle

- [ ] On scan start:
  - Create scan record in database (status: "running")
  - Store scan configuration JSON
  - Link to selected sample ID
  
- [ ] During scan execution:
  - Periodically save data items to database
  - Update scan record with progress info
  
- [ ] On scan completion:
  - Update status to "completed"
  - Set `completed_at` timestamp
  - Finalize all data items
  
- [ ] On scan abort/error:
  - Update status to "aborted" or "error"
  - Save partial data collected
  - Store error message if applicable

### Queue Lifecycle

- [ ] On queue start:
  - Create queue record in database
  - Create child scan records (status: "pending")
  - Track `current_scan_index`
  
- [ ] During queue execution:
  - Update child scan statuses as they run
  - Update `current_scan_index` on each scan completion
  
- [ ] On queue completion/abort:
  - Update queue status
  - Ensure all child scan statuses are correct

### Resume Support

- [ ] Load queue state from database on PyBirch startup
- [ ] Offer to resume interrupted queues
- [ ] Skip already-completed scans when resuming

---

## Phase 4: Browser Launch Links

### URI Scheme Registration

- [ ] Register `pybirch://` URI scheme on Windows
  - Add to Windows Registry via installer or setup script
  - Handler: `pybirch.exe` or `python path/to/launch_handler.py`
  
- [ ] Implement URI handler script (`uri_handler.py` or similar)
  - Parse URI: `pybirch://scan/123` or `pybirch://queue/456`
  - Launch PyBirch GUI if not running
  - Load specified scan/queue configuration
  - Open appropriate window

### URI Formats

```
pybirch://scan/{scan_id}         - Open scan by database ID
pybirch://scan/{scan_id}/run     - Open and immediately run scan
pybirch://queue/{queue_id}       - Open queue by database ID
pybirch://queue/{queue_id}/run   - Open and immediately run queue
```

### Web Interface Integration

- [ ] Add "Open in PyBirch" button to scan detail page
- [ ] Add "Open in PyBirch" button to queue detail page
- [ ] Add "Run in PyBirch" button (opens and starts execution)
- [ ] Handle case when PyBirch is not installed (show download/install instructions)

---

## Phase 5: Web Interface Updates

### Scans Pages

- [ ] Create `/scans` list page
  - Table with: name, sample, status, started_at, completed_at
  - Filter by status, sample, date range
  - Search by name
  - Link to scan detail page
  
- [ ] Create `/scans/<id>` detail page
  - Scan configuration summary
  - Linked sample info
  - Status and timestamps
  - Data visualization (charts/plots)
  - Download data as CSV/JSON
  - "Open in PyBirch" button

### Queues Pages

- [ ] Create `/queues` list page
  - Table with: name, status, scan count, progress, timestamps
  - Filter by status, date range
  - Link to queue detail page
  
- [ ] Create `/queues/<id>` detail page
  - Queue configuration summary
  - List of child scans with statuses
  - Overall progress indicator
  - "Open in PyBirch" / "Resume in PyBirch" buttons

### Sample Integration

- [ ] Add "Scans" section to sample detail page
  - List all scans performed on this sample
  - Link to scan detail pages
  - Quick view of scan results

### Navigation

- [ ] Add "Scans" link to main navigation
- [ ] Add "Queues" link to main navigation

---

## Implementation Notes

### Database Connection from GUI

The GUI will need to communicate with the database. Options:
1. **Direct database access**: Import database models/services into GUI code
2. **REST API**: GUI makes HTTP requests to the web server
3. **Hybrid**: Direct access for reads, API for writes

Recommendation: Use REST API for clean separation. The web server should be running when using database features.

### Data Storage Considerations

- Scan data can be large (thousands of data points)
- Consider pagination for data retrieval
- May want to store raw data files separately and link from database
- WandB integration should continue to work alongside database storage

### Configuration Serialization

- Scan/queue configurations are already serializable (JSON)
- Store full configuration to enable exact reproduction
- Version the configuration format for future compatibility

"""
PyBirch Database Services
=========================
Business logic layer for database operations.
This module is shared between the Flask web UI and PyBirch Qt application.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, func, desc, case
from sqlalchemy.orm import Session, joinedload
from contextlib import contextmanager

from database.models import (
    Template, Equipment, Precursor, PrecursorInventory,
    Procedure, Sample, SamplePrecursor,
    Queue, QueueLog, Scan, MeasurementObject, MeasurementDataPoint,
    Tag, EntityTag, FabricationRun,
    Lab, LabMember, Project, ProjectMember, ItemGuest,
    User, Issue
)
from database.session import get_session, init_db


class DatabaseService:
    """
    High-level database service providing business operations.
    Thread-safe for use with Flask and Qt concurrently.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database service.
        
        Args:
            db_path: Optional path to SQLite database file. Uses default if not provided.
                     Can be a file path or a SQLAlchemy URL.
        """
        self.db_path = db_path
        
        # Convert file path to SQLAlchemy URL if needed
        if db_path and not db_path.startswith(('sqlite://', 'postgresql://', 'mysql://')):
            # It's a file path, convert to SQLAlchemy URL
            db_url = f"sqlite:///{db_path}"
        else:
            db_url = db_path
        
        init_db(db_url)
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for a series of operations."""
        with get_session() as session:
            yield session
    
    # ==================== Dashboard / Statistics ====================
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get statistics for the dashboard."""
        with self.session_scope() as session:
            stats = {
                'samples': {
                    'total': session.query(func.count(Sample.id)).scalar() or 0,
                    'active': session.query(func.count(Sample.id)).filter(Sample.status == 'active').scalar() or 0,
                },
                'scans': {
                    'total': session.query(func.count(Scan.id)).scalar() or 0,
                    'completed': session.query(func.count(Scan.id)).filter(Scan.status == 'completed').scalar() or 0,
                    'running': session.query(func.count(Scan.id)).filter(Scan.status == 'running').scalar() or 0,
                },
                'queues': {
                    'total': session.query(func.count(Queue.id)).scalar() or 0,
                    'active': session.query(func.count(Queue.id)).filter(Queue.status.in_(['running', 'paused'])).scalar() or 0,
                },
                'equipment': {
                    'total': session.query(func.count(Equipment.id)).scalar() or 0,
                    'available': session.query(func.count(Equipment.id)).filter(Equipment.status == 'available').scalar() or 0,
                },
                'precursors': {
                    'total': session.query(func.count(Precursor.id)).scalar() or 0,
                },
                'procedures': {
                    'total': session.query(func.count(Procedure.id)).scalar() or 0,
                    'active': session.query(func.count(Procedure.id)).filter(Procedure.is_active == True).scalar() or 0,
                },
                'labs': {
                    'total': session.query(func.count(Lab.id)).scalar() or 0,
                    'active': session.query(func.count(Lab.id)).filter(Lab.is_active == True).scalar() or 0,
                },
                'projects': {
                    'total': session.query(func.count(Project.id)).scalar() or 0,
                    'active': session.query(func.count(Project.id)).filter(Project.status == 'active').scalar() or 0,
                },
                'issues': {
                    'total': session.query(func.count(Issue.id)).scalar() or 0,
                    'open': session.query(func.count(Issue.id)).filter(Issue.status == 'open').scalar() or 0,
                    'in_progress': session.query(func.count(Issue.id)).filter(Issue.status == 'in_progress').scalar() or 0,
                },
            }
            
            # Recent activity
            stats['recent_scans'] = self._get_recent_scans(session, limit=5)
            stats['recent_samples'] = self._get_recent_samples(session, limit=5)
            stats['open_issues'] = self._get_open_issues(session, limit=5)
            
            return stats
    
    def _get_recent_scans(self, session: Session, limit: int = 5) -> List[Dict]:
        """Get recent scans for dashboard."""
        scans = session.query(Scan).order_by(desc(Scan.created_at)).limit(limit).all()
        return [self._scan_to_dict(s) for s in scans]
    
    def _get_recent_samples(self, session: Session, limit: int = 5) -> List[Dict]:
        """Get recent samples for dashboard."""
        samples = session.query(Sample).order_by(desc(Sample.created_at)).limit(limit).all()
        return [self._sample_to_dict(s) for s in samples]
    
    def _get_open_issues(self, session: Session, limit: int = 5) -> List[Dict]:
        """Get open issues for dashboard."""
        issues = session.query(Issue).filter(
            Issue.status.in_(['open', 'in_progress'])
        ).order_by(
            # Priority order: critical > high > medium > low
            case(
                (Issue.priority == 'critical', 1),
                (Issue.priority == 'high', 2),
                (Issue.priority == 'medium', 3),
                else_=4
            ),
            desc(Issue.created_at)
        ).limit(limit).all()
        return [self._issue_to_dict(i) for i in issues]
    
    # ==================== Samples ====================
    
    def get_samples(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        material: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of samples with optional filtering.
        
        Returns:
            Tuple of (samples list, total count)
        """
        with self.session_scope() as session:
            query = session.query(Sample)
            
            # Apply filters
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Sample.sample_id.ilike(search_term),
                        Sample.name.ilike(search_term),
                        Sample.material.ilike(search_term),
                        Sample.description.ilike(search_term)
                    )
                )
            
            if status:
                query = query.filter(Sample.status == status)
            
            if material:
                query = query.filter(Sample.material.ilike(f"%{material}%"))
            
            # Get total count
            total = query.count()
            
            # Paginate
            offset = (page - 1) * per_page
            samples = query.order_by(desc(Sample.created_at)).offset(offset).limit(per_page).all()
            
            return [self._sample_to_dict(s) for s in samples], total
    
    def get_sample(self, sample_id: int) -> Optional[Dict]:
        """Get a single sample by ID with related data."""
        with self.session_scope() as session:
            sample = session.query(Sample).options(
                joinedload(Sample.scans),
                joinedload(Sample.queues),
                joinedload(Sample.precursor_associations).joinedload(SamplePrecursor.precursor),
                joinedload(Sample.project),
                joinedload(Sample.parent_sample),
                joinedload(Sample.fabrication_runs).joinedload(FabricationRun.procedure),
            ).filter(Sample.id == sample_id).first()
            
            if not sample:
                return None
            
            result = self._sample_to_dict(sample)
            result['scans'] = [self._scan_to_dict(s) for s in sample.scans]
            result['queues'] = [self._queue_to_dict(q) for q in sample.queues]
            
            # Add relationship data
            result['project'] = {
                'id': sample.project.id,
                'name': sample.project.name,
                'code': sample.project.code,
            } if sample.project else None
            
            result['parent_sample'] = {
                'id': sample.parent_sample.id,
                'sample_id': sample.parent_sample.sample_id,
                'name': sample.parent_sample.name,
                'material': sample.parent_sample.material,
            } if sample.parent_sample else None
            
            result['precursors'] = [{
                'id': a.id,
                'precursor_id': a.precursor_id,
                'precursor_name': a.precursor.name if a.precursor else None,
                'chemical_formula': a.precursor.chemical_formula if a.precursor else None,
                'quantity_used': float(a.quantity_used) if a.quantity_used else None,
                'quantity_unit': a.quantity_unit,
                'role': a.role,
                'composition_percent': float(a.composition_percent) if a.composition_percent else None,
            } for a in sample.precursor_associations]
            
            # Get derived samples (children)
            derived_samples = session.query(Sample).filter(
                Sample.parent_sample_id == sample_id,
                Sample.status != 'archived'
            ).all()
            result['derived_samples'] = [{
                'id': s.id,
                'sample_id': s.sample_id,
                'name': s.name,
                'material': s.material,
            } for s in derived_samples]
            
            # Get fabrication runs
            result['fabrication_runs'] = [{
                'id': run.id,
                'procedure_id': run.procedure_id,
                'procedure_name': run.procedure.name if run.procedure else None,
                'procedure_type': run.procedure.procedure_type if run.procedure else None,
                'run_number': run.run_number,
                'status': run.status,
                'operator': run.operator,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'notes': run.notes,
                'weather_conditions': run.weather_conditions,
                'created_at': run.created_at.isoformat() if run.created_at else None,
            } for run in sample.fabrication_runs]
            
            return result
    
    def get_sample_by_sample_id(self, sample_id_str: str) -> Optional[Dict]:
        """Get sample by the user-friendly sample_id string."""
        with self.session_scope() as session:
            sample = session.query(Sample).filter(Sample.sample_id == sample_id_str).first()
            return self._sample_to_dict(sample) if sample else None
    
    def generate_next_sample_id(self, prefix: str = "S") -> str:
        """Generate the next available sample ID.
        
        Format: {prefix}-{YYYY}-{NNN} e.g., S-2026-001
        
        Args:
            prefix: The prefix for the sample ID (default: "S")
            
        Returns:
            A unique sample ID string
        """
        from datetime import datetime
        import re
        
        year = datetime.now().year
        pattern = f"{prefix}-{year}-"
        
        with self.session_scope() as session:
            # Find all sample_ids matching this year's pattern
            samples = session.query(Sample.sample_id).filter(
                Sample.sample_id.like(f"{pattern}%")
            ).all()
            
            # Extract the numeric parts and find the max
            max_num = 0
            for (sample_id,) in samples:
                match = re.search(rf"{re.escape(pattern)}(\d+)", sample_id)
                if match:
                    num = int(match.group(1))
                    max_num = max(max_num, num)
            
            # Generate the next ID
            next_num = max_num + 1
            return f"{pattern}{next_num:03d}"

    def create_sample(self, data: Dict[str, Any]) -> Dict:
        """Create a new sample."""
        with self.session_scope() as session:
            sample = Sample(**data)
            session.add(sample)
            session.flush()
            return self._sample_to_dict(sample)
    
    def update_sample(self, sample_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update an existing sample."""
        with self.session_scope() as session:
            sample = session.query(Sample).filter(Sample.id == sample_id).first()
            if not sample:
                return None
            
            for key, value in data.items():
                if hasattr(sample, key) and key not in ('id', 'created_at'):
                    setattr(sample, key, value)
            
            session.flush()
            return self._sample_to_dict(sample)
    
    def delete_sample(self, sample_id: int) -> bool:
        """Delete a sample (soft delete by setting status to 'archived')."""
        with self.session_scope() as session:
            sample = session.query(Sample).filter(Sample.id == sample_id).first()
            if sample:
                sample.status = 'archived'
                return True
            return False
    
    def _sample_to_dict(self, sample: Sample) -> Dict:
        """Convert Sample model to dictionary."""
        return {
            'id': sample.id,
            'sample_id': sample.sample_id,
            'name': sample.name,
            'material': sample.material,
            'sample_type': sample.sample_type,
            'substrate': sample.substrate,
            'dimensions': sample.dimensions,
            'status': sample.status,
            'storage_location': sample.storage_location,
            'description': sample.description,
            'additional_tags': sample.additional_tags,
            'extra_data': sample.extra_data,
            'created_at': sample.created_at.isoformat() if sample.created_at else None,
            'updated_at': sample.updated_at.isoformat() if sample.updated_at else None,
            'created_by': sample.created_by,
            'project_id': sample.project_id,
            'parent_sample_id': sample.parent_sample_id,
        }
    
    def get_samples_simple_list(self, exclude_id: Optional[int] = None) -> List[Dict]:
        """Get a simple list of all samples for dropdowns (id, sample_id, name, material)."""
        with self.session_scope() as session:
            query = session.query(Sample).filter(Sample.status != 'archived')
            if exclude_id:
                query = query.filter(Sample.id != exclude_id)
            samples = query.order_by(Sample.sample_id).all()
            return [{
                'id': s.id,
                'sample_id': s.sample_id,
                'name': s.name,
                'material': s.material,
                'display': f"{s.sample_id}" + (f" - {s.name}" if s.name else "") + (f" ({s.material})" if s.material else "")
            } for s in samples]
    
    def get_projects_simple_list(self) -> List[Dict]:
        """Get a simple list of all projects for dropdowns."""
        with self.session_scope() as session:
            projects = session.query(Project).filter(
                Project.status.in_(['planning', 'active', 'paused'])
            ).order_by(Project.name).all()
            return [{
                'id': p.id,
                'name': p.name,
                'code': p.code,
                'display': f"{p.name}" + (f" ({p.code})" if p.code else "")
            } for p in projects]
    
    def get_precursors_simple_list(self) -> List[Dict]:
        """Get a simple list of all precursors for dropdowns."""
        with self.session_scope() as session:
            precursors = session.query(Precursor).order_by(Precursor.name).all()
            return [{
                'id': p.id,
                'name': p.name,
                'chemical_formula': p.chemical_formula,
                'display': f"{p.name}" + (f" ({p.chemical_formula})" if p.chemical_formula else "")
            } for p in precursors]
    
    def get_equipment_simple_list(self) -> List[Dict]:
        """Get a simple list of all equipment for dropdowns."""
        with self.session_scope() as session:
            equipment = session.query(Equipment).filter(
                Equipment.status != 'retired'
            ).order_by(Equipment.name).all()
            return [{
                'id': e.id,
                'name': e.name,
                'model': e.model,
                'display': f"{e.name}" + (f" ({e.model})" if e.model else "")
            } for e in equipment]
    
    def add_sample_precursor(
        self,
        sample_id: int,
        precursor_id: int,
        quantity_used: Optional[float] = None,
        quantity_unit: Optional[str] = None,
        role: Optional[str] = None,
        composition_percent: Optional[float] = None
    ) -> bool:
        """Add a precursor to a sample."""
        with self.session_scope() as session:
            # Check if association already exists
            existing = session.query(SamplePrecursor).filter(
                SamplePrecursor.sample_id == sample_id,
                SamplePrecursor.precursor_id == precursor_id,
                SamplePrecursor.role == role
            ).first()
            if existing:
                return False
            
            assoc = SamplePrecursor(
                sample_id=sample_id,
                precursor_id=precursor_id,
                quantity_used=quantity_used,
                quantity_unit=quantity_unit,
                role=role,
                composition_percent=composition_percent
            )
            session.add(assoc)
            return True
    
    def remove_sample_precursor(self, sample_id: int, precursor_id: int, role: Optional[str] = None) -> bool:
        """Remove a precursor from a sample."""
        with self.session_scope() as session:
            query = session.query(SamplePrecursor).filter(
                SamplePrecursor.sample_id == sample_id,
                SamplePrecursor.precursor_id == precursor_id
            )
            if role:
                query = query.filter(SamplePrecursor.role == role)
            assoc = query.first()
            if assoc:
                session.delete(assoc)
                return True
            return False
    
    def get_sample_precursors(self, sample_id: int) -> List[Dict]:
        """Get all precursors for a sample."""
        with self.session_scope() as session:
            associations = session.query(SamplePrecursor).options(
                joinedload(SamplePrecursor.precursor)
            ).filter(SamplePrecursor.sample_id == sample_id).all()
            return [{
                'id': a.id,
                'precursor_id': a.precursor_id,
                'precursor_name': a.precursor.name if a.precursor else None,
                'chemical_formula': a.precursor.chemical_formula if a.precursor else None,
                'quantity_used': float(a.quantity_used) if a.quantity_used else None,
                'quantity_unit': a.quantity_unit,
                'role': a.role,
                'composition_percent': float(a.composition_percent) if a.composition_percent else None,
            } for a in associations]
    
    # ==================== Scans ====================
    
    def get_scans(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        sample_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of scans with optional filtering."""
        with self.session_scope() as session:
            query = session.query(Scan)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Scan.scan_name.ilike(search_term),
                        Scan.project_name.ilike(search_term),
                        Scan.scan_id.ilike(search_term)
                    )
                )
            
            if status:
                query = query.filter(Scan.status == status)
            
            if sample_id:
                query = query.filter(Scan.sample_id == sample_id)
            
            total = query.count()
            offset = (page - 1) * per_page
            scans = query.order_by(desc(Scan.created_at)).offset(offset).limit(per_page).all()
            
            return [self._scan_to_dict(s) for s in scans], total
    
    def get_scan(self, scan_id: int) -> Optional[Dict]:
        """Get a single scan by ID with measurement data."""
        with self.session_scope() as session:
            scan = session.query(Scan).options(
                joinedload(Scan.sample),
                joinedload(Scan.measurement_objects),
            ).filter(Scan.id == scan_id).first()
            
            if not scan:
                return None
            
            result = self._scan_to_dict(scan)
            result['sample'] = self._sample_to_dict(scan.sample) if scan.sample else None
            result['measurement_objects'] = [
                self._measurement_object_to_dict(mo) 
                for mo in scan.measurement_objects
            ]
            return result
    
    def get_scan_data_points(self, scan_id: int, measurement_name: Optional[str] = None) -> List[Dict]:
        """Get measurement data points for a scan."""
        with self.session_scope() as session:
            query = session.query(MeasurementDataPoint).join(MeasurementObject).filter(
                MeasurementObject.scan_id == scan_id
            )
            
            if measurement_name:
                query = query.filter(MeasurementObject.name == measurement_name)
            
            points = query.order_by(MeasurementDataPoint.sequence_index).all()
            return [
                {
                    'id': p.id,
                    'sequence_index': p.sequence_index,
                    'values': p.values,
                    'timestamp': p.timestamp.isoformat() if p.timestamp else None,
                    'extra_data': p.extra_data,
                }
                for p in points
            ]

    def _scan_to_dict(self, scan: Scan) -> Dict:
        """Convert Scan model to dictionary."""
        return {
            'id': scan.id,
            'scan_id': scan.scan_id,
            'scan_name': scan.scan_name,
            'project_name': scan.project_name,
            'owner': scan.owner,
            'status': scan.status,
            'scan_type': scan.scan_type,
            'job_type': scan.job_type,
            'started_at': scan.started_at.isoformat() if scan.started_at else None,
            'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
            'duration_seconds': float(scan.duration_seconds) if scan.duration_seconds else None,
            'sample_id': scan.sample_id,
            'queue_id': scan.queue_id,
            'notes': scan.notes,
            'wandb_link': scan.wandb_link,
            'created_at': scan.created_at.isoformat() if scan.created_at else None,
            'pybirch_uri': f"pybirch://scan/{scan.id}",
        }
    
    def _measurement_object_to_dict(self, mo: MeasurementObject) -> Dict:
        """Convert MeasurementObject to dictionary."""
        return {
            'id': mo.id,
            'name': mo.name,
            'data_type': mo.data_type,
            'unit': mo.unit,
            'instrument_name': mo.instrument_name,
            'columns': mo.columns,
            'description': mo.description,
        }

    def create_scan(self, data: Dict[str, Any]) -> Dict:
        """Create a new scan record.
        
        Args:
            data: Dictionary with scan data including:
                - scan_id: Unique scan identifier (optional, will generate if not provided)
                - scan_name: Human-readable name
                - scan_type: Type of scan
                - sample_id: Associated sample ID
                - queue_id: Associated queue ID (optional)
                - project_id: Associated project ID (optional)
                - owner: Owner/operator name
                - settings: Scan settings dictionary
                - notes: Optional notes
                
        Returns:
            Created scan as dictionary
        """
        with self.session_scope() as session:
            # Generate scan_id if not provided
            if 'scan_id' not in data or not data['scan_id']:
                from datetime import datetime
                import random
                data['scan_id'] = f"SCAN-{datetime.now().strftime('%Y%m%d')}-{random.randint(0, 999):03d}"
            
            scan = Scan(**data)
            session.add(scan)
            session.flush()
            return self._scan_to_dict(scan)
    
    def update_scan(self, scan_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update an existing scan.
        
        Args:
            scan_id: Database scan ID (not scan_id string)
            data: Dictionary with fields to update
            
        Returns:
            Updated scan as dictionary, or None if not found
        """
        with self.session_scope() as session:
            scan = session.query(Scan).filter(Scan.id == scan_id).first()
            if not scan:
                return None
            
            for key, value in data.items():
                if hasattr(scan, key):
                    setattr(scan, key, value)
            
            session.flush()
            return self._scan_to_dict(scan)
    
    def update_scan_status(self, scan_id: int, status: str, **kwargs) -> Optional[Dict]:
        """Update scan status with optional additional fields.
        
        Args:
            scan_id: Database scan ID
            status: New status ('pending', 'running', 'paused', 'completed', 'failed', 'aborted')
            **kwargs: Additional fields to update (started_at, completed_at, error_message, etc.)
            
        Returns:
            Updated scan as dictionary, or None if not found
        """
        data = {'status': status, **kwargs}
        return self.update_scan(scan_id, data)
    
    def get_scan_by_scan_id(self, scan_id_str: str) -> Optional[Dict]:
        """Get a scan by its scan_id string (not database ID).
        
        Args:
            scan_id_str: The scan_id string like 'SCAN-20250101-001'
            
        Returns:
            Scan as dictionary, or None if not found
        """
        with self.session_scope() as session:
            scan = session.query(Scan).filter(Scan.scan_id == scan_id_str).first()
            return self._scan_to_dict(scan) if scan else None
    
    def delete_scan(self, scan_id: int) -> bool:
        """Delete a scan and its associated data.
        
        Args:
            scan_id: Database scan ID
            
        Returns:
            True if deleted, False if not found
        """
        with self.session_scope() as session:
            scan = session.query(Scan).filter(Scan.id == scan_id).first()
            if not scan:
                return False
            
            # Delete associated measurement data
            for mo in scan.measurement_objects:
                session.query(MeasurementDataPoint).filter(
                    MeasurementDataPoint.measurement_id == mo.id
                ).delete()
                session.delete(mo)
            
            session.delete(scan)
            return True
    
    def create_measurement_object(
        self, 
        scan_id: int, 
        name: str, 
        data_type: str = 'float',
        unit: Optional[str] = None,
        instrument_name: Optional[str] = None,
        columns: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> Dict:
        """Create a measurement object for a scan.
        
        Args:
            scan_id: Database scan ID
            name: Measurement name/identifier
            data_type: Type of data ('float', 'int', 'string', 'array', 'blob')
            unit: Unit of measurement
            instrument_name: Name of instrument
            columns: Column names for tabular data
            description: Description of measurement
            
        Returns:
            Created measurement object as dictionary
        """
        with self.session_scope() as session:
            mo = MeasurementObject(
                scan_id=scan_id,
                name=name,
                data_type=data_type,
                unit=unit,
                instrument_name=instrument_name,
                columns=columns,
                description=description,
            )
            session.add(mo)
            session.flush()
            return self._measurement_object_to_dict(mo)
    
    def get_measurement_object(self, scan_id: int, name: str) -> Optional[Dict]:
        """Get a measurement object by scan ID and name.
        
        Args:
            scan_id: Database scan ID
            name: Measurement name
            
        Returns:
            Measurement object as dictionary, or None if not found
        """
        with self.session_scope() as session:
            mo = session.query(MeasurementObject).filter(
                MeasurementObject.scan_id == scan_id,
                MeasurementObject.name == name
            ).first()
            return self._measurement_object_to_dict(mo) if mo else None
    
    def create_data_point(
        self,
        measurement_id: int,
        values: Dict[str, Any],
        sequence_index: Optional[int] = None,
        timestamp: Optional[datetime] = None,
        extra_data: Optional[Dict] = None,
    ) -> Dict:
        """Create a single measurement data point.
        
        Args:
            measurement_id: Measurement object ID
            values: Dictionary of values
            sequence_index: Sequence index in the measurement
            timestamp: Timestamp for the data point
            extra_data: Additional metadata
            
        Returns:
            Created data point as dictionary
        """
        with self.session_scope() as session:
            point = MeasurementDataPoint(
                measurement_id=measurement_id,
                values=values,
                sequence_index=sequence_index,
                timestamp=timestamp or datetime.now(),
                extra_data=extra_data,
            )
            session.add(point)
            session.flush()
            return {
                'id': point.id,
                'measurement_id': point.measurement_id,
                'sequence_index': point.sequence_index,
                'values': point.values,
                'timestamp': point.timestamp.isoformat() if point.timestamp else None,
            }
    
    def bulk_create_data_points(
        self,
        measurement_id: int,
        data_points: List[Dict[str, Any]],
    ) -> int:
        """Bulk create measurement data points.
        
        Args:
            measurement_id: Measurement object ID
            data_points: List of data point dictionaries with 'values', optional 'sequence_index', 'timestamp', 'extra_data'
            
        Returns:
            Number of data points created
        """
        with self.session_scope() as session:
            points = []
            for i, dp in enumerate(data_points):
                point = MeasurementDataPoint(
                    measurement_id=measurement_id,
                    values=dp.get('values', dp),
                    sequence_index=dp.get('sequence_index', i),
                    timestamp=dp.get('timestamp', datetime.now()),
                    extra_data=dp.get('extra_data'),
                )
                points.append(point)
            
            session.bulk_save_objects(points)
            return len(points)

    # ==================== Queues ====================
    
    def get_queues(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of queues with optional filtering."""
        with self.session_scope() as session:
            query = session.query(Queue)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Queue.name.ilike(search_term),
                        Queue.queue_id.ilike(search_term)
                    )
                )
            
            if status:
                query = query.filter(Queue.status == status)
            
            total = query.count()
            offset = (page - 1) * per_page
            queues = query.order_by(desc(Queue.created_at)).offset(offset).limit(per_page).all()
            
            return [self._queue_to_dict(q) for q in queues], total
    
    def get_queue(self, queue_id: int) -> Optional[Dict]:
        """Get a single queue by ID with related scans."""
        with self.session_scope() as session:
            queue = session.query(Queue).options(
                joinedload(Queue.sample),
                joinedload(Queue.scans),
            ).filter(Queue.id == queue_id).first()
            
            if not queue:
                return None
            
            result = self._queue_to_dict(queue)
            result['sample'] = self._sample_to_dict(queue.sample) if queue.sample else None
            result['scans'] = [self._scan_to_dict(s) for s in queue.scans]
            return result
    
    def _queue_to_dict(self, queue: Queue) -> Dict:
        """Convert Queue model to dictionary."""
        return {
            'id': queue.id,
            'queue_id': queue.queue_id,
            'name': queue.name,
            'status': queue.status,
            'execution_mode': queue.execution_mode,
            'priority': queue.priority,
            'total_scans': queue.total_scans,
            'completed_scans': queue.completed_scans,
            'started_at': queue.started_at.isoformat() if queue.started_at else None,
            'completed_at': queue.completed_at.isoformat() if queue.completed_at else None,
            'sample_id': queue.sample_id,
            'operator': queue.operator,
            'notes': queue.notes,
            'created_at': queue.created_at.isoformat() if queue.created_at else None,
            'pybirch_uri': f"pybirch://queue/{queue.id}",
        }
    
    def create_queue(self, data: Dict[str, Any]) -> Dict:
        """Create a new queue record.
        
        Args:
            data: Dictionary with queue data including:
                - queue_id: Unique queue identifier (optional, will generate if not provided)
                - name: Human-readable name
                - execution_mode: 'sequential' or 'parallel'
                - sample_id: Associated sample ID (optional)
                - project_id: Associated project ID (optional)
                - operator: Operator name
                - total_scans: Total number of scans planned
                - notes: Optional notes
                
        Returns:
            Created queue as dictionary
        """
        with self.session_scope() as session:
            # Generate queue_id if not provided
            if 'queue_id' not in data or not data['queue_id']:
                from datetime import datetime
                import random
                data['queue_id'] = f"Q-{datetime.now().strftime('%Y%m%d')}-{random.randint(0, 999):03d}"
            
            queue = Queue(**data)
            session.add(queue)
            session.flush()
            return self._queue_to_dict(queue)
    
    def update_queue(self, queue_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update an existing queue.
        
        Args:
            queue_id: Database queue ID (not queue_id string)
            data: Dictionary with fields to update
            
        Returns:
            Updated queue as dictionary, or None if not found
        """
        with self.session_scope() as session:
            queue = session.query(Queue).filter(Queue.id == queue_id).first()
            if not queue:
                return None
            
            for key, value in data.items():
                if hasattr(queue, key):
                    setattr(queue, key, value)
            
            session.flush()
            return self._queue_to_dict(queue)
    
    def update_queue_status(self, queue_id: int, status: str, **kwargs) -> Optional[Dict]:
        """Update queue status with optional additional fields.
        
        Args:
            queue_id: Database queue ID
            status: New status ('pending', 'running', 'paused', 'completed', 'stopped', 'failed')
            **kwargs: Additional fields to update (started_at, completed_at, completed_scans, etc.)
            
        Returns:
            Updated queue as dictionary, or None if not found
        """
        data = {'status': status, **kwargs}
        return self.update_queue(queue_id, data)
    
    def get_queue_by_queue_id(self, queue_id_str: str) -> Optional[Dict]:
        """Get a queue by its queue_id string (not database ID).
        
        Args:
            queue_id_str: The queue_id string like 'Q-20250101-001'
            
        Returns:
            Queue as dictionary, or None if not found
        """
        with self.session_scope() as session:
            queue = session.query(Queue).filter(Queue.queue_id == queue_id_str).first()
            return self._queue_to_dict(queue) if queue else None
    
    def delete_queue(self, queue_id: int) -> bool:
        """Delete a queue (does not delete associated scans).
        
        Args:
            queue_id: Database queue ID
            
        Returns:
            True if deleted, False if not found
        """
        with self.session_scope() as session:
            queue = session.query(Queue).filter(Queue.id == queue_id).first()
            if not queue:
                return False
            
            # Unlink scans from this queue
            session.query(Scan).filter(Scan.queue_id == queue_id).update(
                {'queue_id': None}
            )
            
            session.delete(queue)
            return True
    
    def create_queue_log(
        self,
        queue_id: int,
        level: str,
        message: str,
        scan_id: Optional[str] = None,
        extra_data: Optional[Dict] = None,
    ) -> Dict:
        """Create a log entry for a queue.
        
        Args:
            queue_id: Database queue ID
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
            message: Log message
            scan_id: Associated scan_id string (optional)
            extra_data: Additional data (optional)
            
        Returns:
            Created log entry as dictionary
        """
        with self.session_scope() as session:
            log = QueueLog(
                queue_id=queue_id,
                level=level,
                message=message,
                scan_id=scan_id,
                extra_data=extra_data,
            )
            session.add(log)
            session.flush()
            return {
                'id': log.id,
                'queue_id': log.queue_id,
                'level': log.level,
                'message': log.message,
                'scan_id': log.scan_id,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'extra_data': log.extra_data,
            }
    
    def get_queue_logs(
        self,
        queue_id: int,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get log entries for a queue.
        
        Args:
            queue_id: Database queue ID
            level: Filter by level (optional)
            limit: Maximum number of entries to return
            
        Returns:
            List of log entries as dictionaries
        """
        with self.session_scope() as session:
            query = session.query(QueueLog).filter(QueueLog.queue_id == queue_id)
            
            if level:
                query = query.filter(QueueLog.level == level)
            
            logs = query.order_by(desc(QueueLog.timestamp)).limit(limit).all()
            
            return [
                {
                    'id': log.id,
                    'queue_id': log.queue_id,
                    'level': log.level,
                    'message': log.message,
                    'scan_id': log.scan_id,
                    'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                    'extra_data': log.extra_data,
                }
                for log in logs
            ]
    
    def get_equipment_by_name(self, name: str) -> Optional[Dict]:
        """Get equipment by name.
        
        Args:
            name: Equipment name
            
        Returns:
            Equipment as dictionary, or None if not found
        """
        with self.session_scope() as session:
            equipment = session.query(Equipment).filter(Equipment.name == name).first()
            return self._equipment_to_dict(equipment) if equipment else None

    # ==================== Equipment ====================
    
    def get_equipment_list(
        self,
        search: Optional[str] = None,
        equipment_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of equipment."""
        with self.session_scope() as session:
            query = session.query(Equipment)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Equipment.name.ilike(search_term),
                        Equipment.manufacturer.ilike(search_term),
                        Equipment.model.ilike(search_term)
                    )
                )
            
            if equipment_type:
                query = query.filter(Equipment.equipment_type == equipment_type)
            
            if status:
                query = query.filter(Equipment.status == status)
            
            total = query.count()
            offset = (page - 1) * per_page
            equipment = query.order_by(Equipment.name).offset(offset).limit(per_page).all()
            
            return [self._equipment_to_dict(e) for e in equipment], total
    
    def get_equipment(self, equipment_id: int) -> Optional[Dict]:
        """Get a single equipment by ID."""
        with self.session_scope() as session:
            equipment = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            return self._equipment_to_dict(equipment) if equipment else None
    
    def create_equipment(self, data: Dict[str, Any]) -> Dict:
        """Create new equipment."""
        with self.session_scope() as session:
            equipment = Equipment(**data)
            session.add(equipment)
            session.flush()
            return self._equipment_to_dict(equipment)
    
    def update_equipment(self, equipment_id: int, data: Dict) -> Optional[Dict]:
        """Update an existing equipment."""
        with self.session_scope() as session:
            equipment = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not equipment:
                return None
            
            for field in ['name', 'equipment_type', 'pybirch_class', 'manufacturer', 'model',
                          'serial_number', 'adapter', 'location', 'status', 'specifications']:
                if field in data:
                    setattr(equipment, field, data[field])
            
            session.flush()
            return self._equipment_to_dict(equipment)
    
    def _equipment_to_dict(self, equipment: Equipment) -> Dict:
        """Convert Equipment model to dictionary."""
        return {
            'id': equipment.id,
            'name': equipment.name,
            'equipment_type': equipment.equipment_type,
            'pybirch_class': equipment.pybirch_class,
            'manufacturer': equipment.manufacturer,
            'model': equipment.model,
            'serial_number': equipment.serial_number,
            'adapter': equipment.adapter,
            'location': equipment.location,
            'status': equipment.status,
            'specifications': equipment.specifications,
            'calibration_date': equipment.calibration_date.isoformat() if equipment.calibration_date else None,
            'next_calibration_date': equipment.next_calibration_date.isoformat() if equipment.next_calibration_date else None,
            'created_at': equipment.created_at.isoformat() if equipment.created_at else None,
        }
    
    # ==================== Precursors ====================
    
    def get_precursors(
        self,
        search: Optional[str] = None,
        state: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of precursors."""
        with self.session_scope() as session:
            query = session.query(Precursor)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Precursor.name.ilike(search_term),
                        Precursor.chemical_formula.ilike(search_term),
                        Precursor.supplier.ilike(search_term)
                    )
                )
            
            if state:
                query = query.filter(Precursor.state == state)
            
            total = query.count()
            offset = (page - 1) * per_page
            precursors = query.order_by(Precursor.name).offset(offset).limit(per_page).all()
            
            return [self._precursor_to_dict(p) for p in precursors], total
    
    def get_precursor(self, precursor_id: int) -> Optional[Dict]:
        """Get a single precursor by ID."""
        with self.session_scope() as session:
            precursor = session.query(Precursor).filter(Precursor.id == precursor_id).first()
            return self._precursor_to_dict(precursor) if precursor else None
    
    def create_precursor(self, data: Dict[str, Any]) -> Dict:
        """Create a new precursor."""
        with self.session_scope() as session:
            precursor = Precursor(**data)
            session.add(precursor)
            session.flush()
            return self._precursor_to_dict(precursor)
    
    def update_precursor(self, precursor_id: int, data: Dict) -> Optional[Dict]:
        """Update an existing precursor."""
        with self.session_scope() as session:
            precursor = session.query(Precursor).filter(Precursor.id == precursor_id).first()
            if not precursor:
                return None
            
            for field in ['name', 'chemical_formula', 'cas_number', 'supplier', 'lot_number',
                          'purity', 'state', 'status', 'concentration', 'concentration_unit',
                          'storage_conditions', 'safety_info']:
                if field in data:
                    setattr(precursor, field, data[field])
            
            session.flush()
            return self._precursor_to_dict(precursor)
    
    def _precursor_to_dict(self, precursor: Precursor) -> Dict:
        """Convert Precursor model to dictionary."""
        return {
            'id': precursor.id,
            'name': precursor.name,
            'chemical_formula': precursor.chemical_formula,
            'cas_number': precursor.cas_number,
            'supplier': precursor.supplier,
            'lot_number': precursor.lot_number,
            'purity': float(precursor.purity) if precursor.purity else None,
            'state': precursor.state,
            'status': precursor.status,
            'concentration': float(precursor.concentration) if precursor.concentration else None,
            'concentration_unit': precursor.concentration_unit,
            'storage_conditions': precursor.storage_conditions,
            'expiration_date': precursor.expiration_date.isoformat() if precursor.expiration_date else None,
            'created_at': precursor.created_at.isoformat() if precursor.created_at else None,
        }
    
    # ==================== Procedures ====================
    
    def get_procedures(
        self,
        search: Optional[str] = None,
        procedure_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of procedures."""
        with self.session_scope() as session:
            query = session.query(Procedure).filter(Procedure.is_active == True)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Procedure.name.ilike(search_term),
                        Procedure.description.ilike(search_term)
                    )
                )
            
            if procedure_type:
                query = query.filter(Procedure.procedure_type == procedure_type)
            
            total = query.count()
            offset = (page - 1) * per_page
            procedures = query.order_by(Procedure.name).offset(offset).limit(per_page).all()
            
            return [self._procedure_to_dict(p) for p in procedures], total
    
    def get_procedures_simple_list(self) -> List[Dict]:
        """Get simple list of active procedures for dropdowns."""
        with self.session_scope() as session:
            procedures = session.query(Procedure).filter(
                Procedure.is_active == True
            ).order_by(Procedure.name).all()
            
            return [{
                'id': p.id,
                'name': p.name,
                'procedure_type': p.procedure_type,
                'version': p.version,
            } for p in procedures]
    
    def get_procedure(self, procedure_id: int) -> Optional[Dict]:
        """Get a single procedure by ID with fabrication runs."""
        with self.session_scope() as session:
            procedure = session.query(Procedure).filter(Procedure.id == procedure_id).first()
            if not procedure:
                return None
            
            result = self._procedure_to_dict(procedure)
            
            # Get fabrication runs (samples that used this procedure)
            runs = session.query(FabricationRun).filter(
                FabricationRun.procedure_id == procedure_id
            ).order_by(FabricationRun.created_at.desc()).all()
            
            result['fabrication_runs'] = [
                {
                    'id': run.id,
                    'sample_id': run.sample_id,
                    'sample_name': run.sample.name if run.sample else None,
                    'sample_sample_id': run.sample.sample_id if run.sample else None,
                    'run_number': run.run_number,
                    'status': run.status,
                    'operator': run.operator,
                    'started_at': run.started_at.isoformat() if run.started_at else None,
                    'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                    'weather_conditions': run.weather_conditions,
                }
                for run in runs
            ]
            
            return result
    
    def create_fabrication_run(self, data: Dict, fetch_weather: bool = True) -> Dict:
        """Create a new fabrication run, optionally fetching current weather.
        
        Args:
            data: Fabrication run data including sample_id, procedure_id, operator, etc.
            fetch_weather: If True, automatically fetch current weather conditions.
            
        Returns:
            Dictionary representation of the created fabrication run.
        """
        with self.session_scope() as session:
            # Optionally fetch weather conditions
            weather = data.get('weather_conditions')
            if weather is None and fetch_weather:
                try:
                    from database.weather import get_weather_conditions
                    weather = get_weather_conditions()
                except Exception:
                    pass  # Weather fetch is best-effort
            
            run = FabricationRun(
                sample_id=data['sample_id'],
                procedure_id=data['procedure_id'],
                run_number=data.get('run_number'),
                started_at=data.get('started_at'),
                status=data.get('status', 'pending'),
                operator=data.get('operator'),
                actual_parameters=data.get('actual_parameters'),
                notes=data.get('notes'),
                weather_conditions=weather,
            )
            session.add(run)
            session.flush()
            
            return {
                'id': run.id,
                'sample_id': run.sample_id,
                'procedure_id': run.procedure_id,
                'run_number': run.run_number,
                'status': run.status,
                'operator': run.operator,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'weather_conditions': run.weather_conditions,
                'created_at': run.created_at.isoformat() if run.created_at else None,
            }
    
    def update_fabrication_run(self, run_id: int, data: Dict) -> Optional[Dict]:
        """Update a fabrication run."""
        with self.session_scope() as session:
            run = session.query(FabricationRun).filter(FabricationRun.id == run_id).first()
            if not run:
                return None
            
            for field in ['procedure_id', 'run_number', 'status', 'operator', 
                          'actual_parameters', 'notes', 'results']:
                if field in data:
                    setattr(run, field, data[field])
            
            # Handle datetime fields
            if 'started_at' in data:
                run.started_at = data['started_at']
            if 'completed_at' in data:
                run.completed_at = data['completed_at']
            
            session.flush()
            
            return {
                'id': run.id,
                'sample_id': run.sample_id,
                'procedure_id': run.procedure_id,
                'run_number': run.run_number,
                'status': run.status,
                'operator': run.operator,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'notes': run.notes,
                'weather_conditions': run.weather_conditions,
            }
    
    def delete_fabrication_run(self, run_id: int) -> bool:
        """Delete a fabrication run."""
        with self.session_scope() as session:
            run = session.query(FabricationRun).filter(FabricationRun.id == run_id).first()
            if not run:
                return False
            session.delete(run)
            return True
    
    def create_procedure(self, data: Dict) -> Dict:
        """Create a new procedure."""
        with self.session_scope() as session:
            procedure = Procedure(
                name=data['name'],
                procedure_type=data.get('procedure_type'),
                version=data.get('version', '1.0'),
                description=data.get('description'),
                steps=data.get('steps'),
                parameters=data.get('parameters'),
                estimated_duration_minutes=data.get('estimated_duration_minutes'),
                safety_requirements=data.get('safety_requirements'),
                created_by=data.get('created_by'),
                is_active=True,
            )
            session.add(procedure)
            session.flush()
            return self._procedure_to_dict(procedure)
    
    def update_procedure(self, procedure_id: int, data: Dict) -> Optional[Dict]:
        """Update an existing procedure."""
        with self.session_scope() as session:
            procedure = session.query(Procedure).filter(Procedure.id == procedure_id).first()
            if not procedure:
                return None
            
            for field in ['name', 'procedure_type', 'version', 'description', 'steps', 
                          'parameters', 'estimated_duration_minutes', 'safety_requirements', 
                          'created_by', 'is_active']:
                if field in data:
                    setattr(procedure, field, data[field])
            
            session.flush()
            return self._procedure_to_dict(procedure)
    
    def _procedure_to_dict(self, procedure: Procedure) -> Dict:
        """Convert Procedure model to dictionary."""
        return {
            'id': procedure.id,
            'name': procedure.name,
            'procedure_type': procedure.procedure_type,
            'version': procedure.version,
            'description': procedure.description,
            'steps': procedure.steps,
            'parameters': procedure.parameters,
            'estimated_duration_minutes': procedure.estimated_duration_minutes,
            'safety_requirements': procedure.safety_requirements,
            'is_active': procedure.is_active,
            'created_at': procedure.created_at.isoformat() if procedure.created_at else None,
            'created_by': procedure.created_by,
        }
    
    # ==================== Labs ====================
    
    def get_labs(
        self,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of labs."""
        with self.session_scope() as session:
            query = session.query(Lab).filter(Lab.is_active == True)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Lab.name.ilike(search_term),
                        Lab.code.ilike(search_term),
                        Lab.university.ilike(search_term),
                        Lab.department.ilike(search_term)
                    )
                )
            
            total = query.count()
            offset = (page - 1) * per_page
            labs = query.order_by(Lab.name).offset(offset).limit(per_page).all()
            
            return [self._lab_to_dict(l) for l in labs], total
    
    def get_labs_simple_list(self) -> List[Dict]:
        """Get a simple list of all active labs for dropdowns."""
        with self.session_scope() as session:
            labs = session.query(Lab).filter(
                Lab.is_active == True
            ).order_by(Lab.name).all()
            return [{
                'id': l.id,
                'name': l.name,
                'code': l.code,
                'display': f"{l.name}" + (f" ({l.code})" if l.code else "")
            } for l in labs]
    
    def get_lab(self, lab_id: int) -> Optional[Dict]:
        """Get a single lab with members and projects."""
        with self.session_scope() as session:
            lab = session.query(Lab).options(
                joinedload(Lab.members),
                joinedload(Lab.projects),
            ).filter(Lab.id == lab_id).first()
            
            if not lab:
                return None
            
            result = self._lab_to_dict(lab)
            result['members'] = [self._lab_member_to_dict(m) for m in lab.members if m.is_active]
            result['projects'] = [self._project_to_dict(p) for p in lab.projects]
            return result
    
    def create_lab(self, data: Dict[str, Any]) -> Dict:
        """Create a new lab."""
        with self.session_scope() as session:
            lab = Lab(**data)
            session.add(lab)
            session.flush()
            return self._lab_to_dict(lab)
    
    def update_lab(self, lab_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update an existing lab."""
        with self.session_scope() as session:
            lab = session.query(Lab).filter(Lab.id == lab_id).first()
            if not lab:
                return None
            
            allowed_fields = ['name', 'code', 'university', 'department', 'description',
                            'address', 'website', 'email', 'phone', 'logo_path', 'settings', 'is_active']
            for field in allowed_fields:
                if field in data:
                    setattr(lab, field, data[field])
            
            session.flush()
            return self._lab_to_dict(lab)
    
    def delete_lab(self, lab_id: int) -> bool:
        """Soft delete a lab."""
        with self.session_scope() as session:
            lab = session.query(Lab).filter(Lab.id == lab_id).first()
            if lab:
                lab.is_active = False
                return True
            return False
    
    def _lab_to_dict(self, lab: Lab) -> Dict:
        """Convert Lab model to dictionary."""
        return {
            'id': lab.id,
            'name': lab.name,
            'code': lab.code,
            'university': lab.university,
            'department': lab.department,
            'description': lab.description,
            'address': lab.address,
            'website': lab.website,
            'email': lab.email,
            'phone': lab.phone,
            'logo_path': lab.logo_path,
            'is_active': lab.is_active,
            'created_at': lab.created_at.isoformat() if lab.created_at else None,
        }
    
    # ==================== Lab Members ====================
    
    def get_lab_members(self, lab_id: int) -> List[Dict]:
        """Get all members of a lab."""
        with self.session_scope() as session:
            members = session.query(LabMember).filter(
                LabMember.lab_id == lab_id,
                LabMember.is_active == True
            ).order_by(LabMember.role, LabMember.name).all()
            return [self._lab_member_to_dict(m) for m in members]
    
    def get_lab_member(self, member_id: int) -> Optional[Dict]:
        """Get a single lab member."""
        with self.session_scope() as session:
            member = session.query(LabMember).filter(LabMember.id == member_id).first()
            return self._lab_member_to_dict(member) if member else None
    
    def create_lab_member(self, lab_id: int, data: Dict[str, Any]) -> Dict:
        """Add a member to a lab."""
        with self.session_scope() as session:
            member = LabMember(lab_id=lab_id, **data)
            session.add(member)
            session.flush()
            return self._lab_member_to_dict(member)
    
    def update_lab_member(self, member_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update a lab member."""
        with self.session_scope() as session:
            member = session.query(LabMember).filter(LabMember.id == member_id).first()
            if not member:
                return None
            
            allowed_fields = ['name', 'email', 'role', 'title', 'orcid', 'phone',
                            'office_location', 'is_active', 'notes']
            for field in allowed_fields:
                if field in data:
                    setattr(member, field, data[field])
            
            session.flush()
            return self._lab_member_to_dict(member)
    
    def remove_lab_member(self, member_id: int) -> bool:
        """Remove a member from lab (soft delete)."""
        with self.session_scope() as session:
            member = session.query(LabMember).filter(LabMember.id == member_id).first()
            if member:
                member.is_active = False
                member.left_at = datetime.utcnow()
                return True
            return False
    
    def _lab_member_to_dict(self, member: LabMember) -> Dict:
        """Convert LabMember model to dictionary."""
        return {
            'id': member.id,
            'lab_id': member.lab_id,
            'name': member.name,
            'email': member.email,
            'role': member.role,
            'title': member.title,
            'orcid': member.orcid,
            'phone': member.phone,
            'office_location': member.office_location,
            'is_active': member.is_active,
            'joined_at': member.joined_at.isoformat() if member.joined_at else None,
            'left_at': member.left_at.isoformat() if member.left_at else None,
            'notes': member.notes,
        }
    
    # ==================== Projects ====================
    
    def get_projects(
        self,
        search: Optional[str] = None,
        lab_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of projects."""
        with self.session_scope() as session:
            query = session.query(Project).options(joinedload(Project.lab))
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Project.name.ilike(search_term),
                        Project.code.ilike(search_term),
                        Project.description.ilike(search_term)
                    )
                )
            
            if lab_id:
                query = query.filter(Project.lab_id == lab_id)
            
            if status:
                query = query.filter(Project.status == status)
            
            total = query.count()
            offset = (page - 1) * per_page
            projects = query.order_by(desc(Project.created_at)).offset(offset).limit(per_page).all()
            
            results = []
            for p in projects:
                proj_dict = self._project_to_dict(p)
                proj_dict['lab_name'] = p.lab.name if p.lab else None
                results.append(proj_dict)
            return results, total
    
    def get_project(self, project_id: int) -> Optional[Dict]:
        """Get a single project with related data."""
        with self.session_scope() as session:
            project = session.query(Project).options(
                joinedload(Project.lab),
                joinedload(Project.members),
                joinedload(Project.samples),
                joinedload(Project.scans),
                joinedload(Project.queues),
            ).filter(Project.id == project_id).first()
            
            if not project:
                return None
            
            result = self._project_to_dict(project)
            result['lab'] = self._lab_to_dict(project.lab) if project.lab else None
            result['members'] = [self._project_member_to_dict(m) for m in project.members if m.is_active]
            result['samples'] = [self._sample_to_dict(s) for s in project.samples[:10]]
            result['scans'] = [self._scan_to_dict(s) for s in project.scans[:10]]
            result['queues'] = [self._queue_to_dict(q) for q in project.queues[:10]]
            result['sample_count'] = len(project.samples)
            result['scan_count'] = len(project.scans)
            result['queue_count'] = len(project.queues)
            return result
    
    def create_project(self, data: Dict[str, Any]) -> Dict:
        """Create a new project."""
        with self.session_scope() as session:
            project = Project(**data)
            session.add(project)
            session.flush()
            return self._project_to_dict(project)
    
    def update_project(self, project_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update an existing project."""
        with self.session_scope() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                return None
            
            allowed_fields = ['name', 'code', 'description', 'status', 'start_date', 'end_date',
                            'funding_source', 'grant_number', 'budget', 'goals', 'settings', 'lab_id']
            for field in allowed_fields:
                if field in data:
                    setattr(project, field, data[field])
            
            session.flush()
            return self._project_to_dict(project)
    
    def delete_project(self, project_id: int) -> bool:
        """Archive a project."""
        with self.session_scope() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = 'archived'
                return True
            return False
    
    def _project_to_dict(self, project: Project) -> Dict:
        """Convert Project model to dictionary."""
        return {
            'id': project.id,
            'lab_id': project.lab_id,
            'name': project.name,
            'code': project.code,
            'description': project.description,
            'status': project.status,
            'start_date': project.start_date.isoformat() if project.start_date else None,
            'end_date': project.end_date.isoformat() if project.end_date else None,
            'funding_source': project.funding_source,
            'grant_number': project.grant_number,
            'budget': float(project.budget) if project.budget else None,
            'goals': project.goals,
            'created_at': project.created_at.isoformat() if project.created_at else None,
            'created_by': project.created_by,
        }
    
    # ==================== Project Members ====================
    
    def get_project_members(self, project_id: int) -> List[Dict]:
        """Get all members of a project."""
        with self.session_scope() as session:
            members = session.query(ProjectMember).options(
                joinedload(ProjectMember.lab_member)
            ).filter(
                ProjectMember.project_id == project_id,
                ProjectMember.is_active == True
            ).order_by(ProjectMember.role).all()
            return [self._project_member_to_dict(m) for m in members]
    
    def add_project_member(self, project_id: int, data: Dict[str, Any]) -> Dict:
        """Add a member to a project."""
        with self.session_scope() as session:
            member = ProjectMember(project_id=project_id, **data)
            session.add(member)
            session.flush()
            return self._project_member_to_dict(member)
    
    def update_project_member(self, member_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update a project member."""
        with self.session_scope() as session:
            member = session.query(ProjectMember).filter(ProjectMember.id == member_id).first()
            if not member:
                return None
            
            allowed_fields = ['role', 'permissions', 'is_active', 'notes',
                            'external_name', 'external_email', 'external_affiliation']
            for field in allowed_fields:
                if field in data:
                    setattr(member, field, data[field])
            
            session.flush()
            return self._project_member_to_dict(member)
    
    def remove_project_member(self, member_id: int) -> bool:
        """Remove a member from project."""
        with self.session_scope() as session:
            member = session.query(ProjectMember).filter(ProjectMember.id == member_id).first()
            if member:
                member.is_active = False
                member.left_at = datetime.utcnow()
                return True
            return False
    
    def _project_member_to_dict(self, member: ProjectMember) -> Dict:
        """Convert ProjectMember model to dictionary."""
        result = {
            'id': member.id,
            'project_id': member.project_id,
            'lab_member_id': member.lab_member_id,
            'role': member.role,
            'permissions': member.permissions,
            'is_active': member.is_active,
            'joined_at': member.joined_at.isoformat() if member.joined_at else None,
            'left_at': member.left_at.isoformat() if member.left_at else None,
            'notes': member.notes,
            'external_name': member.external_name,
            'external_email': member.external_email,
            'external_affiliation': member.external_affiliation,
        }
        # Include lab member info if available
        if member.lab_member:
            result['name'] = member.lab_member.name
            result['email'] = member.lab_member.email
            result['title'] = member.lab_member.title
        else:
            result['name'] = member.external_name
            result['email'] = member.external_email
            result['title'] = member.external_affiliation
        return result
    
    # ==================== Item Guests (Collaborator Access) ====================
    
    def get_item_guests(self, entity_type: str, entity_id: int) -> List[Dict]:
        """Get all guests for a specific item."""
        with self.session_scope() as session:
            guests = session.query(ItemGuest).filter(
                ItemGuest.entity_type == entity_type,
                ItemGuest.entity_id == entity_id,
                ItemGuest.is_active == True
            ).order_by(ItemGuest.granted_at).all()
            return [self._item_guest_to_dict(g) for g in guests]
    
    def add_item_guest(self, entity_type: str, entity_id: int, data: Dict[str, Any]) -> Dict:
        """Add guest access to an item."""
        import secrets
        with self.session_scope() as session:
            guest = ItemGuest(
                entity_type=entity_type,
                entity_id=entity_id,
                access_token=secrets.token_urlsafe(32),
                **data
            )
            session.add(guest)
            session.flush()
            return self._item_guest_to_dict(guest)
    
    def update_item_guest(self, guest_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update guest access."""
        with self.session_scope() as session:
            guest = session.query(ItemGuest).filter(ItemGuest.id == guest_id).first()
            if not guest:
                return None
            
            allowed_fields = ['access_level', 'expires_at', 'is_active', 'notes']
            for field in allowed_fields:
                if field in data:
                    setattr(guest, field, data[field])
            
            session.flush()
            return self._item_guest_to_dict(guest)
    
    def remove_item_guest(self, guest_id: int) -> bool:
        """Revoke guest access."""
        with self.session_scope() as session:
            guest = session.query(ItemGuest).filter(ItemGuest.id == guest_id).first()
            if guest:
                guest.is_active = False
                return True
            return False
    
    def get_guest_by_token(self, token: str) -> Optional[Dict]:
        """Get guest access by token for verification."""
        with self.session_scope() as session:
            guest = session.query(ItemGuest).filter(
                ItemGuest.access_token == token,
                ItemGuest.is_active == True
            ).first()
            
            if guest:
                # Check expiration
                if guest.expires_at and guest.expires_at < datetime.utcnow():
                    return None
                # Update last accessed
                guest.last_accessed_at = datetime.utcnow()
                session.flush()
                return self._item_guest_to_dict(guest)
            return None
    
    def _item_guest_to_dict(self, guest: ItemGuest) -> Dict:
        """Convert ItemGuest model to dictionary."""
        return {
            'id': guest.id,
            'entity_type': guest.entity_type,
            'entity_id': guest.entity_id,
            'guest_name': guest.guest_name,
            'guest_email': guest.guest_email,
            'guest_affiliation': guest.guest_affiliation,
            'access_level': guest.access_level,
            'access_token': guest.access_token,
            'granted_by': guest.granted_by,
            'granted_at': guest.granted_at.isoformat() if guest.granted_at else None,
            'expires_at': guest.expires_at.isoformat() if guest.expires_at else None,
            'last_accessed_at': guest.last_accessed_at.isoformat() if guest.last_accessed_at else None,
            'is_active': guest.is_active,
            'notes': guest.notes,
        }
    
    # ==================== Templates ====================
    
    def get_templates(
        self,
        search: Optional[str] = None,
        entity_type: Optional[str] = None,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of templates with filtering."""
        with self.session_scope() as session:
            query = session.query(Template).filter(Template.is_active == True)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Template.name.ilike(search_term),
                        Template.description.ilike(search_term)
                    )
                )
            
            if entity_type:
                query = query.filter(Template.entity_type == entity_type)
            
            if project_id:
                query = query.filter(Template.project_id == project_id)
            
            if status:
                query = query.filter(Template.status == status)
            
            total = query.count()
            offset = (page - 1) * per_page
            templates = query.order_by(Template.name).offset(offset).limit(per_page).all()
            
            return [self._template_to_dict(t) for t in templates], total
    
    def get_template(self, template_id: int) -> Optional[Dict]:
        """Get a single template by ID."""
        with self.session_scope() as session:
            template = session.query(Template).filter(
                Template.id == template_id,
                Template.is_active == True
            ).first()
            
            if not template:
                return None
            
            return self._template_to_dict(template)
    
    def create_template(self, data: Dict[str, Any]) -> Dict:
        """Create a new template."""
        with self.session_scope() as session:
            template = Template(**data)
            session.add(template)
            session.flush()
            return self._template_to_dict(template)
    
    def update_template(self, template_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update an existing template."""
        with self.session_scope() as session:
            template = session.query(Template).filter(
                Template.id == template_id,
                Template.is_active == True
            ).first()
            if not template:
                return None
            
            for key, value in data.items():
                if hasattr(template, key) and key not in ('id', 'created_at'):
                    setattr(template, key, value)
            
            session.flush()
            return self._template_to_dict(template)
    
    def delete_template(self, template_id: int) -> bool:
        """Soft delete a template by setting is_active to False."""
        with self.session_scope() as session:
            template = session.query(Template).filter(Template.id == template_id).first()
            if not template:
                return False
            template.is_active = False
            return True
    
    def _template_to_dict(self, template: Template) -> Dict:
        """Convert Template model to dictionary."""
        template_data = template.template_data or {}
        
        # Get status, default to 'active' if not set
        status = getattr(template, 'status', 'active') or 'active'
        
        return {
            'id': template.id,
            'name': template.name,
            'entity_type': template.entity_type,
            'description': template.description,
            'template_data': template.template_data,
            'status': status,
            'lab_id': template.lab_id,
            'project_id': template.project_id,
            'lab_name': template.lab.name if template.lab else None,
            'project_name': template.project.name if template.project else None,
            'created_at': template.created_at.isoformat() if template.created_at else None,
            'updated_at': template.updated_at.isoformat() if template.updated_at else None,
            'created_by': template.created_by,
            'is_active': template.is_active,
        }
    
    # ==================== Permissions Management ====================
    
    def get_entity_permissions(self, entity_type: str, entity_id: int) -> Dict:
        """Get all permissions for a specific entity."""
        with self.session_scope() as session:
            result = {
                'entity_type': entity_type,
                'entity_id': entity_id,
                'entity_name': '',
                'members': [],
                'guests': [],
            }
            
            # Get entity name
            if entity_type == 'lab':
                lab = session.query(Lab).filter(Lab.id == entity_id).first()
                if lab:
                    result['entity_name'] = lab.name
                    # Get lab members
                    members = session.query(LabMember).filter(
                        LabMember.lab_id == entity_id,
                        LabMember.is_active == True
                    ).order_by(LabMember.role).all()
                    result['members'] = [self._lab_member_to_dict(m) for m in members]
            
            elif entity_type == 'project':
                project = session.query(Project).filter(Project.id == entity_id).first()
                if project:
                    result['entity_name'] = project.name
                    # Get project members
                    members = session.query(ProjectMember).filter(
                        ProjectMember.project_id == entity_id,
                        ProjectMember.is_active == True
                    ).all()
                    result['members'] = [self._project_member_to_dict(m) for m in members]
                    # Get guests
                    guests = session.query(ItemGuest).filter(
                        ItemGuest.entity_type == 'project',
                        ItemGuest.entity_id == entity_id,
                        ItemGuest.is_active == True
                    ).all()
                    result['guests'] = [self._item_guest_to_dict(g) for g in guests]
            
            elif entity_type == 'sample':
                sample = session.query(Sample).filter(Sample.id == entity_id).first()
                if sample:
                    result['entity_name'] = sample.sample_id or sample.name or f'Sample #{entity_id}'
                    # Get guests
                    guests = session.query(ItemGuest).filter(
                        ItemGuest.entity_type == 'sample',
                        ItemGuest.entity_id == entity_id,
                        ItemGuest.is_active == True
                    ).all()
                    result['guests'] = [self._item_guest_to_dict(g) for g in guests]
            
            elif entity_type == 'scan':
                scan = session.query(Scan).filter(Scan.id == entity_id).first()
                if scan:
                    result['entity_name'] = scan.scan_name or f'Scan #{entity_id}'
                    guests = session.query(ItemGuest).filter(
                        ItemGuest.entity_type == 'scan',
                        ItemGuest.entity_id == entity_id,
                        ItemGuest.is_active == True
                    ).all()
                    result['guests'] = [self._item_guest_to_dict(g) for g in guests]
            
            elif entity_type == 'queue':
                queue = session.query(Queue).filter(Queue.id == entity_id).first()
                if queue:
                    result['entity_name'] = queue.name or f'Queue #{entity_id}'
                    guests = session.query(ItemGuest).filter(
                        ItemGuest.entity_type == 'queue',
                        ItemGuest.entity_id == entity_id,
                        ItemGuest.is_active == True
                    ).all()
                    result['guests'] = [self._item_guest_to_dict(g) for g in guests]
            
            return result
    
    def get_all_entities_for_permissions(self) -> Dict[str, List[Dict]]:
        """Get all entities that can have permissions managed."""
        with self.session_scope() as session:
            result = {
                'labs': [],
                'projects': [],
                'samples': [],
                'scans': [],
                'queues': [],
            }
            
            # Labs
            labs = session.query(Lab).filter(Lab.is_active == True).order_by(Lab.name).all()
            result['labs'] = [{'id': l.id, 'name': l.name, 'code': l.code} for l in labs]
            
            # Projects  
            projects = session.query(Project).order_by(Project.name).all()
            result['projects'] = [{'id': p.id, 'name': p.name, 'code': p.code, 'status': p.status} for p in projects]
            
            # Samples (recent 100)
            samples = session.query(Sample).order_by(Sample.created_at.desc()).limit(100).all()
            result['samples'] = [{'id': s.id, 'name': s.sample_id or s.name or f'Sample #{s.id}'} for s in samples]
            
            # Scans (recent 100)
            scans = session.query(Scan).order_by(Scan.created_at.desc()).limit(100).all()
            result['scans'] = [{'id': s.id, 'name': s.scan_name or f'Scan #{s.id}'} for s in scans]
            
            # Queues (recent 50)
            queues = session.query(Queue).order_by(Queue.created_at.desc()).limit(50).all()
            result['queues'] = [{'id': q.id, 'name': q.name or f'Queue #{q.id}'} for q in queues]
            
            return result
    
    def update_lab_member_role(self, member_id: int, new_role: str) -> Optional[Dict]:
        """Update a lab member's role."""
        valid_roles = ['principal_investigator', 'administrator', 'member', 'student', 'visiting']
        if new_role not in valid_roles:
            return None
        
        with self.session_scope() as session:
            member = session.query(LabMember).filter(LabMember.id == member_id).first()
            if not member:
                return None
            member.role = new_role
            session.flush()
            return self._lab_member_to_dict(member)
    
    def update_project_member_role(self, member_id: int, new_role: str) -> Optional[Dict]:
        """Update a project member's role."""
        valid_roles = ['lead', 'collaborator', 'advisor', 'contributor']
        if new_role not in valid_roles:
            return None
        
        with self.session_scope() as session:
            member = session.query(ProjectMember).filter(ProjectMember.id == member_id).first()
            if not member:
                return None
            member.role = new_role
            session.flush()
            return self._project_member_to_dict(member)
    
    # ==================== User Authentication ====================
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username."""
        with self.session_scope() as session:
            user = session.query(User).filter(
                User.username == username,
                User.is_active == True
            ).first()
            return self._user_to_dict(user) if user else None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        with self.session_scope() as session:
            user = session.query(User).filter(
                User.email == email,
                User.is_active == True
            ).first()
            return self._user_to_dict(user) if user else None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID."""
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            return self._user_to_dict(user) if user else None
    
    def get_user_by_google_id(self, google_id: str) -> Optional[Dict]:
        """Get user by Google OAuth ID."""
        with self.session_scope() as session:
            user = session.query(User).filter(User.google_id == google_id).first()
            return self._user_to_dict(user) if user else None
    
    def create_user(self, username: str, email: str, password: Optional[str] = None, **kwargs) -> Dict:
        """Create a new user with hashed password or OAuth credentials."""
        import hashlib
        import secrets
        
        password_hash = None
        if password:
            # Simple password hashing (use werkzeug.security in production)
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest() + ':' + salt
        
        with self.session_scope() as session:
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                google_id=kwargs.get('google_id'),
                name=kwargs.get('name'),
                role=kwargs.get('role', 'user'),
                lab_id=kwargs.get('lab_id'),
            )
            session.add(user)
            session.flush()
            return self._user_to_dict(user)
    
    def verify_password(self, username: str, password: str) -> Optional[Dict]:
        """Verify user password and return user if valid."""
        import hashlib
        
        with self.session_scope() as session:
            user = session.query(User).filter(
                User.username == username,
                User.is_active == True
            ).first()
            
            if not user or not user.password_hash:
                return None
            
            # Parse hash and salt
            try:
                stored_hash, salt = user.password_hash.split(':')
                computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                
                if computed_hash == stored_hash:
                    # Update last login
                    user.last_login = datetime.utcnow()
                    session.flush()
                    return self._user_to_dict(user)
            except ValueError:
                pass
            
            return None
    
    def update_user(self, user_id: int, data: Dict[str, Any] = None, **kwargs) -> Optional[Dict]:
        """Update user information."""
        # Support both dict and kwargs for flexibility
        if data is None:
            data = kwargs
        else:
            data.update(kwargs)
            
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            allowed_fields = ['name', 'email', 'role', 'lab_id', 'is_active', 'last_login', 'google_id']
            for field in allowed_fields:
                if field in data:
                    setattr(user, field, data[field])
            
            session.flush()
            return self._user_to_dict(user)
    
    def change_password(self, user_id: int, new_password: str) -> bool:
        """Change user password."""
        import hashlib
        import secrets
        
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256((new_password + salt).encode()).hexdigest() + ':' + salt
            user.password_hash = password_hash
            session.flush()
            return True
    
    def get_users(self, role: Optional[str] = None, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """Get paginated list of users."""
        with self.session_scope() as session:
            query = session.query(User).filter(User.is_active == True)
            
            if role:
                query = query.filter(User.role == role)
            
            total = query.count()
            users = query.order_by(User.username).offset((page - 1) * per_page).limit(per_page).all()
            
            return [self._user_to_dict(u) for u in users], total
    
    def _user_to_dict(self, user: User) -> Dict:
        """Convert User model to dictionary."""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.name,
            'role': user.role,
            'lab_id': user.lab_id,
            'google_id': user.google_id,
            'is_active': user.is_active,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat() if user.created_at else None,
        }
    
    # ==================== Issue Tracking ====================
    
    def get_issues(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        reporter_id: Optional[int] = None,
        assignee_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of issues."""
        with self.session_scope() as session:
            query = session.query(Issue)
            
            if status:
                query = query.filter(Issue.status == status)
            if category:
                query = query.filter(Issue.category == category)
            if reporter_id:
                query = query.filter(Issue.reporter_id == reporter_id)
            if assignee_id:
                query = query.filter(Issue.assignee_id == assignee_id)
            
            total = query.count()
            issues = query.order_by(desc(Issue.created_at)).offset((page - 1) * per_page).limit(per_page).all()
            
            return [self._issue_to_dict(i, session) for i in issues], total
    
    def get_issue(self, issue_id: int) -> Optional[Dict]:
        """Get issue by ID."""
        with self.session_scope() as session:
            issue = session.query(Issue).filter(Issue.id == issue_id).first()
            return self._issue_to_dict(issue, session) if issue else None
    
    def create_issue(self, data: Dict[str, Any]) -> Dict:
        """Create a new issue."""
        with self.session_scope() as session:
            issue = Issue(
                title=data.get('title'),
                description=data.get('description'),
                error_message=data.get('error_message'),
                steps_to_reproduce=data.get('steps_to_reproduce'),
                category=data.get('category', 'bug'),
                priority=data.get('priority', 'medium'),
                status='open',
                reporter_id=data.get('reporter_id'),
                related_url=data.get('related_url'),
                browser_info=data.get('browser_info'),
            )
            session.add(issue)
            session.flush()
            return self._issue_to_dict(issue, session)
    
    def update_issue(self, issue_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update an issue."""
        with self.session_scope() as session:
            issue = session.query(Issue).filter(Issue.id == issue_id).first()
            if not issue:
                return None
            
            allowed_fields = [
                'title', 'description', 'error_message', 'steps_to_reproduce',
                'category', 'priority', 'status', 'assignee_id', 'resolution'
            ]
            
            for field in allowed_fields:
                if field in data:
                    setattr(issue, field, data[field])
            
            # Handle status changes
            if data.get('status') in ['resolved', 'closed'] and not issue.resolved_at:
                issue.resolved_at = datetime.utcnow()
            elif data.get('status') in ['open', 'in_progress']:
                issue.resolved_at = None
            
            session.flush()
            return self._issue_to_dict(issue, session)
    
    def delete_issue(self, issue_id: int) -> bool:
        """Delete an issue."""
        with self.session_scope() as session:
            issue = session.query(Issue).filter(Issue.id == issue_id).first()
            if issue:
                session.delete(issue)
                return True
            return False
    
    def get_issue_stats(self) -> Dict:
        """Get issue statistics."""
        with self.session_scope() as session:
            total = session.query(Issue).count()
            open_count = session.query(Issue).filter(Issue.status == 'open').count()
            in_progress = session.query(Issue).filter(Issue.status == 'in_progress').count()
            resolved = session.query(Issue).filter(Issue.status.in_(['resolved', 'closed'])).count()
            
            return {
                'total': total,
                'open': open_count,
                'in_progress': in_progress,
                'resolved': resolved,
            }
    
    def _issue_to_dict(self, issue: Issue, session: Session) -> Dict:
        """Convert Issue model to dictionary."""
        reporter_name = None
        assignee_name = None
        
        if issue.reporter_id:
            reporter = session.query(User).filter(User.id == issue.reporter_id).first()
            reporter_name = reporter.name or reporter.username if reporter else None
        
        if issue.assignee_id:
            assignee = session.query(User).filter(User.id == issue.assignee_id).first()
            assignee_name = assignee.name or assignee.username if assignee else None
        
        return {
            'id': issue.id,
            'title': issue.title,
            'description': issue.description,
            'error_message': issue.error_message,
            'steps_to_reproduce': issue.steps_to_reproduce,
            'category': issue.category,
            'priority': issue.priority,
            'status': issue.status,
            'reporter_id': issue.reporter_id,
            'reporter_name': reporter_name,
            'assignee_id': issue.assignee_id,
            'assignee_name': assignee_name,
            'related_url': issue.related_url,
            'browser_info': issue.browser_info,
            'resolution': issue.resolution,
            'resolved_at': issue.resolved_at.isoformat() if issue.resolved_at else None,
            'created_at': issue.created_at.isoformat() if issue.created_at else None,
            'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
        }
    
    # ==================== Search ====================
    
    def global_search(self, query: str, limit: int = 10) -> Dict[str, List[Dict]]:
        """Search across all entity types."""
        results = {
            'samples': [],
            'scans': [],
            'queues': [],
            'equipment': [],
            'precursors': [],
        }
        
        if not query or len(query) < 2:
            return results
        
        samples, _ = self.get_samples(search=query, per_page=limit)
        results['samples'] = samples
        
        scans, _ = self.get_scans(search=query, per_page=limit)
        results['scans'] = scans
        
        queues, _ = self.get_queues(search=query, per_page=limit)
        results['queues'] = queues
        
        equipment, _ = self.get_equipment_list(search=query, per_page=limit)
        results['equipment'] = equipment
        
        precursors, _ = self.get_precursors(search=query, per_page=limit)
        results['precursors'] = precursors
        
        return results


# Singleton instance for easy import
_db_service: Optional[DatabaseService] = None


def get_db_service(db_path: Optional[str] = None) -> DatabaseService:
    """Get the singleton database service instance."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService(db_path)
    return _db_service

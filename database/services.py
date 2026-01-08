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
    Template, Equipment, Instrument, Precursor, PrecursorInventory,
    Procedure, Sample, SamplePrecursor, ProcedurePrecursor,
    Queue, QueueLog, Scan, ScanLog, MeasurementObject, MeasurementDataPoint,
    Tag, EntityTag, FabricationRun, FabricationRunPrecursor,
    Lab, LabMember, Project, ProjectMember, ItemGuest,
    User, UserPin, Issue, EntityImage,
    EquipmentImage, EquipmentIssue, ProcedureEquipment,
    InstrumentDefinitionIssue
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
                'instruments': {
                    'total': session.query(func.count(Instrument.id)).scalar() or 0,
                    'available': session.query(func.count(Instrument.id)).filter(Instrument.status == 'available').scalar() or 0,
                },
                'equipment': {
                    'total': session.query(func.count(Equipment.id)).scalar() or 0,
                    'operational': session.query(func.count(Equipment.id)).filter(Equipment.status == 'operational').scalar() or 0,
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
                'templates': {
                    'total': session.query(func.count(Template.id)).scalar() or 0,
                    'active': session.query(func.count(Template.id)).filter(Template.is_active == True).scalar() or 0,
                },
                'fabrication_runs': {
                    'total': session.query(func.count(FabricationRun.id)).scalar() or 0,
                    'completed': session.query(func.count(FabricationRun.id)).filter(FabricationRun.status == 'completed').scalar() or 0,
                },
            }
            
            # Import models not in main imports for stats
            from database.models import InstrumentDefinition, Computer
            
            stats['instrument_definitions'] = {
                'total': session.query(func.count(InstrumentDefinition.id)).scalar() or 0,
                'movement': session.query(func.count(InstrumentDefinition.id)).filter(InstrumentDefinition.instrument_type == 'movement').scalar() or 0,
                'measurement': session.query(func.count(InstrumentDefinition.id)).filter(InstrumentDefinition.instrument_type == 'measurement').scalar() or 0,
            }
            
            stats['computers'] = {
                'total': session.query(func.count(Computer.id)).scalar() or 0,
            }
            
            # Recent activity
            stats['recent_scans'] = self._get_recent_scans(session, limit=5)
            stats['recent_samples'] = self._get_recent_samples(session, limit=5)
            stats['open_issues'] = self._get_open_issues(session, limit=5)
            stats['open_equipment_issues'] = self._get_open_equipment_issues(session, limit=5)
            
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
        return [self._issue_to_dict(i, session) for i in issues]
    
    def _get_open_equipment_issues(self, session: Session, limit: int = 5) -> List[Dict]:
        """Get open equipment issues for dashboard."""
        issues = session.query(EquipmentIssue).filter(
            EquipmentIssue.status.in_(['open', 'in_progress'])
        ).order_by(
            # Priority order: critical > high > medium > low
            case(
                (EquipmentIssue.priority == 'critical', 1),
                (EquipmentIssue.priority == 'high', 2),
                (EquipmentIssue.priority == 'medium', 3),
                else_=4
            ),
            desc(EquipmentIssue.created_at)
        ).limit(limit).all()
        return [self._equipment_issue_to_dict(i) for i in issues]
    
    # ==================== Samples ====================
    
    def get_samples(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        material: Optional[str] = None,
        lab_id: Optional[int] = None,
        project_id: Optional[int] = None,
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
            
            if lab_id:
                query = query.filter(Sample.lab_id == lab_id)
            
            if project_id:
                query = query.filter(Sample.project_id == project_id)
            
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
                'failure_mode': run.failure_mode,
                'created_by': run.created_by,
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
                'lab_id': p.lab_id,
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
    
    def get_instruments_simple_list(self) -> List[Dict]:
        """Get a simple list of all instruments for dropdowns."""
        with self.session_scope() as session:
            instruments = session.query(Instrument).filter(
                Instrument.status != 'retired'
            ).order_by(Instrument.name).all()
            return [{
                'id': i.id,
                'name': i.name,
                'model': i.model,
                'display': f"{i.name}" + (f" ({i.model})" if i.model else "")
            } for i in instruments]
    
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
    
    def clear_sample_precursors(self, sample_id: int) -> int:
        """Remove all precursors from a sample.
        
        Returns:
            Number of precursors removed
        """
        with self.session_scope() as session:
            count = session.query(SamplePrecursor).filter(
                SamplePrecursor.sample_id == sample_id
            ).delete()
            return count
    
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
        queue_id: Optional[int] = None,
        lab_id: Optional[int] = None,
        project_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of scans with optional filtering.
        
        Args:
            search: Search term for scan_name, project_name, or scan_id
            status: Filter by status
            sample_id: Filter by sample
            queue_id: Filter by parent queue (scans are children of queues)
            lab_id: Filter by lab
            project_id: Filter by project
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Tuple of (list of scan dicts, total count)
        """
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
            
            if queue_id:
                query = query.filter(Scan.queue_id == queue_id)
            
            if project_id:
                query = query.filter(Scan.project_id == project_id)
            elif lab_id:
                # Filter by direct lab_id or through project
                query = query.filter(
                    or_(
                        Scan.lab_id == lab_id,
                        Scan.project_id.in_(
                            session.query(Project.id).filter(Project.lab_id == lab_id)
                        )
                    )
                )
            
            total = query.count()
            offset = (page - 1) * per_page
            scans = query.options(joinedload(Scan.queue)).order_by(desc(Scan.created_at)).offset(offset).limit(per_page).all()
            
            return [self._scan_to_dict(s) for s in scans], total
    
    def get_scan(self, scan_id: int) -> Optional[Dict]:
        """Get a single scan by ID with measurement data, parent queue, and logs."""
        with self.session_scope() as session:
            scan = session.query(Scan).options(
                joinedload(Scan.sample),
                joinedload(Scan.measurement_objects),
                joinedload(Scan.queue),
                joinedload(Scan.logs),
            ).filter(Scan.id == scan_id).first()
            
            if not scan:
                return None
            
            result = self._scan_to_dict(scan)
            result['sample'] = self._sample_to_dict(scan.sample) if scan.sample else None
            result['queue'] = self._queue_to_dict(scan.queue) if scan.queue else None
            result['measurement_objects'] = [
                self._measurement_object_to_dict(mo) 
                for mo in scan.measurement_objects
            ]
            result['logs'] = [self._scan_log_to_dict(log) for log in scan.logs]
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

    def get_visualization_data(self, scan_id: int) -> Dict[str, Dict]:
        """Get measurement data organized for visualization.
        
        Returns data grouped by measurement object with metadata for proper charting.
        Each measurement object gets its own data set with column information.
        
        Args:
            scan_id: Database ID of the scan
            
        Returns:
            Dictionary mapping measurement names to visualization data:
            {
                'Voltage_Meter': {
                    'id': 1,
                    'name': 'Voltage_Meter',
                    'columns': ['current', 'voltage'],
                    'unit': 'V',
                    'instrument_name': 'IV_Voltage_Meter',
                    'x_column': 'current',  # First column for X-axis
                    'y_column': 'voltage',  # Second column for Y-axis
                    'data_points': [
                        {'x': -0.001, 'y': -0.016, 'index': 0},
                        ...
                    ],
                    'all_values': [  # All raw values for table display
                        {'current': -0.001, 'voltage': -0.016, 'sequence_index': 0},
                        ...
                    ]
                }
            }
        """
        result = {}
        
        with self.session_scope() as session:
            # Get all measurement objects for this scan with their data
            measurement_objects = session.query(MeasurementObject).filter(
                MeasurementObject.scan_id == scan_id
            ).all()
            
            for mo in measurement_objects:
                columns = mo.columns or []
                
                # Determine X and Y columns
                if len(columns) >= 2:
                    x_column = columns[0]
                    y_column = columns[1]
                elif len(columns) == 1:
                    x_column = None  # Will use sequence_index
                    y_column = columns[0]
                else:
                    x_column = None
                    y_column = None
                
                # Get data points for this measurement object
                points = session.query(MeasurementDataPoint).filter(
                    MeasurementDataPoint.measurement_object_id == mo.id
                ).order_by(MeasurementDataPoint.sequence_index).all()
                
                # Build chart-ready data
                chart_data = []
                all_values = []
                
                for p in points:
                    values = p.values or {}
                    
                    # For chart: extract X and Y values
                    if x_column and x_column in values:
                        x_val = values[x_column]
                    else:
                        x_val = p.sequence_index
                    
                    if y_column and y_column in values:
                        y_val = values[y_column]
                    else:
                        # If no y_column, try to get the first value
                        y_val = next(iter(values.values()), None) if values else None
                    
                    chart_data.append({
                        'x': x_val,
                        'y': y_val,
                        'index': p.sequence_index
                    })
                    
                    # For table: all values plus metadata
                    row = dict(values)
                    row['sequence_index'] = p.sequence_index
                    row['timestamp'] = p.timestamp.isoformat() if p.timestamp else None
                    if p.extra_data:
                        row['extra_data'] = p.extra_data
                    all_values.append(row)
                
                result[mo.name] = {
                    'id': mo.id,
                    'name': mo.name,
                    'columns': columns,
                    'unit': mo.unit,
                    'instrument_name': mo.instrument_name,
                    'data_type': mo.data_type,
                    'x_column': x_column or 'sequence_index',
                    'y_column': y_column,
                    'data_points': chart_data,
                    'all_values': all_values,
                    'point_count': len(points)
                }
        
        return result

    def generate_scan_csv(self, scan_id: int, columns: List[str] = None, include_metadata: bool = True) -> str:
        """Generate CSV content for scan data export.
        
        Args:
            scan_id: Database ID of the scan
            columns: List of columns to include (None = all)
            include_metadata: Whether to include header comments with metadata
            
        Returns:
            CSV content as string, or None if scan not found
        """
        import csv
        import io
        from datetime import datetime
        
        with self.session_scope() as session:
            scan = session.query(Scan).get(scan_id)
            if not scan:
                return None
            
            # Get visualization data to build CSV
            viz_data = self.get_visualization_data(scan_id)
            
            output = io.StringIO()
            
            # Write metadata header
            if include_metadata:
                output.write(f"# PyBirch Scan Export\n")
                output.write(f"# Scan ID: {scan.id}\n")
                output.write(f"# Scan Name: {scan.scan_name or 'Unnamed'}\n")
                output.write(f"# Scan Type: {scan.scan_type or '-'}\n")
                output.write(f"# Project: {scan.project_name or '-'}\n")
                output.write(f"# Queue ID: {scan.queue_id or '-'}\n")
                output.write(f"# Export Date: {datetime.now().isoformat()}\n")
                output.write(f"#\n")
            
            # For each measurement object, write a section
            for mo_name, data in viz_data.items():
                if include_metadata:
                    output.write(f"# Measurement Object: {mo_name}\n")
                    output.write(f"# Instrument: {data.get('instrument_name', '-')}\n")
                    output.write(f"# Unit: {data.get('unit', '-')}\n")
                    output.write(f"# Total Points: {data.get('point_count', 0)}\n")
                    output.write(f"#\n")
                
                # Determine columns to include
                all_cols = ['sequence_index'] + (data.get('columns') or []) + ['timestamp']
                if columns:
                    # Filter to requested columns
                    csv_cols = [c for c in all_cols if c in columns]
                else:
                    csv_cols = all_cols
                
                # Write CSV data
                writer = csv.DictWriter(output, fieldnames=csv_cols, extrasaction='ignore')
                writer.writeheader()
                
                for row in data.get('all_values', []):
                    writer.writerow(row)
                
                output.write("\n")  # Blank line between measurement objects
            
            return output.getvalue()

    def _scan_to_dict(self, scan: Scan) -> Dict:
        """Convert Scan model to dictionary."""
        return {
            'id': scan.id,
            'scan_id': scan.scan_id,
            'scan_name': scan.scan_name,
            'project_name': scan.project_name,
            'created_by': scan.created_by,
            'status': scan.status,
            'scan_type': scan.scan_type,
            'job_type': scan.job_type,
            'started_at': scan.started_at.isoformat() if scan.started_at else None,
            'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
            'duration_seconds': float(scan.duration_seconds) if scan.duration_seconds else None,
            'sample_id': scan.sample_id,
            'queue_id': scan.queue_id,
            'queue_name': scan.queue.name if scan.queue else None,
            'notes': scan.notes,
            'wandb_link': scan.wandb_link,
            'created_at': scan.created_at.isoformat() if scan.created_at else None,
            'pybirch_uri': f"pybirch://scan/{scan.id}",
            'lab_id': scan.lab_id,
            'project_id': scan.project_id,
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
    
    def get_scan_measurements(self, scan_id: int) -> List[Dict]:
        """Get all measurement objects for a scan.
        
        Args:
            scan_id: Database scan ID
            
        Returns:
            List of measurement objects as dictionaries
        """
        with self.session_scope() as session:
            measurements = session.query(MeasurementObject).filter(
                MeasurementObject.scan_id == scan_id
            ).all()
            return [self._measurement_object_to_dict(mo) for mo in measurements]
    
    def get_measurement_data_points(
        self,
        measurement_id: int,
        page: int = 1,
        per_page: int = 1000
    ) -> List[Dict]:
        """Get data points for a measurement.
        
        Args:
            measurement_id: Measurement object ID
            page: Page number (1-indexed)
            per_page: Items per page (default 1000)
            
        Returns:
            List of data points as dictionaries
        """
        with self.session_scope() as session:
            points = session.query(MeasurementDataPoint).filter(
                MeasurementDataPoint.measurement_id == measurement_id
            ).order_by(
                MeasurementDataPoint.sequence_index
            ).offset((page - 1) * per_page).limit(per_page).all()
            
            return [{
                'id': point.id,
                'measurement_id': point.measurement_id,
                'sequence_index': point.sequence_index,
                'values': point.values,
                'timestamp': point.timestamp.isoformat() if point.timestamp else None,
                'extra_data': point.extra_data,
            } for point in points]
    
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
                    measurement_object_id=measurement_id,  # Fixed: use measurement_object_id not measurement_id
                    values=dp.get('values', dp),
                    sequence_index=dp.get('sequence_index', i),
                    timestamp=dp.get('timestamp', datetime.now()),
                    extra_data=dp.get('extra_data'),
                )
                points.append(point)
            
            session.bulk_save_objects(points)
            return len(points)

    def get_data_point_count(
        self,
        scan_id: int,
        measurement_name: Optional[str] = None,
    ) -> int:
        """Get count of data points for a scan.
        
        Args:
            scan_id: Database scan ID
            measurement_name: Optional measurement name to filter by
            
        Returns:
            Count of data points
        """
        with self.session_scope() as session:
            query = session.query(func.count(MeasurementDataPoint.id)).join(
                MeasurementObject
            ).filter(MeasurementObject.scan_id == scan_id)
            
            if measurement_name:
                query = query.filter(MeasurementObject.name == measurement_name)
            
            return query.scalar() or 0

    # ==================== Queues ====================
    
    def get_queues(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        lab_id: Optional[int] = None,
        project_id: Optional[int] = None,
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
            
            if project_id:
                query = query.filter(Queue.project_id == project_id)
            elif lab_id:
                # Filter by direct lab_id or through project
                query = query.filter(
                    or_(
                        Queue.lab_id == lab_id,
                        Queue.project_id.in_(
                            session.query(Project.id).filter(Project.lab_id == lab_id)
                        )
                    )
                )
            
            total = query.count()
            offset = (page - 1) * per_page
            queues = query.order_by(desc(Queue.created_at)).offset(offset).limit(per_page).all()
            
            return [self._queue_to_dict(q) for q in queues], total
    
    def get_queue(self, queue_id: int) -> Optional[Dict]:
        """Get a single queue by ID with related scans and logs."""
        with self.session_scope() as session:
            queue = session.query(Queue).options(
                joinedload(Queue.sample),
                joinedload(Queue.scans),
                joinedload(Queue.logs),
            ).filter(Queue.id == queue_id).first()
            
            if not queue:
                return None
            
            result = self._queue_to_dict(queue)
            result['sample'] = self._sample_to_dict(queue.sample) if queue.sample else None
            result['scans'] = [self._scan_to_dict(s) for s in queue.scans]
            result['logs'] = [self._queue_log_to_dict(log) for log in queue.logs]
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
            'created_by': queue.created_by,
            'notes': queue.notes,
            'created_at': queue.created_at.isoformat() if queue.created_at else None,
            'pybirch_uri': f"pybirch://queue/{queue.id}",
            'lab_id': queue.lab_id,
            'project_id': queue.project_id,
        }
    
    def _queue_log_to_dict(self, log: QueueLog) -> Dict:
        """Convert QueueLog model to dictionary."""
        return {
            'id': log.id,
            'queue_id': log.queue_id,
            'scan_id': log.scan_id,
            'level': log.level,
            'message': log.message,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None,
            'extra_data': log.extra_data,
        }
    
    def _scan_log_to_dict(self, log: ScanLog) -> Dict:
        """Convert ScanLog model to dictionary."""
        return {
            'id': log.id,
            'scan_id': log.scan_id,
            'phase': log.phase,
            'level': log.level,
            'message': log.message,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None,
            'progress': float(log.progress) if log.progress is not None else None,
            'extra_data': log.extra_data,
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
    
    def create_scan_log(
        self,
        scan_id: int,
        level: str,
        message: str,
        phase: Optional[str] = None,
        progress: Optional[float] = None,
        extra_data: Optional[Dict] = None,
    ) -> Dict:
        """Create a log entry for a scan.
        
        Args:
            scan_id: Database scan ID
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
            message: Log message
            phase: Scan phase ('setup', 'running', 'cleanup', 'analysis')
            progress: Progress percentage (0-100)
            extra_data: Additional data (optional)
            
        Returns:
            Created log entry as dictionary
        """
        with self.session_scope() as session:
            log = ScanLog(
                scan_id=scan_id,
                level=level,
                message=message,
                phase=phase,
                progress=progress,
                extra_data=extra_data,
            )
            session.add(log)
            session.flush()
            return self._scan_log_to_dict(log)
    
    def get_scan_logs(
        self,
        scan_id: int,
        level: Optional[str] = None,
        phase: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """Get log entries for a scan.
        
        Args:
            scan_id: Database scan ID
            level: Filter by level (optional)
            phase: Filter by phase (optional)
            limit: Maximum number of entries to return
            
        Returns:
            List of log entries as dictionaries (oldest first)
        """
        with self.session_scope() as session:
            query = session.query(ScanLog).filter(ScanLog.scan_id == scan_id)
            
            if level:
                query = query.filter(ScanLog.level == level)
            if phase:
                query = query.filter(ScanLog.phase == phase)
            
            logs = query.order_by(ScanLog.timestamp).limit(limit).all()
            
            return [self._scan_log_to_dict(log) for log in logs]
    
    def get_instrument_by_name(self, name: str) -> Optional[Dict]:
        """Get instrument by name.
        
        Args:
            name: Instrument name
            
        Returns:
            Instrument as dictionary, or None if not found
        """
        with self.session_scope() as session:
            instrument = session.query(Instrument).filter(Instrument.name == name).first()
            return self._instrument_to_dict(instrument) if instrument else None

    # ==================== Instruments (PyBirch-compatible devices) ====================
    
    def get_instruments_list(
        self,
        search: Optional[str] = None,
        instrument_type: Optional[str] = None,
        status: Optional[str] = None,
        lab_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of instruments."""
        from sqlalchemy.orm import joinedload
        
        with self.session_scope() as session:
            query = session.query(Instrument).options(
                joinedload(Instrument.definition)
            )
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Instrument.name.ilike(search_term),
                        Instrument.manufacturer.ilike(search_term),
                        Instrument.model.ilike(search_term),
                        Instrument.pybirch_class.ilike(search_term)
                    )
                )
            
            if instrument_type:
                query = query.filter(Instrument.instrument_type == instrument_type)
            
            if status:
                query = query.filter(Instrument.status == status)
            
            if lab_id:
                query = query.filter(Instrument.lab_id == lab_id)
            
            total = query.count()
            offset = (page - 1) * per_page
            instruments = query.order_by(Instrument.name).offset(offset).limit(per_page).all()
            
            return [self._instrument_to_dict(i) for i in instruments], total
    
    def get_instrument(self, instrument_id: int) -> Optional[Dict]:
        """Get a single instrument by ID."""
        from sqlalchemy.orm import joinedload
        from database.models import ComputerBinding, Computer
        
        with self.session_scope() as session:
            instrument = session.query(Instrument).options(
                joinedload(Instrument.definition),
                joinedload(Instrument.computer_bindings).joinedload(ComputerBinding.computer)
            ).filter(Instrument.id == instrument_id).first()
            return self._instrument_to_dict(instrument, include_computer_bindings=True) if instrument else None
    
    def create_instrument(self, data: Dict[str, Any]) -> Dict:
        """Create new instrument."""
        from sqlalchemy.orm import joinedload
        
        with self.session_scope() as session:
            instrument = Instrument(**data)
            session.add(instrument)
            session.flush()
            # Re-query to get the definition relationship loaded
            if instrument.definition_id:
                session.refresh(instrument)
            return self._instrument_to_dict(instrument)
    
    def update_instrument(self, instrument_id: int, data: Dict) -> Optional[Dict]:
        """Update an existing instrument."""
        with self.session_scope() as session:
            instrument = session.query(Instrument).filter(Instrument.id == instrument_id).first()
            if not instrument:
                return None
            
            for field in ['name', 'instrument_type', 'pybirch_class', 'manufacturer', 'model',
                          'serial_number', 'location', 'status', 'specifications',
                          'lab_id', 'equipment_id', 'definition_id']:
                if field in data:
                    setattr(instrument, field, data[field])
            
            session.flush()
            # Refresh to get updated definition relationship
            if instrument.definition_id:
                session.refresh(instrument)
            return self._instrument_to_dict(instrument)
    
    def delete_instrument(self, instrument_id: int) -> bool:
        """Delete an instrument by ID."""
        with self.session_scope() as session:
            instrument = session.query(Instrument).filter(Instrument.id == instrument_id).first()
            if not instrument:
                return False
            session.delete(instrument)
            return True
    
    def get_instruments_by_definition(
        self,
        definition_id: int,
        include_bindings: bool = True,
    ) -> List[Dict]:
        """Get all instrument instances using a specific definition.
        
        Args:
            definition_id: ID of the InstrumentDefinition
            include_bindings: If True, include computer bindings for each instrument
        
        Returns:
            List of instruments with optional binding info
        """
        from database.models import ComputerBinding
        from sqlalchemy.orm import joinedload
        
        with self.session_scope() as session:
            instruments = session.query(Instrument).options(
                joinedload(Instrument.definition)
            ).filter(
                Instrument.definition_id == definition_id
            ).order_by(Instrument.name).all()
            
            result = []
            for instrument in instruments:
                inst_dict = self._instrument_to_dict(instrument)
                
                if include_bindings:
                    # Get computer bindings for this instrument with computer info
                    bindings = session.query(ComputerBinding).options(
                        joinedload(ComputerBinding.computer)
                    ).filter(
                        ComputerBinding.instrument_id == instrument.id
                    ).all()
                    inst_dict['computer_bindings'] = [
                        self._computer_binding_to_dict(b) for b in bindings
                    ]
                
                result.append(inst_dict)
            
            return result
    
    def get_instruments_without_definition(self) -> List[Dict]:
        """Get all instruments that don't have a definition linked.
        
        Returns:
            List of instruments without definition_id set
        """
        from sqlalchemy.orm import joinedload
        
        with self.session_scope() as session:
            instruments = session.query(Instrument).options(
                joinedload(Instrument.definition)
            ).filter(
                Instrument.definition_id.is_(None)
            ).order_by(Instrument.name).all()
            
            return [self._instrument_to_dict(i) for i in instruments]
    
    def link_instrument_to_definition(
        self,
        instrument_id: int,
        definition_id: int,
    ) -> Optional[Dict]:
        """Link an existing instrument to a definition.
        
        Args:
            instrument_id: ID of the instrument to link
            definition_id: ID of the definition to link to
        
        Returns:
            Updated instrument as dictionary, or None if not found
        """
        from database.models import InstrumentDefinition
        
        with self.session_scope() as session:
            instrument = session.query(Instrument).filter(
                Instrument.id == instrument_id
            ).first()
            
            if not instrument:
                return None
            
            # Verify definition exists
            definition = session.query(InstrumentDefinition).filter(
                InstrumentDefinition.id == definition_id
            ).first()
            
            if not definition:
                return None
            
            # Update the instrument
            instrument.definition_id = definition_id
            # Also set pybirch_class to match for backwards compatibility
            instrument.pybirch_class = definition.name
            # Optionally sync instrument_type
            instrument.instrument_type = definition.instrument_type
            
            session.flush()
            session.refresh(instrument)
            return self._instrument_to_dict(instrument)
    
    def unlink_instrument_from_definition(
        self,
        instrument_id: int,
    ) -> Optional[Dict]:
        """Unlink an instrument from its definition.
        
        Args:
            instrument_id: ID of the instrument to unlink
        
        Returns:
            Updated instrument as dictionary, or None if not found
        """
        with self.session_scope() as session:
            instrument = session.query(Instrument).filter(
                Instrument.id == instrument_id
            ).first()
            
            if not instrument:
                return None
            
            instrument.definition_id = None
            session.flush()
            return self._instrument_to_dict(instrument)
    
    def create_instrument_for_definition(
        self,
        definition_id: int,
        data: Dict[str, Any],
    ) -> Optional[Dict]:
        """Create a new instrument instance linked to a definition.
        
        Args:
            definition_id: ID of the InstrumentDefinition to link
            data: Instrument data including:
                - name: Display name for this instance (required)
                - serial_number: Physical device serial (optional)
                - location: Physical location (optional)
                - manufacturer, model: Device info (optional)
        
        Returns:
            Created instrument as dictionary, or None if definition not found
        """
        from database.models import InstrumentDefinition
        
        with self.session_scope() as session:
            # Verify definition exists
            definition = session.query(InstrumentDefinition).filter(
                InstrumentDefinition.id == definition_id
            ).first()
            
            if not definition:
                return None
            
            # Create instrument linked to definition
            instrument = Instrument(
                name=data['name'],
                instrument_type=definition.instrument_type,
                pybirch_class=definition.name,
                manufacturer=data.get('manufacturer') or definition.manufacturer,
                model=data.get('model'),
                serial_number=data.get('serial_number'),
                location=data.get('location'),
                status=data.get('status', 'available'),
                lab_id=data.get('lab_id'),
                definition_id=definition_id,
            )
            
            session.add(instrument)
            session.flush()
            session.refresh(instrument)
            
            return self._instrument_to_dict(instrument)
    
    def _instrument_to_dict(self, instrument: Instrument, include_computer_bindings: bool = False) -> Dict:
        """Convert Instrument model to dictionary."""
        # Get definition info if linked
        definition_name = None
        definition_display_name = None
        if instrument.definition_id and instrument.definition:
            definition_name = instrument.definition.name
            definition_display_name = instrument.definition.display_name
        
        result = {
            'id': instrument.id,
            'name': instrument.name,
            'instrument_type': instrument.instrument_type,
            'pybirch_class': instrument.pybirch_class,
            'manufacturer': instrument.manufacturer,
            'model': instrument.model,
            'serial_number': instrument.serial_number,
            'location': instrument.location,
            'status': instrument.status,
            'specifications': instrument.specifications,
            'lab_id': instrument.lab_id,
            'equipment_id': instrument.equipment_id,
            'definition_id': instrument.definition_id,
            'definition_name': definition_name,
            'definition_display_name': definition_display_name,
            'created_at': instrument.created_at.isoformat() if instrument.created_at else None,
        }
        
        # Include computer bindings if requested
        if include_computer_bindings and hasattr(instrument, 'computer_bindings'):
            bindings = []
            for binding in instrument.computer_bindings:
                binding_dict = {
                    'id': binding.id,
                    'computer_name': binding.computer_name,
                    'computer_id': binding.computer_id,
                    'adapter': binding.adapter,
                    'adapter_type': binding.adapter_type,
                    'is_primary': binding.is_primary,
                    'last_connected': binding.last_connected.isoformat() if binding.last_connected else None,
                }
                # Include linked Computer info if available
                if binding.computer:
                    binding_dict['computer'] = {
                        'id': binding.computer.id,
                        'nickname': binding.computer.nickname,
                        'location': binding.computer.location,
                    }
                bindings.append(binding_dict)
            result['computer_bindings'] = bindings
        
        return result

    # ==================== Instrument Definitions (Stored Code) ====================
    
    def create_instrument_definition(self, data: Dict[str, Any]) -> Dict:
        """Create a new instrument definition.
        
        Args:
            data: Dictionary with definition fields:
                - name: Class name (required, unique)
                - display_name: Human-readable name (required)
                - instrument_type: 'movement' or 'measurement' (required)
                - source_code: Python source code (required)
                - base_class: Base class name (required)
                - description, category, manufacturer, etc. (optional)
        
        Returns:
            Created definition as dictionary
        """
        from database.models import InstrumentDefinition, InstrumentDefinitionVersion
        
        with self.session_scope() as session:
            definition = InstrumentDefinition(
                name=data['name'],
                display_name=data['display_name'],
                description=data.get('description'),
                instrument_type=data['instrument_type'],
                category=data.get('category'),
                manufacturer=data.get('manufacturer'),
                source_code=data['source_code'],
                base_class=data['base_class'],
                dependencies=data.get('dependencies'),
                settings_schema=data.get('settings_schema'),
                default_settings=data.get('default_settings'),
                data_columns=data.get('data_columns'),
                data_units=data.get('data_units'),
                position_column=data.get('position_column'),
                position_units=data.get('position_units'),
                lab_id=data.get('lab_id'),
                is_public=data.get('is_public', False),
                is_builtin=data.get('is_builtin', False),
                is_approved=data.get('is_approved', True),
                created_by=data.get('created_by'),
            )
            session.add(definition)
            session.flush()
            
            # Create initial version
            version = InstrumentDefinitionVersion(
                definition_id=definition.id,
                version=1,
                source_code=data['source_code'],
                change_summary='Initial version',
                created_by=data.get('created_by'),
            )
            session.add(version)
            session.flush()
            
            return self._instrument_definition_to_dict(definition)
    
    def get_instrument_definitions(
        self,
        instrument_type: Optional[str] = None,
        category: Optional[str] = None,
        lab_id: Optional[int] = None,
        include_public: bool = True,
        include_builtin: bool = True,
        search: Optional[str] = None,
    ) -> List[Dict]:
        """Get instrument definitions.
        
        Args:
            instrument_type: Filter by 'movement' or 'measurement'
            category: Filter by category (e.g., 'Lock-In Amplifier')
            lab_id: Filter by lab (also includes public/builtin if flags set)
            include_public: Include public definitions from other labs
            include_builtin: Include built-in PyBirch definitions
            search: Search in name, display_name, description
        
        Returns:
            List of definitions as dictionaries
        """
        from database.models import InstrumentDefinition
        
        with self.session_scope() as session:
            query = session.query(InstrumentDefinition)
            
            # Apply type filter
            if instrument_type:
                query = query.filter(InstrumentDefinition.instrument_type == instrument_type)
            
            # Apply category filter
            if category:
                query = query.filter(InstrumentDefinition.category == category)
            
            # Apply lab/visibility filter
            if lab_id is not None:
                filters = [InstrumentDefinition.lab_id == lab_id]
                if include_public:
                    filters.append(InstrumentDefinition.is_public == True)
                if include_builtin:
                    filters.append(InstrumentDefinition.is_builtin == True)
                query = query.filter(or_(*filters))
            
            # Apply search filter
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        InstrumentDefinition.name.ilike(search_term),
                        InstrumentDefinition.display_name.ilike(search_term),
                        InstrumentDefinition.description.ilike(search_term),
                    )
                )
            
            # Only approved definitions
            query = query.filter(InstrumentDefinition.is_approved == True)
            
            definitions = query.order_by(InstrumentDefinition.display_name).all()
            return [self._instrument_definition_to_dict(d) for d in definitions]
    
    def get_instrument_definition(self, definition_id: int) -> Optional[Dict]:
        """Get a single instrument definition by ID."""
        from database.models import InstrumentDefinition
        
        with self.session_scope() as session:
            definition = session.query(InstrumentDefinition).filter(
                InstrumentDefinition.id == definition_id
            ).first()
            return self._instrument_definition_to_dict(definition) if definition else None
    
    def get_instrument_definition_by_name(self, name: str) -> Optional[Dict]:
        """Get an instrument definition by class name."""
        from database.models import InstrumentDefinition
        
        with self.session_scope() as session:
            definition = session.query(InstrumentDefinition).filter(
                InstrumentDefinition.name == name
            ).first()
            return self._instrument_definition_to_dict(definition) if definition else None
    
    def update_instrument_definition(
        self, 
        definition_id: int, 
        data: Dict[str, Any],
        change_summary: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> Optional[Dict]:
        """Update an instrument definition.
        
        If source_code is changed, creates a new version.
        
        Args:
            definition_id: ID of definition to update
            data: Fields to update
            change_summary: Description of changes (for version history)
            updated_by: Username making the change
        
        Returns:
            Updated definition as dictionary
        """
        from database.models import InstrumentDefinition, InstrumentDefinitionVersion
        
        with self.session_scope() as session:
            definition = session.query(InstrumentDefinition).filter(
                InstrumentDefinition.id == definition_id
            ).first()
            
            if not definition:
                return None
            
            # Check if source code changed
            old_source = definition.source_code
            new_source = data.get('source_code', old_source)
            source_changed = new_source != old_source
            
            # Update fields
            updatable_fields = [
                'display_name', 'description', 'category', 'manufacturer',
                'source_code', 'base_class', 'dependencies', 'settings_schema',
                'default_settings', 'data_columns', 'data_units',
                'position_column', 'position_units', 'is_public', 'is_approved',
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(definition, field, data[field])
            
            # If source code changed, create new version
            if source_changed:
                definition.version += 1
                
                version = InstrumentDefinitionVersion(
                    definition_id=definition.id,
                    version=definition.version,
                    source_code=new_source,
                    change_summary=change_summary or 'Updated',
                    created_by=updated_by,
                )
                session.add(version)
            
            session.flush()
            return self._instrument_definition_to_dict(definition)
    
    def delete_instrument_definition(self, definition_id: int) -> bool:
        """Delete an instrument definition and all its versions."""
        from database.models import InstrumentDefinition
        
        with self.session_scope() as session:
            definition = session.query(InstrumentDefinition).filter(
                InstrumentDefinition.id == definition_id
            ).first()
            
            if not definition:
                return False
            
            session.delete(definition)
            return True
    
    def get_instrument_definition_versions(self, definition_id: int) -> List[Dict]:
        """Get version history for an instrument definition."""
        from database.models import InstrumentDefinitionVersion
        
        with self.session_scope() as session:
            versions = session.query(InstrumentDefinitionVersion).filter(
                InstrumentDefinitionVersion.definition_id == definition_id
            ).order_by(InstrumentDefinitionVersion.version.desc()).all()
            
            return [{
                'id': v.id,
                'definition_id': v.definition_id,
                'version': v.version,
                'source_code': v.source_code,
                'change_summary': v.change_summary,
                'created_by': v.created_by,
                'created_at': v.created_at.isoformat() if v.created_at else None,
            } for v in versions]
    
    def _instrument_definition_to_dict(self, definition) -> Dict:
        """Convert InstrumentDefinition model to dictionary."""
        if not definition:
            return {}
        return {
            'id': definition.id,
            'name': definition.name,
            'display_name': definition.display_name,
            'description': definition.description,
            'instrument_type': definition.instrument_type,
            'category': definition.category,
            'manufacturer': definition.manufacturer,
            'source_code': definition.source_code,
            'base_class': definition.base_class,
            'dependencies': definition.dependencies,
            'settings_schema': definition.settings_schema,
            'default_settings': definition.default_settings,
            'data_columns': definition.data_columns,
            'data_units': definition.data_units,
            'position_column': definition.position_column,
            'position_units': definition.position_units,
            'lab_id': definition.lab_id,
            'version': definition.version,
            'is_public': definition.is_public,
            'is_builtin': definition.is_builtin,
            'is_approved': definition.is_approved,
            'status': definition.status or 'operational',
            'created_by': definition.created_by,
            'created_at': definition.created_at.isoformat() if definition.created_at else None,
            'updated_at': definition.updated_at.isoformat() if definition.updated_at else None,
        }
    
    # ==================== Computer Bindings ====================
    
    def bind_instrument_to_computer(
        self,
        instrument_id: int,
        computer_name: str,
        computer_id: Optional[str] = None,
        username: Optional[str] = None,
        adapter: Optional[str] = None,
        adapter_type: Optional[str] = None,
        is_primary: bool = True,
        nickname: Optional[str] = None,
    ) -> Dict:
        """Bind an instrument to a computer.
        
        Creates or updates a computer binding for the instrument.
        Also creates/updates the Computer record with nickname.
        
        Args:
            instrument_id: ID of the instrument
            computer_name: Hostname of the computer
            computer_id: MAC address or UUID (optional)
            username: OS username (optional)
            adapter: VISA address or connection string
            adapter_type: 'GPIB', 'USB', 'Serial', 'TCP', etc.
            is_primary: Whether this is the primary computer for this instrument
            nickname: Friendly name for the computer (optional) - stored on Computer, not binding
        
        Returns:
            Binding as dictionary
        """
        from database.models import ComputerBinding, Computer
        from datetime import datetime
        
        with self.session_scope() as session:
            # Get or create Computer record
            computer = session.query(Computer).filter(
                Computer.computer_name == computer_name
            ).first()
            
            if computer:
                # Update existing computer
                if computer_id:
                    computer.computer_id = computer_id
                if nickname is not None:
                    computer.nickname = nickname
            else:
                # Create new computer
                computer = Computer(
                    computer_name=computer_name,
                    computer_id=computer_id,
                    nickname=nickname,
                )
                session.add(computer)
                session.flush()
            
            # Check if binding exists
            binding = session.query(ComputerBinding).filter(
                ComputerBinding.instrument_id == instrument_id,
                ComputerBinding.computer_name == computer_name,
            ).first()
            
            if binding:
                # Update existing binding
                if computer_id:
                    binding.computer_id = computer_id
                if username:
                    binding.username = username
                if adapter:
                    binding.adapter = adapter
                if adapter_type:
                    binding.adapter_type = adapter_type
                binding.is_primary = is_primary
                binding.last_connected = datetime.utcnow()
                binding.computer_id_fk = computer.id
            else:
                # Create new binding
                binding = ComputerBinding(
                    instrument_id=instrument_id,
                    computer_name=computer_name,
                    computer_id=computer_id,
                    computer_id_fk=computer.id,
                    username=username,
                    adapter=adapter,
                    adapter_type=adapter_type,
                    is_primary=is_primary,
                    last_connected=datetime.utcnow(),
                )
                session.add(binding)
            
            session.flush()
            return self._computer_binding_to_dict(binding, computer)
    
    def get_computer_bindings(
        self,
        computer_name: Optional[str] = None,
        instrument_id: Optional[int] = None,
    ) -> List[Dict]:
        """Get computer bindings.
        
        Args:
            computer_name: Filter by computer hostname
            instrument_id: Filter by instrument ID
        
        Returns:
            List of bindings with instrument details
        """
        from database.models import ComputerBinding, Instrument, InstrumentDefinition
        from sqlalchemy.orm import joinedload
        
        with self.session_scope() as session:
            query = session.query(ComputerBinding).options(
                joinedload(ComputerBinding.computer)
            ).join(Instrument)
            
            if computer_name:
                query = query.filter(ComputerBinding.computer_name == computer_name)
            
            if instrument_id:
                query = query.filter(ComputerBinding.instrument_id == instrument_id)
            
            bindings = query.all()
            
            result = []
            for binding in bindings:
                binding_dict = self._computer_binding_to_dict(binding)
                binding_dict['instrument'] = self._instrument_to_dict(binding.instrument)
                
                # Include definition if available
                if binding.instrument.definition_id:
                    definition = session.query(InstrumentDefinition).filter(
                        InstrumentDefinition.id == binding.instrument.definition_id
                    ).first()
                    if definition:
                        binding_dict['instrument']['definition'] = self._instrument_definition_to_dict(definition)
                
                result.append(binding_dict)
            
            return result
    
    def update_computer_binding_settings(
        self,
        binding_id: int,
        settings: Dict[str, Any],
    ) -> Optional[Dict]:
        """Update the last_settings for a computer binding.
        
        Args:
            binding_id: ID of the binding
            settings: Current instrument settings to save
        
        Returns:
            Updated binding as dictionary
        """
        from database.models import ComputerBinding
        from datetime import datetime
        
        with self.session_scope() as session:
            binding = session.query(ComputerBinding).filter(
                ComputerBinding.id == binding_id
            ).first()
            
            if not binding:
                return None
            
            binding.last_settings = settings
            binding.last_connected = datetime.utcnow()
            session.flush()
            
            return self._computer_binding_to_dict(binding)
    
    def delete_computer_binding(self, binding_id: int) -> bool:
        """Delete a computer binding."""
        from database.models import ComputerBinding
        
        with self.session_scope() as session:
            binding = session.query(ComputerBinding).filter(
                ComputerBinding.id == binding_id
            ).first()
            
            if not binding:
                return False
            
            session.delete(binding)
            return True
    
    def get_definition_ids_for_computer(
        self,
        computer_name: str,
        include_public: bool = True,
    ) -> List[int]:
        """Get instrument definition IDs that are bound to a specific computer.
        
        This method finds all InstrumentDefinition IDs where at least one
        Instrument instance using that definition is bound to the given computer.
        
        Args:
            computer_name: The hostname of the computer
            include_public: If True, also include all public (is_public=True) definitions
        
        Returns:
            List of InstrumentDefinition IDs available on this computer
        """
        from database.models import ComputerBinding, Instrument, InstrumentDefinition
        from sqlalchemy import distinct
        
        with self.session_scope() as session:
            # Get definition IDs from instruments bound to this computer
            bound_definition_ids = session.query(distinct(Instrument.definition_id)).join(
                ComputerBinding,
                ComputerBinding.instrument_id == Instrument.id
            ).filter(
                ComputerBinding.computer_name == computer_name,
                Instrument.definition_id.isnot(None)
            ).all()
            
            definition_ids = {row[0] for row in bound_definition_ids}
            
            # Optionally include all public definitions
            if include_public:
                public_ids = session.query(InstrumentDefinition.id).filter(
                    InstrumentDefinition.is_public == True
                ).all()
                definition_ids.update(row[0] for row in public_ids)
            
            return list(definition_ids)
    
    def _computer_binding_to_dict(self, binding, computer=None) -> Dict:
        """Convert ComputerBinding model to dictionary.
        
        Args:
            binding: ComputerBinding model instance
            computer: Optional Computer model instance (if not provided, uses binding.computer relationship)
        """
        if not binding:
            return {}
        
        # Get computer info - nickname comes from Computer, not binding
        if computer is None:
            computer = getattr(binding, 'computer', None)
        
        nickname = None
        computer_location = None
        if computer:
            nickname = computer.nickname
            computer_location = getattr(computer, 'location', None)
        
        return {
            'id': binding.id,
            'instrument_id': binding.instrument_id,
            'computer_name': binding.computer_name,
            'computer_id': binding.computer_id,
            'username': binding.username,
            'nickname': nickname,
            'computer_location': computer_location,
            'adapter': binding.adapter,
            'adapter_type': binding.adapter_type,
            'is_primary': binding.is_primary,
            'last_connected': binding.last_connected.isoformat() if binding.last_connected else None,
            'last_settings': binding.last_settings,
            'created_at': binding.created_at.isoformat() if binding.created_at else None,
            'updated_at': binding.updated_at.isoformat() if binding.updated_at else None,
        }

    # ==================== Computers ====================
    
    def get_computer(self, computer_name: str) -> Optional[Dict]:
        """Get a computer by hostname.
        
        Args:
            computer_name: The hostname of the computer
            
        Returns:
            Computer as dictionary, or None if not found
        """
        from database.models import Computer
        
        with self.session_scope() as session:
            computer = session.query(Computer).filter(
                Computer.computer_name == computer_name
            ).first()
            
            if not computer:
                return None
            
            return self._computer_to_dict(computer)
    
    def get_computer_by_id(self, computer_id: int) -> Optional[Dict]:
        """Get a computer by ID.
        
        Args:
            computer_id: The database ID of the computer
            
        Returns:
            Computer as dictionary, or None if not found
        """
        from database.models import Computer
        
        with self.session_scope() as session:
            computer = session.query(Computer).filter(
                Computer.id == computer_id
            ).first()
            
            if not computer:
                return None
            
            return self._computer_to_dict(computer)
    
    def get_computers_list(self, search: Optional[str] = None) -> List[Dict]:
        """Get list of all computers.
        
        Args:
            search: Optional search term to filter by name or nickname
            
        Returns:
            List of computers as dictionaries
        """
        from database.models import Computer
        from sqlalchemy import or_
        
        with self.session_scope() as session:
            query = session.query(Computer)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Computer.computer_name.ilike(search_term),
                        Computer.nickname.ilike(search_term),
                        Computer.location.ilike(search_term),
                    )
                )
            
            computers = query.order_by(Computer.computer_name).all()
            return [self._computer_to_dict(c) for c in computers]
    
    def update_computer(
        self,
        computer_name: str,
        nickname: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Dict]:
        """Update a computer's information.
        
        Args:
            computer_name: Hostname of the computer to update
            nickname: New friendly name (None to keep existing)
            location: Physical location (None to keep existing)
            description: Additional notes (None to keep existing)
            
        Returns:
            Updated computer as dictionary, or None if not found
        """
        from database.models import Computer
        
        with self.session_scope() as session:
            computer = session.query(Computer).filter(
                Computer.computer_name == computer_name
            ).first()
            
            if not computer:
                return None
            
            if nickname is not None:
                computer.nickname = nickname
            if location is not None:
                computer.location = location
            if description is not None:
                computer.description = description
            
            session.flush()
            return self._computer_to_dict(computer)
    
    def _computer_to_dict(self, computer) -> Dict:
        """Convert Computer model to dictionary."""
        if not computer:
            return {}
        
        return {
            'id': computer.id,
            'lab_id': getattr(computer, 'lab_id', None),
            'lab_name': computer.lab.name if getattr(computer, 'lab', None) else None,
            'computer_name': computer.computer_name,
            'computer_id': computer.computer_id,
            'nickname': computer.nickname,
            'location': getattr(computer, 'location', None),
            'description': getattr(computer, 'description', None),
            'created_at': computer.created_at.isoformat() if computer.created_at else None,
            'updated_at': computer.updated_at.isoformat() if computer.updated_at else None,
        }
    
    def create_computer(
        self,
        computer_name: str,
        computer_id: Optional[str] = None,
        nickname: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        lab_id: Optional[int] = None,
    ) -> Dict:
        """Create a new computer.
        
        Args:
            computer_name: Hostname of the computer (required, unique)
            computer_id: MAC address or UUID (optional)
            nickname: Friendly name (optional)
            location: Physical location (optional)
            description: Additional notes (optional)
            lab_id: Lab ID (optional)
            
        Returns:
            Created computer as dictionary
        """
        from database.models import Computer
        
        with self.session_scope() as session:
            computer = Computer(
                computer_name=computer_name,
                computer_id=computer_id,
                nickname=nickname,
                location=location,
                description=description,
                lab_id=lab_id,
            )
            session.add(computer)
            session.flush()
            return self._computer_to_dict(computer)
    
    def update_computer_by_id(
        self,
        computer_db_id: int,
        computer_name: Optional[str] = None,
        computer_id: Optional[str] = None,
        nickname: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        lab_id: Optional[int] = None,
    ) -> Optional[Dict]:
        """Update a computer by database ID.
        
        Args:
            computer_db_id: Database ID of the computer
            computer_name: Hostname (None to keep existing)
            computer_id: MAC/UUID (None to keep existing)
            nickname: Friendly name (None to keep existing)
            location: Physical location (None to keep existing)
            description: Additional notes (None to keep existing)
            lab_id: Lab ID (None to keep existing)
            
        Returns:
            Updated computer as dictionary, or None if not found
        """
        from database.models import Computer
        
        with self.session_scope() as session:
            computer = session.query(Computer).filter(
                Computer.id == computer_db_id
            ).first()
            
            if not computer:
                return None
            
            if computer_name is not None:
                computer.computer_name = computer_name
            if computer_id is not None:
                computer.computer_id = computer_id
            if nickname is not None:
                computer.nickname = nickname
            if location is not None:
                computer.location = location
            if description is not None:
                computer.description = description
            if lab_id is not None:
                computer.lab_id = lab_id
            
            session.flush()
            return self._computer_to_dict(computer)
    
    def delete_computer(self, computer_db_id: int) -> bool:
        """Delete a computer by database ID.
        
        Note: This will also delete all associated computer bindings.
        
        Args:
            computer_db_id: Database ID of the computer
            
        Returns:
            True if deleted, False if not found
        """
        from database.models import Computer, ComputerBinding
        
        with self.session_scope() as session:
            computer = session.query(Computer).filter(
                Computer.id == computer_db_id
            ).first()
            
            if not computer:
                return False
            
            # Delete associated bindings first
            session.query(ComputerBinding).filter(
                ComputerBinding.computer_id_fk == computer_db_id
            ).delete()
            
            session.delete(computer)
            return True
    
    def get_computer_with_bindings(self, computer_db_id: int) -> Optional[Dict]:
        """Get a computer by ID with all its instrument bindings.
        
        Args:
            computer_db_id: Database ID of the computer
            
        Returns:
            Computer dict with 'bindings' list, or None if not found
        """
        from database.models import Computer, ComputerBinding, Instrument, InstrumentDefinition
        from sqlalchemy.orm import joinedload
        
        with self.session_scope() as session:
            computer = session.query(Computer).filter(
                Computer.id == computer_db_id
            ).first()
            
            if not computer:
                return None
            
            result = self._computer_to_dict(computer)
            
            # Get bindings with instrument info
            bindings = session.query(ComputerBinding).options(
                joinedload(ComputerBinding.instrument).joinedload(Instrument.definition)
            ).filter(
                ComputerBinding.computer_id_fk == computer_db_id
            ).all()
            
            result['bindings'] = []
            for b in bindings:
                binding_dict = {
                    'id': b.id,
                    'instrument_id': b.instrument_id,
                    'adapter': b.adapter,
                    'adapter_type': b.adapter_type,
                    'is_primary': b.is_primary,
                    'last_connected': b.last_connected.isoformat() if b.last_connected else None,
                    'last_settings': b.last_settings,
                }
                if b.instrument:
                    binding_dict['instrument_name'] = b.instrument.name
                    binding_dict['instrument_status'] = b.instrument.status
                    binding_dict['pybirch_class'] = b.instrument.pybirch_class
                    if b.instrument.definition:
                        binding_dict['definition_name'] = b.instrument.definition.name
                result['bindings'].append(binding_dict)
            
            return result
    
    def get_computers(
        self,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of computers with binding counts.
        
        Args:
            search: Optional search term
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Tuple of (list of computers, total count)
        """
        from database.models import Computer, ComputerBinding
        from sqlalchemy import or_, func
        
        with self.session_scope() as session:
            query = session.query(Computer)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Computer.computer_name.ilike(search_term),
                        Computer.nickname.ilike(search_term),
                        Computer.location.ilike(search_term),
                    )
                )
            
            total = query.count()
            
            computers = query.order_by(Computer.computer_name).offset(
                (page - 1) * per_page
            ).limit(per_page).all()
            
            result = []
            for c in computers:
                c_dict = self._computer_to_dict(c)
                # Count bindings
                binding_count = session.query(func.count(ComputerBinding.id)).filter(
                    ComputerBinding.computer_id_fk == c.id
                ).scalar()
                c_dict['binding_count'] = binding_count or 0
                result.append(c_dict)
            
            return result, total

    # ==================== Equipment (Large lab equipment) ====================
    
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
    
    def get_equipment_list(
        self,
        search: Optional[str] = None,
        equipment_type: Optional[str] = None,
        status: Optional[str] = None,
        lab_id: Optional[int] = None,
        owner_id: Optional[int] = None,
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
                        Equipment.model.ilike(search_term),
                        Equipment.description.ilike(search_term)
                    )
                )
            
            if equipment_type:
                query = query.filter(Equipment.equipment_type == equipment_type)
            
            if status:
                query = query.filter(Equipment.status == status)
            
            if lab_id:
                query = query.filter(Equipment.lab_id == lab_id)
            
            if owner_id:
                query = query.filter(Equipment.owner_id == owner_id)
            
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
            
            for field in ['name', 'equipment_type', 'description', 'manufacturer', 'model',
                          'serial_number', 'location', 'room', 'status', 'owner_id',
                          'purchase_date', 'warranty_expiration', 'last_maintenance_date',
                          'next_maintenance_date', 'maintenance_interval_days', 'specifications',
                          'documentation_url', 'lab_id']:
                if field in data:
                    setattr(equipment, field, data[field])
            
            session.flush()
            return self._equipment_to_dict(equipment)
    
    def delete_equipment(self, equipment_id: int) -> bool:
        """Delete equipment by ID."""
        with self.session_scope() as session:
            equipment = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not equipment:
                return False
            session.delete(equipment)
            return True
    
    def _equipment_to_dict(self, equipment: Equipment) -> Dict:
        """Convert Equipment model to dictionary."""
        owner_name = None
        if equipment.owner:
            owner_name = equipment.owner.name or equipment.owner.username
        return {
            'id': equipment.id,
            'name': equipment.name,
            'equipment_type': equipment.equipment_type,
            'description': equipment.description,
            'manufacturer': equipment.manufacturer,
            'model': equipment.model,
            'serial_number': equipment.serial_number,
            'location': equipment.location,
            'room': equipment.room,
            'status': equipment.status,
            'owner_id': equipment.owner_id,
            'owner_name': owner_name,
            'purchase_date': equipment.purchase_date.isoformat() if equipment.purchase_date else None,
            'warranty_expiration': equipment.warranty_expiration.isoformat() if equipment.warranty_expiration else None,
            'last_maintenance_date': equipment.last_maintenance_date.isoformat() if equipment.last_maintenance_date else None,
            'next_maintenance_date': equipment.next_maintenance_date.isoformat() if equipment.next_maintenance_date else None,
            'maintenance_interval_days': equipment.maintenance_interval_days,
            'specifications': equipment.specifications,
            'documentation_url': equipment.documentation_url,
            'lab_id': equipment.lab_id,
            'created_at': equipment.created_at.isoformat() if equipment.created_at else None,
            'updated_at': equipment.updated_at.isoformat() if equipment.updated_at else None,
        }

    # ==================== Equipment Issues ====================
    
    def get_equipment_issues(
        self,
        equipment_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        assignee_id: Optional[int] = None,
        reporter_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of equipment issues."""
        with self.session_scope() as session:
            query = session.query(EquipmentIssue)
            
            if equipment_id:
                query = query.filter(EquipmentIssue.equipment_id == equipment_id)
            
            if status:
                query = query.filter(EquipmentIssue.status == status)
            
            if priority:
                query = query.filter(EquipmentIssue.priority == priority)
            
            if category:
                query = query.filter(EquipmentIssue.category == category)
            
            if assignee_id:
                query = query.filter(EquipmentIssue.assignee_id == assignee_id)
            
            if reporter_id:
                query = query.filter(EquipmentIssue.reporter_id == reporter_id)
            
            total = query.count()
            offset = (page - 1) * per_page
            issues = query.order_by(EquipmentIssue.created_at.desc()).offset(offset).limit(per_page).all()
            
            return [self._equipment_issue_to_dict(i) for i in issues], total
    
    def get_equipment_issue(self, issue_id: int) -> Optional[Dict]:
        """Get a single equipment issue by ID."""
        with self.session_scope() as session:
            issue = session.query(EquipmentIssue).filter(EquipmentIssue.id == issue_id).first()
            return self._equipment_issue_to_dict(issue) if issue else None
    
    def create_equipment_issue(self, data: Dict[str, Any]) -> Dict:
        """Create new equipment issue."""
        with self.session_scope() as session:
            # If no assignee specified but equipment has an owner, default to owner
            if 'assignee_id' not in data or data['assignee_id'] is None:
                equipment = session.query(Equipment).filter(Equipment.id == data.get('equipment_id')).first()
                if equipment and equipment.owner_id:
                    data['assignee_id'] = equipment.owner_id
            
            issue = EquipmentIssue(**data)
            session.add(issue)
            session.flush()
            return self._equipment_issue_to_dict(issue)
    
    def update_equipment_issue(self, issue_id: int, data: Dict) -> Optional[Dict]:
        """Update an existing equipment issue."""
        with self.session_scope() as session:
            issue = session.query(EquipmentIssue).filter(EquipmentIssue.id == issue_id).first()
            if not issue:
                return None
            
            for field in ['title', 'description', 'category', 'priority', 'status',
                          'assignee_id', 'error_message', 'steps_to_reproduce',
                          'resolution', 'cost', 'downtime_hours', 'resolved_at']:
                if field in data:
                    setattr(issue, field, data[field])
            
            session.flush()
            return self._equipment_issue_to_dict(issue)
    
    def _equipment_issue_to_dict(self, issue: EquipmentIssue) -> Dict:
        """Convert EquipmentIssue model to dictionary."""
        reporter_name = None
        if issue.reporter:
            reporter_name = issue.reporter.name or issue.reporter.username
        assignee_name = None
        if issue.assignee:
            assignee_name = issue.assignee.name or issue.assignee.username
        equipment_name = None
        if issue.equipment:
            equipment_name = issue.equipment.name
        return {
            'id': issue.id,
            'equipment_id': issue.equipment_id,
            'equipment_name': equipment_name,
            'title': issue.title,
            'description': issue.description,
            'category': issue.category,
            'priority': issue.priority,
            'status': issue.status,
            'reporter_id': issue.reporter_id,
            'reporter_name': reporter_name,
            'assignee_id': issue.assignee_id,
            'assignee_name': assignee_name,
            'error_message': issue.error_message,
            'steps_to_reproduce': issue.steps_to_reproduce,
            'resolution': issue.resolution,
            'cost': float(issue.cost) if issue.cost else None,
            'downtime_hours': float(issue.downtime_hours) if issue.downtime_hours else None,
            'resolved_at': issue.resolved_at.isoformat() if issue.resolved_at else None,
            'created_at': issue.created_at.isoformat() if issue.created_at else None,
            'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
        }

    # ==================== Instrument Definition Issues ====================
    
    def get_instrument_definition_issues(
        self,
        definition_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        assignee_id: Optional[int] = None,
        reporter_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of instrument definition issues."""
        with self.session_scope() as session:
            query = session.query(InstrumentDefinitionIssue)
            
            if definition_id:
                query = query.filter(InstrumentDefinitionIssue.definition_id == definition_id)
            
            if status:
                query = query.filter(InstrumentDefinitionIssue.status == status)
            
            if priority:
                query = query.filter(InstrumentDefinitionIssue.priority == priority)
            
            if category:
                query = query.filter(InstrumentDefinitionIssue.category == category)
            
            if assignee_id:
                query = query.filter(InstrumentDefinitionIssue.assignee_id == assignee_id)
            
            if reporter_id:
                query = query.filter(InstrumentDefinitionIssue.reporter_id == reporter_id)
            
            total = query.count()
            offset = (page - 1) * per_page
            issues = query.order_by(InstrumentDefinitionIssue.created_at.desc()).offset(offset).limit(per_page).all()
            
            return [self._instrument_definition_issue_to_dict(i) for i in issues], total
    
    def get_instrument_definition_issue(self, issue_id: int) -> Optional[Dict]:
        """Get a single instrument definition issue by ID."""
        with self.session_scope() as session:
            issue = session.query(InstrumentDefinitionIssue).filter(InstrumentDefinitionIssue.id == issue_id).first()
            return self._instrument_definition_issue_to_dict(issue) if issue else None
    
    def create_instrument_definition_issue(self, data: Dict[str, Any]) -> Dict:
        """Create new instrument definition issue."""
        with self.session_scope() as session:
            issue = InstrumentDefinitionIssue(**data)
            session.add(issue)
            session.flush()
            return self._instrument_definition_issue_to_dict(issue)
    
    def update_instrument_definition_issue(self, issue_id: int, data: Dict) -> Optional[Dict]:
        """Update an existing instrument definition issue."""
        with self.session_scope() as session:
            issue = session.query(InstrumentDefinitionIssue).filter(InstrumentDefinitionIssue.id == issue_id).first()
            if not issue:
                return None
            
            for field in ['title', 'description', 'category', 'priority', 'status',
                          'assignee_id', 'error_message', 'steps_to_reproduce',
                          'affected_version', 'fixed_in_version', 'environment_info',
                          'resolution', 'resolution_steps', 'resolved_at']:
                if field in data:
                    setattr(issue, field, data[field])
            
            session.flush()
            return self._instrument_definition_issue_to_dict(issue)
    
    def _instrument_definition_issue_to_dict(self, issue: InstrumentDefinitionIssue) -> Dict:
        """Convert InstrumentDefinitionIssue model to dictionary."""
        reporter_name = None
        if issue.reporter:
            reporter_name = issue.reporter.name or issue.reporter.username
        assignee_name = None
        if issue.assignee:
            assignee_name = issue.assignee.name or issue.assignee.username
        definition_name = None
        if issue.definition:
            definition_name = issue.definition.display_name or issue.definition.name
        return {
            'id': issue.id,
            'definition_id': issue.definition_id,
            'definition_name': definition_name,
            'title': issue.title,
            'description': issue.description,
            'category': issue.category,
            'priority': issue.priority,
            'status': issue.status,
            'reporter_id': issue.reporter_id,
            'reporter_name': reporter_name,
            'assignee_id': issue.assignee_id,
            'assignee_name': assignee_name,
            'error_message': issue.error_message,
            'steps_to_reproduce': issue.steps_to_reproduce,
            'affected_version': issue.affected_version,
            'fixed_in_version': issue.fixed_in_version,
            'environment_info': issue.environment_info,
            'resolution': issue.resolution,
            'resolution_steps': issue.resolution_steps,
            'resolved_at': issue.resolved_at.isoformat() if issue.resolved_at else None,
            'created_at': issue.created_at.isoformat() if issue.created_at else None,
            'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
        }

    # ==================== Equipment Images ====================
    
    def get_equipment_images(self, equipment_id: int) -> List[Dict]:
        """Get all images for an equipment."""
        with self.session_scope() as session:
            images = session.query(EquipmentImage).filter(
                EquipmentImage.equipment_id == equipment_id
            ).order_by(EquipmentImage.is_primary.desc(), EquipmentImage.created_at.desc()).all()
            return [self._equipment_image_to_dict(img) for img in images]
    
    def add_equipment_image(self, equipment_id: int, filename: str, file_path: str,
                            original_filename: Optional[str] = None,
                            file_size: Optional[int] = None,
                            mime_type: Optional[str] = None,
                            caption: Optional[str] = None,
                            is_primary: bool = False,
                            uploaded_by: Optional[str] = None) -> Dict:
        """Add an image to equipment."""
        with self.session_scope() as session:
            # If this is marked as primary, unset any existing primary
            if is_primary:
                session.query(EquipmentImage).filter(
                    EquipmentImage.equipment_id == equipment_id,
                    EquipmentImage.is_primary == True
                ).update({'is_primary': False})
            
            image = EquipmentImage(
                equipment_id=equipment_id,
                filename=filename,
                file_path=file_path,
                original_filename=original_filename,
                file_size=file_size,
                mime_type=mime_type,
                caption=caption,
                is_primary=is_primary,
                uploaded_by=uploaded_by
            )
            session.add(image)
            session.flush()
            return self._equipment_image_to_dict(image)
    
    def delete_equipment_image(self, image_id: int) -> bool:
        """Delete an equipment image."""
        with self.session_scope() as session:
            image = session.query(EquipmentImage).filter(EquipmentImage.id == image_id).first()
            if image:
                session.delete(image)
                return True
            return False
    
    def set_primary_equipment_image(self, equipment_id: int, image_id: int) -> bool:
        """Set an image as the primary image for equipment."""
        with self.session_scope() as session:
            # Unset all primary images for this equipment
            session.query(EquipmentImage).filter(
                EquipmentImage.equipment_id == equipment_id
            ).update({'is_primary': False})
            
            # Set the specified image as primary
            result = session.query(EquipmentImage).filter(
                EquipmentImage.id == image_id,
                EquipmentImage.equipment_id == equipment_id
            ).update({'is_primary': True})
            
            return result > 0
    
    def _equipment_image_to_dict(self, image: EquipmentImage) -> Dict:
        """Convert EquipmentImage model to dictionary."""
        return {
            'id': image.id,
            'equipment_id': image.equipment_id,
            'filename': image.filename,
            'original_filename': image.original_filename,
            'file_path': image.file_path,
            'file_size': image.file_size,
            'mime_type': image.mime_type,
            'caption': image.caption,
            'is_primary': image.is_primary,
            'uploaded_by': image.uploaded_by,
            'created_at': image.created_at.isoformat() if image.created_at else None,
        }
    
    # ==================== Precursors ====================
    
    def get_precursors(
        self,
        search: Optional[str] = None,
        state: Optional[str] = None,
        lab_id: Optional[int] = None,
        project_id: Optional[int] = None,
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
            
            if project_id:
                query = query.filter(Precursor.project_id == project_id)
            elif lab_id:
                # Filter by direct lab_id or through project
                query = query.filter(
                    or_(
                        Precursor.lab_id == lab_id,
                        Precursor.project_id.in_(
                            session.query(Project.id).filter(Project.lab_id == lab_id)
                        )
                    )
                )
            
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
                          'storage_conditions', 'safety_info', 'lab_id', 'project_id']:
                if field in data:
                    setattr(precursor, field, data[field])
            
            session.flush()
            return self._precursor_to_dict(precursor)
    
    def delete_precursor(self, precursor_id: int) -> bool:
        """Delete a precursor by ID."""
        with self.session_scope() as session:
            precursor = session.query(Precursor).filter(Precursor.id == precursor_id).first()
            if not precursor:
                return False
            session.delete(precursor)
            return True
    
    def replace_precursor_in_templates(self, old_precursor_id: int, new_precursor_id: int) -> int:
        """
        Replace references to an old precursor with a new precursor in all templates.
        
        Args:
            old_precursor_id: The ID of the precursor being replaced
            new_precursor_id: The ID of the new precursor to use instead
            
        Returns:
            Number of templates updated
        """
        updated_count = 0
        with self.session_scope() as session:
            # Find all active templates
            templates = session.query(Template).filter(Template.is_active == True).all()
            
            for template in templates:
                if not template.template_data:
                    continue
                    
                linked_ids = template.template_data.get('linked_precursor_ids', [])
                if old_precursor_id in linked_ids:
                    # Replace old ID with new ID
                    new_linked_ids = [new_precursor_id if pid == old_precursor_id else pid for pid in linked_ids]
                    
                    # Update template_data (need to copy to trigger change detection)
                    new_template_data = dict(template.template_data)
                    new_template_data['linked_precursor_ids'] = new_linked_ids
                    template.template_data = new_template_data
                    updated_count += 1
            
            session.flush()
        
        return updated_count
    
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
            'lab_id': precursor.lab_id,
            'project_id': precursor.project_id,
        }
    
    # ==================== Procedures ====================
    
    def get_procedures(
        self,
        search: Optional[str] = None,
        procedure_type: Optional[str] = None,
        lab_id: Optional[int] = None,
        project_id: Optional[int] = None,
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
            
            if project_id:
                query = query.filter(Procedure.project_id == project_id)
            elif lab_id:
                # Filter by direct lab_id or through project
                query = query.filter(
                    or_(
                        Procedure.lab_id == lab_id,
                        Procedure.project_id.in_(
                            session.query(Project.id).filter(Project.lab_id == lab_id)
                        )
                    )
                )
            
            total = query.count()
            offset = (page - 1) * per_page
            procedures = query.order_by(Procedure.name).offset(offset).limit(per_page).all()
            
            return [self._procedure_to_dict(p) for p in procedures], total
    
    def get_procedures_simple_list(self, include_params: bool = False) -> List[Dict]:
        """Get simple list of active procedures for dropdowns.
        
        Args:
            include_params: If True, include parameters and steps for fabrication run forms
        """
        with self.session_scope() as session:
            procedures = session.query(Procedure).filter(
                Procedure.is_active == True
            ).order_by(Procedure.name).all()
            
            result = []
            for p in procedures:
                item = {
                    'id': p.id,
                    'name': p.name,
                    'procedure_type': p.procedure_type,
                    'version': p.version,
                }
                if include_params:
                    item['parameters'] = p.parameters or []
                    item['steps'] = p.steps or []
                    item['failure_modes'] = p.failure_modes or []
                result.append(item)
            return result
    
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
                    'created_by': run.created_by,
                    'started_at': run.started_at.isoformat() if run.started_at else None,
                    'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                    'weather_conditions': run.weather_conditions,
                }
                for run in runs
            ]
            
            return result
    
    def get_fabrication_runs(
        self,
        sample_id: Optional[int] = None,
        procedure_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int]:
        """Get paginated list of fabrication runs with optional filtering."""
        from sqlalchemy.orm import joinedload
        
        with self.session_scope() as session:
            query = session.query(FabricationRun).options(
                joinedload(FabricationRun.sample),
                joinedload(FabricationRun.procedure)
            )
            
            if sample_id:
                query = query.filter(FabricationRun.sample_id == sample_id)
            if procedure_id:
                query = query.filter(FabricationRun.procedure_id == procedure_id)
            if status:
                query = query.filter(FabricationRun.status == status)
            if search:
                search_term = f"%{search}%"
                query = query.outerjoin(Sample, FabricationRun.sample_id == Sample.id).outerjoin(
                    Procedure, FabricationRun.procedure_id == Procedure.id
                ).filter(
                    or_(
                        Sample.name.ilike(search_term),
                        Sample.sample_id.ilike(search_term),
                        Procedure.name.ilike(search_term),
                        FabricationRun.created_by.ilike(search_term),
                        FabricationRun.notes.ilike(search_term),
                    )
                )
            
            total = query.count()
            runs = query.order_by(FabricationRun.created_at.desc()).offset(
                (page - 1) * per_page
            ).limit(per_page).all()
            
            return [{
                'id': run.id,
                'sample_id': run.sample_id,
                'sample_name': run.sample.name if run.sample else None,
                'sample_sample_id': run.sample.sample_id if run.sample else None,
                'procedure_id': run.procedure_id,
                'procedure_name': run.procedure.name if run.procedure else None,
                'run_number': run.run_number,
                'status': run.status,
                'created_by': run.created_by,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'weather_conditions': run.weather_conditions,
                'created_at': run.created_at.isoformat() if run.created_at else None,
            } for run in runs], total
    
    def get_fabrication_run(self, run_id: int) -> Optional[Dict]:
        """Get a single fabrication run by ID."""
        with self.session_scope() as session:
            run = session.query(FabricationRun).filter(FabricationRun.id == run_id).first()
            if not run:
                return None
            return {
                'id': run.id,
                'sample_id': run.sample_id,
                'sample_name': run.sample.name if run.sample else None,
                'sample_sample_id': run.sample.sample_id if run.sample else None,
                'procedure_id': run.procedure_id,
                'procedure_name': run.procedure.name if run.procedure else None,
                'procedure_failure_modes': run.procedure.failure_modes if run.procedure else None,
                'run_number': run.run_number,
                'status': run.status,
                'failure_mode': run.failure_mode,
                'created_by': run.created_by,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'actual_parameters': run.actual_parameters,
                'notes': run.notes,
                'results': run.results,
                'weather_conditions': run.weather_conditions,
                'created_at': run.created_at.isoformat() if run.created_at else None,
            }
    
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
            
            # Inherit lab_id from procedure if not explicitly provided
            lab_id = data.get('lab_id')
            if lab_id is None and data.get('procedure_id'):
                procedure = session.query(Procedure).filter(Procedure.id == data['procedure_id']).first()
                if procedure:
                    lab_id = procedure.lab_id
            
            if lab_id is None:
                raise ValueError("lab_id is required for fabrication run (should be inherited from procedure)")
            
            run = FabricationRun(
                sample_id=data['sample_id'],
                procedure_id=data['procedure_id'],
                run_number=data.get('run_number'),
                started_at=data.get('started_at'),
                status=data.get('status', 'pending'),
                failure_mode=data.get('failure_mode'),
                created_by=data.get('operator') or data.get('created_by'),
                actual_parameters=data.get('actual_parameters'),
                notes=data.get('notes'),
                weather_conditions=weather,
                lab_id=lab_id,
            )
            session.add(run)
            session.flush()
            
            return {
                'id': run.id,
                'sample_id': run.sample_id,
                'procedure_id': run.procedure_id,
                'run_number': run.run_number,
                'status': run.status,
                'created_by': run.created_by,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'weather_conditions': run.weather_conditions,
                'created_at': run.created_at.isoformat() if run.created_at else None,
                'lab_id': run.lab_id,
            }
    
    def update_fabrication_run(self, run_id: int, data: Dict) -> Optional[Dict]:
        """Update a fabrication run."""
        with self.session_scope() as session:
            run = session.query(FabricationRun).filter(FabricationRun.id == run_id).first()
            if not run:
                return None
            
            for field in ['procedure_id', 'run_number', 'status', 'failure_mode', 'created_by', 
                          'actual_parameters', 'notes', 'results', 'lab_id']:
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
                'created_by': run.created_by,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'notes': run.notes,
                'weather_conditions': run.weather_conditions,
                'lab_id': run.lab_id,
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
                failure_modes=data.get('failure_modes'),
                estimated_duration_minutes=data.get('estimated_duration_minutes'),
                safety_requirements=data.get('safety_requirements'),
                created_by=data.get('created_by'),
                is_active=True,
                lab_id=data.get('lab_id'),
                project_id=data.get('project_id'),
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
                          'parameters', 'failure_modes', 'estimated_duration_minutes', 'safety_requirements', 
                          'created_by', 'is_active', 'lab_id', 'project_id']:
                if field in data:
                    setattr(procedure, field, data[field])
            
            session.flush()
            return self._procedure_to_dict(procedure)
    
    def delete_procedure(self, procedure_id: int) -> bool:
        """Delete a procedure by ID (soft delete by setting is_active to False)."""
        with self.session_scope() as session:
            procedure = session.query(Procedure).filter(Procedure.id == procedure_id).first()
            if not procedure:
                return False
            # Soft delete - keep the record but mark as inactive
            procedure.is_active = False
            return True
    
    def _procedure_to_dict(self, procedure: Procedure) -> Dict:
        """Convert Procedure model to dictionary."""
        # Get linked equipment
        equipment_list = []
        if hasattr(procedure, 'equipment_associations') and procedure.equipment_associations:
            for assoc in procedure.equipment_associations:
                if assoc.equipment:
                    equipment_list.append({
                        'id': assoc.equipment.id,
                        'name': assoc.equipment.name,
                        'equipment_type': assoc.equipment.equipment_type,
                        'role': assoc.role,
                        'is_required': assoc.is_required,
                    })
        
        # Get linked precursors
        precursor_list = []
        if hasattr(procedure, 'precursor_associations') and procedure.precursor_associations:
            for assoc in procedure.precursor_associations:
                if assoc.precursor:
                    precursor_list.append({
                        'id': assoc.id,
                        'precursor_id': assoc.precursor.id,
                        'precursor_name': assoc.precursor.name,
                        'chemical_formula': assoc.precursor.chemical_formula,
                        'quantity': float(assoc.quantity) if assoc.quantity else None,
                        'quantity_unit': assoc.quantity_unit,
                        'purpose': assoc.purpose,
                        'is_required': assoc.is_required,
                    })
        
        return {
            'id': procedure.id,
            'name': procedure.name,
            'procedure_type': procedure.procedure_type,
            'version': procedure.version,
            'description': procedure.description,
            'steps': procedure.steps,
            'parameters': procedure.parameters,
            'failure_modes': procedure.failure_modes,
            'estimated_duration_minutes': procedure.estimated_duration_minutes,
            'safety_requirements': procedure.safety_requirements,
            'is_active': procedure.is_active,
            'created_at': procedure.created_at.isoformat() if procedure.created_at else None,
            'created_by': procedure.created_by,
            'equipment': equipment_list,
            'precursors': precursor_list,
            'lab_id': procedure.lab_id,
            'project_id': procedure.project_id,
        }
    
    # ==================== Procedure-Equipment Associations ====================
    
    def get_procedure_equipment(self, procedure_id: int) -> List[Dict]:
        """Get all equipment linked to a procedure."""
        with self.session_scope() as session:
            associations = session.query(ProcedureEquipment).filter(
                ProcedureEquipment.procedure_id == procedure_id
            ).all()
            
            return [{
                'id': a.id,
                'procedure_id': a.procedure_id,
                'equipment_id': a.equipment_id,
                'equipment_name': a.equipment.name if a.equipment else None,
                'equipment_type': a.equipment.equipment_type if a.equipment else None,
                'role': a.role,
                'is_required': a.is_required,
                'notes': a.notes,
            } for a in associations]
    
    def add_procedure_equipment(
        self,
        procedure_id: int,
        equipment_id: int,
        role: Optional[str] = None,
        is_required: bool = True,
        notes: Optional[str] = None
    ) -> Dict:
        """Link equipment to a procedure."""
        with self.session_scope() as session:
            # Check if association already exists
            existing = session.query(ProcedureEquipment).filter(
                ProcedureEquipment.procedure_id == procedure_id,
                ProcedureEquipment.equipment_id == equipment_id
            ).first()
            
            if existing:
                # Update existing association
                existing.role = role
                existing.is_required = is_required
                existing.notes = notes
                session.flush()
                return {
                    'id': existing.id,
                    'procedure_id': existing.procedure_id,
                    'equipment_id': existing.equipment_id,
                    'role': existing.role,
                    'is_required': existing.is_required,
                    'notes': existing.notes,
                }
            
            # Create new association
            association = ProcedureEquipment(
                procedure_id=procedure_id,
                equipment_id=equipment_id,
                role=role,
                is_required=is_required,
                notes=notes
            )
            session.add(association)
            session.flush()
            
            return {
                'id': association.id,
                'procedure_id': association.procedure_id,
                'equipment_id': association.equipment_id,
                'role': association.role,
                'is_required': association.is_required,
                'notes': association.notes,
            }
    
    def remove_procedure_equipment(self, procedure_id: int, equipment_id: int) -> bool:
        """Remove equipment link from a procedure."""
        with self.session_scope() as session:
            association = session.query(ProcedureEquipment).filter(
                ProcedureEquipment.procedure_id == procedure_id,
                ProcedureEquipment.equipment_id == equipment_id
            ).first()
            
            if association:
                session.delete(association)
                return True
            return False
    
    def update_procedure_equipment_list(self, procedure_id: int, equipment_ids: List[int]) -> None:
        """Update the list of equipment linked to a procedure (replaces all associations)."""
        with self.session_scope() as session:
            # Remove all existing associations
            session.query(ProcedureEquipment).filter(
                ProcedureEquipment.procedure_id == procedure_id
            ).delete()
            
            # Add new associations
            for equipment_id in equipment_ids:
                if equipment_id:
                    association = ProcedureEquipment(
                        procedure_id=procedure_id,
                        equipment_id=equipment_id,
                        is_required=True
                    )
                    session.add(association)
            
            session.flush()
    
    # ==================== Procedure-Precursor Associations ====================
    
    def get_procedure_precursors(self, procedure_id: int) -> List[Dict]:
        """Get all precursors linked to a procedure."""
        with self.session_scope() as session:
            associations = session.query(ProcedurePrecursor).options(
                joinedload(ProcedurePrecursor.precursor)
            ).filter(ProcedurePrecursor.procedure_id == procedure_id).all()
            
            return [{
                'id': a.id,
                'precursor_id': a.precursor_id,
                'precursor_name': a.precursor.name if a.precursor else None,
                'chemical_formula': a.precursor.chemical_formula if a.precursor else None,
                'quantity': float(a.quantity) if a.quantity else None,
                'quantity_unit': a.quantity_unit,
                'purpose': a.purpose,
                'is_required': a.is_required,
            } for a in associations]
    
    def add_procedure_precursor(
        self,
        procedure_id: int,
        precursor_id: int,
        quantity: Optional[float] = None,
        quantity_unit: Optional[str] = None,
        purpose: Optional[str] = None,
        is_required: bool = True
    ) -> Optional[Dict]:
        """Link a precursor to a procedure."""
        with self.session_scope() as session:
            # Check if association already exists
            existing = session.query(ProcedurePrecursor).filter(
                ProcedurePrecursor.procedure_id == procedure_id,
                ProcedurePrecursor.precursor_id == precursor_id
            ).first()
            
            if existing:
                return None
            
            association = ProcedurePrecursor(
                procedure_id=procedure_id,
                precursor_id=precursor_id,
                quantity=quantity,
                quantity_unit=quantity_unit,
                purpose=purpose,
                is_required=is_required
            )
            session.add(association)
            session.flush()
            
            return {
                'id': association.id,
                'procedure_id': association.procedure_id,
                'precursor_id': association.precursor_id,
                'quantity': float(association.quantity) if association.quantity else None,
                'quantity_unit': association.quantity_unit,
                'purpose': association.purpose,
                'is_required': association.is_required,
            }
    
    def remove_procedure_precursor(self, procedure_id: int, precursor_id: int) -> bool:
        """Remove a precursor link from a procedure."""
        with self.session_scope() as session:
            association = session.query(ProcedurePrecursor).filter(
                ProcedurePrecursor.procedure_id == procedure_id,
                ProcedurePrecursor.precursor_id == precursor_id
            ).first()
            
            if association:
                session.delete(association)
                return True
            return False
    
    def clear_procedure_precursors(self, procedure_id: int) -> int:
        """Remove all precursors from a procedure.
        
        Returns:
            Number of precursors removed
        """
        with self.session_scope() as session:
            count = session.query(ProcedurePrecursor).filter(
                ProcedurePrecursor.procedure_id == procedure_id
            ).delete()
            return count
    
    def update_procedure_precursor_list(
        self, 
        procedure_id: int, 
        precursors: List[Dict]
    ) -> None:
        """Update the list of precursors linked to a procedure (replaces all associations).
        
        Args:
            procedure_id: ID of the procedure
            precursors: List of dicts with keys: precursor_id, quantity, quantity_unit, purpose, is_required
        """
        with self.session_scope() as session:
            # Remove all existing associations
            session.query(ProcedurePrecursor).filter(
                ProcedurePrecursor.procedure_id == procedure_id
            ).delete()
            
            # Add new associations
            for prec in precursors:
                if prec.get('precursor_id'):
                    association = ProcedurePrecursor(
                        procedure_id=procedure_id,
                        precursor_id=prec['precursor_id'],
                        quantity=prec.get('quantity'),
                        quantity_unit=prec.get('quantity_unit'),
                        purpose=prec.get('purpose'),
                        is_required=prec.get('is_required', True)
                    )
                    session.add(association)
            
            session.flush()
    
    # ==================== Fabrication Run Precursors ====================
    
    def get_fabrication_run_precursors(self, run_id: int) -> List[Dict]:
        """Get all precursors consumed in a fabrication run."""
        with self.session_scope() as session:
            associations = session.query(FabricationRunPrecursor).options(
                joinedload(FabricationRunPrecursor.precursor)
            ).filter(FabricationRunPrecursor.fabrication_run_id == run_id).all()
            
            return [{
                'id': a.id,
                'precursor_id': a.precursor_id,
                'precursor_name': a.precursor.name if a.precursor else None,
                'chemical_formula': a.precursor.chemical_formula if a.precursor else None,
                'quantity_consumed': float(a.quantity_consumed) if a.quantity_consumed else None,
                'quantity_unit': a.quantity_unit,
                'notes': a.notes,
            } for a in associations]
    
    def add_fabrication_run_precursor(
        self,
        run_id: int,
        precursor_id: int,
        quantity_consumed: Optional[float] = None,
        quantity_unit: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[Dict]:
        """Add a precursor to a fabrication run."""
        with self.session_scope() as session:
            # Check if association already exists
            existing = session.query(FabricationRunPrecursor).filter(
                FabricationRunPrecursor.fabrication_run_id == run_id,
                FabricationRunPrecursor.precursor_id == precursor_id
            ).first()
            
            if existing:
                return None
            
            association = FabricationRunPrecursor(
                fabrication_run_id=run_id,
                precursor_id=precursor_id,
                quantity_consumed=quantity_consumed,
                quantity_unit=quantity_unit,
                notes=notes
            )
            session.add(association)
            session.flush()
            
            return {
                'id': association.id,
                'fabrication_run_id': association.fabrication_run_id,
                'precursor_id': association.precursor_id,
                'quantity_consumed': float(association.quantity_consumed) if association.quantity_consumed else None,
                'quantity_unit': association.quantity_unit,
                'notes': association.notes,
            }
    
    def remove_fabrication_run_precursor(self, run_id: int, precursor_id: int) -> bool:
        """Remove a precursor from a fabrication run."""
        with self.session_scope() as session:
            association = session.query(FabricationRunPrecursor).filter(
                FabricationRunPrecursor.fabrication_run_id == run_id,
                FabricationRunPrecursor.precursor_id == precursor_id
            ).first()
            
            if association:
                session.delete(association)
                return True
            return False
    
    def clear_fabrication_run_precursors(self, run_id: int) -> int:
        """Remove all precursors from a fabrication run.
        
        Returns:
            Number of precursors removed
        """
        with self.session_scope() as session:
            count = session.query(FabricationRunPrecursor).filter(
                FabricationRunPrecursor.fabrication_run_id == run_id
            ).delete()
            return count
    
    def update_fabrication_run_precursor_list(
        self, 
        run_id: int, 
        precursors: List[Dict]
    ) -> None:
        """Update the list of precursors for a fabrication run (replaces all associations).
        
        Args:
            run_id: ID of the fabrication run
            precursors: List of dicts with keys: precursor_id, quantity_consumed, quantity_unit, notes
        """
        with self.session_scope() as session:
            # Remove all existing associations
            session.query(FabricationRunPrecursor).filter(
                FabricationRunPrecursor.fabrication_run_id == run_id
            ).delete()
            
            # Add new associations
            for prec in precursors:
                if prec.get('precursor_id'):
                    association = FabricationRunPrecursor(
                        fabrication_run_id=run_id,
                        precursor_id=prec['precursor_id'],
                        quantity_consumed=prec.get('quantity_consumed'),
                        quantity_unit=prec.get('quantity_unit'),
                        notes=prec.get('notes')
                    )
                    session.add(association)
            
            session.flush()
    
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
            
            allowed_fields = ['name', 'email', 'role', 'lab_id', 'is_active', 'last_login', 'google_id',
                              'default_lab_id', 'default_project_id', 'phone', 'orcid', 'office_location']
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
    
    def get_user_preferences(self, user_id: int) -> Dict:
        """Get user's default preferences for forms.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Dictionary with user preferences (default_lab_id, default_project_id, pinned_instruments, etc.)
        """
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return {}
            
            return {
                'default_lab_id': user.default_lab_id,
                'default_project_id': user.default_project_id,
                'pinned_instruments': [],  # TODO: implement when pinned instruments are stored
            }
    
    def update_user_preferences(self, user_id: int, default_lab_id: Optional[int] = None, 
                                 default_project_id: Optional[int] = None) -> Optional[Dict]:
        """Update user's default preferences for forms.
        
        Args:
            user_id: The user's ID
            default_lab_id: Default lab to pre-fill in forms (None to clear)
            default_project_id: Default project to pre-fill in forms (None to clear)
            
        Returns:
            Updated user dict or None if user not found
        """
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            # Allow setting to None to clear defaults
            user.default_lab_id = default_lab_id
            user.default_project_id = default_project_id
            
            session.flush()
            return self._user_to_dict(user)
    
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
            'default_lab_id': user.default_lab_id,
            'default_project_id': user.default_project_id,
            'phone': user.phone,
            'orcid': user.orcid,
            'office_location': user.office_location,
        }
    
    def get_user_profile_data(self, user_id: int) -> Dict:
        """Get comprehensive user profile data including memberships and assignments.
        
        Returns user's lab memberships, project memberships, assigned equipment, and issues.
        """
        with self.session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return {}
            
            # Get lab memberships by matching user email to lab member emails
            lab_memberships = []
            if user.email:
                lab_members = session.query(LabMember).filter(
                    LabMember.email == user.email,
                    LabMember.is_active == True
                ).all()
                for lm in lab_members:
                    lab_memberships.append({
                        'id': lm.id,
                        'lab_id': lm.lab_id,
                        'lab_name': lm.lab.name if lm.lab else None,
                        'role': lm.role,
                        'title': lm.title,
                        'joined_at': lm.joined_at.isoformat() if lm.joined_at else None,
                    })
            
            # Get project memberships
            project_memberships = []
            if user.email:
                # Get project memberships through lab memberships
                for lm in lab_members if user.email else []:
                    for pm in lm.project_memberships:
                        if pm.is_active:
                            project_memberships.append({
                                'id': pm.id,
                                'project_id': pm.project_id,
                                'project_name': pm.project.name if pm.project else None,
                                'project_code': pm.project.code if pm.project else None,
                                'role': pm.role,
                                'joined_at': pm.joined_at.isoformat() if pm.joined_at else None,
                            })
            
            # Get assigned equipment (where user is owner)
            assigned_equipment = []
            for eq in user.owned_equipment:
                assigned_equipment.append({
                    'id': eq.id,
                    'name': eq.name,
                    'equipment_type': eq.equipment_type,
                    'status': eq.status,
                })
            
            # Get assigned issues (both general and equipment issues)
            assigned_issues = []
            for issue in user.issues_assigned:
                assigned_issues.append({
                    'id': issue.id,
                    'title': issue.title,
                    'status': issue.status,
                    'priority': issue.priority,
                    'type': 'general',
                })
            for eq_issue in user.equipment_issues_assigned:
                assigned_issues.append({
                    'id': eq_issue.id,
                    'title': eq_issue.title,
                    'status': eq_issue.status,
                    'priority': eq_issue.priority,
                    'type': 'equipment',
                    'equipment_id': eq_issue.equipment_id,
                    'equipment_name': eq_issue.equipment.name if eq_issue.equipment else None,
                })
            
            return {
                'lab_memberships': lab_memberships,
                'project_memberships': project_memberships,
                'assigned_equipment': assigned_equipment,
                'assigned_issues': assigned_issues,
            }
    
    # ==================== User Pins ====================
    
    def pin_item(self, user_id: int, entity_type: str, entity_id: int) -> bool:
        """Pin an item for a user. Returns True if successfully pinned."""
        with self.session_scope() as session:
            # Check if already pinned
            existing = session.query(UserPin).filter(
                UserPin.user_id == user_id,
                UserPin.entity_type == entity_type,
                UserPin.entity_id == entity_id
            ).first()
            
            if existing:
                return True  # Already pinned
            
            pin = UserPin(
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id
            )
            session.add(pin)
            return True
    
    def unpin_item(self, user_id: int, entity_type: str, entity_id: int) -> bool:
        """Unpin an item for a user. Returns True if successfully unpinned."""
        with self.session_scope() as session:
            pin = session.query(UserPin).filter(
                UserPin.user_id == user_id,
                UserPin.entity_type == entity_type,
                UserPin.entity_id == entity_id
            ).first()
            
            if pin:
                session.delete(pin)
                return True
            return False
    
    def is_pinned(self, user_id: int, entity_type: str, entity_id: int) -> bool:
        """Check if an item is pinned by a user."""
        with self.session_scope() as session:
            return session.query(UserPin).filter(
                UserPin.user_id == user_id,
                UserPin.entity_type == entity_type,
                UserPin.entity_id == entity_id
            ).first() is not None
    
    def get_pinned_ids(self, user_id: int, entity_type: str) -> List[int]:
        """Get list of pinned entity IDs for a user and entity type."""
        with self.session_scope() as session:
            pins = session.query(UserPin.entity_id).filter(
                UserPin.user_id == user_id,
                UserPin.entity_type == entity_type
            ).all()
            return [p[0] for p in pins]
    
    def get_user_pins(self, user_id: int) -> Dict[str, List[int]]:
        """Get all pinned items for a user, grouped by entity type."""
        with self.session_scope() as session:
            pins = session.query(UserPin).filter(UserPin.user_id == user_id).all()
            result = {}
            for pin in pins:
                if pin.entity_type not in result:
                    result[pin.entity_type] = []
                result[pin.entity_type].append(pin.entity_id)
            return result

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
    
    # ==================== Entity Images ====================
    
    def get_entity_images(self, entity_type: str, entity_id: int) -> List[Dict]:
        """Get all images for an entity."""
        with self.session_scope() as session:
            images = session.query(EntityImage).filter(
                EntityImage.entity_type == entity_type,
                EntityImage.entity_id == entity_id
            ).order_by(EntityImage.created_at.desc()).all()
            
            return [self._image_to_dict(img) for img in images]
    
    def get_image(self, image_id: int) -> Optional[Dict]:
        """Get a single image by ID."""
        with self.session_scope() as session:
            image = session.query(EntityImage).filter(EntityImage.id == image_id).first()
            return self._image_to_dict(image) if image else None
    
    def create_entity_image(self, data: Dict[str, Any]) -> Dict:
        """Create a new entity image record."""
        with self.session_scope() as session:
            image = EntityImage(
                entity_type=data['entity_type'],
                entity_id=data['entity_id'],
                filename=data['filename'],
                stored_filename=data['stored_filename'],
                name=data.get('name'),
                description=data.get('description'),
                file_size_bytes=data.get('file_size_bytes'),
                mime_type=data.get('mime_type'),
                width=data.get('width'),
                height=data.get('height'),
                uploaded_by=data.get('uploaded_by'),
            )
            session.add(image)
            session.flush()
            return self._image_to_dict(image)
    
    def update_entity_image(self, image_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Update an entity image's metadata."""
        with self.session_scope() as session:
            image = session.query(EntityImage).filter(EntityImage.id == image_id).first()
            if not image:
                return None
            
            if 'name' in data:
                image.name = data['name']
            if 'description' in data:
                image.description = data['description']
            
            session.flush()
            return self._image_to_dict(image)
    
    def delete_entity_image(self, image_id: int) -> Optional[str]:
        """Delete an entity image. Returns the stored filename for file cleanup."""
        with self.session_scope() as session:
            image = session.query(EntityImage).filter(EntityImage.id == image_id).first()
            if not image:
                return None
            
            stored_filename = image.stored_filename
            session.delete(image)
            return stored_filename
    
    def _image_to_dict(self, image: EntityImage) -> Dict:
        """Convert EntityImage to dictionary."""
        return {
            'id': image.id,
            'entity_type': image.entity_type,
            'entity_id': image.entity_id,
            'filename': image.filename,
            'stored_filename': image.stored_filename,
            'name': image.name,
            'description': image.description,
            'file_size_bytes': image.file_size_bytes,
            'mime_type': image.mime_type,
            'width': image.width,
            'height': image.height,
            'uploaded_by': image.uploaded_by,
            'created_at': image.created_at.isoformat() if image.created_at else None,
        }
    
    # ==================== Search ====================
    
    def advanced_search(
        self,
        query: str = None,
        include_terms: List[str] = None,
        exclude_terms: List[str] = None,
        entity_types: List[str] = None,
        boolean_mode: str = 'AND',  # 'AND' or 'OR'
        # Field-specific filters
        status: str = None,
        owner: str = None,
        material: str = None,
        substrate: str = None,
        lab_id: int = None,
        project_id: int = None,
        # Date range filters
        created_after: str = None,
        created_before: str = None,
        # Pagination
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Advanced search across all entity types with complex filtering.
        
        Args:
            query: Main search query
            include_terms: List of terms that MUST be present
            exclude_terms: List of terms that MUST NOT be present
            entity_types: List of entity types to search (samples, scans, queues, equipment, precursors, procedures)
            boolean_mode: 'AND' (all terms must match) or 'OR' (any term can match)
            status: Filter by status
            owner: Filter by owner/operator/created_by
            material: Filter by material (samples)
            substrate: Filter by substrate (samples)
            lab_id: Filter by lab
            project_id: Filter by project
            created_after: Filter items created after this date (YYYY-MM-DD)
            created_before: Filter items created before this date (YYYY-MM-DD)
            page: Page number
            per_page: Results per page
            
        Returns:
            Dict with results by entity type, totals, and metadata
        """
        from datetime import datetime
        
        # Default to all entity types
        if not entity_types:
            entity_types = ['samples', 'scans', 'queues', 'equipment', 'precursors', 'procedures']
        
        results = {
            'samples': [],
            'scans': [],
            'queues': [],
            'equipment': [],
            'precursors': [],
            'procedures': [],
            'totals': {},
            'grand_total': 0,
            'page': page,
            'per_page': per_page,
        }
        
        # Parse dates
        date_after = None
        date_before = None
        if created_after:
            try:
                date_after = datetime.strptime(created_after, '%Y-%m-%d')
            except ValueError:
                pass
        if created_before:
            try:
                date_before = datetime.strptime(created_before, '%Y-%m-%d')
            except ValueError:
                pass
        
        with self.session_scope() as session:
            # Search Samples
            if 'samples' in entity_types:
                sample_query = session.query(Sample)
                sample_query = self._apply_text_filters(
                    sample_query, Sample, query, include_terms, exclude_terms, boolean_mode,
                    text_fields=['sample_id', 'name', 'material', 'description', 'substrate', 'created_by']
                )
                if status:
                    sample_query = sample_query.filter(Sample.status == status)
                if owner:
                    sample_query = sample_query.filter(Sample.created_by.ilike(f'%{owner}%'))
                if material:
                    sample_query = sample_query.filter(Sample.material.ilike(f'%{material}%'))
                if substrate:
                    sample_query = sample_query.filter(Sample.substrate.ilike(f'%{substrate}%'))
                if lab_id:
                    sample_query = sample_query.filter(Sample.lab_id == lab_id)
                if project_id:
                    sample_query = sample_query.filter(Sample.project_id == project_id)
                if date_after:
                    sample_query = sample_query.filter(Sample.created_at >= date_after)
                if date_before:
                    sample_query = sample_query.filter(Sample.created_at <= date_before)
                
                results['totals']['samples'] = sample_query.count()
                samples = sample_query.order_by(desc(Sample.created_at)).offset((page-1)*per_page).limit(per_page).all()
                results['samples'] = [self._sample_to_dict(s) for s in samples]
            
            # Search Scans
            if 'scans' in entity_types:
                scan_query = session.query(Scan)
                scan_query = self._apply_text_filters(
                    scan_query, Scan, query, include_terms, exclude_terms, boolean_mode,
                    text_fields=['scan_id', 'scan_name', 'project_name', 'created_by', 'notes']
                )
                if status:
                    scan_query = scan_query.filter(Scan.status == status)
                if owner:
                    scan_query = scan_query.filter(Scan.created_by.ilike(f'%{owner}%'))
                if project_id:
                    scan_query = scan_query.filter(Scan.project_id == project_id)
                elif lab_id:
                    scan_query = scan_query.join(Project, Scan.project_id == Project.id).filter(Project.lab_id == lab_id)
                if date_after:
                    scan_query = scan_query.filter(Scan.created_at >= date_after)
                if date_before:
                    scan_query = scan_query.filter(Scan.created_at <= date_before)
                
                results['totals']['scans'] = scan_query.count()
                scans = scan_query.order_by(desc(Scan.created_at)).offset((page-1)*per_page).limit(per_page).all()
                results['scans'] = [self._scan_to_dict(s) for s in scans]
            
            # Search Queues
            if 'queues' in entity_types:
                queue_query = session.query(Queue)
                queue_query = self._apply_text_filters(
                    queue_query, Queue, query, include_terms, exclude_terms, boolean_mode,
                    text_fields=['queue_id', 'name', 'created_by', 'notes']
                )
                if status:
                    queue_query = queue_query.filter(Queue.status == status)
                if owner:
                    queue_query = queue_query.filter(Queue.created_by.ilike(f'%{owner}%'))
                if project_id:
                    queue_query = queue_query.filter(Queue.project_id == project_id)
                elif lab_id:
                    queue_query = queue_query.join(Project, Queue.project_id == Project.id).filter(Project.lab_id == lab_id)
                if date_after:
                    queue_query = queue_query.filter(Queue.created_at >= date_after)
                if date_before:
                    queue_query = queue_query.filter(Queue.created_at <= date_before)
                
                results['totals']['queues'] = queue_query.count()
                queues = queue_query.order_by(desc(Queue.created_at)).offset((page-1)*per_page).limit(per_page).all()
                results['queues'] = [self._queue_to_dict(q) for q in queues]
            
            # Search Equipment
            if 'equipment' in entity_types:
                equip_query = session.query(Equipment)
                equip_query = self._apply_text_filters(
                    equip_query, Equipment, query, include_terms, exclude_terms, boolean_mode,
                    text_fields=['name', 'manufacturer', 'model', 'serial_number', 'location']
                )
                if status:
                    equip_query = equip_query.filter(Equipment.status == status)
                if lab_id:
                    equip_query = equip_query.filter(Equipment.lab_id == lab_id)
                if date_after:
                    equip_query = equip_query.filter(Equipment.created_at >= date_after)
                if date_before:
                    equip_query = equip_query.filter(Equipment.created_at <= date_before)
                
                results['totals']['equipment'] = equip_query.count()
                equipment = equip_query.order_by(Equipment.name).offset((page-1)*per_page).limit(per_page).all()
                results['equipment'] = [self._equipment_to_dict(e) for e in equipment]
            
            # Search Precursors
            if 'precursors' in entity_types:
                prec_query = session.query(Precursor)
                prec_query = self._apply_text_filters(
                    prec_query, Precursor, query, include_terms, exclude_terms, boolean_mode,
                    text_fields=['name', 'chemical_formula', 'supplier', 'cas_number', 'lot_number']
                )
                if status:
                    prec_query = prec_query.filter(Precursor.status == status)
                if project_id:
                    prec_query = prec_query.filter(Precursor.project_id == project_id)
                elif lab_id:
                    prec_query = prec_query.join(Project, Precursor.project_id == Project.id).filter(Project.lab_id == lab_id)
                if date_after:
                    prec_query = prec_query.filter(Precursor.created_at >= date_after)
                if date_before:
                    prec_query = prec_query.filter(Precursor.created_at <= date_before)
                
                results['totals']['precursors'] = prec_query.count()
                precursors = prec_query.order_by(Precursor.name).offset((page-1)*per_page).limit(per_page).all()
                results['precursors'] = [self._precursor_to_dict(p) for p in precursors]
            
            # Search Procedures
            if 'procedures' in entity_types:
                proc_query = session.query(Procedure).filter(Procedure.is_active == True)
                proc_query = self._apply_text_filters(
                    proc_query, Procedure, query, include_terms, exclude_terms, boolean_mode,
                    text_fields=['name', 'description', 'procedure_type', 'created_by']
                )
                if owner:
                    proc_query = proc_query.filter(Procedure.created_by.ilike(f'%{owner}%'))
                if project_id:
                    proc_query = proc_query.filter(Procedure.project_id == project_id)
                elif lab_id:
                    proc_query = proc_query.join(Project, Procedure.project_id == Project.id).filter(Project.lab_id == lab_id)
                if date_after:
                    proc_query = proc_query.filter(Procedure.created_at >= date_after)
                if date_before:
                    proc_query = proc_query.filter(Procedure.created_at <= date_before)
                
                results['totals']['procedures'] = proc_query.count()
                procedures = proc_query.order_by(Procedure.name).offset((page-1)*per_page).limit(per_page).all()
                results['procedures'] = [self._procedure_to_dict(p) for p in procedures]
        
        # Calculate grand total
        results['grand_total'] = sum(results['totals'].values())
        
        return results
    
    def _apply_text_filters(
        self,
        query,
        model,
        search_query: str,
        include_terms: List[str],
        exclude_terms: List[str],
        boolean_mode: str,
        text_fields: List[str]
    ):
        """Apply text-based filters to a query."""
        filters = []
        
        # Build search terms list
        search_terms = []
        if search_query:
            search_terms.append(search_query)
        if include_terms:
            search_terms.extend(include_terms)
        
        # Apply include filters
        if search_terms:
            for term in search_terms:
                term_filter = []
                for field_name in text_fields:
                    if hasattr(model, field_name):
                        field = getattr(model, field_name)
                        term_filter.append(field.ilike(f'%{term}%'))
                if term_filter:
                    filters.append(or_(*term_filter))
        
        # Combine filters based on boolean mode
        if filters:
            if boolean_mode == 'OR':
                query = query.filter(or_(*filters))
            else:  # AND
                query = query.filter(and_(*filters))
        
        # Apply exclude filters
        if exclude_terms:
            for term in exclude_terms:
                for field_name in text_fields:
                    if hasattr(model, field_name):
                        field = getattr(model, field_name)
                        query = query.filter(~field.ilike(f'%{term}%') | (field == None))
        
        return query
    
    def get_search_field_values(self) -> Dict[str, List[str]]:
        """Get unique values for searchable fields to populate filter dropdowns."""
        with self.session_scope() as session:
            result = {
                'statuses': [],
                'materials': [],
                'substrates': [],
                'owners': [],
                'equipment_types': [],
                'procedure_types': [],
            }
            
            # Get unique statuses from samples
            statuses = session.query(Sample.status).distinct().all()
            result['statuses'] = sorted([s[0] for s in statuses if s[0]])
            
            # Get unique materials
            materials = session.query(Sample.material).distinct().all()
            result['materials'] = sorted([m[0] for m in materials if m[0]])
            
            # Get unique substrates
            substrates = session.query(Sample.substrate).distinct().all()
            result['substrates'] = sorted([s[0] for s in substrates if s[0]])
            
            # Get unique owners from multiple tables
            owners = set()
            sample_creators = session.query(Sample.created_by).distinct().all()
            owners.update([o[0] for o in sample_creators if o[0]])
            scan_creators = session.query(Scan.created_by).distinct().all()
            owners.update([o[0] for o in scan_creators if o[0]])
            queue_creators = session.query(Queue.created_by).distinct().all()
            owners.update([o[0] for o in queue_creators if o[0]])
            proc_creators = session.query(Procedure.created_by).distinct().all()
            owners.update([o[0] for o in proc_creators if o[0]])
            result['owners'] = sorted(list(owners))
            
            # Get unique equipment types
            equip_types = session.query(Equipment.equipment_type).distinct().all()
            result['equipment_types'] = sorted([e[0] for e in equip_types if e[0]])
            
            # Get unique procedure types
            proc_types = session.query(Procedure.procedure_type).distinct().all()
            result['procedure_types'] = sorted([p[0] for p in proc_types if p[0]])
            
            return result
    
    def global_search(self, query: str, limit: int = 20) -> Dict[str, List[Dict]]:
        """
        Comprehensive search across all entity types and all text fields.
        Returns results with match context showing which fields matched.
        """
        results = {
            'labs': [],
            'projects': [],
            'samples': [],
            'scans': [],
            'queues': [],
            'instruments': [],
            'equipment': [],
            'precursors': [],
            'procedures': [],
        }
        
        if not query or len(query) < 2:
            return results
        
        # Split query into terms for multi-word search
        terms = [t.strip() for t in query.lower().split() if t.strip()]
        
        def get_match_context(fields_dict: Dict[str, str], max_len: int = 60) -> List[str]:
            """
            Find which fields contain any search terms and return formatted context.
            Returns list of strings like "field: ...context with match..."
            """
            matches = []
            for field_name, value in fields_dict.items():
                if not value:
                    continue
                value_lower = str(value).lower()
                for term in terms:
                    if term in value_lower:
                        # Found a match - format the context
                        idx = value_lower.find(term)
                        start = max(0, idx - 20)
                        end = min(len(value), idx + len(term) + 20)
                        snippet = value[start:end]
                        
                        # Add ellipses if truncated
                        if start > 0:
                            snippet = '...' + snippet
                        if end < len(value):
                            snippet = snippet + '...'
                        
                        # Truncate if still too long
                        if len(snippet) > max_len:
                            snippet = snippet[:max_len-3] + '...'
                        
                        matches.append(f"{field_name}: {snippet}")
                        break  # Only one match per field
            return matches
        
        def matches_all_terms(fields_dict: Dict[str, str]) -> bool:
            """Check if all search terms appear somewhere in any field values."""
            combined = ' '.join((str(v) or '').lower() for v in fields_dict.values())
            return all(term in combined for term in terms)
        
        with self.session_scope() as session:
            # Search Labs
            labs = session.query(Lab).filter(Lab.is_active == True).all()
            for lab in labs:
                fields = {
                    'name': lab.name, 'code': lab.code, 'university': lab.university,
                    'department': lab.department, 'description': lab.description
                }
                if matches_all_terms(fields):
                    lab_dict = self._lab_to_dict(lab)
                    lab_dict['match_context'] = get_match_context(fields)
                    results['labs'].append(lab_dict)
                    if len(results['labs']) >= limit:
                        break
            
            # Search Projects (include lab name in search)
            projects = session.query(Project).options(joinedload(Project.lab)).all()
            for proj in projects:
                lab_name = proj.lab.name if proj.lab else ''
                fields = {
                    'name': proj.name, 'code': proj.code, 'description': proj.description,
                    'lab': lab_name
                }
                if matches_all_terms(fields):
                    proj_dict = self._project_to_dict(proj)
                    proj_dict['lab_name'] = lab_name
                    proj_dict['match_context'] = get_match_context(fields)
                    results['projects'].append(proj_dict)
                    if len(results['projects']) >= limit:
                        break
            
            # Search Samples (include lab/project names in search)
            samples = session.query(Sample).options(
                joinedload(Sample.lab),
                joinedload(Sample.project)
            ).all()
            for s in samples:
                lab_name = s.lab.name if s.lab else ''
                proj_name = s.project.name if s.project else ''
                fields = {
                    'sample_id': s.sample_id, 'name': s.name, 'material': s.material,
                    'substrate': s.substrate, 'description': s.description,
                    'storage_location': s.storage_location, 'sample_type': s.sample_type,
                    'created_by': s.created_by, 'lab': lab_name, 'project': proj_name
                }
                if matches_all_terms(fields):
                    sample_dict = self._sample_to_dict(s)
                    sample_dict['lab_name'] = lab_name
                    sample_dict['project_name_display'] = proj_name
                    sample_dict['match_context'] = get_match_context(fields)
                    results['samples'].append(sample_dict)
                    if len(results['samples']) >= limit:
                        break
            
            # Search Scans (include lab/project names in search)
            scans = session.query(Scan).options(
                joinedload(Scan.project).joinedload(Project.lab)
            ).all()
            for sc in scans:
                proj = sc.project
                lab_name = proj.lab.name if proj and proj.lab else ''
                proj_name = proj.name if proj else ''
                fields = {
                    'scan_id': sc.scan_id, 'scan_name': sc.scan_name,
                    'project_name': sc.project_name, 'scan_type': sc.scan_type,
                    'job_type': sc.job_type, 'notes': sc.notes, 'created_by': sc.created_by,
                    'lab': lab_name, 'project': proj_name
                }
                if matches_all_terms(fields):
                    scan_dict = self._scan_to_dict(sc)
                    scan_dict['lab_name'] = lab_name
                    scan_dict['match_context'] = get_match_context(fields)
                    results['scans'].append(scan_dict)
                    if len(results['scans']) >= limit:
                        break
            
            # Search Queues (include lab/project names in search)
            queues = session.query(Queue).options(
                joinedload(Queue.project).joinedload(Project.lab)
            ).all()
            for q in queues:
                proj = q.project
                lab_name = proj.lab.name if proj and proj.lab else ''
                proj_name = proj.name if proj else ''
                fields = {
                    'queue_id': q.queue_id, 'name': q.name, 'notes': q.notes,
                    'created_by': q.created_by, 'lab': lab_name, 'project': proj_name
                }
                if matches_all_terms(fields):
                    queue_dict = self._queue_to_dict(q)
                    queue_dict['lab_name'] = lab_name
                    queue_dict['match_context'] = get_match_context(fields)
                    results['queues'].append(queue_dict)
                    if len(results['queues']) >= limit:
                        break
            
            # Search Instruments (PyBirch devices)
            instrument_list = session.query(Instrument).filter(Instrument.status != 'retired').all()
            for i in instrument_list:
                fields = {
                    'name': i.name, 'manufacturer': i.manufacturer, 'model': i.model,
                    'serial_number': i.serial_number, 'location': i.location,
                    'instrument_type': i.instrument_type, 'pybirch_class': i.pybirch_class,
                    'adapter': i.adapter
                }
                if matches_all_terms(fields):
                    inst_dict = self._instrument_to_dict(i)
                    inst_dict['match_context'] = get_match_context(fields)
                    results['instruments'].append(inst_dict)
                    if len(results['instruments']) >= limit:
                        break
            
            # Search Equipment (large lab equipment)
            equipment_list = session.query(Equipment).filter(Equipment.status != 'retired').all()
            for e in equipment_list:
                fields = {
                    'name': e.name, 'manufacturer': e.manufacturer, 'model': e.model,
                    'serial_number': e.serial_number, 'location': e.location,
                    'equipment_type': e.equipment_type, 'description': e.description or '',
                    'room': e.room or ''
                }
                if matches_all_terms(fields):
                    eq_dict = self._equipment_to_dict(e)
                    eq_dict['match_context'] = get_match_context(fields)
                    results['equipment'].append(eq_dict)
                    if len(results['equipment']) >= limit:
                        break
            
            # Search Precursors
            precursors = session.query(Precursor).filter(Precursor.status != 'expired').all()
            for p in precursors:
                fields = {
                    'name': p.name, 'chemical_formula': p.chemical_formula,
                    'cas_number': p.cas_number, 'supplier': p.supplier,
                    'lot_number': p.lot_number, 'state': p.state,
                    'storage_conditions': p.storage_conditions, 'safety_info': p.safety_info
                }
                if matches_all_terms(fields):
                    prec_dict = self._precursor_to_dict(p)
                    prec_dict['match_context'] = get_match_context(fields)
                    results['precursors'].append(prec_dict)
                    if len(results['precursors']) >= limit:
                        break
            
            # Search Procedures
            procedures = session.query(Procedure).filter(Procedure.is_active == True).all()
            for proc in procedures:
                fields = {
                    'name': proc.name, 'procedure_type': proc.procedure_type,
                    'description': proc.description, 'created_by': proc.created_by
                }
                if matches_all_terms(fields):
                    proc_dict = self._procedure_to_dict(proc)
                    proc_dict['match_context'] = get_match_context(fields)
                    results['procedures'].append(proc_dict)
                    if len(results['procedures']) >= limit:
                        break
        
        return results


# Singleton instance for easy import
_db_service: Optional[DatabaseService] = None


def get_db_service(db_path: Optional[str] = None) -> DatabaseService:
    """Get the singleton database service instance."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService(db_path)
    return _db_service

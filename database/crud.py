"""
PyBirch Database CRUD Operations
================================
High-level CRUD (Create, Read, Update, Delete) operations for PyBirch entities.
Provides convenient abstractions over raw SQLAlchemy operations.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Type, TypeVar, Generic
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session, joinedload
import uuid

from database.models import (
    Base, Template, Equipment, Precursor, PrecursorInventory,
    Procedure, ProcedureEquipment, ProcedurePrecursor,
    Sample, SamplePrecursor, FabricationRun,
    ScanTemplate, QueueTemplate, QueueTemplateItem,
    Queue, Scan, MeasurementObject, MeasurementDataPoint, MeasurementDataArray,
    AnalysisMethod, Analysis, AnalysisInput, AnalysisResult,
    Tag, EntityTag, Attachment, AuditLog
)

T = TypeVar('T', bound=Base)


class BaseCRUD(Generic[T]):
    """
    Base CRUD class providing common operations for all models.
    """
    
    def __init__(self, model: Type[T]):
        self.model = model
    
    def get(self, session: Session, id: int) -> Optional[T]:
        """Get a single record by ID."""
        return session.get(self.model, id)
    
    def get_all(
        self, 
        session: Session, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[T]:
        """Get multiple records with optional filtering and pagination."""
        query = select(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        
        query = query.offset(skip).limit(limit)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def create(self, session: Session, **kwargs) -> T:
        """Create a new record."""
        obj = self.model(**kwargs)
        session.add(obj)
        session.flush()  # Get the ID
        return obj
    
    def update(self, session: Session, id: int, **kwargs) -> Optional[T]:
        """Update an existing record."""
        obj = self.get(session, id)
        if obj:
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            session.flush()
        return obj
    
    def delete(self, session: Session, id: int) -> bool:
        """Delete a record by ID."""
        obj = self.get(session, id)
        if obj:
            session.delete(obj)
            return True
        return False
    
    def count(self, session: Session, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering."""
        query = select(func.count()).select_from(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        
        result = session.execute(query)
        return result.scalar() or 0


class TemplateCRUD(BaseCRUD[Template]):
    """CRUD operations for Templates."""
    
    def __init__(self):
        super().__init__(Template)
    
    def get_by_name_and_type(
        self, 
        session: Session, 
        name: str, 
        entity_type: str
    ) -> Optional[Template]:
        """Get a template by name and entity type."""
        query = select(Template).where(
            and_(Template.name == name, Template.entity_type == entity_type)
        )
        result = session.execute(query)
        return result.scalar_one_or_none()
    
    def get_by_entity_type(
        self, 
        session: Session, 
        entity_type: str,
        active_only: bool = True
    ) -> List[Template]:
        """Get all templates for a specific entity type."""
        query = select(Template).where(Template.entity_type == entity_type)
        if active_only:
            query = query.where(Template.is_active == True)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def create_template(
        self,
        session: Session,
        name: str,
        entity_type: str,
        template_data: dict,
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Template:
        """Create a new template."""
        return self.create(
            session,
            name=name,
            entity_type=entity_type,
            template_data=template_data,
            description=description,
            created_by=created_by
        )


class EquipmentCRUD(BaseCRUD[Equipment]):
    """CRUD operations for Equipment."""
    
    def __init__(self):
        super().__init__(Equipment)
    
    def get_by_name(self, session: Session, name: str) -> Optional[Equipment]:
        """Get equipment by name."""
        query = select(Equipment).where(Equipment.name == name)
        result = session.execute(query)
        return result.scalar_one_or_none()
    
    def get_by_type(
        self, 
        session: Session, 
        equipment_type: str,
        status: Optional[str] = None
    ) -> List[Equipment]:
        """Get equipment by type with optional status filter."""
        query = select(Equipment).where(Equipment.equipment_type == equipment_type)
        if status:
            query = query.where(Equipment.status == status)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def get_available(self, session: Session) -> List[Equipment]:
        """Get all available equipment."""
        return self.get_all(session, filters={"status": "available"})
    
    def update_status(
        self, 
        session: Session, 
        id: int, 
        status: str
    ) -> Optional[Equipment]:
        """Update equipment status."""
        return self.update(session, id, status=status)


class PrecursorCRUD(BaseCRUD[Precursor]):
    """CRUD operations for Precursors."""
    
    def __init__(self):
        super().__init__(Precursor)
    
    def get_by_name(self, session: Session, name: str) -> Optional[Precursor]:
        """Get precursor by name."""
        query = select(Precursor).where(Precursor.name == name)
        result = session.execute(query)
        return result.scalar_one_or_none()
    
    def get_by_formula(self, session: Session, formula: str) -> List[Precursor]:
        """Get precursors by chemical formula."""
        query = select(Precursor).where(Precursor.chemical_formula == formula)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def search(
        self, 
        session: Session, 
        search_term: str,
        limit: int = 50
    ) -> List[Precursor]:
        """Search precursors by name, formula, or supplier."""
        search_pattern = f"%{search_term}%"
        query = select(Precursor).where(
            or_(
                Precursor.name.ilike(search_pattern),
                Precursor.chemical_formula.ilike(search_pattern),
                Precursor.supplier.ilike(search_pattern)
            )
        ).limit(limit)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def add_inventory(
        self,
        session: Session,
        precursor_id: int,
        quantity: float,
        quantity_unit: str,
        location: Optional[str] = None,
        notes: Optional[str] = None
    ) -> PrecursorInventory:
        """Add inventory record for a precursor."""
        inventory = PrecursorInventory(
            precursor_id=precursor_id,
            quantity=quantity,
            quantity_unit=quantity_unit,
            location=location,
            notes=notes
        )
        session.add(inventory)
        session.flush()
        return inventory


class ProcedureCRUD(BaseCRUD[Procedure]):
    """CRUD operations for Procedures."""
    
    def __init__(self):
        super().__init__(Procedure)
    
    def get_by_name(self, session: Session, name: str) -> Optional[Procedure]:
        """Get procedure by name."""
        query = select(Procedure).where(Procedure.name == name)
        result = session.execute(query)
        return result.scalar_one_or_none()
    
    def get_by_type(
        self, 
        session: Session, 
        procedure_type: str,
        active_only: bool = True
    ) -> List[Procedure]:
        """Get procedures by type."""
        query = select(Procedure).where(Procedure.procedure_type == procedure_type)
        if active_only:
            query = query.where(Procedure.is_active == True)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def add_equipment(
        self,
        session: Session,
        procedure_id: int,
        equipment_id: int,
        role: Optional[str] = None,
        is_required: bool = True
    ) -> ProcedureEquipment:
        """Add equipment to a procedure."""
        assoc = ProcedureEquipment(
            procedure_id=procedure_id,
            equipment_id=equipment_id,
            role=role,
            is_required=is_required
        )
        session.add(assoc)
        session.flush()
        return assoc
    
    def add_precursor(
        self,
        session: Session,
        procedure_id: int,
        precursor_id: int,
        quantity: Optional[float] = None,
        quantity_unit: Optional[str] = None,
        purpose: Optional[str] = None
    ) -> ProcedurePrecursor:
        """Add precursor to a procedure."""
        assoc = ProcedurePrecursor(
            procedure_id=procedure_id,
            precursor_id=precursor_id,
            quantity=quantity,
            quantity_unit=quantity_unit,
            purpose=purpose
        )
        session.add(assoc)
        session.flush()
        return assoc


class SampleCRUD(BaseCRUD[Sample]):
    """CRUD operations for Samples."""
    
    def __init__(self):
        super().__init__(Sample)
    
    def get_by_sample_id(self, session: Session, sample_id: str) -> Optional[Sample]:
        """Get sample by user-friendly sample_id."""
        query = select(Sample).where(Sample.sample_id == sample_id)
        result = session.execute(query)
        return result.scalar_one_or_none()
    
    def get_by_material(self, session: Session, material: str) -> List[Sample]:
        """Get samples by material type."""
        query = select(Sample).where(Sample.material == material)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def get_active(self, session: Session, limit: int = 100) -> List[Sample]:
        """Get all active samples."""
        return self.get_all(session, limit=limit, filters={"status": "active"})
    
    def search(
        self, 
        session: Session, 
        search_term: str,
        limit: int = 50
    ) -> List[Sample]:
        """Search samples by ID, name, or material."""
        search_pattern = f"%{search_term}%"
        query = select(Sample).where(
            or_(
                Sample.sample_id.ilike(search_pattern),
                Sample.name.ilike(search_pattern),
                Sample.material.ilike(search_pattern)
            )
        ).limit(limit)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def create_sample(
        self,
        session: Session,
        sample_id: Optional[str] = None,
        material: Optional[str] = None,
        name: Optional[str] = None,
        sample_type: Optional[str] = None,
        additional_tags: Optional[List[str]] = None,
        template_id: Optional[int] = None,
        created_by: Optional[str] = None,
        **kwargs
    ) -> Sample:
        """Create a new sample with optional template."""
        # Generate sample_id if not provided
        if sample_id is None:
            sample_id = f"S{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Apply template defaults if provided
        if template_id:
            template = session.get(Template, template_id)
            if template and template.entity_type == 'sample':
                template_data = template.template_data or {}
                # Template values are defaults, explicit params override
                material = material or template_data.get('material')
                sample_type = sample_type or template_data.get('sample_type')
                additional_tags = additional_tags or template_data.get('additional_tags')
        
        return self.create(
            session,
            sample_id=sample_id,
            material=material,
            name=name,
            sample_type=sample_type,
            additional_tags=additional_tags,
            template_id=template_id,
            created_by=created_by,
            **kwargs
        )
    
    def add_precursor(
        self,
        session: Session,
        sample_id: int,
        precursor_id: int,
        quantity_used: Optional[float] = None,
        quantity_unit: Optional[str] = None,
        role: Optional[str] = None,
        composition_percent: Optional[float] = None
    ) -> SamplePrecursor:
        """Add precursor to a sample."""
        assoc = SamplePrecursor(
            sample_id=sample_id,
            precursor_id=precursor_id,
            quantity_used=quantity_used,
            quantity_unit=quantity_unit,
            role=role,
            composition_percent=composition_percent
        )
        session.add(assoc)
        session.flush()
        return assoc
    
    def get_with_relations(self, session: Session, id: int) -> Optional[Sample]:
        """Get sample with all related data loaded."""
        query = select(Sample).where(Sample.id == id).options(
            joinedload(Sample.precursor_associations),
            joinedload(Sample.fabrication_runs),
            joinedload(Sample.scans)
        )
        result = session.execute(query)
        return result.unique().scalar_one_or_none()
    
    def from_pybirch(
        self,
        session: Session,
        pybirch_sample,
        created_by: Optional[str] = None
    ) -> Sample:
        """Create database sample from PyBirch Sample object."""
        # Check if sample already exists
        existing = self.get_by_sample_id(session, pybirch_sample.ID)
        if existing:
            return existing
        
        return self.create(
            session,
            sample_id=pybirch_sample.ID,
            material=pybirch_sample.material,
            additional_tags=pybirch_sample.additional_tags,
            created_by=created_by
        )


class ScanCRUD(BaseCRUD[Scan]):
    """CRUD operations for Scans."""
    
    def __init__(self):
        super().__init__(Scan)
    
    def get_by_scan_id(self, session: Session, scan_id: str) -> Optional[Scan]:
        """Get scan by user-friendly scan_id."""
        query = select(Scan).where(Scan.scan_id == scan_id)
        result = session.execute(query)
        return result.scalar_one_or_none()
    
    def get_by_status(self, session: Session, status: str) -> List[Scan]:
        """Get scans by status."""
        return self.get_all(session, filters={"status": status})
    
    def get_by_sample(self, session: Session, sample_id: int) -> List[Scan]:
        """Get all scans for a sample."""
        query = select(Scan).where(Scan.sample_id == sample_id).order_by(Scan.created_at.desc())
        result = session.execute(query)
        return list(result.scalars().all())
    
    def get_by_queue(self, session: Session, queue_id: int) -> List[Scan]:
        """Get all scans in a queue."""
        query = select(Scan).where(Scan.queue_id == queue_id).order_by(Scan.position_in_queue)
        result = session.execute(query)
        return list(result.scalars().all())
    
    def create_scan(
        self,
        session: Session,
        scan_id: Optional[str] = None,
        project_name: Optional[str] = None,
        scan_name: Optional[str] = None,
        scan_type: Optional[str] = None,
        job_type: Optional[str] = None,
        owner: Optional[str] = None,
        sample_id: Optional[int] = None,
        queue_id: Optional[int] = None,
        scan_template_id: Optional[int] = None,
        **kwargs
    ) -> Scan:
        """Create a new scan record."""
        if scan_id is None:
            scan_id = f"SCAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        return self.create(
            session,
            scan_id=scan_id,
            project_name=project_name,
            scan_name=scan_name,
            scan_type=scan_type,
            job_type=job_type,
            owner=owner,
            sample_id=sample_id,
            queue_id=queue_id,
            scan_template_id=scan_template_id,
            **kwargs
        )
    
    def from_pybirch(
        self,
        session: Session,
        pybirch_scan,
        sample_db_id: Optional[int] = None,
        queue_db_id: Optional[int] = None
    ) -> Scan:
        """Create database scan from PyBirch Scan object."""
        settings = pybirch_scan.scan_settings
        
        return self.create_scan(
            session,
            project_name=settings.project_name,
            scan_name=settings.scan_name,
            scan_type=settings.scan_type,
            job_type=settings.job_type,
            owner=pybirch_scan.owner,
            additional_tags=settings.additional_tags,
            status=settings.status,
            scan_tree_data=settings.scan_tree.serialize() if settings.scan_tree else None,
            wandb_link=settings.wandb_link,
            sample_id=sample_db_id,
            queue_id=queue_db_id
        )
    
    def update_status(
        self,
        session: Session,
        id: int,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> Optional[Scan]:
        """Update scan status with optional timestamps."""
        updates = {"status": status}
        if started_at:
            updates["started_at"] = started_at
        if completed_at:
            updates["completed_at"] = completed_at
            # Calculate duration if both timestamps available
            scan = self.get(session, id)
            if scan and scan.started_at:
                duration = (completed_at - scan.started_at).total_seconds()
                updates["duration_seconds"] = duration
        
        return self.update(session, id, **updates)
    
    def add_measurement_object(
        self,
        session: Session,
        scan_id: int,
        name: str,
        instrument_name: Optional[str] = None,
        data_type: str = "numeric",
        unit: Optional[str] = None,
        columns: Optional[List[str]] = None
    ) -> MeasurementObject:
        """Add a measurement object to a scan."""
        mobj = MeasurementObject(
            scan_id=scan_id,
            name=name,
            instrument_name=instrument_name,
            data_type=data_type,
            unit=unit,
            columns=columns
        )
        session.add(mobj)
        session.flush()
        return mobj
    
    def add_measurement_data(
        self,
        session: Session,
        measurement_object_id: int,
        values: dict,
        sequence_index: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ) -> MeasurementDataPoint:
        """Add a data point to a measurement object."""
        point = MeasurementDataPoint(
            measurement_object_id=measurement_object_id,
            values=values,
            sequence_index=sequence_index,
            timestamp=timestamp or datetime.utcnow()
        )
        session.add(point)
        return point
    
    def add_measurement_data_batch(
        self,
        session: Session,
        measurement_object_id: int,
        data_list: List[dict],
        start_index: int = 0
    ) -> int:
        """Add multiple data points efficiently. Returns count added."""
        points = []
        for i, values in enumerate(data_list):
            point = MeasurementDataPoint(
                measurement_object_id=measurement_object_id,
                values=values,
                sequence_index=start_index + i,
                timestamp=datetime.utcnow()
            )
            points.append(point)
        
        session.bulk_save_objects(points)
        return len(points)
    
    def get_with_data(self, session: Session, id: int) -> Optional[Scan]:
        """Get scan with measurement data loaded."""
        query = select(Scan).where(Scan.id == id).options(
            joinedload(Scan.measurement_objects).joinedload(MeasurementObject.data_points)
        )
        result = session.execute(query)
        return result.unique().scalar_one_or_none()


class QueueCRUD(BaseCRUD[Queue]):
    """CRUD operations for Queues."""
    
    def __init__(self):
        super().__init__(Queue)
    
    def get_by_queue_id(self, session: Session, queue_id: str) -> Optional[Queue]:
        """Get queue by user-friendly queue_id."""
        query = select(Queue).where(Queue.queue_id == queue_id)
        result = session.execute(query)
        return result.scalar_one_or_none()
    
    def get_by_status(self, session: Session, status: str) -> List[Queue]:
        """Get queues by status."""
        return self.get_all(session, filters={"status": status})
    
    def get_running(self, session: Session) -> List[Queue]:
        """Get all running queues."""
        return self.get_by_status(session, "running")
    
    def get_pending(self, session: Session) -> List[Queue]:
        """Get all pending queues."""
        return self.get_by_status(session, "pending")
    
    def create_queue(
        self,
        session: Session,
        queue_id: Optional[str] = None,
        name: Optional[str] = None,
        sample_id: Optional[int] = None,
        queue_template_id: Optional[int] = None,
        execution_mode: str = "SERIAL",
        operator: Optional[str] = None,
        **kwargs
    ) -> Queue:
        """Create a new queue record."""
        if queue_id is None:
            queue_id = f"Q_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        return self.create(
            session,
            queue_id=queue_id,
            name=name,
            sample_id=sample_id,
            queue_template_id=queue_template_id,
            execution_mode=execution_mode,
            operator=operator,
            **kwargs
        )
    
    def from_pybirch(
        self,
        session: Session,
        pybirch_queue,
        sample_db_id: Optional[int] = None
    ) -> Queue:
        """Create database queue from PyBirch Queue object."""
        return self.create_queue(
            session,
            queue_id=pybirch_queue.QID,
            execution_mode=pybirch_queue.execution_mode.name,
            total_scans=len(pybirch_queue),
            sample_id=sample_db_id,
            serialized_data=pybirch_queue.serialize()
        )
    
    def update_status(
        self,
        session: Session,
        id: int,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        completed_scans: Optional[int] = None
    ) -> Optional[Queue]:
        """Update queue status with optional timestamps."""
        updates = {"status": status}
        if started_at:
            updates["started_at"] = started_at
        if completed_at:
            updates["completed_at"] = completed_at
        if completed_scans is not None:
            updates["completed_scans"] = completed_scans
        
        return self.update(session, id, **updates)
    
    def get_with_scans(self, session: Session, id: int) -> Optional[Queue]:
        """Get queue with all scans loaded."""
        query = select(Queue).where(Queue.id == id).options(
            joinedload(Queue.scans)
        )
        result = session.execute(query)
        return result.unique().scalar_one_or_none()


class AnalysisCRUD(BaseCRUD[Analysis]):
    """CRUD operations for Analysis."""
    
    def __init__(self):
        super().__init__(Analysis)
    
    def get_by_analysis_id(self, session: Session, analysis_id: str) -> Optional[Analysis]:
        """Get analysis by user-friendly analysis_id."""
        query = select(Analysis).where(Analysis.analysis_id == analysis_id)
        result = session.execute(query)
        return result.scalar_one_or_none()
    
    def create_analysis(
        self,
        session: Session,
        analysis_id: Optional[str] = None,
        name: Optional[str] = None,
        analysis_method_id: Optional[int] = None,
        parameters: Optional[dict] = None,
        operator: Optional[str] = None
    ) -> Analysis:
        """Create a new analysis record."""
        if analysis_id is None:
            analysis_id = f"A_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        return self.create(
            session,
            analysis_id=analysis_id,
            name=name,
            analysis_method_id=analysis_method_id,
            parameters=parameters,
            operator=operator
        )
    
    def add_input(
        self,
        session: Session,
        analysis_id: int,
        measurement_object_id: Optional[int] = None,
        scan_id: Optional[int] = None,
        input_role: Optional[str] = None,
        data_range: Optional[dict] = None
    ) -> AnalysisInput:
        """Add input data to an analysis."""
        input_obj = AnalysisInput(
            analysis_id=analysis_id,
            measurement_object_id=measurement_object_id,
            scan_id=scan_id,
            input_role=input_role,
            data_range=data_range
        )
        session.add(input_obj)
        session.flush()
        return input_obj
    
    def add_result(
        self,
        session: Session,
        analysis_id: int,
        result_name: str,
        result_type: str = "scalar",
        value: Optional[float] = None,
        value_unit: Optional[str] = None,
        uncertainty: Optional[float] = None,
        data_blob: Optional[bytes] = None,
        file_path: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> AnalysisResult:
        """Add a result to an analysis."""
        result = AnalysisResult(
            analysis_id=analysis_id,
            result_name=result_name,
            result_type=result_type,
            value=value,
            value_unit=value_unit,
            uncertainty=uncertainty,
            data_blob=data_blob,
            file_path=file_path,
            metadata=metadata
        )
        session.add(result)
        session.flush()
        return result
    
    def get_with_results(self, session: Session, id: int) -> Optional[Analysis]:
        """Get analysis with all results loaded."""
        query = select(Analysis).where(Analysis.id == id).options(
            joinedload(Analysis.inputs),
            joinedload(Analysis.results)
        )
        result = session.execute(query)
        return result.unique().scalar_one_or_none()


# Convenience instances
template_crud = TemplateCRUD()
equipment_crud = EquipmentCRUD()
precursor_crud = PrecursorCRUD()
procedure_crud = ProcedureCRUD()
sample_crud = SampleCRUD()
scan_crud = ScanCRUD()
queue_crud = QueueCRUD()
analysis_crud = AnalysisCRUD()

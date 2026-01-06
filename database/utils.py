"""
PyBirch Database Utilities
==========================
Utility functions for common database operations.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

from database.session import get_session, get_db
from database.models import (
    Sample, Scan, Queue, MeasurementObject, MeasurementDataPoint,
    Template, Tag, EntityTag
)
from database.crud import (
    sample_crud, scan_crud, queue_crud, template_crud
)


def generate_sample_id(prefix: str = "S") -> str:
    """Generate a unique sample ID based on timestamp."""
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}"


def generate_scan_id(project_name: str = "", scan_name: str = "") -> str:
    """Generate a unique scan ID."""
    import uuid
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    short_uuid = uuid.uuid4().hex[:8]
    
    if project_name and scan_name:
        return f"{project_name}_{scan_name}_{timestamp}"
    return f"SCAN_{timestamp}_{short_uuid}"


def get_scan_data_as_dataframe(scan_id: int, measurement_name: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Retrieve scan measurement data as pandas DataFrames.
    
    Args:
        scan_id: Database ID of the scan
        measurement_name: Optional filter for specific measurement
        
    Returns:
        Dictionary mapping measurement names to DataFrames
    """
    result = {}
    
    with get_session() as session:
        scan = scan_crud.get_with_data(session, scan_id)
        if not scan:
            return result
        
        for mobj in scan.measurement_objects:
            if measurement_name and mobj.name != measurement_name:
                continue
            
            # Extract data points
            data = []
            for point in sorted(mobj.data_points, key=lambda p: p.sequence_index or 0):
                row = point.values.copy()
                row['_sequence_index'] = point.sequence_index
                row['_timestamp'] = point.timestamp
                data.append(row)
            
            if data:
                df = pd.DataFrame(data)
                result[mobj.name] = df
    
    return result


def get_sample_scan_history(sample_id: str) -> List[Dict[str, Any]]:
    """
    Get the scan history for a sample.
    
    Args:
        sample_id: User-friendly sample ID (e.g., 'S001')
        
    Returns:
        List of scan summary dictionaries
    """
    history = []
    
    with get_session() as session:
        sample = sample_crud.get_by_sample_id(session, sample_id)
        if not sample:
            return history
        
        scans = scan_crud.get_by_sample(session, sample.id)
        for scan in scans:
            history.append({
                'scan_id': scan.scan_id,
                'scan_name': scan.scan_name,
                'scan_type': scan.scan_type,
                'status': scan.status,
                'started_at': scan.started_at,
                'completed_at': scan.completed_at,
                'duration_seconds': scan.duration_seconds,
                'owner': scan.owner,
                'wandb_link': scan.wandb_link
            })
    
    return history


def create_sample_from_template(
    template_name: str,
    sample_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    created_by: Optional[str] = None
) -> Optional[Sample]:
    """
    Create a new sample using a template.
    
    Args:
        template_name: Name of the sample template
        sample_id: Optional custom sample ID
        overrides: Optional dict of values to override template defaults
        created_by: Operator name
        
    Returns:
        Created Sample object or None if template not found
    """
    with get_session() as session:
        template = template_crud.get_by_name_and_type(session, template_name, 'sample')
        if not template:
            print(f"Template '{template_name}' not found")
            return None
        
        # Start with template data
        data = template.template_data.copy()
        
        # Apply overrides
        if overrides:
            data.update(overrides)
        
        # Generate sample_id if not provided
        if sample_id is None:
            sample_id = generate_sample_id()
        
        sample = sample_crud.create_sample(
            session,
            sample_id=sample_id,
            template_id=template.id,
            created_by=created_by,
            **data
        )
        
        return sample


def add_tags_to_entity(
    entity_type: str,
    entity_id: int,
    tag_names: List[str]
) -> bool:
    """
    Add tags to an entity.
    
    Args:
        entity_type: Type of entity ('sample', 'scan', 'queue', etc.)
        entity_id: Database ID of the entity
        tag_names: List of tag names to add
        
    Returns:
        True if successful
    """
    with get_session() as session:
        for tag_name in tag_names:
            # Get or create tag
            tag = session.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                session.add(tag)
                session.flush()
            
            # Create association if not exists
            existing = session.query(EntityTag).filter(
                EntityTag.tag_id == tag.id,
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == entity_id
            ).first()
            
            if not existing:
                assoc = EntityTag(
                    tag_id=tag.id,
                    entity_type=entity_type,
                    entity_id=entity_id
                )
                session.add(assoc)
        
        return True


def get_entity_tags(entity_type: str, entity_id: int) -> List[str]:
    """
    Get all tags for an entity.
    
    Args:
        entity_type: Type of entity
        entity_id: Database ID of the entity
        
    Returns:
        List of tag names
    """
    with get_session() as session:
        tags = session.query(Tag).join(EntityTag).filter(
            EntityTag.entity_type == entity_type,
            EntityTag.entity_id == entity_id
        ).all()
        
        return [tag.name for tag in tags]


def search_samples(
    search_term: Optional[str] = None,
    material: Optional[str] = None,
    tags: Optional[List[str]] = None,
    status: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Search samples with various filters.
    
    Args:
        search_term: Text to search in ID, name, material
        material: Filter by material
        tags: Filter by tags (samples must have ALL tags)
        status: Filter by status
        limit: Maximum results
        
    Returns:
        List of sample summary dictionaries
    """
    results = []
    
    with get_session() as session:
        query = session.query(Sample)
        
        if search_term:
            pattern = f"%{search_term}%"
            query = query.filter(
                (Sample.sample_id.ilike(pattern)) |
                (Sample.name.ilike(pattern)) |
                (Sample.material.ilike(pattern))
            )
        
        if material:
            query = query.filter(Sample.material == material)
        
        if status:
            query = query.filter(Sample.status == status)
        
        if tags:
            # Subquery to find samples with all specified tags
            for tag_name in tags:
                tag_subq = session.query(EntityTag.entity_id).join(Tag).filter(
                    EntityTag.entity_type == 'sample',
                    Tag.name == tag_name
                ).subquery()
                query = query.filter(Sample.id.in_(tag_subq))
        
        samples = query.limit(limit).all()
        
        for sample in samples:
            results.append({
                'id': sample.id,
                'sample_id': sample.sample_id,
                'name': sample.name,
                'material': sample.material,
                'sample_type': sample.sample_type,
                'status': sample.status,
                'created_at': sample.created_at,
                'tags': get_entity_tags('sample', sample.id)
            })
    
    return results


def export_scan_to_csv(scan_id: int, output_dir: str) -> List[str]:
    """
    Export scan data to CSV files.
    
    Args:
        scan_id: Database ID of the scan
        output_dir: Directory to save CSV files
        
    Returns:
        List of created file paths
    """
    import os
    
    files = []
    data = get_scan_data_as_dataframe(scan_id)
    
    with get_session() as session:
        scan = session.get(Scan, scan_id)
        if not scan:
            return files
        
        base_name = scan.scan_id or f"scan_{scan_id}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    for name, df in data.items():
        # Clean up measurement name for filename
        clean_name = name.replace('/', '_').replace('\\', '_').replace(' ', '_')
        filename = f"{base_name}_{clean_name}.csv"
        filepath = os.path.join(output_dir, filename)
        
        df.to_csv(filepath, index=False)
        files.append(filepath)
    
    return files


def get_database_stats() -> Dict[str, Any]:
    """
    Get statistics about the database contents.
    
    Returns:
        Dictionary with table counts and other stats
    """
    db = get_db()
    stats = db.get_table_stats()
    
    # Add some computed stats
    with get_session() as session:
        # Recent activity
        recent_scans = session.query(Scan).filter(
            Scan.created_at >= datetime.now().replace(hour=0, minute=0, second=0)
        ).count()
        stats['scans_today'] = recent_scans
        
        # Status breakdown
        scan_statuses = session.query(Scan.status, func.count(Scan.id)).group_by(Scan.status).all()
        stats['scans_by_status'] = dict(scan_statuses)
    
    return stats


# Import func for statistics
from sqlalchemy import func

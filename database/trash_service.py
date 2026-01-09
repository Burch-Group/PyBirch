"""
PyBirch Trash Service
=====================
Handles soft-delete (trash) operations for all trashable entities.

Features:
- Trash items (soft-delete with 30-day retention)
- Restore items from trash
- Permanent deletion after retention period
- Cascade trash for labs, projects, queues, locations
- Query filtering for trashed items
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Type
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session
from contextlib import contextmanager

from database.models import (
    Lab, Project, Sample, Equipment, Precursor, Procedure,
    Instrument, Queue, Scan, Location, Template,
    ScanTemplate, QueueTemplate, FabricationRun, Issue,
    EquipmentIssue, DriverIssue, Analysis, EntityImage, Attachment,
    Driver, Computer
)
from database.session import get_session


# Retention period in days before permanent deletion
TRASH_RETENTION_DAYS = 30

# Entity type to model mapping
ENTITY_MODEL_MAP = {
    'lab': Lab,
    'project': Project,
    'sample': Sample,
    'equipment': Equipment,
    'precursor': Precursor,
    'procedure': Procedure,
    'instrument': Instrument,
    'driver': Driver,
    'computer': Computer,
    'queue': Queue,
    'scan': Scan,
    'location': Location,
    'template': Template,
    'scan_template': ScanTemplate,
    'queue_template': QueueTemplate,
    'fabrication_run': FabricationRun,
    'issue': Issue,
    'equipment_issue': EquipmentIssue,
    'driver_issue': DriverIssue,
    'analysis': Analysis,
    'image': EntityImage,
    'attachment': Attachment,
}


class TrashService:
    """Service for managing trashed items."""
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for a series of operations."""
        with get_session() as session:
            yield session
    
    # ==================== Core Operations ====================
    
    def trash_item(
        self,
        entity_type: str,
        entity_id: int,
        trashed_by: Optional[str] = None,
        cascade: bool = True
    ) -> Dict[str, Any]:
        """
        Move an item to trash (soft-delete).
        
        Args:
            entity_type: Type of entity (e.g., 'sample', 'equipment')
            entity_id: ID of the entity
            trashed_by: Username of person who trashed the item
            cascade: Whether to cascade trash to related items
            
        Returns:
            Dict with success status and message
        """
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return {'success': False, 'error': f'Unknown entity type: {entity_type}'}
        
        with self.session_scope() as session:
            item = session.query(model).filter(model.id == entity_id).first()
            if not item:
                return {'success': False, 'error': f'{entity_type.title()} not found'}
            
            if item.trashed_at:
                return {'success': False, 'error': f'{entity_type.title()} is already in trash'}
            
            now = datetime.utcnow()
            item.trashed_at = now
            item.trashed_by = trashed_by
            
            # Handle cascade operations
            cascade_count = 0
            if cascade:
                cascade_count = self._cascade_trash(session, entity_type, entity_id, now, trashed_by)
            
            session.commit()
            
            deletion_date = now + timedelta(days=TRASH_RETENTION_DAYS)
            return {
                'success': True,
                'message': f'{entity_type.title()} moved to trash. Will be permanently deleted on {deletion_date.strftime("%Y-%m-%d")}.',
                'cascade_count': cascade_count,
                'deletion_date': deletion_date.isoformat()
            }
    
    def restore_item(
        self,
        entity_type: str,
        entity_id: int,
        cascade: bool = True
    ) -> Dict[str, Any]:
        """
        Restore an item from trash.
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            cascade: Whether to cascade restore to related items
            
        Returns:
            Dict with success status and message
        """
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return {'success': False, 'error': f'Unknown entity type: {entity_type}'}
        
        with self.session_scope() as session:
            item = session.query(model).filter(model.id == entity_id).first()
            if not item:
                return {'success': False, 'error': f'{entity_type.title()} not found'}
            
            if not item.trashed_at:
                return {'success': False, 'error': f'{entity_type.title()} is not in trash'}
            
            item.trashed_at = None
            item.trashed_by = None
            
            # Handle cascade operations
            cascade_count = 0
            if cascade:
                cascade_count = self._cascade_restore(session, entity_type, entity_id)
            
            session.commit()
            
            return {
                'success': True,
                'message': f'{entity_type.title()} restored from trash.',
                'cascade_count': cascade_count
            }
    
    def permanently_delete_item(
        self,
        entity_type: str,
        entity_id: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Permanently delete an item (must be in trash or force=True).
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            force: If True, delete even if not in trash (use with caution!)
            
        Returns:
            Dict with success status and message
        """
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return {'success': False, 'error': f'Unknown entity type: {entity_type}'}
        
        with self.session_scope() as session:
            item = session.query(model).filter(model.id == entity_id).first()
            if not item:
                return {'success': False, 'error': f'{entity_type.title()} not found'}
            
            if not item.trashed_at and not force:
                return {'success': False, 'error': f'{entity_type.title()} must be in trash before permanent deletion'}
            
            # Clean up related data before deletion
            self._cleanup_before_delete(session, entity_type, entity_id)
            
            session.delete(item)
            session.commit()
            
            return {
                'success': True,
                'message': f'{entity_type.title()} permanently deleted.'
            }
    
    # ==================== Cascade Operations ====================
    
    def _cascade_trash(
        self,
        session: Session,
        entity_type: str,
        entity_id: int,
        trashed_at: datetime,
        trashed_by: Optional[str]
    ) -> int:
        """Cascade trash operation to related items. Returns count of cascaded items."""
        count = 0
        
        if entity_type == 'lab':
            # Trash all lab's projects, samples, equipment, etc.
            for model, fk_field in [
                (Project, 'lab_id'),
                (Sample, 'lab_id'),
                (Equipment, 'lab_id'),
                (Precursor, 'lab_id'),
                (Procedure, 'lab_id'),
                (Instrument, 'lab_id'),
                (Location, 'lab_id'),
                (Computer, 'lab_id'),
                (Queue, 'lab_id'),
                (Scan, 'lab_id'),
            ]:
                items = session.query(model).filter(
                    getattr(model, fk_field) == entity_id,
                    model.trashed_at == None
                ).all()
                for item in items:
                    item.trashed_at = trashed_at
                    item.trashed_by = trashed_by
                    count += 1
        
        elif entity_type == 'project':
            # Trash all project's samples, scans, queues
            for model, fk_field in [
                (Sample, 'project_id'),
                (Scan, 'project_id'),
                (Queue, 'project_id'),
                (Procedure, 'project_id'),
                (Precursor, 'project_id'),
            ]:
                items = session.query(model).filter(
                    getattr(model, fk_field) == entity_id,
                    model.trashed_at == None
                ).all()
                for item in items:
                    item.trashed_at = trashed_at
                    item.trashed_by = trashed_by
                    count += 1
        
        elif entity_type == 'queue':
            # Trash all queue's scans
            scans = session.query(Scan).filter(
                Scan.queue_id == entity_id,
                Scan.trashed_at == None
            ).all()
            for scan in scans:
                scan.trashed_at = trashed_at
                scan.trashed_by = trashed_by
                count += 1
        
        elif entity_type == 'location':
            # Recursively trash child locations
            count += self._cascade_trash_locations(session, entity_id, trashed_at, trashed_by)
        
        return count
    
    def _cascade_trash_locations(
        self,
        session: Session,
        parent_id: int,
        trashed_at: datetime,
        trashed_by: Optional[str]
    ) -> int:
        """Recursively trash child locations."""
        count = 0
        children = session.query(Location).filter(
            Location.parent_location_id == parent_id,
            Location.trashed_at == None
        ).all()
        
        for child in children:
            child.trashed_at = trashed_at
            child.trashed_by = trashed_by
            count += 1
            # Recursively process grandchildren
            count += self._cascade_trash_locations(session, child.id, trashed_at, trashed_by)
        
        return count
    
    def _cascade_restore(
        self,
        session: Session,
        entity_type: str,
        entity_id: int
    ) -> int:
        """Cascade restore operation to related items. Returns count of restored items."""
        count = 0
        
        if entity_type == 'lab':
            # Restore all lab's items that were trashed at the same time
            lab = session.query(Lab).filter(Lab.id == entity_id).first()
            if lab:
                # We restore items that were trashed by the same cascade
                for model, fk_field in [
                    (Project, 'lab_id'),
                    (Sample, 'lab_id'),
                    (Equipment, 'lab_id'),
                    (Precursor, 'lab_id'),
                    (Procedure, 'lab_id'),
                    (Instrument, 'lab_id'),
                    (Location, 'lab_id'),
                    (Computer, 'lab_id'),
                    (Queue, 'lab_id'),
                    (Scan, 'lab_id'),
                ]:
                    items = session.query(model).filter(
                        getattr(model, fk_field) == entity_id,
                        model.trashed_at != None
                    ).all()
                    for item in items:
                        item.trashed_at = None
                        item.trashed_by = None
                        count += 1
        
        elif entity_type == 'project':
            for model, fk_field in [
                (Sample, 'project_id'),
                (Scan, 'project_id'),
                (Queue, 'project_id'),
                (Procedure, 'project_id'),
                (Precursor, 'project_id'),
            ]:
                items = session.query(model).filter(
                    getattr(model, fk_field) == entity_id,
                    model.trashed_at != None
                ).all()
                for item in items:
                    item.trashed_at = None
                    item.trashed_by = None
                    count += 1
        
        elif entity_type == 'queue':
            scans = session.query(Scan).filter(
                Scan.queue_id == entity_id,
                Scan.trashed_at != None
            ).all()
            for scan in scans:
                scan.trashed_at = None
                scan.trashed_by = None
                count += 1
        
        elif entity_type == 'location':
            count += self._cascade_restore_locations(session, entity_id)
        
        return count
    
    def _cascade_restore_locations(self, session: Session, parent_id: int) -> int:
        """Recursively restore child locations."""
        count = 0
        children = session.query(Location).filter(
            Location.parent_location_id == parent_id,
            Location.trashed_at != None
        ).all()
        
        for child in children:
            child.trashed_at = None
            child.trashed_by = None
            count += 1
            count += self._cascade_restore_locations(session, child.id)
        
        return count
    
    def _cleanup_before_delete(self, session: Session, entity_type: str, entity_id: int):
        """Clean up references before permanent deletion."""
        # This handles foreign key cleanup and orphaned records
        # For now, we rely on CASCADE DELETE in the database
        # But add any manual cleanup here as needed
        pass
    
    # ==================== Query Helpers ====================
    
    def get_trashed_items(
        self,
        entity_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Get all trashed items, optionally filtered by type.
        
        Returns:
            Dict with items grouped by type and total count
        """
        with self.session_scope() as session:
            result = {'items': [], 'total': 0, 'by_type': {}}
            
            types_to_query = [entity_type] if entity_type else list(ENTITY_MODEL_MAP.keys())
            
            for etype in types_to_query:
                model = ENTITY_MODEL_MAP.get(etype)
                if not model:
                    continue
                
                items = session.query(model).filter(
                    model.trashed_at != None
                ).order_by(model.trashed_at.desc()).all()
                
                type_items = []
                for item in items:
                    item_dict = {
                        'id': item.id,
                        'entity_type': etype,
                        'name': getattr(item, 'name', None) or getattr(item, 'sample_id', None) or getattr(item, 'scan_id', None) or f'{etype}_{item.id}',
                        'trashed_at': item.trashed_at.isoformat() if item.trashed_at else None,
                        'trashed_by': item.trashed_by,
                        'days_until_deletion': item.days_until_permanent_deletion,
                        'deletion_date': item.scheduled_deletion_date.isoformat() if item.scheduled_deletion_date else None,
                    }
                    type_items.append(item_dict)
                    result['items'].append(item_dict)
                
                result['by_type'][etype] = {
                    'items': type_items,
                    'count': len(type_items)
                }
            
            result['total'] = len(result['items'])
            
            # Sort by deletion date (most urgent first)
            result['items'].sort(key=lambda x: x.get('days_until_deletion', 999))
            
            # Paginate
            offset = (page - 1) * per_page
            result['items'] = result['items'][offset:offset + per_page]
            
            return result
    
    def cleanup_expired_trash(self) -> Dict[str, int]:
        """
        Permanently delete all items past their retention period.
        Should be called periodically (e.g., daily cron job).
        
        Returns:
            Dict with counts of deleted items by type
        """
        cutoff_date = datetime.utcnow() - timedelta(days=TRASH_RETENTION_DAYS)
        deleted_counts = {}
        
        with self.session_scope() as session:
            for entity_type, model in ENTITY_MODEL_MAP.items():
                # Find expired items
                expired = session.query(model).filter(
                    model.trashed_at != None,
                    model.trashed_at < cutoff_date
                ).all()
                
                count = len(expired)
                if count > 0:
                    for item in expired:
                        self._cleanup_before_delete(session, entity_type, item.id)
                        session.delete(item)
                    deleted_counts[entity_type] = count
            
            session.commit()
        
        return deleted_counts
    
    def get_trash_stats(self) -> Dict[str, Any]:
        """Get statistics about trashed items."""
        with self.session_scope() as session:
            stats = {
                'total_trashed': 0,
                'expiring_soon': 0,  # Within 7 days
                'by_type': {}
            }
            
            seven_days_from_now = datetime.utcnow() + timedelta(days=7)
            expiry_cutoff = seven_days_from_now - timedelta(days=TRASH_RETENTION_DAYS)
            
            for entity_type, model in ENTITY_MODEL_MAP.items():
                count = session.query(func.count(model.id)).filter(
                    model.trashed_at != None
                ).scalar() or 0
                
                expiring_count = session.query(func.count(model.id)).filter(
                    model.trashed_at != None,
                    model.trashed_at < expiry_cutoff
                ).scalar() or 0
                
                if count > 0:
                    stats['by_type'][entity_type] = {
                        'count': count,
                        'expiring_soon': expiring_count
                    }
                    stats['total_trashed'] += count
                    stats['expiring_soon'] += expiring_count
            
            return stats


# Singleton instance
trash_service = TrashService()

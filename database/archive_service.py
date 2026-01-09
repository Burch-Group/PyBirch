"""
PyBirch Archive Service
=======================
Handles archive operations for all archivable entities.

Features:
- Archive items (hide from normal queries indefinitely)
- Unarchive items to restore visibility
- Query filtering for archived items

Unlike trash, archived items are never automatically deleted.
Use archiving for old items that should be preserved for historical reference.
"""

from datetime import datetime
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


# Entity type to model mapping (same as trash service)
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


class ArchiveService:
    """Service for managing archived items."""
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for a series of operations."""
        with get_session() as session:
            yield session
    
    # ==================== Core Operations ====================
    
    def archive_item(
        self,
        entity_type: str,
        entity_id: int,
        archived_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Archive an item (hide from normal queries).
        
        Args:
            entity_type: Type of entity (e.g., 'sample', 'equipment')
            entity_id: ID of the entity
            archived_by: Username of person who archived the item
            
        Returns:
            Dict with success status and message
        """
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return {'success': False, 'error': f'Unknown entity type: {entity_type}'}
        
        # Check if model has archive capability
        if not hasattr(model, 'archived_at'):
            return {'success': False, 'error': f'{entity_type.title()} does not support archiving'}
        
        with self.session_scope() as session:
            item = session.query(model).filter(model.id == entity_id).first()
            if not item:
                return {'success': False, 'error': f'{entity_type.title()} not found'}
            
            if item.archived_at:
                return {'success': False, 'error': f'{entity_type.title()} is already archived'}
            
            # Check if item is in trash
            if hasattr(item, 'trashed_at') and item.trashed_at:
                return {'success': False, 'error': f'Cannot archive item that is in trash'}
            
            # Archive the item
            item.archived_at = datetime.utcnow()
            item.archived_by = archived_by
            
            session.commit()
            
            return {
                'success': True,
                'message': f'{entity_type.title()} archived successfully',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'archived_at': item.archived_at.isoformat()
            }
    
    def unarchive_item(
        self,
        entity_type: str,
        entity_id: int
    ) -> Dict[str, Any]:
        """
        Unarchive an item (restore to normal visibility).
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            
        Returns:
            Dict with success status and message
        """
        model = ENTITY_MODEL_MAP.get(entity_type)
        if not model:
            return {'success': False, 'error': f'Unknown entity type: {entity_type}'}
        
        if not hasattr(model, 'archived_at'):
            return {'success': False, 'error': f'{entity_type.title()} does not support archiving'}
        
        with self.session_scope() as session:
            item = session.query(model).filter(model.id == entity_id).first()
            if not item:
                return {'success': False, 'error': f'{entity_type.title()} not found'}
            
            if not item.archived_at:
                return {'success': False, 'error': f'{entity_type.title()} is not archived'}
            
            # Unarchive the item
            item.archived_at = None
            item.archived_by = None
            
            session.commit()
            
            return {
                'success': True,
                'message': f'{entity_type.title()} unarchived successfully',
                'entity_type': entity_type,
                'entity_id': entity_id
            }
    
    def get_archived_items(
        self,
        entity_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Get paginated list of archived items.
        
        Args:
            entity_type: Optional filter by entity type
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Dict with items and pagination info
        """
        with self.session_scope() as session:
            items = []
            total = 0
            
            types_to_query = [entity_type] if entity_type else list(ENTITY_MODEL_MAP.keys())
            
            for etype in types_to_query:
                model = ENTITY_MODEL_MAP.get(etype)
                if not model or not hasattr(model, 'archived_at'):
                    continue
                
                query = session.query(model).filter(model.archived_at != None)
                
                # Skip trashed items
                if hasattr(model, 'trashed_at'):
                    query = query.filter(model.trashed_at == None)
                
                count = query.count()
                total += count
                
                archived_items = query.order_by(model.archived_at.desc()).all()
                
                for item in archived_items:
                    item_dict = {
                        'entity_type': etype,
                        'entity_id': item.id,
                        'archived_at': item.archived_at.isoformat() if item.archived_at else None,
                        'archived_by': item.archived_by,
                    }
                    
                    # Add display name based on entity type
                    if hasattr(item, 'name'):
                        item_dict['name'] = item.name
                    elif hasattr(item, 'sample_id'):
                        item_dict['name'] = item.sample_id
                    elif hasattr(item, 'title'):
                        item_dict['name'] = item.title
                    else:
                        item_dict['name'] = f'{etype.title()} #{item.id}'
                    
                    items.append(item_dict)
            
            # Sort all items by archived date
            items.sort(key=lambda x: x['archived_at'] or '', reverse=True)
            
            # Paginate
            offset = (page - 1) * per_page
            paginated_items = items[offset:offset + per_page]
            
            return {
                'items': paginated_items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """
        Get statistics about archived items.
        
        Returns:
            Dict with archive counts by entity type
        """
        with self.session_scope() as session:
            stats = {'total_archived': 0, 'by_type': {}}
            
            for entity_type, model in ENTITY_MODEL_MAP.items():
                if not hasattr(model, 'archived_at'):
                    continue
                
                query = session.query(func.count(model.id)).filter(model.archived_at != None)
                
                # Skip trashed items
                if hasattr(model, 'trashed_at'):
                    query = query.filter(model.trashed_at == None)
                
                count = query.scalar() or 0
                
                if count > 0:
                    stats['by_type'][entity_type] = count
                    stats['total_archived'] += count
            
            return stats


# Singleton instance
_archive_service = None


def get_archive_service() -> ArchiveService:
    """Get or create the singleton ArchiveService instance."""
    global _archive_service
    if _archive_service is None:
        _archive_service = ArchiveService()
    return _archive_service

"""
Validators
==========
Validation functions for database integration.
"""

from typing import Optional, List


# Valid scan statuses
SCAN_STATUSES = [
    'pending',
    'running',
    'paused',
    'completed',
    'failed',
    'aborted',
]

# Valid queue statuses
QUEUE_STATUSES = [
    'pending',
    'running',
    'paused',
    'completed',
    'stopped',
    'failed',
]

# Valid equipment statuses
EQUIPMENT_STATUSES = [
    'active',
    'inactive',
    'maintenance',
    'error',
]

# Valid equipment types
EQUIPMENT_TYPES = [
    'source',
    'detector',
    'manipulator',
    'controller',
    'analyzer',
    'other',
]


def validate_sample_id(
    db_service,
    sample_id: Optional[int],
    raise_error: bool = True,
) -> bool:
    """
    Validate that a sample ID exists in the database.
    
    Args:
        db_service: Database service instance
        sample_id: Sample ID to validate
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    if sample_id is None:
        return True  # None is allowed
    
    sample = db_service.get_sample(sample_id)
    if sample is None:
        if raise_error:
            raise ValueError(f"Sample with ID {sample_id} not found")
        return False
    
    return True


def validate_project_id(
    db_service,
    project_id: Optional[int],
    raise_error: bool = True,
) -> bool:
    """
    Validate that a project ID exists in the database.
    
    Args:
        db_service: Database service instance
        project_id: Project ID to validate
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    if project_id is None:
        return True  # None is allowed
    
    project = db_service.get_project(project_id)
    if project is None:
        if raise_error:
            raise ValueError(f"Project with ID {project_id} not found")
        return False
    
    return True


def validate_equipment_id(
    db_service,
    equipment_id: Optional[int],
    raise_error: bool = True,
) -> bool:
    """
    Validate that an equipment ID exists in the database.
    
    Args:
        db_service: Database service instance
        equipment_id: Equipment ID to validate
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    if equipment_id is None:
        return True  # None is allowed
    
    equipment = db_service.get_equipment(equipment_id)
    if equipment is None:
        if raise_error:
            raise ValueError(f"Equipment with ID {equipment_id} not found")
        return False
    
    return True


def validate_scan_status(
    status: str,
    raise_error: bool = True,
) -> bool:
    """
    Validate a scan status value.
    
    Args:
        status: Status to validate
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    if status not in SCAN_STATUSES:
        if raise_error:
            raise ValueError(
                f"Invalid scan status '{status}'. "
                f"Valid values: {', '.join(SCAN_STATUSES)}"
            )
        return False
    
    return True


def validate_queue_status(
    status: str,
    raise_error: bool = True,
) -> bool:
    """
    Validate a queue status value.
    
    Args:
        status: Status to validate
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    if status not in QUEUE_STATUSES:
        if raise_error:
            raise ValueError(
                f"Invalid queue status '{status}'. "
                f"Valid values: {', '.join(QUEUE_STATUSES)}"
            )
        return False
    
    return True


def validate_equipment_status(
    status: str,
    raise_error: bool = True,
) -> bool:
    """
    Validate an equipment status value.
    
    Args:
        status: Status to validate
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    if status not in EQUIPMENT_STATUSES:
        if raise_error:
            raise ValueError(
                f"Invalid equipment status '{status}'. "
                f"Valid values: {', '.join(EQUIPMENT_STATUSES)}"
            )
        return False
    
    return True


def validate_equipment_type(
    equipment_type: str,
    raise_error: bool = True,
) -> bool:
    """
    Validate an equipment type value.
    
    Args:
        equipment_type: Type to validate
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    if equipment_type not in EQUIPMENT_TYPES:
        if raise_error:
            raise ValueError(
                f"Invalid equipment type '{equipment_type}'. "
                f"Valid values: {', '.join(EQUIPMENT_TYPES)}"
            )
        return False
    
    return True


def validate_ids_list(
    ids: List[int],
    id_type: str = 'ID',
    raise_error: bool = True,
) -> bool:
    """
    Validate a list of IDs.
    
    Args:
        ids: List of IDs to validate
        id_type: Type name for error messages
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    if not ids:
        return True
    
    for i, id_val in enumerate(ids):
        if not isinstance(id_val, int) or id_val < 1:
            if raise_error:
                raise ValueError(
                    f"Invalid {id_type} at index {i}: {id_val}. "
                    f"Must be a positive integer."
                )
            return False
    
    return True


def validate_measurement_data(
    data: dict,
    raise_error: bool = True,
) -> bool:
    """
    Validate measurement data point structure.
    
    Args:
        data: Data point dictionary
        raise_error: Whether to raise an error if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If invalid and raise_error is True
    """
    required_fields = ['measurement_id']
    
    for field in required_fields:
        if field not in data:
            if raise_error:
                raise ValueError(f"Missing required field: {field}")
            return False
    
    # Check that at least one value field is present
    value_fields = [
        'value_float', 'value_int', 'value_string',
        'value_blob', 'channel', 'step_index'
    ]
    
    if not any(data.get(f) is not None for f in value_fields):
        if raise_error:
            raise ValueError(
                "At least one value field must be present: "
                f"{', '.join(value_fields)}"
            )
        return False
    
    return True

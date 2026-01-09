"""
PyBirch Database REST API v1
============================
Versioned REST API endpoints for programmatic access to the PyBirch database.

This module provides a complete REST API that can be used by:
- PyBirch desktop client (via API client)
- Third-party integrations
- Automated scripts and pipelines

API Version: v1
Base URL: /api/v1/
"""

from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any, Tuple
from flask import Blueprint, request, jsonify, g, session, current_app

from database.services import get_db_service


# Create versioned API blueprint
api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


# ==================== Response Helpers ====================

def api_response(
    data: Any = None,
    meta: Optional[Dict] = None,
    status: int = 200
) -> Tuple[Dict, int]:
    """Create a standardized successful API response.
    
    Args:
        data: Response data (dict, list, or None)
        meta: Optional metadata (pagination, etc.)
        status: HTTP status code
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    response = {
        "success": True,
        "data": data
    }
    if meta:
        response["meta"] = meta
    return jsonify(response), status


def api_error(
    message: str,
    code: str = "ERROR",
    details: Optional[Dict] = None,
    status: int = 400
) -> Tuple[Dict, int]:
    """Create a standardized error API response.
    
    Args:
        message: Human-readable error message
        code: Machine-readable error code
        details: Optional additional error details
        status: HTTP status code
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    response = {
        "success": False,
        "error": {
            "code": code,
            "message": message
        }
    }
    if details:
        response["error"]["details"] = details
    return jsonify(response), status


def paginated_response(items: list, total: int, page: int, per_page: int):
    """Create a paginated API response."""
    return api_response(
        data=items,
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if per_page > 0 else 0
        }
    )


# ==================== Authentication ====================

def get_api_key_from_request() -> Optional[str]:
    """Extract API key from request headers."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return request.headers.get('X-API-Key')


def api_auth_optional(f):
    """Decorator that checks for API key but doesn't require it."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = get_api_key_from_request()
        g.api_key = api_key
        g.api_authenticated = False
        
        if api_key:
            # TODO: Validate API key against database
            # For now, any API key is accepted
            g.api_authenticated = True
        elif 'user_id' in session:
            # Fall back to session authentication
            g.api_authenticated = True
            
        return f(*args, **kwargs)
    return decorated_function


def api_auth_required(f):
    """Decorator that requires API authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = get_api_key_from_request()
        g.api_key = api_key
        g.api_authenticated = False
        
        if api_key:
            # TODO: Validate API key against database
            g.api_authenticated = True
        elif 'user_id' in session:
            g.api_authenticated = True
        else:
            return api_error(
                "Authentication required",
                code="AUTH_REQUIRED",
                status=401
            )
            
        return f(*args, **kwargs)
    return decorated_function


# ==================== Error Handlers ====================

@api_v1_bp.errorhandler(404)
def not_found(e):
    return api_error("Resource not found", code="NOT_FOUND", status=404)


@api_v1_bp.errorhandler(500)
def internal_error(e):
    return api_error("Internal server error", code="INTERNAL_ERROR", status=500)


# ==================== Health Check ====================

@api_v1_bp.route('/health')
def health_check():
    """API health check endpoint."""
    db = get_db_service()
    db_healthy = db._db_manager.health_check() if hasattr(db, '_db_manager') else True
    
    return api_response({
        "status": "healthy" if db_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "v1"
    })


# ==================== Labs ====================

@api_v1_bp.route('/labs', methods=['GET'])
@api_auth_optional
def list_labs():
    """List all labs with optional filtering."""
    try:
        db = get_db_service()
        labs, total = db.get_labs(
            search=request.args.get('search'),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            labs, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/labs/<int:lab_id>', methods=['GET'])
@api_auth_optional
def get_lab(lab_id):
    """Get a single lab by ID."""
    try:
        db = get_db_service()
        lab = db.get_lab(lab_id)
        if not lab:
            return api_error("Lab not found", code="NOT_FOUND", status=404)
        return api_response(lab)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/labs', methods=['POST'])
@api_auth_required
def create_lab():
    """Create a new lab."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        lab = db.create_lab(data)
        return api_response(lab, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/labs/<int:lab_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_lab(lab_id):
    """Update a lab."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        lab = db.update_lab(lab_id, data)
        if not lab:
            return api_error("Lab not found", code="NOT_FOUND", status=404)
        return api_response(lab)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/labs/<int:lab_id>', methods=['DELETE'])
@api_auth_required
def delete_lab(lab_id):
    """Delete a lab."""
    try:
        db = get_db_service()
        success = db.delete_lab(lab_id)
        if not success:
            return api_error("Lab not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


# ==================== Projects ====================

@api_v1_bp.route('/projects', methods=['GET'])
@api_auth_optional
def list_projects():
    """List all projects with optional filtering."""
    try:
        db = get_db_service()
        projects, total = db.get_projects(
            search=request.args.get('search'),
            lab_id=request.args.get('lab_id', type=int),
            status=request.args.get('status'),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            projects, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/projects/<int:project_id>', methods=['GET'])
@api_auth_optional
def get_project(project_id):
    """Get a single project by ID."""
    try:
        db = get_db_service()
        project = db.get_project(project_id)
        if not project:
            return api_error("Project not found", code="NOT_FOUND", status=404)
        return api_response(project)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/projects', methods=['POST'])
@api_auth_required
def create_project():
    """Create a new project."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name', 'lab_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        project = db.create_project(data)
        return api_response(project, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/projects/<int:project_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_project(project_id):
    """Update a project."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        project = db.update_project(project_id, data)
        if not project:
            return api_error("Project not found", code="NOT_FOUND", status=404)
        return api_response(project)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@api_auth_required
def delete_project(project_id):
    """Delete a project."""
    try:
        db = get_db_service()
        success = db.delete_project(project_id)
        if not success:
            return api_error("Project not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


# ==================== Samples ====================

@api_v1_bp.route('/samples', methods=['GET'])
@api_auth_optional
def list_samples():
    """List samples with optional filtering."""
    try:
        db = get_db_service()
        samples, total = db.get_samples(
            search=request.args.get('search'),
            status=request.args.get('status'),
            lab_id=request.args.get('lab_id', type=int),
            project_id=request.args.get('project_id', type=int),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            samples, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/samples/<int:sample_id>', methods=['GET'])
@api_auth_optional
def get_sample(sample_id):
    """Get a single sample by ID."""
    try:
        db = get_db_service()
        sample = db.get_sample(sample_id)
        if not sample:
            return api_error("Sample not found", code="NOT_FOUND", status=404)
        return api_response(sample)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/samples', methods=['POST'])
@api_auth_required
def create_sample():
    """Create a new sample."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['sample_id', 'lab_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        sample = db.create_sample(data)
        return api_response(sample, status=201)
    except Exception as e:
        error_msg = str(e)
        if "UNIQUE constraint" in error_msg or "duplicate" in error_msg.lower():
            return api_error("Sample ID already exists", code="DUPLICATE_ID", status=409)
        return api_error(error_msg, code="CREATE_ERROR", status=500)


@api_v1_bp.route('/samples/<int:sample_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_sample(sample_id):
    """Update a sample."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        sample = db.update_sample(sample_id, data)
        if not sample:
            return api_error("Sample not found", code="NOT_FOUND", status=404)
        return api_response(sample)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/samples/<int:sample_id>', methods=['DELETE'])
@api_auth_required
def delete_sample(sample_id):
    """Delete a sample."""
    try:
        db = get_db_service()
        success = db.delete_sample(sample_id)
        if not success:
            return api_error("Sample not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


# ==================== Equipment ====================

@api_v1_bp.route('/equipment', methods=['GET'])
@api_auth_optional
def list_equipment():
    """List equipment with optional filtering."""
    try:
        db = get_db_service()
        equipment, total = db.get_equipment_list(
            search=request.args.get('search'),
            status=request.args.get('status'),
            equipment_type=request.args.get('type'),
            lab_id=request.args.get('lab_id', type=int),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            equipment, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/equipment/<int:equipment_id>', methods=['GET'])
@api_auth_optional
def get_equipment(equipment_id):
    """Get a single piece of equipment by ID."""
    try:
        db = get_db_service()
        equipment = db.get_equipment(equipment_id)
        if not equipment:
            return api_error("Equipment not found", code="NOT_FOUND", status=404)
        return api_response(equipment)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/equipment', methods=['POST'])
@api_auth_required
def create_equipment():
    """Create new equipment."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name', 'lab_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        equipment = db.create_equipment(data)
        return api_response(equipment, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/equipment/<int:equipment_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_equipment(equipment_id):
    """Update equipment."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        equipment = db.update_equipment(equipment_id, data)
        if not equipment:
            return api_error("Equipment not found", code="NOT_FOUND", status=404)
        return api_response(equipment)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/equipment/<int:equipment_id>', methods=['DELETE'])
@api_auth_required
def delete_equipment(equipment_id):
    """Delete equipment."""
    try:
        db = get_db_service()
        success = db.delete_equipment(equipment_id)
        if not success:
            return api_error("Equipment not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


# ==================== Precursors ====================

@api_v1_bp.route('/precursors', methods=['GET'])
@api_auth_optional
def list_precursors():
    """List precursors with optional filtering."""
    try:
        db = get_db_service()
        precursors, total = db.get_precursors(
            search=request.args.get('search'),
            state=request.args.get('state'),
            lab_id=request.args.get('lab_id', type=int),
            project_id=request.args.get('project_id', type=int),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            precursors, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/precursors/<int:precursor_id>', methods=['GET'])
@api_auth_optional
def get_precursor(precursor_id):
    """Get a single precursor by ID."""
    try:
        db = get_db_service()
        precursor = db.get_precursor(precursor_id)
        if not precursor:
            return api_error("Precursor not found", code="NOT_FOUND", status=404)
        return api_response(precursor)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/precursors', methods=['POST'])
@api_auth_required
def create_precursor():
    """Create a new precursor."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name', 'lab_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        precursor = db.create_precursor(data)
        return api_response(precursor, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/precursors/<int:precursor_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_precursor(precursor_id):
    """Update a precursor."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        precursor = db.update_precursor(precursor_id, data)
        if not precursor:
            return api_error("Precursor not found", code="NOT_FOUND", status=404)
        return api_response(precursor)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/precursors/<int:precursor_id>', methods=['DELETE'])
@api_auth_required
def delete_precursor(precursor_id):
    """Delete a precursor."""
    try:
        db = get_db_service()
        success = db.delete_precursor(precursor_id)
        if not success:
            return api_error("Precursor not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


# ==================== Procedures ====================

@api_v1_bp.route('/procedures', methods=['GET'])
@api_auth_optional
def list_procedures():
    """List procedures with optional filtering."""
    try:
        db = get_db_service()
        procedures, total = db.get_procedures(
            search=request.args.get('search'),
            procedure_type=request.args.get('type'),
            lab_id=request.args.get('lab_id', type=int),
            project_id=request.args.get('project_id', type=int),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            procedures, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/procedures/<int:procedure_id>', methods=['GET'])
@api_auth_optional
def get_procedure(procedure_id):
    """Get a single procedure by ID."""
    try:
        db = get_db_service()
        procedure = db.get_procedure(procedure_id)
        if not procedure:
            return api_error("Procedure not found", code="NOT_FOUND", status=404)
        return api_response(procedure)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/procedures', methods=['POST'])
@api_auth_required
def create_procedure():
    """Create a new procedure."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name', 'lab_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        procedure = db.create_procedure(data)
        return api_response(procedure, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/procedures/<int:procedure_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_procedure(procedure_id):
    """Update a procedure."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        procedure = db.update_procedure(procedure_id, data)
        if not procedure:
            return api_error("Procedure not found", code="NOT_FOUND", status=404)
        return api_response(procedure)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/procedures/<int:procedure_id>', methods=['DELETE'])
@api_auth_required
def delete_procedure(procedure_id):
    """Delete a procedure."""
    try:
        db = get_db_service()
        success = db.delete_procedure(procedure_id)
        if not success:
            return api_error("Procedure not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


# ==================== Queues ====================

@api_v1_bp.route('/queues', methods=['GET'])
@api_auth_optional
def list_queues():
    """List queues with optional filtering."""
    try:
        db = get_db_service()
        queues, total = db.get_queues(
            search=request.args.get('search'),
            status=request.args.get('status'),
            lab_id=request.args.get('lab_id', type=int),
            project_id=request.args.get('project_id', type=int),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            queues, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/queues/<int:queue_id>', methods=['GET'])
@api_auth_optional
def get_queue(queue_id):
    """Get a single queue by ID."""
    try:
        db = get_db_service()
        queue = db.get_queue(queue_id)
        if not queue:
            return api_error("Queue not found", code="NOT_FOUND", status=404)
        return api_response(queue)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/queues', methods=['POST'])
@api_auth_required
def create_queue():
    """Create a new queue."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name', 'lab_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        queue = db.create_queue(data)
        return api_response(queue, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/queues/<int:queue_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_queue(queue_id):
    """Update a queue."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        queue = db.update_queue(queue_id, data)
        if not queue:
            return api_error("Queue not found", code="NOT_FOUND", status=404)
        return api_response(queue)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/queues/<int:queue_id>', methods=['DELETE'])
@api_auth_required
def delete_queue(queue_id):
    """Delete a queue."""
    try:
        db = get_db_service()
        success = db.delete_queue(queue_id)
        if not success:
            return api_error("Queue not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


@api_v1_bp.route('/queues/<int:queue_id>/status', methods=['PATCH'])
@api_auth_required
def update_queue_status(queue_id):
    """Update queue status."""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return api_error("status field required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        queue = db.update_queue_status(queue_id, data['status'])
        if not queue:
            return api_error("Queue not found", code="NOT_FOUND", status=404)
        return api_response(queue)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/queues/<int:queue_id>/scans', methods=['GET'])
@api_auth_optional
def list_queue_scans(queue_id):
    """List scans belonging to a queue (scans are children of queues)."""
    try:
        db = get_db_service()
        # Verify queue exists
        queue = db.get_queue(queue_id)
        if not queue:
            return api_error("Queue not found", code="NOT_FOUND", status=404)
        
        scans, total = db.get_scans(
            queue_id=queue_id,
            search=request.args.get('search'),
            status=request.args.get('status'),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            scans, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


# ==================== Scans ====================

@api_v1_bp.route('/scans', methods=['GET'])
@api_auth_optional
def list_scans():
    """List scans with optional filtering."""
    try:
        db = get_db_service()
        scans, total = db.get_scans(
            search=request.args.get('search'),
            status=request.args.get('status'),
            sample_id=request.args.get('sample_id', type=int),
            queue_id=request.args.get('queue_id', type=int),
            lab_id=request.args.get('lab_id', type=int),
            project_id=request.args.get('project_id', type=int),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            scans, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/scans/<int:scan_id>', methods=['GET'])
@api_auth_optional
def get_scan(scan_id):
    """Get a single scan by ID."""
    try:
        db = get_db_service()
        scan = db.get_scan(scan_id)
        if not scan:
            return api_error("Scan not found", code="NOT_FOUND", status=404)
        return api_response(scan)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/scans', methods=['POST'])
@api_auth_required
def create_scan():
    """Create a new scan."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['lab_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        scan = db.create_scan(data)
        return api_response(scan, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/scans/<int:scan_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_scan(scan_id):
    """Update a scan."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        scan = db.update_scan(scan_id, data)
        if not scan:
            return api_error("Scan not found", code="NOT_FOUND", status=404)
        return api_response(scan)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/scans/<int:scan_id>', methods=['DELETE'])
@api_auth_required
def delete_scan(scan_id):
    """Delete a scan."""
    try:
        db = get_db_service()
        success = db.delete_scan(scan_id)
        if not success:
            return api_error("Scan not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


@api_v1_bp.route('/scans/<int:scan_id>/status', methods=['PATCH'])
@api_auth_required
def update_scan_status(scan_id):
    """Update scan status."""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return api_error("status field required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        # Pass additional fields from data (like started_at, completed_at, error_message)
        extra_fields = {k: v for k, v in data.items() if k != 'status'}
        scan = db.update_scan_status(scan_id, data['status'], **extra_fields)
        if not scan:
            return api_error("Scan not found", code="NOT_FOUND", status=404)
        return api_response(scan)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


# ==================== Measurements & Data Points ====================

@api_v1_bp.route('/scans/<int:scan_id>/measurements', methods=['GET'])
@api_auth_optional
def list_scan_measurements(scan_id):
    """Get measurement objects for a scan."""
    try:
        db = get_db_service()
        scan = db.get_scan(scan_id)
        if not scan:
            return api_error("Scan not found", code="NOT_FOUND", status=404)
        
        measurements = db.get_scan_measurements(scan_id)
        return api_response(measurements)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/scans/<int:scan_id>/measurements', methods=['POST'])
@api_auth_required
def create_measurement(scan_id):
    """Create a measurement object for a scan."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        scan = db.get_scan(scan_id)
        if not scan:
            return api_error("Scan not found", code="NOT_FOUND", status=404)
        
        measurement = db.create_measurement_object(
            scan_id=scan_id,
            name=data['name'],
            data_type=data.get('data_type', 'float'),
            unit=data.get('unit'),
            instrument_name=data.get('instrument_name'),
            columns=data.get('columns'),
            description=data.get('description')
        )
        return api_response(measurement, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/measurements/<int:measurement_id>/data', methods=['GET'])
@api_auth_optional
def get_measurement_data(measurement_id):
    """Get data points for a measurement."""
    try:
        db = get_db_service()
        data_points = db.get_measurement_data_points(measurement_id)
        return api_response(data_points)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/measurements/<int:measurement_id>/data', methods=['POST'])
@api_auth_required
def submit_measurement_data(measurement_id):
    """Submit data points for a measurement (bulk insert)."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        points = data.get('points', data.get('data_points', []))
        if not points:
            return api_error("No data points provided", code="INVALID_INPUT", status=400)
        
        # Limit bulk insert size
        max_points = 10000
        if len(points) > max_points:
            return api_error(
                f"Too many data points ({len(points)}). Maximum is {max_points} per request.",
                code="LIMIT_EXCEEDED",
                status=400
            )
        
        db = get_db_service()
        count = db.bulk_create_data_points(measurement_id, points)
        
        return api_response({
            "count": count,
            "measurement_id": measurement_id
        }, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


# ==================== Instruments ====================

@api_v1_bp.route('/instruments', methods=['GET'])
@api_auth_optional
def list_instruments():
    """List instruments with optional filtering."""
    try:
        db = get_db_service()
        instruments, total = db.get_instruments_list(
            search=request.args.get('search'),
            instrument_type=request.args.get('type'),
            status=request.args.get('status'),
            lab_id=request.args.get('lab_id', type=int),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            instruments, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/instruments/<int:instrument_id>', methods=['GET'])
@api_auth_optional
def get_instrument(instrument_id):
    """Get a single instrument by ID."""
    try:
        db = get_db_service()
        instrument = db.get_instrument(instrument_id)
        if not instrument:
            return api_error("Instrument not found", code="NOT_FOUND", status=404)
        return api_response(instrument)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/instruments', methods=['POST'])
@api_auth_required
def create_instrument():
    """Create a new instrument."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name', 'lab_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        instrument = db.create_instrument(data)
        return api_response(instrument, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/instruments/<int:instrument_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_instrument(instrument_id):
    """Update an instrument."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        instrument = db.update_instrument(instrument_id, data)
        if not instrument:
            return api_error("Instrument not found", code="NOT_FOUND", status=404)
        return api_response(instrument)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/instruments/<int:instrument_id>', methods=['DELETE'])
@api_auth_required
def delete_instrument(instrument_id):
    """Delete an instrument."""
    try:
        db = get_db_service()
        success = db.delete_instrument(instrument_id)
        if not success:
            return api_error("Instrument not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


# ==================== Fabrication Runs ====================

@api_v1_bp.route('/fabrication-runs', methods=['GET'])
@api_auth_optional
def list_fabrication_runs():
    """List fabrication runs with optional filtering."""
    try:
        db = get_db_service()
        runs, total = db.get_fabrication_runs(
            sample_id=request.args.get('sample_id', type=int),
            procedure_id=request.args.get('procedure_id', type=int),
            status=request.args.get('status'),
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 20, type=int)
        )
        return paginated_response(
            runs, total,
            request.args.get('page', 1, type=int),
            request.args.get('per_page', 20, type=int)
        )
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/fabrication-runs/<int:run_id>', methods=['GET'])
@api_auth_optional
def get_fabrication_run(run_id):
    """Get a single fabrication run by ID."""
    try:
        db = get_db_service()
        run = db.get_fabrication_run(run_id)
        if not run:
            return api_error("Fabrication run not found", code="NOT_FOUND", status=404)
        return api_response(run)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/fabrication-runs', methods=['POST'])
@api_auth_required
def create_fabrication_run():
    """Create a new fabrication run."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['sample_id', 'procedure_id']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        db = get_db_service()
        run = db.create_fabrication_run(data)
        return api_response(run, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/fabrication-runs/<int:run_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_fabrication_run(run_id):
    """Update a fabrication run."""
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        run = db.update_fabrication_run(run_id, data)
        if not run:
            return api_error("Fabrication run not found", code="NOT_FOUND", status=404)
        return api_response(run)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


# ==================== Search ====================

@api_v1_bp.route('/search', methods=['GET'])
@api_auth_optional
def global_search():
    """Global search across all entities."""
    try:
        query = request.args.get('q', '')
        if not query:
            return api_error("Query parameter 'q' is required", code="INVALID_INPUT", status=400)
        
        db = get_db_service()
        results = db.global_search(query)
        return api_response(results)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


# ==================== Drivers ====================

@api_v1_bp.route('/drivers', methods=['GET'])
@api_auth_optional
def list_drivers():
    """List drivers with optional filtering.
    
    Query Parameters:
        type: Filter by 'movement' or 'measurement'
        category: Filter by category (e.g., 'Lock-In Amplifier')
        lab_id: Filter by lab ID
        search: Search in name, display_name, description
        include_public: Include public drivers (default: true)
        include_builtin: Include built-in drivers (default: true)
    """
    try:
        db = get_db_service()
        drivers = db.get_drivers(
            instrument_type=request.args.get('type'),
            category=request.args.get('category'),
            lab_id=request.args.get('lab_id', type=int),
            include_public=request.args.get('include_public', 'true').lower() == 'true',
            include_builtin=request.args.get('include_builtin', 'true').lower() == 'true',
            search=request.args.get('search'),
        )
        return api_response({
            'items': drivers,
            'total': len(drivers)
        })
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/drivers/<int:driver_id>', methods=['GET'])
@api_auth_optional
def get_driver(driver_id):
    """Get a single driver by ID."""
    try:
        db = get_db_service()
        driver = db.get_driver(driver_id)
        if not driver:
            return api_error("Driver not found", code="NOT_FOUND", status=404)
        return api_response(driver)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/drivers/by-name/<string:name>', methods=['GET'])
@api_auth_optional
def get_driver_by_name(name):
    """Get a driver by class name."""
    try:
        db = get_db_service()
        driver = db.get_driver_by_name(name)
        if not driver:
            return api_error("Driver not found", code="NOT_FOUND", status=404)
        return api_response(driver)
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/drivers', methods=['POST'])
@api_auth_required
def create_driver():
    """Create a new driver.
    
    Required fields:
        - name: Class name (must be unique)
        - display_name: Human-readable name
        - instrument_type: 'movement' or 'measurement'
        - source_code: Python source code
        - base_class: Base class name
    
    Optional fields:
        - description, category, manufacturer, dependencies
        - settings_schema, default_settings
        - data_columns, data_units, position_column, position_units
        - lab_id, is_public, is_builtin, is_approved, created_by
    """
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        required_fields = ['name', 'display_name', 'instrument_type', 'source_code', 'base_class']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return api_error(
                f"Missing required fields: {', '.join(missing)}",
                code="MISSING_FIELDS",
                details={"missing": missing},
                status=400
            )
        
        # Validate instrument_type
        if data['instrument_type'] not in ('movement', 'measurement'):
            return api_error(
                "instrument_type must be 'movement' or 'measurement'",
                code="INVALID_INPUT",
                status=400
            )
        
        db = get_db_service()
        driver = db.create_driver(data)
        return api_response(driver, status=201)
    except Exception as e:
        return api_error(str(e), code="CREATE_ERROR", status=500)


@api_v1_bp.route('/drivers/<int:driver_id>', methods=['PATCH', 'PUT'])
@api_auth_required
def update_driver(driver_id):
    """Update a driver.
    
    If source_code is changed, creates a new version.
    
    Query Parameters:
        change_summary: Description of changes (for version history)
    """
    try:
        data = request.get_json()
        if not data:
            return api_error("Request body required", code="INVALID_INPUT", status=400)
        
        # Validate instrument_type if provided
        if 'instrument_type' in data and data['instrument_type'] not in ('movement', 'measurement'):
            return api_error(
                "instrument_type must be 'movement' or 'measurement'",
                code="INVALID_INPUT",
                status=400
            )
        
        db = get_db_service()
        driver = db.update_driver(
            driver_id, 
            data,
            change_summary=request.args.get('change_summary'),
            updated_by=request.args.get('updated_by'),
        )
        if not driver:
            return api_error("Driver not found", code="NOT_FOUND", status=404)
        return api_response(driver)
    except Exception as e:
        return api_error(str(e), code="UPDATE_ERROR", status=500)


@api_v1_bp.route('/drivers/<int:driver_id>', methods=['DELETE'])
@api_auth_required
def delete_driver(driver_id):
    """Delete a driver and all its versions."""
    try:
        db = get_db_service()
        success = db.delete_driver(driver_id)
        if not success:
            return api_error("Driver not found", code="NOT_FOUND", status=404)
        return api_response({"deleted": True})
    except Exception as e:
        return api_error(str(e), code="DELETE_ERROR", status=500)


@api_v1_bp.route('/drivers/<int:driver_id>/versions', methods=['GET'])
@api_auth_optional
def get_driver_versions(driver_id):
    """Get version history for a driver."""
    try:
        db = get_db_service()
        
        # First verify the driver exists
        driver = db.get_driver(driver_id)
        if not driver:
            return api_error("Driver not found", code="NOT_FOUND", status=404)
        
        versions = db.get_driver_versions(driver_id)
        return api_response({
            'items': versions,
            'total': len(versions),
            'driver_id': driver_id,
            'driver_name': driver['name']
        })
    except Exception as e:
        return api_error(str(e), code="QUERY_ERROR", status=500)


@api_v1_bp.route('/drivers/<int:driver_id>/validate', methods=['POST'])
@api_auth_optional
def validate_driver(driver_id):
    """Validate a driver's source code.
    
    Attempts to compile and instantiate the class to check for errors.
    
    Returns:
        - valid: Boolean indicating if code is valid
        - errors: List of any compilation/instantiation errors
        - warnings: List of any warnings
    """
    try:
        db = get_db_service()
        driver = db.get_driver(driver_id)
        if not driver:
            return api_error("Driver not found", code="NOT_FOUND", status=404)
        
        errors = []
        warnings = []
        
        # Try to compile the source code
        try:
            compile(driver['source_code'], f"<{driver['name']}>", 'exec')
        except SyntaxError as e:
            errors.append({
                'type': 'SyntaxError',
                'message': str(e),
                'line': e.lineno,
                'offset': e.offset,
            })
            return api_response({
                'valid': False,
                'errors': errors,
                'warnings': warnings
            })
        
        # Try to create the class (but not instantiate it)
        try:
            from pybirch.Instruments.factory import InstrumentFactory
            factory = InstrumentFactory(db)
            cls = factory.create_class_from_driver(driver)
            
            if cls is None:
                errors.append({
                    'type': 'ClassCreationError',
                    'message': 'Failed to create class from driver'
                })
        except Exception as e:
            errors.append({
                'type': type(e).__name__,
                'message': str(e)
            })
        
        return api_response({
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        })
    except Exception as e:
        return api_error(str(e), code="VALIDATION_ERROR", status=500)


@api_v1_bp.route('/drivers/validate-code', methods=['POST'])
@api_auth_optional
def validate_driver_code():
    """Validate source code without saving.
    
    Request body:
        - source_code: Python source code to validate
        - base_class: Expected base class name
    
    Returns:
        - valid: Boolean indicating if code is valid
        - errors: List of any compilation errors
        - class_name: Detected class name (if valid)
        - detected_base_class: Detected base class (if valid)
    """
    try:
        data = request.get_json()
        if not data or 'source_code' not in data:
            return api_error("source_code is required", code="INVALID_INPUT", status=400)
        
        source_code = data['source_code']
        expected_base = data.get('base_class')
        
        errors = []
        warnings = []
        class_name = None
        detected_base = None
        
        # Try to compile
        try:
            compile(source_code, "<code>", 'exec')
        except SyntaxError as e:
            errors.append({
                'type': 'SyntaxError',
                'message': str(e),
                'line': e.lineno,
                'offset': e.offset,
            })
            return api_response({
                'valid': False,
                'errors': errors,
                'warnings': warnings
            })
        
        # Parse the AST to find class drivers
        import ast
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                    if node.bases:
                        base = node.bases[0]
                        if isinstance(base, ast.Name):
                            detected_base = base.id
                        elif isinstance(base, ast.Attribute):
                            detected_base = base.attr
                    break
            
            if not class_name:
                errors.append({
                    'type': 'ParseError',
                    'message': 'No class definition found in source code'
                })
            
            if expected_base and detected_base and expected_base != detected_base:
                warnings.append({
                    'type': 'BaseClassMismatch',
                    'message': f"Expected base class '{expected_base}' but found '{detected_base}'"
                })
                
        except Exception as e:
            errors.append({
                'type': 'ParseError',
                'message': str(e)
            })
        
        return api_response({
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'class_name': class_name,
            'detected_base_class': detected_base
        })
    except Exception as e:
        return api_error(str(e), code="VALIDATION_ERROR", status=500)

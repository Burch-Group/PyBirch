"""
PyBirch Database Web Routes
===========================
Flask route handlers for the web UI and REST API.
"""

import os
import shutil
from datetime import datetime
from functools import wraps
from io import BytesIO
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, g, send_file, Response, current_app, make_response
from database.services import get_db_service

# Main blueprint for HTML pages
main_bp = Blueprint('main', __name__)

# API blueprint for JSON endpoints
api_bp = Blueprint('api', __name__)


# ==================== Authentication Helpers ====================

def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('main.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """Decorator to require login for API routes (returns JSON error instead of redirect)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Authentication required. Please log in.'}), 401
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('main.login', next=request.url))
        if g.current_user.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@main_bp.before_request
def load_current_user():
    """Load current user before each request."""
    g.current_user = None
    if 'user_id' in session:
        db = get_db_service()
        g.current_user = db.get_user_by_id(session['user_id'])


@main_bp.before_request
def init_page_view_tracking():
    """Initialize page view tracking before each request."""
    g.page_view_id = None


@main_bp.after_request
def track_page_view(response):
    """Log page views for analytics (only for successful HTML page requests)."""
    # Only track successful GET requests for HTML pages
    if (request.method == 'GET' and 
        response.status_code == 200 and 
        response.content_type and 
        'text/html' in response.content_type):
        
        # Skip static files and certain paths
        skip_paths = ['/static/', '/api/', '/favicon', '/_']
        if not any(request.path.startswith(p) for p in skip_paths):
            try:
                db = get_db_service()
                user_id = session.get('user_id')
                session_id = session.get('_id') or getattr(session, 'sid', None)
                
                result = db.log_page_view(
                    page_path=request.path,
                    user_id=user_id,
                    referrer=request.referrer,
                    session_id=str(session_id) if session_id else None
                )
                page_view_id = result['id']
                
                # Store in session for fallback
                session['_current_page_view_id'] = page_view_id
                
                # Inject page view ID into HTML response for JavaScript tracking
                if response.direct_passthrough is False:
                    try:
                        data = response.get_data(as_text=True)
                        # Insert a script tag with the page view ID before </body>
                        inject_script = f'<script>window.__PAGE_VIEW_ID__={page_view_id};</script></body>'
                        data = data.replace('</body>', inject_script)
                        response.set_data(data)
                    except Exception:
                        pass  # If injection fails, session fallback will be used
                        
            except Exception as e:
                # Don't let tracking errors break the response
                current_app.logger.warning(f"Page view tracking error: {e}")
    
    return response


@api_bp.before_request
def api_load_current_user():
    """Load current user before each API request."""
    g.current_user = None
    if 'user_id' in session:
        db = get_db_service()
        g.current_user = db.get_user_by_id(session['user_id'])


@main_bp.context_processor
def inject_user():
    """Inject current user into all templates."""
    return {'current_user': g.current_user}


@main_bp.context_processor
def inject_template_helpers():
    """Inject helper functions for templates."""
    
    def get_file_icon(ext):
        """Get an emoji icon for a file type."""
        ext = (ext or '').lower()
        
        # Document types
        if ext in ['pdf']:
            return '📄'
        elif ext in ['doc', 'docx', 'odt', 'rtf', 'txt']:
            return '📝'
        elif ext in ['xls', 'xlsx', 'ods', 'csv']:
            return '📊'
        elif ext in ['ppt', 'pptx', 'odp']:
            return '📽️'
        # Data/Code
        elif ext in ['json', 'yaml', 'yml', 'xml', 'toml']:
            return '📋'
        elif ext in ['py', 'ipynb', 'r', 'jl', 'm']:
            return '🐍'
        # Scientific
        elif ext in ['kdf', 'gds', 'gdsii']:
            return '🔬'
        elif ext in ['spm', 'afm', 'nid', 'gsf', 'sxm', 'mtrx', 'ibw']:
            return '📈'
        elif ext in ['h5', 'hdf5', 'hdf', 'nc', 'netcdf', 'mat', 'npy', 'npz']:
            return '💾'
        elif ext in ['fits', 'fit', 'cif', 'pdb']:
            return '🧬'
        # Archives
        elif ext in ['zip', 'tar', 'gz', 'bz2', '7z', 'rar']:
            return '📦'
        # Images
        elif ext in ['tif', 'tiff', 'raw', 'dng', 'svg', 'eps', 'ai']:
            return '🖼️'
        # Default
        return '📁'
    
    def format_file_size(bytes):
        """Format file size in human-readable format."""
        if not bytes:
            return ''
        if bytes < 1024:
            return f'{bytes} B'
        if bytes < 1024 * 1024:
            return f'{bytes / 1024:.1f} KB'
        if bytes < 1024 * 1024 * 1024:
            return f'{bytes / (1024 * 1024):.1f} MB'
        return f'{bytes / (1024 * 1024 * 1024):.1f} GB'
    
    return {
        'get_file_icon': get_file_icon,
        'format_file_size': format_file_size,
    }


# ==================== HTML Routes ====================

@main_bp.route('/')
def index():
    """Dashboard page."""
    db = get_db_service()
    stats = db.get_dashboard_stats()
    return render_template('index.html', stats=stats)


@main_bp.route('/search')
def search():
    """Global search page."""
    query = request.args.get('q', '')
    db = get_db_service()
    results = db.global_search(query) if query else {}
    return render_template('search.html', query=query, results=results)


@main_bp.route('/search/advanced')
def advanced_search():
    """Advanced search page with filters."""
    db = get_db_service()
    
    # Get search parameters
    query = request.args.get('q', '')
    entity_types = request.args.getlist('types') or None
    status = request.args.get('status') or None
    lab_id = request.args.get('lab_id', type=int)
    project_id = request.args.get('project_id', type=int)
    created_after = request.args.get('created_after') or None
    created_before = request.args.get('created_before') or None
    page = request.args.get('page', 1, type=int)
    
    # Only run search if we have any criteria
    results = {}
    if query or entity_types or status or lab_id or project_id or created_after or created_before:
        results = db.advanced_search(
            query=query if query else None,
            entity_types=entity_types,
            status=status,
            lab_id=lab_id,
            project_id=project_id,
            created_after=created_after,
            created_before=created_before,
            page=page,
        )
    
    # Get labs and projects for filter dropdowns
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    
    return render_template('advanced_search.html',
        query=query,
        results=results,
        entity_types=entity_types or [],
        status=status,
        lab_id=lab_id,
        project_id=project_id,
        created_after=created_after,
        created_before=created_before,
        page=page,
        labs=labs,
        projects=projects,
    )


# -------------------- Site-Wide Filters --------------------

@main_bp.route('/set-site-filters', methods=['POST'])
def set_site_filters():
    """Set site-wide lab and project filters stored in session."""
    lab_id = request.form.get('lab_id')
    project_id = request.form.get('project_id')
    show_archived = request.form.get('show_archived')
    show_trashed = request.form.get('show_trashed')
    
    # Store in session
    session['filter_lab_id'] = int(lab_id) if lab_id else None
    session['filter_project_id'] = int(project_id) if project_id else None
    session['show_archived'] = bool(show_archived)
    session['show_trashed'] = bool(show_trashed)
    
    # Redirect back to the referring page or index
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/clear-site-filters')
def clear_site_filters():
    """Clear site-wide lab and project filters."""
    session.pop('filter_lab_id', None)
    session.pop('filter_project_id', None)
    session.pop('show_archived', None)
    session.pop('show_trashed', None)
    
    # Redirect back to the referring page or index
    return redirect(request.referrer or url_for('main.index'))


# -------------------- Samples --------------------

@main_bp.route('/samples')
def samples():
    """Samples list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    lab_id = request.args.get('lab_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    db = get_db_service()
    samples_list, total = db.get_samples(
        search=search if search else None,
        status=status if status else None,
        lab_id=lab_id,
        project_id=project_id,
        page=page
    )
    
    # Get labs and projects for filter dropdowns
    labs_list, _ = db.get_labs(per_page=100)
    projects_list = db.get_projects_simple_list()
    
    total_pages = (total + 19) // 20
    
    # Get pinned sample IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'sample')
    
    return render_template('samples.html',
        samples=samples_list,
        labs=labs_list,
        projects=projects_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
        lab_id=lab_id,
        project_id=project_id,
        pinned_ids=pinned_ids
    )


@main_bp.route('/samples/<int:sample_id>')
def sample_detail(sample_id):
    """Sample detail page."""
    db = get_db_service()
    sample = db.get_sample(sample_id)
    if not sample:
        flash('Sample not found', 'error')
        return redirect(url_for('main.samples'))
    images = db.get_entity_images('sample', sample_id)
    attachments = db.get_entity_attachments('sample', sample_id)
    object_location = db.get_object_location('sample', sample_id)
    locations_list = db.get_locations_simple_list()
    return render_template('sample_detail.html', sample=sample, images=images, attachments=attachments,
                           object_type='sample', object_id=sample_id, object_location=object_location, locations_list=locations_list)


@main_bp.route('/samples/new', methods=['GET', 'POST'])
def sample_new():
    """Create new sample page."""
    db = get_db_service()
    
    # Check if a template_id was provided (e.g., from QR code scan)
    template_id = request.args.get('template_id', type=int)
    template = None
    prefilled_sample = None
    
    if template_id:
        template = db.get_template(template_id)
        if template and template['entity_type'] == 'sample':
            # Create a prefilled sample dict from template data
            template_data = template.get('template_data', {})
            prefilled_sample = {
                'name': template_data.get('name', ''),
                'material': template_data.get('material', ''),
                'sample_type': template_data.get('sample_type', ''),
                'substrate': template_data.get('substrate', ''),
                'storage_location': template_data.get('storage_location', ''),
                'description': template_data.get('description', ''),
                'created_by': template_data.get('created_by', ''),
                'status': template_data.get('status', 'active'),
            }
    
    if request.method == 'POST':
        # Get lab_id, project_id and parent_sample_id, converting empty strings to None
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        
        project_id = request.form.get('project_id')
        project_id = int(project_id) if project_id else None
        
        parent_sample_id = request.form.get('parent_sample_id')
        parent_sample_id = int(parent_sample_id) if parent_sample_id else None
        
        data = {
            'sample_id': request.form.get('sample_id'),
            'name': request.form.get('name'),
            'material': request.form.get('material'),
            'sample_type': request.form.get('sample_type'),
            'substrate': request.form.get('substrate'),
            'status': request.form.get('status', 'active'),
            'description': request.form.get('description'),
            'created_by': request.form.get('created_by'),
            'lab_id': lab_id,
            'project_id': project_id,
            'parent_sample_id': parent_sample_id,
        }
        try:
            sample = db.create_sample(data)
            
            # Handle precursors - multiple precursors can be added
            precursor_ids = request.form.getlist('precursor_id[]')
            precursor_roles = request.form.getlist('precursor_role[]')
            precursor_quantities = request.form.getlist('precursor_quantity[]')
            precursor_units = request.form.getlist('precursor_unit[]')
            
            for i, prec_id in enumerate(precursor_ids):
                if prec_id:
                    role = precursor_roles[i] if i < len(precursor_roles) else None
                    quantity = float(precursor_quantities[i]) if i < len(precursor_quantities) and precursor_quantities[i] else None
                    unit = precursor_units[i] if i < len(precursor_units) else None
                    db.add_sample_precursor(
                        sample_id=sample['id'],
                        precursor_id=int(prec_id),
                        quantity_used=quantity,
                        quantity_unit=unit,
                        role=role
                    )
            
            # Handle database location assignment
            db_location_id = request.form.get('db_location_id')
            location_notes = request.form.get('location_notes')
            if db_location_id:
                db.add_object_to_location(
                    location_id=int(db_location_id),
                    object_type='sample',
                    object_id=sample['id'],
                    notes=location_notes,
                    placed_by=g.current_user.get('username') if g.current_user else None
                )
            
            flash(f'Sample {sample["sample_id"]} created successfully', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample['id']))
        except Exception as e:
            flash(f'Error creating sample: {str(e)}', 'error')
    
    # Get dropdown data
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    samples_list = db.get_samples_simple_list()
    precursors = db.get_precursors_simple_list()
    locations = db.get_locations_simple_list()
    
    # Get user defaults
    default_lab_id = None
    default_project_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
        default_project_id = user_prefs.get('default_project_id')
    
    # Use prefilled_sample if we have a template, otherwise create with generated ID
    if prefilled_sample:
        sample_data = prefilled_sample
    else:
        # Generate a suggested sample ID
        next_id = db.generate_next_sample_id()
        sample_data = {'sample_id': next_id}
    
    return render_template('sample_form.html', 
                          sample=sample_data, 
                          action='Create',
                          labs=labs,
                          projects=projects,
                          samples_list=samples_list,
                          precursors=precursors,
                          locations=locations,
                          sample_precursors=[],
                          template=template,
                          default_lab_id=default_lab_id,
                          default_project_id=default_project_id)


@main_bp.route('/samples/<int:sample_id>/edit', methods=['GET', 'POST'])
def sample_edit(sample_id):
    """Edit sample page."""
    db = get_db_service()
    sample = db.get_sample(sample_id)
    
    if not sample:
        flash('Sample not found', 'error')
        return redirect(url_for('main.samples'))
    
    if request.method == 'POST':
        # Get lab_id, project_id and parent_sample_id, converting empty strings to None
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        
        project_id = request.form.get('project_id')
        project_id = int(project_id) if project_id else None
        
        parent_sample_id = request.form.get('parent_sample_id')
        parent_sample_id = int(parent_sample_id) if parent_sample_id else None
        
        data = {
            'name': request.form.get('name'),
            'material': request.form.get('material'),
            'sample_type': request.form.get('sample_type'),
            'substrate': request.form.get('substrate'),
            'status': request.form.get('status'),
            'description': request.form.get('description'),
            'lab_id': lab_id,
            'project_id': project_id,
            'parent_sample_id': parent_sample_id,
        }
        try:
            db.update_sample(sample_id, data)
            
            # Handle precursors - clear existing and re-add from form
            db.clear_sample_precursors(sample_id)
            
            precursor_ids = request.form.getlist('precursor_id[]')
            precursor_roles = request.form.getlist('precursor_role[]')
            precursor_quantities = request.form.getlist('precursor_quantity[]')
            precursor_units = request.form.getlist('precursor_unit[]')
            
            for i, prec_id in enumerate(precursor_ids):
                if prec_id:
                    role = precursor_roles[i] if i < len(precursor_roles) else None
                    quantity = float(precursor_quantities[i]) if i < len(precursor_quantities) and precursor_quantities[i] else None
                    unit = precursor_units[i] if i < len(precursor_units) else None
                    db.add_sample_precursor(
                        sample_id=sample_id,
                        precursor_id=int(prec_id),
                        quantity_used=quantity,
                        quantity_unit=unit,
                        role=role
                    )
            
            # Handle database location assignment
            db_location_id = request.form.get('db_location_id')
            location_notes = request.form.get('location_notes')
            if db_location_id:
                db.add_object_to_location(
                    location_id=int(db_location_id),
                    object_type='sample',
                    object_id=sample_id,
                    notes=location_notes,
                    placed_by=g.current_user.get('username') if g.current_user else None
                )
            else:
                # Remove from any current location if no location selected
                db.remove_object_from_location('sample', sample_id)
            
            flash('Sample updated successfully', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample_id))
        except Exception as e:
            flash(f'Error updating sample: {str(e)}', 'error')
    
    # Get dropdown data
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    samples_list = db.get_samples_simple_list(exclude_id=sample_id)  # Exclude self
    precursors = db.get_precursors_simple_list()
    locations = db.get_locations_simple_list()
    sample_precursors = db.get_sample_precursors(sample_id)
    
    # Get current location for this sample
    current_location = db.get_object_location('sample', sample_id)
    if current_location:
        sample['current_location_id'] = current_location['location_id']
        sample['current_location_notes'] = current_location.get('notes', '')
    
    return render_template('sample_form.html', 
                          sample=sample, 
                          action='Edit',
                          labs=labs,
                          projects=projects,
                          samples_list=samples_list,
                          precursors=precursors,
                          locations=locations,
                          sample_precursors=sample_precursors)


@main_bp.route('/samples/<int:sample_id>/duplicate', methods=['GET', 'POST'])
@login_required
def sample_duplicate(sample_id):
    """Duplicate a sample with a new ID."""
    db = get_db_service()
    original = db.get_sample(sample_id)
    
    if not original:
        flash('Sample not found', 'error')
        return redirect(url_for('main.samples'))
    
    if request.method == 'POST':
        # Get lab_id, project_id and parent_sample_id, converting empty strings to None
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        
        project_id = request.form.get('project_id')
        project_id = int(project_id) if project_id else None
        
        parent_sample_id = request.form.get('parent_sample_id')
        parent_sample_id = int(parent_sample_id) if parent_sample_id else None
        
        data = {
            'sample_id': request.form.get('sample_id'),
            'name': request.form.get('name'),
            'material': request.form.get('material'),
            'sample_type': request.form.get('sample_type'),
            'substrate': request.form.get('substrate'),
            'status': request.form.get('status', 'active'),
            'description': request.form.get('description'),
            'created_by': g.current_user.get('username') if g.current_user else None,
            'lab_id': lab_id,
            'project_id': project_id,
            'parent_sample_id': parent_sample_id or sample_id,  # Default parent to original
        }
        try:
            sample = db.create_sample(data)
            flash(f'Sample {sample["sample_id"]} created from duplicate', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample['id']))
        except Exception as e:
            flash(f'Error creating sample: {str(e)}', 'error')
    
    # Pre-fill form with original data but new ID
    duplicated = original.copy()
    duplicated['sample_id'] = db.generate_next_sample_id('S')
    duplicated['name'] = f"{original['name']} (Copy)"
    duplicated['parent_sample_id'] = sample_id
    
    # Get dropdown data
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    samples_list = db.get_samples_simple_list()
    precursors = db.get_precursors_simple_list()
    
    return render_template('sample_form.html',
        sample=duplicated,
        action='Duplicate',
        labs=labs,
        projects=projects,
        samples_list=samples_list,
        precursors=precursors,
        sample_precursors=[],
    )


@main_bp.route('/samples/<int:sample_id>/delete', methods=['POST'])
@login_required
def sample_delete(sample_id):
    """Move a sample to trash."""
    db = get_db_service()
    sample = db.get_sample(sample_id)
    
    if not sample:
        flash('Sample not found', 'error')
        return redirect(url_for('main.samples'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('sample', sample_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash(f'Sample "{sample["sample_id"]}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving sample to trash'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.samples'))


# -------------------- Fabrication Runs --------------------

@main_bp.route('/samples/<int:sample_id>/fabrication-runs/new', methods=['GET', 'POST'])
@login_required
def fabrication_run_new(sample_id):
    """Add a new fabrication run to a sample."""
    db = get_db_service()
    sample = db.get_sample(sample_id)
    
    if not sample:
        flash('Sample not found', 'error')
        return redirect(url_for('main.samples'))
    
    if request.method == 'POST':
        from datetime import datetime
        
        started_at = None
        started_at_str = request.form.get('started_at')
        if started_at_str:
            try:
                started_at = datetime.fromisoformat(started_at_str)
            except ValueError:
                pass
        
        # Parse procedure parameters and step parameters from form
        actual_parameters = {'procedure_parameters': {}, 'step_parameters': {}}
        
        for key, value in request.form.items():
            if key.startswith('proc_param[') and key.endswith(']'):
                # Extract parameter name from proc_param[param_name]
                param_name = key[11:-1]
                actual_parameters['procedure_parameters'][param_name] = value
            elif key.startswith('step_param['):
                # Extract step index and param name from step_param[idx][param_name]
                import re
                match = re.match(r'step_param\[(\d+)\]\[(.+)\]', key)
                if match:
                    step_idx = match.group(1)
                    param_name = match.group(2)
                    if step_idx not in actual_parameters['step_parameters']:
                        actual_parameters['step_parameters'][step_idx] = {}
                    actual_parameters['step_parameters'][step_idx][param_name] = value
        
        # Only include actual_parameters if there are any
        if not actual_parameters['procedure_parameters'] and not actual_parameters['step_parameters']:
            actual_parameters = None
        
        status = request.form.get('status', 'pending')
        failure_mode = request.form.get('failure_mode') if status == 'failed' else None
        
        data = {
            'sample_id': sample_id,
            'procedure_id': int(request.form.get('procedure_id')),
            'run_number': int(request.form.get('run_number')) if request.form.get('run_number') else None,
            'operator': request.form.get('operator') or g.current_user.get('username'),
            'status': status,
            'failure_mode': failure_mode,
            'started_at': started_at,
            'notes': request.form.get('notes'),
            'actual_parameters': actual_parameters,
        }
        
        try:
            run = db.create_fabrication_run(data, fetch_weather=True)
            
            # Handle precursors consumed
            precursor_ids = request.form.getlist('precursor_id[]')
            precursor_quantities = request.form.getlist('precursor_quantity[]')
            precursor_units = request.form.getlist('precursor_unit[]')
            precursor_notes = request.form.getlist('precursor_notes[]')
            
            precursor_list = []
            for i, prec_id in enumerate(precursor_ids):
                if prec_id:
                    precursor_list.append({
                        'precursor_id': int(prec_id),
                        'quantity_consumed': float(precursor_quantities[i]) if i < len(precursor_quantities) and precursor_quantities[i] else None,
                        'quantity_unit': precursor_units[i] if i < len(precursor_units) else None,
                        'notes': precursor_notes[i] if i < len(precursor_notes) else None,
                    })
            
            if precursor_list:
                db.update_fabrication_run_precursor_list(run['id'], precursor_list)
            
            flash(f'Fabrication run added successfully', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample_id))
        except Exception as e:
            flash(f'Error creating fabrication run: {str(e)}', 'error')
    
    procedures = db.get_procedures_simple_list(include_params=True)
    precursors = db.get_precursors_simple_list()
    
    # Get current datetime for auto-populating started_at
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    
    return render_template('fabrication_run_form.html',
                          sample=sample,
                          procedures=procedures,
                          precursors=precursors,
                          action='Add',
                          run=None,
                          now=now)


@main_bp.route('/fabrication-runs/<int:run_id>/edit', methods=['GET', 'POST'])
@login_required
def fabrication_run_edit(run_id):
    """Edit a fabrication run."""
    db = get_db_service()
    
    # Get the run with its sample
    with db.session_scope() as session:
        from database.models import FabricationRun
        run_obj = session.query(FabricationRun).filter(FabricationRun.id == run_id).first()
        if not run_obj:
            flash('Fabrication run not found', 'error')
            return redirect(url_for('main.samples'))
        
        run = {
            'id': run_obj.id,
            'sample_id': run_obj.sample_id,
            'procedure_id': run_obj.procedure_id,
            'run_number': run_obj.run_number,
            'status': run_obj.status,
            'failure_mode': run_obj.failure_mode,
            'created_by': run_obj.created_by,
            'started_at': run_obj.started_at.isoformat() if run_obj.started_at else None,
            'completed_at': run_obj.completed_at.isoformat() if run_obj.completed_at else None,
            'notes': run_obj.notes,
            'results': run_obj.results,
            'actual_parameters': run_obj.actual_parameters,
        }
        sample_id = run_obj.sample_id
    
    sample = db.get_sample(sample_id)
    
    if request.method == 'POST':
        from datetime import datetime
        
        started_at = None
        started_at_str = request.form.get('started_at')
        if started_at_str:
            try:
                started_at = datetime.fromisoformat(started_at_str)
            except ValueError:
                pass
        
        completed_at = None
        completed_at_str = request.form.get('completed_at')
        if completed_at_str:
            try:
                completed_at = datetime.fromisoformat(completed_at_str)
            except ValueError:
                pass
        
        # Parse procedure parameters and step parameters from form
        actual_parameters = {'procedure_parameters': {}, 'step_parameters': {}}
        
        for key, value in request.form.items():
            if key.startswith('proc_param[') and key.endswith(']'):
                # Extract parameter name from proc_param[param_name]
                param_name = key[11:-1]
                actual_parameters['procedure_parameters'][param_name] = value
            elif key.startswith('step_param['):
                # Extract step index and param name from step_param[idx][param_name]
                import re
                match = re.match(r'step_param\[(\d+)\]\[(.+)\]', key)
                if match:
                    step_idx = match.group(1)
                    param_name = match.group(2)
                    if step_idx not in actual_parameters['step_parameters']:
                        actual_parameters['step_parameters'][step_idx] = {}
                    actual_parameters['step_parameters'][step_idx][param_name] = value
        
        # Only include actual_parameters if there are any
        if not actual_parameters['procedure_parameters'] and not actual_parameters['step_parameters']:
            actual_parameters = None
        
        status = request.form.get('status', 'pending')
        failure_mode = request.form.get('failure_mode') if status == 'failed' else None
        
        data = {
            'procedure_id': int(request.form.get('procedure_id')),
            'run_number': int(request.form.get('run_number')) if request.form.get('run_number') else None,
            'operator': request.form.get('operator'),
            'status': status,
            'failure_mode': failure_mode,
            'started_at': started_at,
            'completed_at': completed_at,
            'notes': request.form.get('notes'),
            'results': request.form.get('results'),
            'actual_parameters': actual_parameters,
        }
        
        try:
            db.update_fabrication_run(run_id, data)
            
            # Handle precursors consumed
            precursor_ids = request.form.getlist('precursor_id[]')
            precursor_quantities = request.form.getlist('precursor_quantity[]')
            precursor_units = request.form.getlist('precursor_unit[]')
            precursor_notes = request.form.getlist('precursor_notes[]')
            
            precursor_list = []
            for i, prec_id in enumerate(precursor_ids):
                if prec_id:
                    precursor_list.append({
                        'precursor_id': int(prec_id),
                        'quantity_consumed': float(precursor_quantities[i]) if i < len(precursor_quantities) and precursor_quantities[i] else None,
                        'quantity_unit': precursor_units[i] if i < len(precursor_units) else None,
                        'notes': precursor_notes[i] if i < len(precursor_notes) else None,
                    })
            
            db.update_fabrication_run_precursor_list(run_id, precursor_list)
            
            flash('Fabrication run updated successfully', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample_id))
        except Exception as e:
            flash(f'Error updating fabrication run: {str(e)}', 'error')
    
    procedures = db.get_procedures_simple_list(include_params=True)
    precursors = db.get_precursors_simple_list()
    run_precursors = db.get_fabrication_run_precursors(run_id)
    
    return render_template('fabrication_run_form.html',
                          sample=sample,
                          procedures=procedures,
                          precursors=precursors,
                          run_precursors=run_precursors,
                          action='Edit',
                          run=run)


@main_bp.route('/fabrication-runs/<int:run_id>')
def fabrication_run_detail(run_id):
    """View a fabrication run detail page."""
    db = get_db_service()
    
    with db.session_scope() as session:
        from database.models import FabricationRun, Sample, Procedure
        from sqlalchemy.orm import joinedload
        
        run_obj = session.query(FabricationRun).options(
            joinedload(FabricationRun.sample),
            joinedload(FabricationRun.procedure),
        ).filter(FabricationRun.id == run_id).first()
        
        if not run_obj:
            flash('Fabrication run not found', 'error')
            return redirect(url_for('main.samples'))
        
        run = {
            'id': run_obj.id,
            'sample_id': run_obj.sample_id,
            'procedure_id': run_obj.procedure_id,
            'run_number': run_obj.run_number,
            'status': run_obj.status,
            'created_by': run_obj.created_by,
            'started_at': run_obj.started_at.isoformat() if run_obj.started_at else None,
            'completed_at': run_obj.completed_at.isoformat() if run_obj.completed_at else None,
            'notes': run_obj.notes,
            'results': run_obj.results,
            'actual_parameters': run_obj.actual_parameters,
            'weather_conditions': run_obj.weather_conditions,
            'created_at': run_obj.created_at.isoformat() if run_obj.created_at else None,
        }
        
        sample = {
            'id': run_obj.sample.id,
            'sample_id': run_obj.sample.sample_id,
            'name': run_obj.sample.name,
        } if run_obj.sample else None
        
        procedure = None
        if run_obj.procedure:
            procedure = {
                'id': run_obj.procedure.id,
                'name': run_obj.procedure.name,
                'procedure_type': run_obj.procedure.procedure_type,
                'version': run_obj.procedure.version,
                'steps': run_obj.procedure.steps,
                'parameters': run_obj.procedure.parameters,
            }
    
    # Get images, attachments and precursors
    images = db.get_entity_images('fabrication_run', run_id)
    attachments = db.get_entity_attachments('fabrication_run', run_id)
    precursors = db.get_fabrication_run_precursors(run_id)
    
    return render_template('fabrication_run_detail.html',
                          run=run,
                          sample=sample,
                          procedure=procedure,
                          images=images,
                          attachments=attachments,
                          precursors=precursors,
                          entity_type='fabrication_run',
                          entity_id=run_id)


@main_bp.route('/fabrication-runs/<int:run_id>/delete', methods=['POST'])
@login_required
def fabrication_run_delete(run_id):
    """Move a fabrication run to trash."""
    db = get_db_service()
    
    # Get sample_id before trashing
    with db.session_scope() as session:
        from database.models import FabricationRun
        run = session.query(FabricationRun).filter(FabricationRun.id == run_id).first()
        if not run:
            flash('Fabrication run not found', 'error')
            return redirect(url_for('main.samples'))
        sample_id = run.sample_id
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('fabrication_run', run_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash('Fabrication run moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving fabrication run to trash'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.sample_detail', sample_id=sample_id))


@main_bp.route('/procedures/<int:procedure_id>/run', methods=['GET', 'POST'])
@login_required
def fabrication_run_from_procedure(procedure_id):
    """Start a fabrication run from a procedure, applying to multiple samples."""
    db = get_db_service()
    procedure = db.get_procedure(procedure_id)
    
    if not procedure:
        flash('Procedure not found', 'error')
        return redirect(url_for('main.procedures'))
    
    if request.method == 'POST':
        from datetime import datetime
        import re
        
        # Get selected sample IDs
        sample_ids = request.form.getlist('sample_ids')
        if not sample_ids:
            flash('Please select at least one sample', 'error')
        else:
            started_at = None
            started_at_str = request.form.get('started_at')
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(started_at_str)
                except ValueError:
                    pass
            
            operator = request.form.get('operator') or g.current_user.get('username')
            status = request.form.get('status', 'pending')
            notes = request.form.get('notes')
            run_number = int(request.form.get('run_number')) if request.form.get('run_number') else None
            
            # Parse actual_parameters from form
            actual_parameters = {'procedure_parameters': {}, 'step_parameters': {}}
            
            # Parse procedure-level parameters: proc_param[name]
            proc_param_pattern = re.compile(r'^proc_param\[(.+)\]$')
            for key, value in request.form.items():
                match = proc_param_pattern.match(key)
                if match:
                    param_name = match.group(1)
                    actual_parameters['procedure_parameters'][param_name] = value
            
            # Parse step-level parameters: step_param[idx][name]
            step_param_pattern = re.compile(r'^step_param\[(\d+)\]\[(.+)\]$')
            for key, value in request.form.items():
                match = step_param_pattern.match(key)
                if match:
                    step_idx = match.group(1)
                    param_name = match.group(2)
                    if step_idx not in actual_parameters['step_parameters']:
                        actual_parameters['step_parameters'][step_idx] = {}
                    actual_parameters['step_parameters'][step_idx][param_name] = value
            
            # Create a fabrication run for each selected sample
            created_count = 0
            for sample_id in sample_ids:
                try:
                    data = {
                        'sample_id': int(sample_id),
                        'procedure_id': procedure_id,
                        'run_number': run_number,
                        'operator': operator,
                        'status': status,
                        'started_at': started_at,
                        'notes': notes,
                        'actual_parameters': actual_parameters,
                    }
                    db.create_fabrication_run(data, fetch_weather=(created_count == 0))  # Fetch weather only once
                    created_count += 1
                except Exception as e:
                    flash(f'Error creating run for sample {sample_id}: {str(e)}', 'error')
            
            if created_count > 0:
                flash(f'Created {created_count} fabrication run(s) successfully', 'success')
                return redirect(url_for('main.procedure_detail', procedure_id=procedure_id))
    
    samples = db.get_samples_simple_list()
    
    # Get current datetime for auto-populating started_at
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    
    return render_template('fabrication_run_from_procedure.html',
                          procedure=procedure,
                          samples=samples,
                          now=now)


# -------------------- Fabrication Runs --------------------

@main_bp.route('/fabrication-runs')
def fabrication_runs():
    """Fabrication runs list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    db = get_db_service()
    runs_list, total = db.get_fabrication_runs(
        search=search if search else None,
        status=status if status else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'fabrication_run')
    
    return render_template('fabrication_runs.html',
        runs=runs_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
        pinned_ids=pinned_ids
    )


# -------------------- Scans --------------------

@main_bp.route('/scans')
def scans():
    """Scans list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    lab_id = request.args.get('lab_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    db = get_db_service()
    scans_list, total = db.get_scans(
        search=search if search else None,
        status=status if status else None,
        lab_id=lab_id,
        project_id=project_id,
        page=page
    )
    
    # Get labs and projects for filter dropdowns
    labs_list, _ = db.get_labs(per_page=100)
    projects_list = db.get_projects_simple_list()
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'scan')
    
    return render_template('scans.html',
        scans=scans_list,
        labs=labs_list,
        projects=projects_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
        lab_id=lab_id,
        project_id=project_id,
        pinned_ids=pinned_ids
    )


@main_bp.route('/scans/<int:scan_id>')
def scan_detail(scan_id):
    """Scan detail page."""
    db = get_db_service()
    scan = db.get_scan(scan_id)
    if not scan:
        flash('Scan not found', 'error')
        return redirect(url_for('main.scans'))
    
    # Get data points for visualization
    data_points = db.get_scan_data_points(scan_id)
    
    # Get visualization data organized by measurement object
    visualization_data = db.get_visualization_data(scan_id)
    
    # Get samples and projects for the edit links modal
    samples = db.get_samples_simple_list()
    projects = db.get_projects_simple_list()
    
    return render_template('scan_detail.html', 
                          scan=scan, 
                          data_points=data_points,
                          visualization_data=visualization_data,
                          samples=samples,
                          projects=projects)


@main_bp.route('/scans/<int:scan_id>/download-csv')
def download_scan_csv(scan_id):
    """Download scan data as CSV file."""
    import csv
    from io import StringIO
    
    db = get_db_service()
    scan = db.get_scan(scan_id)
    if not scan:
        flash('Scan not found', 'error')
        return redirect(url_for('main.scans'))
    
    # Get visualization data which has all measurement data organized
    visualization_data = db.get_visualization_data(scan_id)
    
    # Create CSV content
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header info
    writer.writerow([f"# Scan: {scan.get('scan_id', scan_id)}"])
    writer.writerow([f"# Name: {scan.get('name', 'Unnamed')}"])
    writer.writerow([f"# Status: {scan.get('status', 'unknown')}"])
    writer.writerow([f"# Created: {scan.get('created_at', '')}"])
    writer.writerow([])
    
    # Write data for each measurement object
    for name, data in visualization_data.items():
        writer.writerow([f"# Measurement: {name}"])
        
        columns = data.get('columns', [])
        if columns:
            writer.writerow(['index'] + columns)
        else:
            writer.writerow(['index', 'x', 'y'])
        
        all_values = data.get('all_values', [])
        for row in all_values:
            if columns:
                writer.writerow([row.get('sequence_index', '')] + [row.get(col, '') for col in columns])
            else:
                writer.writerow([row.get('sequence_index', ''), row.get('x', ''), row.get('y', '')])
        
        writer.writerow([])
    
    # Create response
    output.seek(0)
    filename = f"scan_{scan.get('scan_id', scan_id)}.csv"
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@main_bp.route('/scans/<int:scan_id>/delete', methods=['POST'])
@login_required
def scan_delete(scan_id):
    """Move a scan to trash."""
    db = get_db_service()
    scan = db.get_scan(scan_id)
    
    if not scan:
        flash('Scan not found', 'error')
        return redirect(url_for('main.scans'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('scan', scan_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash(f'Scan "{scan.get("name", scan_id)}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving scan to trash'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.scans'))


@main_bp.route('/scans/<int:scan_id>/edit-links', methods=['POST'])
@login_required
def scan_edit_links(scan_id):
    """Edit sample and project links for a scan."""
    db = get_db_service()
    scan = db.get_scan(scan_id)
    
    if not scan:
        flash('Scan not found', 'error')
        return redirect(url_for('main.scans'))
    
    try:
        # Get form values - empty string means "None" (unlink)
        sample_id_str = request.form.get('sample_id', '')
        project_id_str = request.form.get('project_id', '')
        
        data = {}
        
        # Handle sample_id - convert to int or None
        if sample_id_str == '':
            data['sample_id'] = None
        else:
            data['sample_id'] = int(sample_id_str)
        
        # Handle project_id - convert to int or None
        if project_id_str == '':
            data['project_id'] = None
        else:
            data['project_id'] = int(project_id_str)
        
        updated = db.update_scan(scan_id, data)
        if updated:
            flash('Scan links updated successfully', 'success')
        else:
            flash('Error updating scan links', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.scan_detail', scan_id=scan_id))


# -------------------- Queues --------------------

@main_bp.route('/queues')
def queues():
    """Queues list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    lab_id = request.args.get('lab_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    db = get_db_service()
    queues_list, total = db.get_queues(
        search=search if search else None,
        status=status if status else None,
        lab_id=lab_id,
        project_id=project_id,
        page=page
    )
    
    # Get labs and projects for filter dropdowns
    labs_list, _ = db.get_labs(per_page=100)
    projects_list = db.get_projects_simple_list()
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'queue')
    
    return render_template('queues.html',
        queues=queues_list,
        labs=labs_list,
        projects=projects_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
        lab_id=lab_id,
        project_id=project_id,
        pinned_ids=pinned_ids
    )


@main_bp.route('/queues/<int:queue_id>')
def queue_detail(queue_id):
    """Queue detail page."""
    db = get_db_service()
    queue = db.get_queue(queue_id)
    if not queue:
        flash('Queue not found', 'error')
        return redirect(url_for('main.queues'))
    
    # Get samples and projects for the edit links modal
    samples = db.get_samples_simple_list()
    projects = db.get_projects_simple_list()
    
    return render_template('queue_detail.html', queue=queue, samples=samples, projects=projects)


@main_bp.route('/queues/<int:queue_id>/delete', methods=['POST'])
@login_required
def queue_delete(queue_id):
    """Move a queue to trash (cascades to scans)."""
    db = get_db_service()
    queue = db.get_queue(queue_id)
    
    if not queue:
        flash('Queue not found', 'error')
        return redirect(url_for('main.queues'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('queue', queue_id, trashed_by=username, cascade=True)
        
        if result['success']:
            flash(f'Queue "{queue.get("name", queue_id)}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving queue to trash'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.queues'))


@main_bp.route('/queues/<int:queue_id>/edit-links', methods=['POST'])
@login_required
def queue_edit_links(queue_id):
    """Edit sample and project links for a queue."""
    db = get_db_service()
    queue = db.get_queue(queue_id)
    
    if not queue:
        flash('Queue not found', 'error')
        return redirect(url_for('main.queues'))
    
    try:
        # Get form values - empty string means "None" (unlink)
        sample_id_str = request.form.get('sample_id', '')
        project_id_str = request.form.get('project_id', '')
        
        data = {}
        
        # Handle sample_id - convert to int or None
        if sample_id_str == '':
            data['sample_id'] = None
        else:
            data['sample_id'] = int(sample_id_str)
        
        # Handle project_id - convert to int or None
        if project_id_str == '':
            data['project_id'] = None
        else:
            data['project_id'] = int(project_id_str)
        
        updated = db.update_queue(queue_id, data)
        if updated:
            flash('Queue links updated successfully', 'success')
        else:
            flash('Error updating queue links', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.queue_detail', queue_id=queue_id))


# -------------------- Equipment --------------------

@main_bp.route('/equipment')
def equipment():
    """Equipment list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    lab_id = request.args.get('lab_id', type=int)
    
    db = get_db_service()
    equipment_list, total = db.get_equipment_list(
        search=search if search else None,
        status=status if status else None,
        lab_id=lab_id,
        page=page
    )
    
    # Get labs for filter dropdown
    labs_list, _ = db.get_labs(per_page=100)
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'equipment')
    
    return render_template('equipment.html',
        equipment=equipment_list,
        labs=labs_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
        lab_id=lab_id,
        pinned_ids=pinned_ids
    )


@main_bp.route('/equipment/<int:equipment_id>')
def equipment_detail(equipment_id):
    """Equipment detail page."""
    db = get_db_service()
    item = db.get_equipment(equipment_id)
    if not item:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    # Check and trigger any due maintenance tasks
    db.check_and_trigger_maintenance_tasks()
    
    # Get maintenance tasks for this equipment
    maintenance_tasks = db.get_maintenance_tasks(equipment_id)
    
    # Get child instruments (instruments that belong to this equipment)
    child_instruments, _ = db.get_instruments_list(equipment_id=equipment_id, per_page=100)
    
    # Get recent issues for this equipment
    recent_issues, _ = db.get_equipment_issues(equipment_id=equipment_id, per_page=5)
    
    # Get available instruments (not assigned to any equipment) for linking
    available_instruments, _ = db.get_instruments_list(no_equipment=True, per_page=500)
    
    # Get images and attachments
    images = db.get_entity_images('equipment', equipment_id)
    attachments = db.get_entity_attachments('equipment', equipment_id)
    
    # Get location data
    object_location = db.get_object_location('equipment', equipment_id)
    locations_list = db.get_locations_simple_list()
    
    return render_template('equipment_detail.html', 
        equipment=item,
        maintenance_tasks=maintenance_tasks,
        child_instruments=child_instruments,
        recent_issues=recent_issues,
        available_instruments=available_instruments,
        images=images,
        attachments=attachments,
        entity_type='equipment',
        entity_id=equipment_id,
        object_type='equipment',
        object_id=equipment_id,
        object_location=object_location,
        locations_list=locations_list
    )


@main_bp.route('/equipment/<int:equipment_id>/link-instrument', methods=['POST'])
def equipment_link_instrument(equipment_id):
    """Link an existing instrument to this equipment."""
    db = get_db_service()
    
    # Verify equipment exists
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    instrument_id = request.form.get('instrument_id', type=int)
    if not instrument_id:
        flash('Please select an instrument to link', 'warning')
        return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))
    
    # Get the instrument
    instrument = db.get_instrument(instrument_id)
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))
    
    # Check if already linked to another equipment
    if instrument.get('equipment_id') and instrument['equipment_id'] != equipment_id:
        flash('This instrument is already linked to another equipment', 'warning')
        return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))
    
    # Update the instrument to link it to this equipment
    db.update_instrument(instrument_id, {'equipment_id': equipment_id})
    flash(f'Instrument "{instrument["name"]}" linked to this equipment', 'success')
    return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))


@main_bp.route('/equipment/<int:equipment_id>/unlink-instrument/<int:instrument_id>', methods=['POST'])
def equipment_unlink_instrument(equipment_id, instrument_id):
    """Unlink an instrument from this equipment."""
    db = get_db_service()
    
    # Verify equipment exists
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    # Get the instrument
    instrument = db.get_instrument(instrument_id)
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))
    
    # Check if it belongs to this equipment
    if instrument.get('equipment_id') != equipment_id:
        flash('This instrument is not linked to this equipment', 'warning')
        return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))
    
    # Update the instrument to unlink it
    db.update_instrument(instrument_id, {'equipment_id': None})
    flash(f'Instrument "{instrument["name"]}" unlinked from this equipment', 'success')
    return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))


@main_bp.route('/equipment/new', methods=['GET', 'POST'])
def equipment_new():
    """Create new equipment page."""
    db = get_db_service()
    
    return_url = request.args.get('return_url') or request.referrer
    
    # Check if a template_id was provided (e.g., from QR code scan)
    template_id = request.args.get('template_id', type=int)
    template = None
    prefilled = None
    
    if template_id:
        template = db.get_template(template_id)
        if template and template['entity_type'] == 'equipment':
            td = template.get('template_data', {})
            prefilled = {
                'name': td.get('name', ''),
                'equipment_type': td.get('equipment_type', ''),
                'pybirch_class': td.get('pybirch_class', ''),
                'manufacturer': td.get('manufacturer', ''),
                'model': td.get('model', ''),
                'serial_number': td.get('serial_number', ''),
                'location': td.get('location', ''),
                'status': td.get('status', 'available'),
            }
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        db_location_id = request.form.get('db_location_id')
        location_notes = request.form.get('location_notes')
        owner_id = request.form.get('owner_id')
        maintenance_interval = request.form.get('maintenance_interval_days')
        
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'equipment_type': request.form.get('equipment_type'),
            'pybirch_class': request.form.get('pybirch_class'),
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'status': request.form.get('status', 'available'),
            'lab_id': int(lab_id) if lab_id else None,
            'owner_id': int(owner_id) if owner_id else None,
            'purchase_date': request.form.get('purchase_date') or None,
            'warranty_expiration': request.form.get('warranty_expiration') or None,
            'last_maintenance_date': request.form.get('last_maintenance_date') or None,
            'next_maintenance_date': request.form.get('next_maintenance_date') or None,
            'maintenance_interval_days': int(maintenance_interval) if maintenance_interval else None,
            'documentation_url': request.form.get('documentation_url') or None,
        }
        try:
            item = db.create_equipment(data)
            
            # Handle database location assignment
            if db_location_id:
                db.add_object_to_location(
                    location_id=int(db_location_id),
                    object_type='equipment',
                    object_id=item['id'],
                    notes=location_notes,
                    placed_by=g.current_user.get('username') if g.current_user else None
                )
            
            flash(f'Equipment {item["name"]} created successfully', 'success')
            return redirect(url_for('main.equipment_detail', equipment_id=item['id']))
        except Exception as e:
            flash(f'Error creating equipment: {str(e)}', 'error')
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    # Get locations for dropdown
    locations = db.get_locations_simple_list()
    
    # Get users for owner dropdown
    users, _ = db.get_users(per_page=1000)
    
    # Get user defaults
    default_lab_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
    
    return render_template('equipment_form.html', equipment=prefilled, action='Create', template=template, labs=labs, locations=locations, users=users, default_lab_id=default_lab_id, return_url=return_url)


@main_bp.route('/equipment/<int:equipment_id>/edit', methods=['GET', 'POST'])
def equipment_edit(equipment_id):
    """Edit equipment page."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    return_url = request.args.get('return_url') or request.referrer
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        db_location_id = request.form.get('db_location_id')
        location_notes = request.form.get('location_notes')
        owner_id = request.form.get('owner_id')
        maintenance_interval = request.form.get('maintenance_interval_days')
        
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'equipment_type': request.form.get('equipment_type'),
            'pybirch_class': request.form.get('pybirch_class'),
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'status': request.form.get('status', 'available'),
            'lab_id': int(lab_id) if lab_id else None,
            'owner_id': int(owner_id) if owner_id else None,
            'purchase_date': request.form.get('purchase_date') or None,
            'warranty_expiration': request.form.get('warranty_expiration') or None,
            'last_maintenance_date': request.form.get('last_maintenance_date') or None,
            'next_maintenance_date': request.form.get('next_maintenance_date') or None,
            'maintenance_interval_days': int(maintenance_interval) if maintenance_interval else None,
            'documentation_url': request.form.get('documentation_url') or None,
        }
        try:
            updated = db.update_equipment(equipment_id, data)
            
            # Handle database location assignment
            if db_location_id:
                db.add_object_to_location(
                    location_id=int(db_location_id),
                    object_type='equipment',
                    object_id=equipment_id,
                    notes=location_notes,
                    placed_by=g.current_user.get('username') if g.current_user else None
                )
            else:
                # Remove from any current location if no location selected
                db.remove_object_from_location('equipment', equipment_id)
            
            flash(f'Equipment "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))
        except Exception as e:
            flash(f'Error updating equipment: {str(e)}', 'error')
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    # Get locations for dropdown
    locations = db.get_locations_simple_list()
    
    # Get users for owner dropdown
    users, _ = db.get_users(per_page=1000)
    
    # Get current location for this equipment
    current_location = db.get_object_location('equipment', equipment_id)
    if current_location:
        equipment['current_location_id'] = current_location['location_id']
        equipment['current_location_notes'] = current_location.get('notes', '')
    
    return render_template('equipment_form.html', equipment=equipment, action='Edit', labs=labs, locations=locations, users=users, return_url=return_url)


@main_bp.route('/equipment/<int:equipment_id>/duplicate', methods=['GET', 'POST'])
@login_required
def equipment_duplicate(equipment_id):
    """Duplicate equipment with a new ID."""
    db = get_db_service()
    original = db.get_equipment(equipment_id)
    
    if not original:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        data = {
            'name': request.form.get('name'),
            'equipment_type': request.form.get('equipment_type'),
            'pybirch_class': request.form.get('pybirch_class'),
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'status': request.form.get('status', 'available'),
            'lab_id': int(lab_id) if lab_id else None,
        }
        try:
            item = db.create_equipment(data)
            flash(f'Equipment "{item["name"]}" created from duplicate', 'success')
            return redirect(url_for('main.equipment_detail', equipment_id=item['id']))
        except Exception as e:
            flash(f'Error creating equipment: {str(e)}', 'error')
    
    # Pre-fill form with original data but new name
    duplicated = original.copy()
    duplicated['name'] = f"{original['name']} (Copy)"
    duplicated['serial_number'] = ''  # Clear serial number for duplicate
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    return render_template('equipment_form.html',
        equipment=duplicated,
        action='Duplicate',
        labs=labs,
    )


@main_bp.route('/equipment/<int:equipment_id>/delete', methods=['POST'])
@login_required
def equipment_delete(equipment_id):
    """Move equipment to trash."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('equipment', equipment_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash(f'Equipment "{equipment["name"]}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving equipment to trash'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.equipment'))


@main_bp.route('/equipment/<int:equipment_id>/upload-image', methods=['POST'])
@login_required
def equipment_image_upload(equipment_id):
    """Upload an image for equipment."""
    import os
    from werkzeug.utils import secure_filename
    
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        return jsonify({'success': False, 'error': 'Equipment not found'}), 404
    
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    
    try:
        # Save the file
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'equipment')
        os.makedirs(upload_folder, exist_ok=True)
        
        filename = secure_filename(f"equipment_{equipment_id}_{file.filename}")
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Get file info
        file_size = os.path.getsize(filepath)
        mime_type = file.content_type
        
        # Check if this is the first image (make it primary)
        existing_images = db.get_equipment_images(equipment_id)
        is_primary = len(existing_images) == 0
        
        # Add image record to database
        image_record = db.add_equipment_image(
            equipment_id=equipment_id,
            filename=filename,
            file_path=f"/static/uploads/equipment/{filename}",
            original_filename=file.filename,
            file_size=file_size,
            mime_type=mime_type,
            is_primary=is_primary,
            uploaded_by=g.current_user.get('username') if g.current_user else None
        )
        
        return jsonify({'success': True, 'image': image_record})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/equipment/<int:equipment_id>/images/<int:image_id>/set-primary', methods=['POST'])
@login_required
def equipment_image_set_primary(equipment_id, image_id):
    """Set an image as the primary image for equipment."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    try:
        db.set_primary_equipment_image(equipment_id, image_id)
        flash('Primary image updated', 'success')
    except Exception as e:
        flash(f'Error setting primary image: {str(e)}', 'error')
    
    return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))


@main_bp.route('/equipment/<int:equipment_id>/images/<int:image_id>/delete', methods=['POST'])
@login_required
def equipment_image_delete(equipment_id, image_id):
    """Delete an equipment image."""
    import os
    
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    try:
        # Get image info before deleting
        images = db.get_equipment_images(equipment_id)
        image = next((img for img in images if img['id'] == image_id), None)
        
        if image:
            # Delete the file
            file_path = os.path.join(current_app.root_path, image['file_path'].lstrip('/'))
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete database record
            db.delete_equipment_image(image_id)
            flash('Image deleted', 'success')
        else:
            flash('Image not found', 'error')
    except Exception as e:
        flash(f'Error deleting image: {str(e)}', 'error')
    
    return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))


# -------------------- Equipment Issues --------------------

@main_bp.route('/equipment/<int:equipment_id>/issues')
def equipment_issues(equipment_id):
    """List issues for a specific piece of equipment."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    issues, total = db.get_equipment_issues(
        equipment_id=equipment_id,
        status=status if status else None,
        priority=priority if priority else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    return render_template('equipment_issues.html',
        equipment=equipment,
        issues=issues,
        page=page,
        total_pages=total_pages,
        total=total,
        status=status,
        priority=priority,
    )


@main_bp.route('/equipment/<int:equipment_id>/issues/<int:issue_id>')
def equipment_issue_detail(equipment_id, issue_id):
    """View a specific equipment issue."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    issue = db.get_equipment_issue(issue_id)
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('main.equipment_issues', equipment_id=equipment_id))
    
    # Get users for assignee dropdown
    users, _ = db.get_users(per_page=1000)
    
    # Get images and attachments for this issue
    images = db.get_entity_images('equipment_issue', issue_id)
    attachments = db.get_entity_attachments('equipment_issue', issue_id)
    
    # Get update history for timeline
    updates = db.get_issue_updates('equipment_issue', issue_id)
    
    return render_template('equipment_issue_detail.html',
        equipment=equipment,
        issue=issue,
        users=users,
        images=images,
        attachments=attachments,
        entity_type='equipment_issue',
        entity_id=issue_id,
        issue_type='equipment_issue',
        issue_id=issue_id,
        updates=updates,
    )


@main_bp.route('/equipment/<int:equipment_id>/issues/new', methods=['GET', 'POST'])
@login_required
def equipment_issue_new(equipment_id):
    """Create a new issue for equipment."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    if request.method == 'POST':
        assignee_id = request.form.get('assignee_id')
        data = {
            'equipment_id': equipment_id,
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'priority': request.form.get('priority', 'medium'),
            'category': request.form.get('category'),
            'status': 'open',
            'reported_by': g.current_user.get('username') if g.current_user else None,
            'assignee_id': int(assignee_id) if assignee_id else None,
        }
        
        try:
            issue = db.create_equipment_issue(data)
            flash(f'Issue "{issue["title"]}" reported successfully', 'success')
            return redirect(url_for('main.equipment_issue_detail', equipment_id=equipment_id, issue_id=issue['id']))
        except Exception as e:
            flash(f'Error reporting issue: {str(e)}', 'error')
    
    # Get users for assignee dropdown
    users, _ = db.get_users(per_page=1000)
    
    # Default assignee to equipment owner if available
    default_assignee_id = equipment.get('owner_id') if equipment else None
    
    return render_template('equipment_issue_form.html',
        equipment=equipment,
        issue=None,
        action='Report',
        users=users,
        default_assignee_id=default_assignee_id,
    )


@main_bp.route('/equipment/<int:equipment_id>/issues/<int:issue_id>/edit', methods=['GET', 'POST'])
@login_required
def equipment_issue_edit(equipment_id, issue_id):
    """Edit an equipment issue."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    issue = db.get_equipment_issue(issue_id)
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('main.equipment_issues', equipment_id=equipment_id))
    
    if request.method == 'POST':
        assignee_id = request.form.get('assignee_id')
        data = {
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'priority': request.form.get('priority', 'medium'),
            'category': request.form.get('category'),
            'status': request.form.get('status', 'open'),
            'resolution': request.form.get('resolution'),
            'assignee_id': int(assignee_id) if assignee_id else None,
        }
        
        try:
            db.update_equipment_issue(issue_id, data)
            flash(f'Issue updated successfully', 'success')
            return redirect(url_for('main.equipment_issue_detail', equipment_id=equipment_id, issue_id=issue_id))
        except Exception as e:
            flash(f'Error updating issue: {str(e)}', 'error')
    
    # Get users for assignee dropdown
    users, _ = db.get_users(per_page=1000)
    
    return render_template('equipment_issue_form.html',
        equipment=equipment,
        issue=issue,
        action='Edit',
        users=users,
    )


@main_bp.route('/equipment/<int:equipment_id>/issues/<int:issue_id>/status', methods=['POST'])
@login_required
def equipment_issue_update_status(equipment_id, issue_id):
    """Update equipment issue status (quick update without full edit)."""
    db = get_db_service()
    
    issue = db.get_equipment_issue(issue_id)
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('main.equipment_issues', equipment_id=equipment_id))
    
    old_status = issue.get('status')
    new_status = request.form.get('status')
    resolution_note = request.form.get('resolution')
    
    data = {
        'status': new_status,
    }
    
    assignee_id = request.form.get('assignee_id')
    if assignee_id:
        data['assignee_id'] = int(assignee_id)
    else:
        data['assignee_id'] = None
    
    # Handle resolved_at based on status change
    from datetime import datetime
    if new_status in ['resolved', 'closed'] and old_status not in ['resolved', 'closed']:
        data['resolved_at'] = datetime.utcnow()
    
    try:
        db.update_equipment_issue(issue_id, data)
        
        # Create an update entry if there's a status change or resolution note
        if old_status != new_status or resolution_note:
            author_name = None
            author_id = None
            if g.current_user:
                author_name = g.current_user.get('name') or g.current_user.get('username')
                author_id = g.current_user.get('id')
            
            update_type = 'status_change' if old_status != new_status else 'comment'
            if resolution_note and new_status in ['resolved', 'closed']:
                update_type = 'resolution'
            
            db.create_issue_update({
                'issue_type': 'equipment_issue',
                'issue_id': issue_id,
                'update_type': update_type,
                'content': resolution_note,
                'old_status': old_status if old_status != new_status else None,
                'new_status': new_status if old_status != new_status else None,
                'author_id': author_id,
                'author_name': author_name,
            })
        
        flash('Issue status updated', 'success')
    except Exception as e:
        flash(f'Error updating issue: {str(e)}', 'error')
    
    return redirect(url_for('main.equipment_issue_detail', equipment_id=equipment_id, issue_id=issue_id))


@main_bp.route('/equipment/issues')
def all_equipment_issues():
    """List all equipment issues across all equipment."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    category = request.args.get('category', '')
    
    db = get_db_service()
    issues, total = db.get_equipment_issues(
        status=status if status else None,
        priority=priority if priority else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    return render_template('all_equipment_issues.html',
        issues=issues,
        page=page,
        total_pages=total_pages,
        total=total,
        status=status,
        priority=priority,
        category=category,
    )


# -------------------- Maintenance Tasks --------------------

@main_bp.route('/equipment/<int:equipment_id>/maintenance')
def equipment_maintenance_tasks(equipment_id):
    """List maintenance tasks for equipment."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    # Check and trigger any due maintenance tasks
    db.check_and_trigger_maintenance_tasks()
    
    tasks = db.get_maintenance_tasks(equipment_id)
    users, _ = db.get_users()
    
    return render_template('equipment_maintenance_tasks.html',
        equipment=equipment,
        tasks=tasks,
        users=users,
    )


@main_bp.route('/equipment/<int:equipment_id>/maintenance/new', methods=['GET', 'POST'])
@login_required
def equipment_maintenance_task_new(equipment_id):
    """Create a new maintenance task."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    if request.method == 'POST':
        data = {
            'equipment_id': equipment_id,
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'interval_days': int(request.form.get('interval_days', 30)),
            'issue_title': request.form.get('issue_title') or request.form.get('name'),
            'issue_description': request.form.get('issue_description'),
            'issue_category': request.form.get('issue_category', 'maintenance'),
            'issue_priority': request.form.get('issue_priority', 'medium'),
            'default_assignee_id': request.form.get('default_assignee_id') or None,
            'is_active': request.form.get('is_active') == 'on',
            'created_by_id': g.current_user.get('id') if g.current_user else None,
        }
        
        if data['default_assignee_id']:
            data['default_assignee_id'] = int(data['default_assignee_id'])
        
        try:
            db.create_maintenance_task(data)
            flash('Maintenance task created', 'success')
            return redirect(url_for('main.equipment_maintenance_tasks', equipment_id=equipment_id))
        except Exception as e:
            flash(f'Error creating task: {str(e)}', 'error')
    
    users, _ = db.get_users()
    return render_template('equipment_maintenance_task_form.html',
        equipment=equipment,
        task=None,
        users=users,
    )


@main_bp.route('/equipment/<int:equipment_id>/maintenance/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def equipment_maintenance_task_edit(equipment_id, task_id):
    """Edit a maintenance task."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    task = db.get_maintenance_task(task_id)
    if not task:
        flash('Maintenance task not found', 'error')
        return redirect(url_for('main.equipment_maintenance_tasks', equipment_id=equipment_id))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'interval_days': int(request.form.get('interval_days', 30)),
            'issue_title': request.form.get('issue_title'),
            'issue_description': request.form.get('issue_description'),
            'issue_category': request.form.get('issue_category', 'maintenance'),
            'issue_priority': request.form.get('issue_priority', 'medium'),
            'default_assignee_id': request.form.get('default_assignee_id') or None,
            'is_active': request.form.get('is_active') == 'on',
        }
        
        if data['default_assignee_id']:
            data['default_assignee_id'] = int(data['default_assignee_id'])
        
        try:
            db.update_maintenance_task(task_id, data)
            flash('Maintenance task updated', 'success')
            return redirect(url_for('main.equipment_maintenance_tasks', equipment_id=equipment_id))
        except Exception as e:
            flash(f'Error updating task: {str(e)}', 'error')
    
    users, _ = db.get_users()
    return render_template('equipment_maintenance_task_form.html',
        equipment=equipment,
        task=task,
        users=users,
    )


@main_bp.route('/equipment/<int:equipment_id>/maintenance/<int:task_id>/delete', methods=['POST'])
@login_required
def equipment_maintenance_task_delete(equipment_id, task_id):
    """Delete a maintenance task."""
    db = get_db_service()
    
    try:
        db.delete_maintenance_task(task_id)
        flash('Maintenance task deleted', 'success')
    except Exception as e:
        flash(f'Error deleting task: {str(e)}', 'error')
    
    return redirect(url_for('main.equipment_maintenance_tasks', equipment_id=equipment_id))


@main_bp.route('/equipment/<int:equipment_id>/maintenance/<int:task_id>/trigger', methods=['POST'])
@login_required
def equipment_maintenance_task_trigger(equipment_id, task_id):
    """Manually trigger a maintenance task to create its issue now."""
    db = get_db_service()
    
    task = db.get_maintenance_task(task_id)
    if not task:
        flash('Maintenance task not found', 'error')
        return redirect(url_for('main.equipment_maintenance_tasks', equipment_id=equipment_id))
    
    if task['current_issue_id']:
        flash('This task already has an open issue', 'warning')
        return redirect(url_for('main.equipment_maintenance_tasks', equipment_id=equipment_id))
    
    # Force the next_due_date to today to trigger it
    from datetime import date
    db.update_maintenance_task(task_id, {'next_due_date': date.today()})
    created = db.check_and_trigger_maintenance_tasks()
    
    if created:
        flash('Maintenance issue created', 'success')
    else:
        flash('Could not create maintenance issue', 'error')
    
    return redirect(url_for('main.equipment_maintenance_tasks', equipment_id=equipment_id))


# -------------------- Equipment Bookings & Scheduling --------------------

@main_bp.route('/equipment/<int:equipment_id>/schedule')
def equipment_schedule(equipment_id):
    """Equipment schedule/calendar view."""
    db = get_db_service()
    
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    # Get scheduling configuration
    config = db.get_equipment_scheduling_config(equipment_id)
    
    # Get upcoming bookings
    bookings, total = db.get_equipment_bookings(
        equipment_id=equipment_id,
        include_past=False,
        per_page=100
    )
    
    return render_template('equipment_schedule.html',
        equipment=equipment,
        bookings=bookings,
        config=config,
        total=total
    )


@main_bp.route('/equipment/<int:equipment_id>/schedule/calendar-events')
def equipment_calendar_events(equipment_id):
    """API endpoint for calendar events (FullCalendar.js)."""
    db = get_db_service()
    
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    start = datetime.fromisoformat(start_date.replace('Z', '')) if start_date else None
    end = datetime.fromisoformat(end_date.replace('Z', '')) if end_date else None
    
    events = db.get_bookings_for_calendar(
        equipment_id=equipment_id,
        start_date=start,
        end_date=end
    )
    
    return jsonify(events)


@main_bp.route('/equipment/<int:equipment_id>/book', methods=['GET', 'POST'])
@login_required
def equipment_book(equipment_id):
    """Create a new equipment booking."""
    db = get_db_service()
    
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    config = db.get_equipment_scheduling_config(equipment_id)
    
    if request.method == 'POST':
        try:
            # Parse datetime from form
            start_date = request.form.get('start_date')
            start_time = request.form.get('start_time')
            end_date = request.form.get('end_date')
            end_time = request.form.get('end_time')
            
            start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
            
            # Check availability
            availability = db.check_booking_availability(
                equipment_id, start_datetime, end_datetime
            )
            
            if not availability['available']:
                for issue in availability['issues']:
                    flash(issue['message'], 'error')
                return redirect(url_for('main.equipment_book', equipment_id=equipment_id))
            
            data = {
                'equipment_id': equipment_id,
                'user_id': g.current_user['id'],
                'title': request.form.get('title'),
                'description': request.form.get('description'),
                'start_time': start_datetime,
                'end_time': end_datetime,
                'project_id': request.form.get('project_id', type=int),
                'notes': request.form.get('notes'),
                'is_recurring': request.form.get('is_recurring') == 'on',
                'recurrence_rule': request.form.get('recurrence_rule'),
                'created_by': g.current_user['username'],
            }
            
            booking = db.create_equipment_booking(data)
            
            # Sync to shared Google Calendar if configured
            if config and config.get('google_calendar_id') and config.get('sync_to_external'):
                try:
                    from database.calendar_integration import get_calendar_service
                    cal_service = get_calendar_service(db)
                    if cal_service:
                        admin_id = config.get('shared_calendar_admin_id') or g.current_user['id']
                        # Add equipment name for calendar event
                        booking['equipment_name'] = equipment['name']
                        booking['user_name'] = g.current_user.get('name') or g.current_user['username']
                        cal_service.sync_booking_to_shared_calendar(
                            admin_id, config['google_calendar_id'], booking
                        )
                except Exception as e:
                    # Don't fail booking creation if calendar sync fails
                    pass
            
            flash('Booking created successfully', 'success')
            
            return redirect(url_for('main.equipment_booking_detail', 
                equipment_id=equipment_id, booking_id=booking['id']))
        
        except ValueError as e:
            flash(str(e), 'error')
    
    # Get projects for dropdown
    projects_list = db.get_projects_simple_list()
    
    # Get default values from query params (for calendar click)
    default_start = request.args.get('start', '')
    default_end = request.args.get('end', '')
    
    return render_template('equipment_booking_form.html',
        equipment=equipment,
        config=config,
        projects_list=projects_list,
        booking=None,
        default_start=default_start,
        default_end=default_end
    )


@main_bp.route('/equipment/<int:equipment_id>/bookings/<int:booking_id>')
def equipment_booking_detail(equipment_id, booking_id):
    """Equipment booking detail page."""
    db = get_db_service()
    
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    booking = db.get_equipment_booking(booking_id)
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))
    
    return render_template('equipment_booking_detail.html',
        equipment=equipment,
        booking=booking
    )


@main_bp.route('/equipment/<int:equipment_id>/bookings/<int:booking_id>/edit', methods=['GET', 'POST'])
@login_required
def equipment_booking_edit(equipment_id, booking_id):
    """Edit an equipment booking."""
    db = get_db_service()
    
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    booking = db.get_equipment_booking(booking_id)
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))
    
    # Check ownership
    if booking['user_id'] != g.current_user['id'] and g.current_user['role'] != 'admin':
        flash('You can only edit your own bookings', 'error')
        return redirect(url_for('main.equipment_booking_detail', 
            equipment_id=equipment_id, booking_id=booking_id))
    
    config = db.get_equipment_scheduling_config(equipment_id)
    
    if request.method == 'POST':
        try:
            start_date = request.form.get('start_date')
            start_time = request.form.get('start_time')
            end_date = request.form.get('end_date')
            end_time = request.form.get('end_time')
            
            start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
            
            # Check availability (excluding current booking)
            availability = db.check_booking_availability(
                equipment_id, start_datetime, end_datetime, exclude_booking_id=booking_id
            )
            
            if not availability['available']:
                for issue in availability['issues']:
                    flash(issue['message'], 'error')
                return redirect(url_for('main.equipment_booking_edit', 
                    equipment_id=equipment_id, booking_id=booking_id))
            
            data = {
                'title': request.form.get('title'),
                'description': request.form.get('description'),
                'start_time': start_datetime,
                'end_time': end_datetime,
                'project_id': request.form.get('project_id', type=int),
                'notes': request.form.get('notes'),
            }
            
            db.update_equipment_booking(booking_id, data)
            flash('Booking updated successfully', 'success')
            
            return redirect(url_for('main.equipment_booking_detail', 
                equipment_id=equipment_id, booking_id=booking_id))
        
        except ValueError as e:
            flash(str(e), 'error')
    
    projects_list = db.get_projects_simple_list()
    
    return render_template('equipment_booking_form.html',
        equipment=equipment,
        config=config,
        projects_list=projects_list,
        booking=booking
    )


@main_bp.route('/equipment/<int:equipment_id>/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def equipment_booking_cancel(equipment_id, booking_id):
    """Cancel an equipment booking."""
    db = get_db_service()
    
    booking = db.get_equipment_booking(booking_id)
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))
    
    # Check ownership
    if booking['user_id'] != g.current_user['id'] and g.current_user['role'] != 'admin':
        flash('You can only cancel your own bookings', 'error')
        return redirect(url_for('main.equipment_booking_detail', 
            equipment_id=equipment_id, booking_id=booking_id))
    
    reason = request.form.get('reason', '')
    db.cancel_booking(booking_id, reason=reason, cancelled_by=g.current_user['username'])
    
    # Delete from shared Google Calendar if configured
    config = db.get_equipment_scheduling_config(equipment_id)
    if config and config.get('google_calendar_id') and booking.get('google_event_id'):
        try:
            from database.calendar_integration import get_calendar_service
            cal_service = get_calendar_service(db)
            if cal_service:
                admin_id = config.get('shared_calendar_admin_id') or g.current_user['id']
                cal_service.sync_booking_to_shared_calendar(
                    admin_id, config['google_calendar_id'], booking, delete=True
                )
        except Exception:
            pass  # Don't fail if calendar sync fails
    
    flash('Booking cancelled', 'success')
    
    return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))


@main_bp.route('/equipment/<int:equipment_id>/bookings/<int:booking_id>/checkin', methods=['POST'])
@login_required
def equipment_booking_checkin(equipment_id, booking_id):
    """Check in to a booking."""
    db = get_db_service()
    
    booking = db.get_equipment_booking(booking_id)
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))
    
    if booking['user_id'] != g.current_user['id']:
        flash('You can only check in to your own bookings', 'error')
        return redirect(url_for('main.equipment_booking_detail', 
            equipment_id=equipment_id, booking_id=booking_id))
    
    db.checkin_booking(booking_id)
    flash('Checked in successfully', 'success')
    
    return redirect(url_for('main.equipment_booking_detail', 
        equipment_id=equipment_id, booking_id=booking_id))


@main_bp.route('/equipment/<int:equipment_id>/bookings/<int:booking_id>/checkout', methods=['POST'])
@login_required
def equipment_booking_checkout(equipment_id, booking_id):
    """Check out of a booking."""
    db = get_db_service()
    
    booking = db.get_equipment_booking(booking_id)
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))
    
    if booking['user_id'] != g.current_user['id']:
        flash('You can only check out of your own bookings', 'error')
        return redirect(url_for('main.equipment_booking_detail', 
            equipment_id=equipment_id, booking_id=booking_id))
    
    db.checkout_booking(booking_id)
    flash('Checked out successfully', 'success')
    
    return redirect(url_for('main.equipment_booking_detail', 
        equipment_id=equipment_id, booking_id=booking_id))


@main_bp.route('/equipment/<int:equipment_id>/schedule/settings', methods=['GET', 'POST'])
@login_required
def equipment_schedule_settings(equipment_id):
    """Configure scheduling settings for equipment."""
    db = get_db_service()
    
    equipment = db.get_equipment(equipment_id)
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    # Check permissions (owner or admin)
    if equipment.get('owner_id') != g.current_user['id'] and g.current_user['role'] != 'admin':
        flash('Only equipment owners or admins can configure scheduling', 'error')
        return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))
    
    if request.method == 'POST':
        data = {
            'scheduling_enabled': request.form.get('scheduling_enabled') == 'on',
            'min_booking_duration': request.form.get('min_booking_duration', type=int) or 30,
            'max_booking_duration': request.form.get('max_booking_duration', type=int) or 480,
            'default_booking_duration': request.form.get('default_booking_duration', type=int) or 60,
            'min_advance_booking': request.form.get('min_advance_booking', type=int) or 0,
            'max_advance_booking': request.form.get('max_advance_booking', type=int) or 30,
            'buffer_time': request.form.get('buffer_time', type=int) or 0,
            'requires_approval': request.form.get('requires_approval') == 'on',
            'allow_recurring': request.form.get('allow_recurring') == 'on',
            'send_confirmation_email': request.form.get('send_confirmation_email') == 'on',
            'send_reminder_email': request.form.get('send_reminder_email') == 'on',
            'reminder_hours_before': request.form.get('reminder_hours_before', type=int) or 24,
        }
        
        # Parse availability schedule
        availability = {}
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            if request.form.get(f'{day}_enabled') == 'on':
                availability[day] = {
                    'start': request.form.get(f'{day}_start', '09:00'),
                    'end': request.form.get(f'{day}_end', '17:00')
                }
        data['availability_schedule'] = availability if availability else None
        
        db.create_or_update_scheduling_config(equipment_id, data)
        flash('Scheduling settings saved', 'success')
        
        return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))
    
    config = db.get_equipment_scheduling_config(equipment_id)
    users = db.get_users_simple_list()
    
    return render_template('equipment_schedule_settings.html',
        equipment=equipment,
        config=config,
        users=users
    )


@main_bp.route('/equipment/<int:equipment_id>/schedule/ical')
def equipment_ical_feed(equipment_id):
    """Generate iCal feed for equipment bookings."""
    db = get_db_service()
    
    ical_content = db.generate_ical_feed(equipment_id=equipment_id)
    
    response = make_response(ical_content)
    response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=equipment-{equipment_id}-schedule.ics'
    return response


@main_bp.route('/my-bookings')
@login_required
def my_bookings():
    """User's booking dashboard."""
    db = get_db_service()
    
    page = request.args.get('page', 1, type=int)
    include_past = request.args.get('include_past', 'false') == 'true'
    status = request.args.get('status', '')
    
    bookings, total = db.get_equipment_bookings(
        user_id=g.current_user['id'],
        status=status if status else None,
        include_past=include_past,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get upcoming bookings for widget
    upcoming = db.get_user_upcoming_bookings(g.current_user['id'], limit=5)
    
    return render_template('my_bookings.html',
        bookings=bookings,
        upcoming=upcoming,
        page=page,
        total_pages=total_pages,
        total=total,
        include_past=include_past,
        status=status
    )


@main_bp.route('/my-bookings/ical')
@login_required
def my_bookings_ical_feed():
    """Generate iCal feed for user's bookings."""
    db = get_db_service()
    
    ical_content = db.generate_ical_feed(user_id=g.current_user['id'])
    
    response = make_response(ical_content)
    response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=my-equipment-bookings.ics'
    return response


@main_bp.route('/schedule')
def lab_schedule():
    """Lab-wide equipment schedule view."""
    db = get_db_service()
    
    lab_id = session.get('filter_lab_id')
    
    # Get all equipment for the lab
    equipment_list, _ = db.get_equipment_list(lab_id=lab_id, per_page=100)
    
    return render_template('lab_schedule.html',
        equipment_list=equipment_list,
        lab_id=lab_id
    )


@main_bp.route('/schedule/calendar-events')
def lab_calendar_events():
    """API endpoint for lab-wide calendar events."""
    db = get_db_service()
    
    lab_id = session.get('filter_lab_id')
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    start = datetime.fromisoformat(start_date.replace('Z', '')) if start_date else None
    end = datetime.fromisoformat(end_date.replace('Z', '')) if end_date else None
    
    events = db.get_bookings_for_calendar(
        lab_id=lab_id,
        start_date=start,
        end_date=end
    )
    
    return jsonify(events)


# -------------------- Calendar Integration --------------------

@main_bp.route('/settings/calendar')
@login_required
def calendar_settings():
    """User calendar integration settings."""
    db = get_db_service()
    
    integrations = db.get_user_calendar_integrations(g.current_user['id'])
    
    # Check available providers
    from database.calendar_integration import get_calendar_service
    cal_service = get_calendar_service(db)
    
    available_providers = {
        'google': cal_service.is_google_available() if cal_service else False,
        'outlook': cal_service.is_microsoft_available() if cal_service else False,
    }
    
    return render_template('calendar_settings.html',
        integrations=integrations,
        available_providers=available_providers
    )


@main_bp.route('/settings/calendar/connect/google')
@login_required
def connect_google_calendar():
    """Initiate Google Calendar OAuth flow."""
    from database.calendar_integration import get_calendar_service
    
    db = get_db_service()
    cal_service = get_calendar_service(db)
    
    if not cal_service or not cal_service.is_google_available():
        flash('Google Calendar integration is not configured', 'error')
        return redirect(url_for('main.calendar_settings'))
    
    redirect_uri = url_for('main.google_calendar_callback', _external=True)
    
    try:
        auth_url = cal_service.get_google_auth_url(g.current_user['id'], redirect_uri)
        return redirect(auth_url)
    except Exception as e:
        flash(f'Error connecting to Google: {str(e)}', 'error')
        return redirect(url_for('main.calendar_settings'))


@main_bp.route('/settings/calendar/callback/google')
@login_required
def google_calendar_callback():
    """Handle Google Calendar OAuth callback."""
    from database.calendar_integration import get_calendar_service
    
    db = get_db_service()
    cal_service = get_calendar_service(db)
    
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        flash(f'Google authorization error: {error}', 'error')
        return redirect(url_for('main.calendar_settings'))
    
    if not code:
        flash('No authorization code received', 'error')
        return redirect(url_for('main.calendar_settings'))
    
    redirect_uri = url_for('main.google_calendar_callback', _external=True)
    
    try:
        cal_service.handle_google_callback(g.current_user['id'], code, redirect_uri)
        flash('Google Calendar connected successfully!', 'success')
    except Exception as e:
        flash(f'Error connecting Google Calendar: {str(e)}', 'error')
    
    return redirect(url_for('main.calendar_settings'))


@main_bp.route('/settings/calendar/disconnect/<provider>', methods=['POST'])
@login_required
def disconnect_calendar(provider):
    """Disconnect a calendar integration."""
    db = get_db_service()
    
    if db.delete_calendar_integration(g.current_user['id'], provider):
        flash(f'{provider.capitalize()} calendar disconnected', 'success')
    else:
        flash(f'Could not disconnect {provider} calendar', 'error')
    
    return redirect(url_for('main.calendar_settings'))


@main_bp.route('/settings/calendar/sync/<provider>', methods=['POST'])
@login_required
def sync_calendar(provider):
    """Manually sync bookings with external calendar."""
    from database.calendar_integration import get_calendar_service
    
    db = get_db_service()
    cal_service = get_calendar_service(db)
    
    if not cal_service:
        flash('Calendar service not available', 'error')
        return redirect(url_for('main.calendar_settings'))
    
    # Get user's upcoming bookings
    bookings = db.get_user_upcoming_bookings(g.current_user['id'], limit=50)
    
    synced = 0
    for booking in bookings:
        if provider == 'google':
            if not booking.get('google_event_id'):
                event_id = cal_service.create_google_event(g.current_user['id'], booking)
                if event_id:
                    synced += 1
    
    if synced > 0:
        flash(f'Synced {synced} booking(s) to {provider.capitalize()} Calendar', 'success')
    else:
        flash('All bookings already synced', 'info')
    
    return redirect(url_for('main.calendar_settings'))


# -------------------- Shared Equipment Calendars --------------------

@main_bp.route('/equipment/<int:equipment_id>/schedule/settings/shared-calendar', methods=['GET', 'POST'])
@login_required
def equipment_shared_calendar(equipment_id):
    """Manage shared Google Calendar for equipment scheduling."""
    from database.calendar_integration import get_calendar_service
    
    db = get_db_service()
    equipment = db.get_equipment_by_id(equipment_id)
    
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment_list'))
    
    # Check admin permission
    if not g.current_user.get('is_admin') and equipment.get('created_by_id') != g.current_user['id']:
        flash('Permission denied', 'error')
        return redirect(url_for('main.equipment_schedule', equipment_id=equipment_id))
    
    config = db.get_equipment_scheduling_config(equipment_id)
    cal_service = get_calendar_service(db)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_calendar':
            # Create a new shared Google Calendar
            if not cal_service or not cal_service.is_google_available():
                flash('Google Calendar integration not configured', 'error')
                return redirect(url_for('main.equipment_shared_calendar', equipment_id=equipment_id))
            
            calendar_name = request.form.get('calendar_name', f"{equipment['name']} Schedule")
            
            result = cal_service.create_shared_calendar(
                admin_user_id=g.current_user['id'],
                calendar_name=calendar_name,
                description=f"Equipment scheduling calendar for {equipment['name']}"
            )
            
            if result:
                # Store the calendar ID in scheduling config
                db.update_equipment_scheduling_config(equipment_id, {
                    'google_calendar_id': result['id'],
                    'shared_calendar_admin_id': g.current_user['id'],
                    'shared_calendar_name': calendar_name,
                    'sync_to_external': True,
                })
                flash(f'Created shared calendar: {calendar_name}', 'success')
            else:
                flash('Failed to create calendar', 'error')
        
        elif action == 'share_domain':
            # Share with a domain
            domain = request.form.get('domain', '').strip()
            role = request.form.get('role', 'reader')
            
            if config and config.get('google_calendar_id') and domain:
                admin_id = config.get('shared_calendar_admin_id') or g.current_user['id']
                success = cal_service.share_calendar_with_domain(
                    admin_id, config['google_calendar_id'], domain, role
                )
                if success:
                    db.update_equipment_scheduling_config(equipment_id, {
                        'shared_calendar_domain': domain
                    })
                    flash(f'Shared calendar with {domain}', 'success')
                else:
                    flash('Failed to share calendar with domain', 'error')
        
        elif action == 'share_user':
            # Share with specific user
            email = request.form.get('email', '').strip()
            role = request.form.get('role', 'reader')
            
            if config and config.get('google_calendar_id') and email:
                admin_id = config.get('shared_calendar_admin_id') or g.current_user['id']
                success = cal_service.share_calendar_with_user(
                    admin_id, config['google_calendar_id'], email, role
                )
                if success:
                    flash(f'Shared calendar with {email}', 'success')
                else:
                    flash('Failed to share calendar', 'error')
        
        elif action == 'make_public':
            # Make calendar publicly viewable
            if config and config.get('google_calendar_id'):
                admin_id = config.get('shared_calendar_admin_id') or g.current_user['id']
                success = cal_service.make_calendar_public(
                    admin_id, config['google_calendar_id']
                )
                if success:
                    db.update_equipment_scheduling_config(equipment_id, {
                        'shared_calendar_public': True
                    })
                    flash('Calendar is now publicly viewable', 'success')
                else:
                    flash('Failed to make calendar public', 'error')
        
        elif action == 'populate':
            # Populate calendar with existing bookings
            if config and config.get('google_calendar_id'):
                admin_id = config.get('shared_calendar_admin_id') or g.current_user['id']
                
                # Get all bookings for this equipment
                bookings = db.get_equipment_bookings(
                    equipment_id=equipment_id,
                    status=['pending', 'confirmed', 'checked_in'],
                    limit=500
                )
                
                result = cal_service.populate_shared_calendar(
                    admin_id, 
                    config['google_calendar_id'],
                    bookings,
                    clear_existing=request.form.get('clear_existing') == '1'
                )
                
                if result.get('error'):
                    flash(f"Sync error: {result['error']}", 'error')
                else:
                    db.update_equipment_scheduling_config(equipment_id, {
                        'last_calendar_sync': datetime.utcnow().isoformat()
                    })
                    flash(f"Synced {result['created']} new, {result['updated']} updated bookings", 'success')
        
        elif action == 'remove_access':
            # Remove user/domain access
            rule_id = request.form.get('rule_id')
            if config and config.get('google_calendar_id') and rule_id:
                admin_id = config.get('shared_calendar_admin_id') or g.current_user['id']
                success = cal_service.remove_calendar_access(
                    admin_id, config['google_calendar_id'], rule_id
                )
                if success:
                    flash('Access removed', 'success')
                else:
                    flash('Failed to remove access', 'error')
        
        return redirect(url_for('main.equipment_shared_calendar', equipment_id=equipment_id))
    
    # GET: Display shared calendar settings
    subscribers = []
    share_link = None
    embed_link = None
    
    if config and config.get('google_calendar_id') and cal_service:
        admin_id = config.get('shared_calendar_admin_id') or g.current_user['id']
        subscribers = cal_service.get_calendar_subscribers(admin_id, config['google_calendar_id'])
        share_link = cal_service.get_calendar_share_link(config['google_calendar_id'])
        embed_link = cal_service.get_calendar_share_link(config['google_calendar_id'], embed=True)
    
    google_available = cal_service and cal_service.is_google_available() if cal_service else False
    
    return render_template('equipment_shared_calendar.html',
        equipment=equipment,
        config=config,
        subscribers=subscribers,
        share_link=share_link,
        embed_link=embed_link,
        google_available=google_available,
    )


@main_bp.route('/lab/<int:lab_id>/shared-calendar', methods=['GET', 'POST'])
@login_required  
def lab_shared_calendar(lab_id):
    """Manage shared Google Calendar for all equipment in a lab."""
    from database.calendar_integration import get_calendar_service
    
    db = get_db_service()
    lab = db.get_lab_by_id(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    cal_service = get_calendar_service(db)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_lab_calendar':
            # Create a unified lab equipment calendar
            if not cal_service or not cal_service.is_google_available():
                flash('Google Calendar integration not configured', 'error')
                return redirect(url_for('main.lab_shared_calendar', lab_id=lab_id))
            
            calendar_name = request.form.get('calendar_name', f"{lab['name']} Equipment Schedule")
            
            result = cal_service.create_shared_calendar(
                admin_user_id=g.current_user['id'],
                calendar_name=calendar_name,
                description=f"Equipment scheduling calendar for {lab['name']} lab"
            )
            
            if result:
                # Store in lab metadata (or create a new lab_calendar table)
                # For now, store in session/flash for demo
                flash(f"Created lab calendar: {calendar_name}. Calendar ID: {result['id']}", 'success')
                # TODO: Store lab calendar ID in database
            else:
                flash('Failed to create calendar', 'error')
        
        elif action == 'populate_lab':
            # Populate with all equipment bookings in the lab
            calendar_id = request.form.get('calendar_id')
            if calendar_id and cal_service:
                # Get all equipment in the lab
                equipment_list = db.get_equipment_by_lab(lab_id)
                all_bookings = []
                
                for eq in equipment_list:
                    bookings = db.get_equipment_bookings(
                        equipment_id=eq['id'],
                        status=['pending', 'confirmed', 'checked_in'],
                        limit=200
                    )
                    all_bookings.extend(bookings)
                
                result = cal_service.populate_shared_calendar(
                    g.current_user['id'],
                    calendar_id,
                    all_bookings,
                    clear_existing=request.form.get('clear_existing') == '1'
                )
                
                if result.get('error'):
                    flash(f"Sync error: {result['error']}", 'error')
                else:
                    flash(f"Synced {result['created']} new, {result['updated']} updated bookings from {len(equipment_list)} equipment items", 'success')
        
        return redirect(url_for('main.lab_shared_calendar', lab_id=lab_id))
    
    google_available = cal_service and cal_service.is_google_available() if cal_service else False
    
    # Get equipment in the lab
    equipment_list = db.get_equipment_by_lab(lab_id)
    
    return render_template('lab_shared_calendar.html',
        lab=lab,
        equipment_list=equipment_list,
        google_available=google_available,
    )


# -------------------- Locations --------------------

@main_bp.route('/locations')
def locations():
    """Locations list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    location_type = request.args.get('type', '')
    parent_id = request.args.get('parent_id', type=int)
    
    db = get_db_service()
    locations_list, total = db.get_locations_list(
        search=search if search else None,
        location_type=location_type if location_type else None,
        parent_id=parent_id,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'location')
    
    return render_template('locations.html',
        locations=locations_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        location_type=location_type,
        parent_id=parent_id,
        pinned_ids=pinned_ids
    )


@main_bp.route('/locations/<int:location_id>')
def location_detail(location_id):
    """Location detail page."""
    db = get_db_service()
    location = db.get_location(location_id)
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('main.locations'))
    
    # Get all locations for moving objects
    all_locations = db.get_locations_simple_list()
    
    # Get lists for adding objects
    equipment_list = db.get_equipment_simple_list()
    instruments_list = db.get_instruments_simple_list()
    samples_list = db.get_samples_simple_list()
    precursors_list = db.get_precursors_simple_list()
    computers_list = db.get_computers_list()
    
    # Get images and attachments
    images = db.get_entity_images('location', location_id)
    attachments = db.get_entity_attachments('location', location_id)
    
    return render_template('location_detail.html', 
                          location=location, 
                          all_locations=all_locations,
                          equipment_list=equipment_list,
                          instruments_list=instruments_list,
                          samples_list=samples_list,
                          precursors_list=precursors_list,
                          computers_list=computers_list,
                          images=images,
                          attachments=attachments,
                          entity_type='location',
                          entity_id=location_id)


@main_bp.route('/locations/new', methods=['GET', 'POST'])
@login_required
def location_new():
    """Create new location page."""
    db = get_db_service()
    
    # Check if parent_id was provided
    parent_id = request.args.get('parent_id', type=int)
    parent_location = None
    if parent_id:
        parent_location = db.get_location(parent_id)
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        parent_location_id = request.form.get('parent_location_id')
        
        data = {
            'name': request.form.get('name'),
            'location_type': request.form.get('location_type'),
            'description': request.form.get('description'),
            'room_number': request.form.get('room_number'),
            'building': request.form.get('building'),
            'floor': request.form.get('floor'),
            'capacity': request.form.get('capacity'),
            'conditions': request.form.get('conditions'),
            'access_notes': request.form.get('access_notes'),
            'lab_id': int(lab_id) if lab_id else None,
            'parent_location_id': int(parent_location_id) if parent_location_id else None,
            'created_by': g.current_user.get('username') if g.current_user else None,
        }
        
        if not data['lab_id']:
            flash('Lab is required', 'error')
        elif not data['name']:
            flash('Name is required', 'error')
        else:
            try:
                location = db.create_location(data)
                flash(f'Location "{data["name"]}" created successfully', 'success')
                return redirect(url_for('main.location_detail', location_id=location['id']))
            except Exception as e:
                flash(f'Error creating location: {str(e)}', 'error')
    
    # Get dropdown data
    labs = db.get_labs_simple_list()
    all_locations = db.get_locations_simple_list()
    
    # Get user defaults
    default_lab_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
    
    return render_template('location_form.html',
        action='New',
        location=None,
        parent_location=parent_location,
        labs=labs,
        all_locations=all_locations,
        default_lab_id=default_lab_id,
    )


@main_bp.route('/locations/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
def location_edit(location_id):
    """Edit location page."""
    db = get_db_service()
    location = db.get_location(location_id)
    
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('main.locations'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        parent_location_id = request.form.get('parent_location_id')
        
        # Prevent setting self as parent
        if parent_location_id and int(parent_location_id) == location_id:
            flash('A location cannot be its own parent', 'error')
        else:
            data = {
                'name': request.form.get('name'),
                'location_type': request.form.get('location_type'),
                'description': request.form.get('description'),
                'room_number': request.form.get('room_number'),
                'building': request.form.get('building'),
                'floor': request.form.get('floor'),
                'capacity': request.form.get('capacity'),
                'conditions': request.form.get('conditions'),
                'access_notes': request.form.get('access_notes'),
                'lab_id': int(lab_id) if lab_id else None,
                'parent_location_id': int(parent_location_id) if parent_location_id else None,
            }
            
            try:
                updated = db.update_location(location_id, data)
                flash(f'Location "{updated["name"]}" updated successfully', 'success')
                return redirect(url_for('main.location_detail', location_id=location_id))
            except Exception as e:
                flash(f'Error updating location: {str(e)}', 'error')
    
    # Get dropdown data
    labs = db.get_labs_simple_list()
    # Exclude this location and its children from parent options
    all_locations = [loc for loc in db.get_locations_simple_list() if loc['id'] != location_id]
    
    return render_template('location_form.html',
        action='Edit',
        location=location,
        labs=labs,
        all_locations=all_locations,
    )


@main_bp.route('/locations/<int:location_id>/duplicate', methods=['GET', 'POST'])
@login_required
def location_duplicate(location_id):
    """Duplicate a location with a new name."""
    db = get_db_service()
    location = db.get_location(location_id)
    
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('main.locations'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        parent_location_id = request.form.get('parent_location_id')
        
        data = {
            'name': request.form.get('name'),
            'location_type': request.form.get('location_type'),
            'description': request.form.get('description'),
            'room_number': request.form.get('room_number'),
            'building': request.form.get('building'),
            'floor': request.form.get('floor'),
            'capacity': request.form.get('capacity'),
            'conditions': request.form.get('conditions'),
            'access_notes': request.form.get('access_notes'),
            'lab_id': int(lab_id) if lab_id else None,
            'parent_location_id': int(parent_location_id) if parent_location_id else None,
            'created_by': g.current_user.get('username') if g.current_user else None,
        }
        
        if not data['lab_id']:
            flash('Lab is required', 'error')
        elif not data['name']:
            flash('Name is required', 'error')
        else:
            try:
                new_location = db.create_location(data)
                flash(f'Location "{data["name"]}" created successfully (duplicated from "{location["name"]}")', 'success')
                return redirect(url_for('main.location_detail', location_id=new_location['id']))
            except Exception as e:
                flash(f'Error duplicating location: {str(e)}', 'error')
    
    # Pre-fill with existing data but suggest a new name
    location['name'] = f"{location['name']} (Copy)"
    
    # Get dropdown data
    labs = db.get_labs_simple_list()
    all_locations = db.get_locations_simple_list()
    
    return render_template('location_form.html',
        action='Duplicate',
        location=location,
        labs=labs,
        all_locations=all_locations,
    )


@main_bp.route('/locations/<int:location_id>/delete', methods=['POST'])
@login_required
def location_delete(location_id):
    """Move a location to trash (soft-delete with cascade to child locations)."""
    db = get_db_service()
    location = db.get_location(location_id)
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('location', location_id, trashed_by=username, cascade=True)
        
        if result['success']:
            name = location.get('name', f'#{location_id}') if location else f'#{location_id}'
            flash(f'Location "{name}" moved to trash. It will be permanently deleted in 30 days.', 'success')
        else:
            flash(result.get('error', 'Location not found'), 'error')
    except Exception as e:
        flash(f'Error deleting location: {str(e)}', 'error')
    
    return redirect(url_for('main.locations'))


@main_bp.route('/locations/<int:location_id>/add-object', methods=['POST'])
@login_required
def location_add_object(location_id):
    """Add an object to a location."""
    db = get_db_service()
    
    object_type = request.form.get('object_type')
    object_id = request.form.get('object_id')
    notes = request.form.get('notes')
    
    if not object_type or not object_id:
        flash('Object type and ID are required', 'error')
        return redirect(url_for('main.location_detail', location_id=location_id))
    
    try:
        db.add_object_to_location(
            location_id=location_id,
            object_type=object_type,
            object_id=int(object_id),
            notes=notes,
            placed_by=g.current_user.get('username') if g.current_user else None
        )
        flash('Object added to location successfully', 'success')
    except Exception as e:
        flash(f'Error adding object: {str(e)}', 'error')
    
    return redirect(url_for('main.location_detail', location_id=location_id))


@main_bp.route('/locations/<int:location_id>/remove-object', methods=['POST'])
@login_required
def location_remove_object(location_id):
    """Remove an object from a location."""
    db = get_db_service()
    
    object_type = request.form.get('object_type')
    object_id = request.form.get('object_id')
    
    if not object_type or not object_id:
        flash('Object type and ID are required', 'error')
        return redirect(url_for('main.location_detail', location_id=location_id))
    
    try:
        db.remove_object_from_location(object_type=object_type, object_id=int(object_id))
        flash('Object removed from location', 'success')
    except Exception as e:
        flash(f'Error removing object: {str(e)}', 'error')
    
    return redirect(url_for('main.location_detail', location_id=location_id))


@main_bp.route('/locations/<int:location_id>/update-object-notes', methods=['POST'])
@login_required
def location_update_object_notes(location_id):
    """Update the notes/directions for an object at a location."""
    db = get_db_service()
    
    object_type = request.form.get('object_type')
    object_id = request.form.get('object_id')
    notes = request.form.get('notes', '').strip() or None
    
    if not object_type or not object_id:
        flash('Object type and ID are required', 'error')
        return redirect(url_for('main.location_detail', location_id=location_id))
    
    try:
        db.update_object_location_notes(object_type=object_type, object_id=int(object_id), notes=notes)
        flash('Notes updated', 'success')
    except Exception as e:
        flash(f'Error updating notes: {str(e)}', 'error')
    
    return redirect(url_for('main.location_detail', location_id=location_id))


# -------------------- Object Location Routes (from object's perspective) --------------------

@main_bp.route('/object/<object_type>/<int:object_id>/set-location', methods=['POST'])
@login_required
def object_set_location(object_type, object_id):
    """Set/change the location for an object."""
    db = get_db_service()
    
    location_id = request.form.get('location_id')
    notes = request.form.get('notes')
    
    if not location_id:
        flash('Location is required', 'error')
    else:
        try:
            db.add_object_to_location(
                location_id=int(location_id),
                object_type=object_type,
                object_id=object_id,
                notes=notes,
                placed_by=g.current_user.get('username') if g.current_user else None
            )
            flash('Location updated successfully', 'success')
        except Exception as e:
            flash(f'Error setting location: {str(e)}', 'error')
    
    # Redirect back to the object's detail page
    redirect_map = {
        'equipment': ('main.equipment_detail', {'equipment_id': object_id}),
        'instrument': ('main.instrument_detail', {'instrument_id': object_id}),
        'sample': ('main.sample_detail', {'sample_id': object_id}),
        'precursor': ('main.precursor_detail', {'precursor_id': object_id}),
        'computer': ('main.computer_detail', {'computer_id': object_id}),
    }
    endpoint, kwargs = redirect_map.get(object_type, ('main.index', {}))
    return redirect(url_for(endpoint, **kwargs))


@main_bp.route('/object/<object_type>/<int:object_id>/remove-location', methods=['POST'])
@login_required
def object_remove_location(object_type, object_id):
    """Remove an object from its current location."""
    db = get_db_service()
    
    try:
        db.remove_object_from_location(object_type=object_type, object_id=object_id)
        flash('Removed from location', 'success')
    except Exception as e:
        flash(f'Error removing from location: {str(e)}', 'error')
    
    # Redirect back to the object's detail page
    redirect_map = {
        'equipment': ('main.equipment_detail', {'equipment_id': object_id}),
        'instrument': ('main.instrument_detail', {'instrument_id': object_id}),
        'sample': ('main.sample_detail', {'sample_id': object_id}),
        'precursor': ('main.precursor_detail', {'precursor_id': object_id}),
        'computer': ('main.computer_detail', {'computer_id': object_id}),
    }
    endpoint, kwargs = redirect_map.get(object_type, ('main.index', {}))
    return redirect(url_for(endpoint, **kwargs))


# -------------------- Precursors --------------------

@main_bp.route('/precursors')
def precursors():
    """Precursors list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    lab_id = request.args.get('lab_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    db = get_db_service()
    precursors_list, total = db.get_precursors(
        search=search if search else None,
        lab_id=lab_id,
        project_id=project_id,
        page=page
    )
    
    # Get labs and projects for filter dropdowns
    labs_list, _ = db.get_labs(per_page=100)
    projects_list = db.get_projects_simple_list()
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'precursor')
    
    return render_template('precursors.html',
        precursors=precursors_list,
        labs=labs_list,
        projects=projects_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        lab_id=lab_id,
        project_id=project_id,
        pinned_ids=pinned_ids
    )


@main_bp.route('/precursors/<int:precursor_id>')
def precursor_detail(precursor_id):
    """Precursor detail page."""
    db = get_db_service()
    item = db.get_precursor(precursor_id)
    if not item:
        flash('Precursor not found', 'error')
        return redirect(url_for('main.precursors'))
    images = db.get_entity_images('precursor', precursor_id)
    attachments = db.get_entity_attachments('precursor', precursor_id)
    object_location = db.get_object_location('precursor', precursor_id)
    locations_list = db.get_locations_simple_list()
    return render_template('precursor_detail.html', precursor=item, images=images, attachments=attachments,
                           object_type='precursor', object_id=precursor_id, object_location=object_location, locations_list=locations_list)


@main_bp.route('/precursors/new', methods=['GET', 'POST'])
def precursor_new():
    """Create new precursor page."""
    db = get_db_service()
    
    # Check if a template_id was provided (e.g., from QR code scan)
    template_id = request.args.get('template_id', type=int)
    template = None
    prefilled = None
    
    if template_id:
        template = db.get_template(template_id)
        if template and template['entity_type'] == 'precursor':
            td = template.get('template_data', {})
            prefilled = {
                'name': td.get('name', ''),
                'chemical_formula': td.get('chemical_formula', ''),
                'cas_number': td.get('cas_number', ''),
                'supplier': td.get('supplier', ''),
                'lot_number': td.get('lot_number', ''),
                'purity': td.get('purity'),
                'state': td.get('state', ''),
                'status': td.get('status', 'new'),
                'storage_conditions': td.get('storage_conditions', ''),
            }
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        data = {
            'name': request.form.get('name'),
            'chemical_formula': request.form.get('chemical_formula'),
            'cas_number': request.form.get('cas_number'),
            'supplier': request.form.get('supplier'),
            'lot_number': request.form.get('lot_number'),
            'purity': float(request.form.get('purity')) if request.form.get('purity') else None,
            'state': request.form.get('state'),
            'status': request.form.get('status', 'new'),
            'storage_conditions': request.form.get('storage_conditions'),
            'lab_id': int(lab_id) if lab_id else None,
            'project_id': int(project_id) if project_id else None,
        }
        try:
            item = db.create_precursor(data)
            
            # Handle database location assignment
            db_location_id = request.form.get('db_location_id')
            location_notes = request.form.get('location_notes')
            if db_location_id:
                db.add_object_to_location(
                    location_id=int(db_location_id),
                    object_type='precursor',
                    object_id=item['id'],
                    notes=location_notes,
                    placed_by=g.current_user.get('username') if g.current_user else None
                )
            
            flash(f'Precursor {item["name"]} created successfully', 'success')
            return redirect(url_for('main.precursor_detail', precursor_id=item['id']))
        except Exception as e:
            flash(f'Error creating precursor: {str(e)}', 'error')
    
    # Get labs, projects for dropdown
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    
    # Get locations for dropdown
    locations = db.get_locations_simple_list()
    
    # Get user defaults
    default_lab_id = None
    default_project_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
        default_project_id = user_prefs.get('default_project_id')
    
    return render_template('precursor_form.html', precursor=prefilled, action='Create', template=template, labs=labs, projects=projects, locations=locations, default_lab_id=default_lab_id, default_project_id=default_project_id)


@main_bp.route('/precursors/<int:precursor_id>/edit', methods=['GET', 'POST'])
def precursor_edit(precursor_id):
    """Edit precursor page."""
    db = get_db_service()
    precursor = db.get_precursor(precursor_id)
    
    if not precursor:
        flash('Precursor not found', 'error')
        return redirect(url_for('main.precursors'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        data = {
            'name': request.form.get('name'),
            'chemical_formula': request.form.get('chemical_formula'),
            'cas_number': request.form.get('cas_number'),
            'supplier': request.form.get('supplier'),
            'lot_number': request.form.get('lot_number'),
            'purity': float(request.form.get('purity')) if request.form.get('purity') else None,
            'state': request.form.get('state'),
            'status': request.form.get('status', 'new'),
            'storage_conditions': request.form.get('storage_conditions'),
            'lab_id': int(lab_id) if lab_id else None,
            'project_id': int(project_id) if project_id else None,
        }
        try:
            updated = db.update_precursor(precursor_id, data)
            
            # Handle database location assignment
            db_location_id = request.form.get('db_location_id')
            location_notes = request.form.get('location_notes')
            if db_location_id:
                db.add_object_to_location(
                    location_id=int(db_location_id),
                    object_type='precursor',
                    object_id=precursor_id,
                    notes=location_notes,
                    placed_by=g.current_user.get('username') if g.current_user else None
                )
            else:
                # Remove from any current location if no location selected
                db.remove_object_from_location('precursor', precursor_id)
            
            flash(f'Precursor "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.precursor_detail', precursor_id=precursor_id))
        except Exception as e:
            flash(f'Error updating precursor: {str(e)}', 'error')
    
    # Get labs, projects for dropdown
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    
    # Get locations for dropdown
    locations = db.get_locations_simple_list()
    
    # Get current location for this precursor
    current_location = db.get_object_location('precursor', precursor_id)
    if current_location:
        precursor['current_location_id'] = current_location['location_id']
        precursor['current_location_notes'] = current_location.get('notes', '')
    
    return render_template('precursor_form.html', precursor=precursor, action='Edit', labs=labs, projects=projects, locations=locations)


@main_bp.route('/precursors/<int:precursor_id>/duplicate', methods=['GET', 'POST'])
@login_required
def precursor_duplicate(precursor_id):
    """Duplicate a precursor with a new ID."""
    db = get_db_service()
    original = db.get_precursor(precursor_id)
    
    if not original:
        flash('Precursor not found', 'error')
        return redirect(url_for('main.precursors'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        data = {
            'name': request.form.get('name'),
            'chemical_formula': request.form.get('chemical_formula'),
            'cas_number': request.form.get('cas_number'),
            'supplier': request.form.get('supplier'),
            'lot_number': request.form.get('lot_number'),
            'purity': float(request.form.get('purity')) if request.form.get('purity') else None,
            'state': request.form.get('state'),
            'status': request.form.get('status', 'new'),
            'storage_conditions': request.form.get('storage_conditions'),
            'lab_id': int(lab_id) if lab_id else None,
            'project_id': int(project_id) if project_id else None,
        }
        try:
            item = db.create_precursor(data)
            flash(f'Precursor "{item["name"]}" created from duplicate', 'success')
            return redirect(url_for('main.precursor_detail', precursor_id=item['id']))
        except Exception as e:
            flash(f'Error creating precursor: {str(e)}', 'error')
    
    # Pre-fill form with original data but new name
    duplicated = original.copy()
    duplicated['name'] = f"{original['name']} (Copy)"
    duplicated['lot_number'] = ''  # Clear lot number for duplicate
    
    # Get labs, projects for dropdown
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    locations = db.get_locations_simple_list()
    
    return render_template('precursor_form.html',
        precursor=duplicated,
        action='Duplicate',
        labs=labs,
        projects=projects,
        locations=locations,
    )


@main_bp.route('/precursors/<int:precursor_id>/delete', methods=['POST'])
@login_required
def precursor_delete(precursor_id):
    """Move a precursor to trash."""
    db = get_db_service()
    precursor = db.get_precursor(precursor_id)
    
    if not precursor:
        flash('Precursor not found', 'error')
        return redirect(url_for('main.precursors'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('precursor', precursor_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash(f'Precursor "{precursor["name"]}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving precursor to trash'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.precursors'))


@main_bp.route('/precursors/<int:precursor_id>/replace', methods=['GET', 'POST'])
@login_required
def precursor_replace(precursor_id):
    """Replace a precursor with a new one, updating all template references."""
    db = get_db_service()
    original = db.get_precursor(precursor_id)
    
    if not original:
        flash('Precursor not found', 'error')
        return redirect(url_for('main.precursors'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        data = {
            'name': request.form.get('name'),
            'chemical_formula': request.form.get('chemical_formula'),
            'cas_number': request.form.get('cas_number'),
            'supplier': request.form.get('supplier'),
            'lot_number': request.form.get('lot_number'),
            'purity': float(request.form.get('purity')) if request.form.get('purity') else None,
            'state': request.form.get('state'),
            'status': request.form.get('status', 'new'),
            'storage_conditions': request.form.get('storage_conditions'),
            'lab_id': int(lab_id) if lab_id else None,
            'project_id': int(project_id) if project_id else None,
        }
        try:
            # Create the new precursor
            item = db.create_precursor(data)
            
            # Replace the old precursor with the new one in all templates
            templates_updated = db.replace_precursor_in_templates(precursor_id, item['id'])
            
            if templates_updated > 0:
                flash(f'Precursor "{item["name"]}" created and replaced in {templates_updated} template(s)', 'success')
            else:
                flash(f'Precursor "{item["name"]}" created (no templates referenced the original)', 'success')
            
            return redirect(url_for('main.precursor_detail', precursor_id=item['id']))
        except Exception as e:
            flash(f'Error creating precursor: {str(e)}', 'error')
    
    # Pre-fill form with original data but new name indicating replacement
    replaced = original.copy()
    replaced['name'] = f"{original['name']} (Replacement)"
    replaced['lot_number'] = ''  # Clear lot number for replacement
    
    # Get labs, projects for dropdown
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    locations = db.get_locations_simple_list()
    
    return render_template('precursor_form.html',
        precursor=replaced,
        action='Replace',
        original_precursor=original,
        labs=labs,
        projects=projects,
        locations=locations,
    )


# -------------------- Waste --------------------

@main_bp.route('/waste')
def waste_list():
    """Waste containers list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    waste_type = request.args.get('type', '')
    status = request.args.get('status', '')
    fill_status = request.args.get('fill_status', '')
    lab_id = request.args.get('lab_id', type=int) or session.get('current_lab_id')
    
    db = get_db_service()
    wastes, total = db.get_wastes(
        search=search,
        waste_type=waste_type,
        status=status,
        fill_status=fill_status,
        lab_id=lab_id,
        page=page,
        per_page=20
    )
    
    # Get filter options
    labs = db.get_labs_simple_list()
    
    # Waste type options
    waste_types = ['chemical', 'biological', 'sharps', 'general', 'radioactive', 'electronic']
    status_options = ['active', 'awaiting_collection', 'collected', 'disposed', 'closed']
    fill_status_options = ['empty', 'partial', 'nearly_full', 'full', 'overfull']
    
    return render_template('waste_list.html',
        wastes=wastes,
        page=page,
        total=total,
        per_page=20,
        search=search,
        waste_type=waste_type,
        status=status,
        fill_status=fill_status,
        lab_id=lab_id,
        labs=labs,
        waste_types=waste_types,
        status_options=status_options,
        fill_status_options=fill_status_options,
    )


@main_bp.route('/waste/<int:waste_id>')
def waste_detail(waste_id):
    """Waste container detail page."""
    db = get_db_service()
    waste = db.get_waste(waste_id)
    
    if not waste:
        flash('Waste container not found', 'error')
        return redirect(url_for('main.waste_list'))
    
    # Get linked precursors
    linked_precursors = db.get_waste_precursors(waste_id)
    
    # Get images and files
    images = db.get_entity_images('waste', waste_id)
    files = db.get_entity_attachments('waste', waste_id)
    
    # Get location
    locations = db.get_object_locations('waste', waste_id)
    
    return render_template('waste_detail.html',
        waste=waste,
        linked_precursors=linked_precursors,
        images=images,
        files=files,
        locations=locations,
        entity_type='waste',
        entity_id=waste_id,
    )


@main_bp.route('/waste/new', methods=['GET', 'POST'])
@login_required
def waste_new():
    """Create a new waste container."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        owner_id = request.form.get('owner_id')
        
        data = {
            'name': request.form.get('name'),
            'waste_type': request.form.get('waste_type'),
            'hazard_classes': request.form.getlist('hazard_classes'),  # Multiple hazard classes
            'container_type': request.form.get('container_type'),
            'container_size': request.form.get('container_size'),
            'current_fill_percent': float(request.form.get('current_fill_percent', 0) or 0),
            'fill_status': request.form.get('fill_status', 'empty'),
            'status': request.form.get('status', 'active'),
            'contents_description': request.form.get('contents_description'),
            'contains_chemicals': request.form.get('contains_chemicals'),
            'ph_range': request.form.get('ph_range'),
            'epa_waste_code': request.form.get('epa_waste_code'),
            'un_number': request.form.get('un_number'),
            'sds_reference': request.form.get('sds_reference'),
            'special_handling': request.form.get('special_handling'),
            'notes': request.form.get('notes'),
            'lab_id': int(lab_id) if lab_id else session.get('current_lab_id'),
            'project_id': int(project_id) if project_id else None,
            'owner_id': int(owner_id) if owner_id else g.current_user['id'],
            'created_by': g.current_user.get('name') or g.current_user.get('email'),
        }
        
        # Handle dates
        if request.form.get('opened_date'):
            data['opened_date'] = request.form.get('opened_date')
        
        try:
            item = db.create_waste(data)
            flash(f'Waste container "{item["name"]}" created', 'success')
            return redirect(url_for('main.waste_detail', waste_id=item['id']))
        except Exception as e:
            flash(f'Error creating waste container: {str(e)}', 'error')
    
    # Get dropdown options
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    users = db.get_users_simple_list()
    locations = db.get_locations_simple_list()
    
    # Get user defaults for lab/project
    default_lab_id = None
    default_project_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
        default_project_id = user_prefs.get('default_project_id')
    
    # Waste options
    waste_types = ['chemical', 'biological', 'sharps', 'general', 'radioactive', 'electronic']
    hazard_classes = ['flammable', 'corrosive', 'toxic', 'oxidizer', 'reactive', 'non-hazardous']
    container_types = ['bottle', 'drum', 'sharps_container', 'bag', 'box', 'other']
    status_options = ['active', 'awaiting_collection', 'collected', 'disposed', 'closed']
    fill_status_options = ['empty', 'partial', 'nearly_full', 'full', 'overfull']
    
    return render_template('waste_form.html',
        waste=None,
        action='Create',
        labs=labs,
        projects=projects,
        users=users,
        locations=locations,
        waste_types=waste_types,
        hazard_classes=hazard_classes,
        container_types=container_types,
        status_options=status_options,
        fill_status_options=fill_status_options,
        current_user_id=g.current_user['id'],
        default_lab_id=default_lab_id,
        default_project_id=default_project_id,
    )


@main_bp.route('/waste/<int:waste_id>/edit', methods=['GET', 'POST'])
@login_required
def waste_edit(waste_id):
    """Edit an existing waste container."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    waste = db.get_waste(waste_id)
    if not waste:
        flash('Waste container not found', 'error')
        return redirect(url_for('main.waste_list'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        owner_id = request.form.get('owner_id')
        
        data = {
            'name': request.form.get('name'),
            'waste_type': request.form.get('waste_type'),
            'hazard_classes': request.form.getlist('hazard_classes'),  # Multiple hazard classes
            'container_type': request.form.get('container_type'),
            'container_size': request.form.get('container_size'),
            'current_fill_percent': float(request.form.get('current_fill_percent', 0) or 0),
            'fill_status': request.form.get('fill_status', 'empty'),
            'status': request.form.get('status', 'active'),
            'contents_description': request.form.get('contents_description'),
            'contains_chemicals': request.form.get('contains_chemicals'),
            'ph_range': request.form.get('ph_range'),
            'epa_waste_code': request.form.get('epa_waste_code'),
            'un_number': request.form.get('un_number'),
            'sds_reference': request.form.get('sds_reference'),
            'special_handling': request.form.get('special_handling'),
            'notes': request.form.get('notes'),
            'disposal_vendor': request.form.get('disposal_vendor'),
            'manifest_number': request.form.get('manifest_number'),
            'lab_id': int(lab_id) if lab_id else session.get('current_lab_id'),
            'project_id': int(project_id) if project_id else None,
            'owner_id': int(owner_id) if owner_id else None,
        }
        
        # Handle dates
        for date_field in ['opened_date', 'full_date', 'collection_requested_date', 
                           'collected_date', 'disposal_date']:
            if request.form.get(date_field):
                data[date_field] = request.form.get(date_field)
            else:
                data[date_field] = None
        
        try:
            item = db.update_waste(waste_id, data)
            flash(f'Waste container "{item["name"]}" updated', 'success')
            return redirect(url_for('main.waste_detail', waste_id=waste_id))
        except Exception as e:
            flash(f'Error updating waste container: {str(e)}', 'error')
    
    # Get dropdown options
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    users = db.get_users_simple_list()
    locations = db.get_locations_simple_list()
    
    # Waste options
    waste_types = ['chemical', 'biological', 'sharps', 'general', 'radioactive', 'electronic']
    hazard_classes = ['flammable', 'corrosive', 'toxic', 'oxidizer', 'reactive', 'non-hazardous']
    container_types = ['bottle', 'drum', 'sharps_container', 'bag', 'box', 'other']
    status_options = ['active', 'awaiting_collection', 'collected', 'disposed', 'closed']
    fill_status_options = ['empty', 'partial', 'nearly_full', 'full', 'overfull']
    
    return render_template('waste_form.html',
        waste=waste,
        action='Edit',
        labs=labs,
        projects=projects,
        users=users,
        locations=locations,
        waste_types=waste_types,
        hazard_classes=hazard_classes,
        container_types=container_types,
        status_options=status_options,
        fill_status_options=fill_status_options,
        current_user_id=g.current_user['id'],
    )


@main_bp.route('/waste/<int:waste_id>/duplicate', methods=['GET', 'POST'])
@login_required
def waste_duplicate(waste_id):
    """Duplicate an existing waste container."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    original = db.get_waste(waste_id)
    if not original:
        flash('Waste container not found', 'error')
        return redirect(url_for('main.waste_list'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        owner_id = request.form.get('owner_id')
        
        data = {
            'name': request.form.get('name'),
            'waste_type': request.form.get('waste_type'),
            'hazard_class': request.form.get('hazard_class'),
            'container_type': request.form.get('container_type'),
            'container_size': request.form.get('container_size'),
            'current_fill_percent': 0,  # Start empty
            'fill_status': 'empty',
            'status': 'active',
            'contents_description': request.form.get('contents_description'),
            'contains_chemicals': request.form.get('contains_chemicals'),
            'ph_range': request.form.get('ph_range'),
            'epa_waste_code': request.form.get('epa_waste_code'),
            'un_number': request.form.get('un_number'),
            'sds_reference': request.form.get('sds_reference'),
            'special_handling': request.form.get('special_handling'),
            'notes': request.form.get('notes'),
            'lab_id': int(lab_id) if lab_id else session.get('current_lab_id'),
            'project_id': int(project_id) if project_id else None,
            'owner_id': int(owner_id) if owner_id else g.current_user['id'],
            'created_by': g.current_user.get('name') or g.current_user.get('email'),
        }
        
        try:
            item = db.create_waste(data)
            flash(f'Waste container "{item["name"]}" created', 'success')
            return redirect(url_for('main.waste_detail', waste_id=item['id']))
        except Exception as e:
            flash(f'Error creating waste container: {str(e)}', 'error')
    
    # Pre-fill form with original data but reset fill level
    duplicated = original.copy()
    duplicated['name'] = f"{original['name']} (Copy)"
    duplicated['current_fill_percent'] = 0
    duplicated['fill_status'] = 'empty'
    duplicated['status'] = 'active'
    duplicated['opened_date'] = None
    duplicated['full_date'] = None
    duplicated['collection_requested_date'] = None
    duplicated['collected_date'] = None
    duplicated['disposal_date'] = None
    
    # Get dropdown options
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    users = db.get_users_simple_list()
    locations = db.get_locations_simple_list()
    
    # Waste options
    waste_types = ['chemical', 'biological', 'sharps', 'general', 'radioactive', 'electronic']
    hazard_classes = ['flammable', 'corrosive', 'toxic', 'oxidizer', 'reactive', 'non-hazardous']
    container_types = ['bottle', 'drum', 'sharps_container', 'bag', 'box', 'other']
    status_options = ['active', 'awaiting_collection', 'collected', 'disposed', 'closed']
    fill_status_options = ['empty', 'partial', 'nearly_full', 'full', 'overfull']
    
    return render_template('waste_form.html',
        waste=duplicated,
        action='Duplicate',
        labs=labs,
        projects=projects,
        users=users,
        locations=locations,
        waste_types=waste_types,
        hazard_classes=hazard_classes,
        container_types=container_types,
        status_options=status_options,
        fill_status_options=fill_status_options,
        current_user_id=g.current_user['id'],
    )


@main_bp.route('/waste/<int:waste_id>/delete', methods=['POST'])
@login_required
def waste_delete(waste_id):
    """Delete a waste container."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    waste = db.get_waste(waste_id)
    if not waste:
        flash('Waste container not found', 'error')
        return redirect(url_for('main.waste_list'))
    
    name = waste['name']
    if db.delete_waste(waste_id):
        flash(f'Waste container "{name}" deleted', 'success')
    else:
        flash('Error deleting waste container', 'error')
    
    return redirect(url_for('main.waste_list'))


@main_bp.route('/waste/<int:waste_id>/replace', methods=['GET', 'POST'])
@login_required
def waste_replace(waste_id):
    """Replace a waste container with a new one, updating all template references."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    original = db.get_waste(waste_id)
    if not original:
        flash('Waste container not found', 'error')
        return redirect(url_for('main.waste_list'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        owner_id = request.form.get('owner_id')
        
        data = {
            'name': request.form.get('name'),
            'waste_type': request.form.get('waste_type'),
            'hazard_class': request.form.get('hazard_class'),
            'container_type': request.form.get('container_type'),
            'container_size': request.form.get('container_size'),
            'current_fill_percent': 0,
            'fill_status': 'empty',
            'status': 'active',
            'contents_description': request.form.get('contents_description'),
            'contains_chemicals': request.form.get('contains_chemicals'),
            'ph_range': request.form.get('ph_range'),
            'epa_waste_code': request.form.get('epa_waste_code'),
            'un_number': request.form.get('un_number'),
            'sds_reference': request.form.get('sds_reference'),
            'special_handling': request.form.get('special_handling'),
            'notes': request.form.get('notes'),
            'lab_id': int(lab_id) if lab_id else session.get('current_lab_id'),
            'project_id': int(project_id) if project_id else None,
            'owner_id': int(owner_id) if owner_id else g.current_user['id'],
            'created_by': g.current_user.get('name') or g.current_user.get('email'),
        }
        
        try:
            item = db.create_waste(data)
            templates_updated = db.replace_waste_in_templates(waste_id, item['id'])
            
            if templates_updated > 0:
                flash(f'Waste container "{item["name"]}" created and replaced in {templates_updated} template(s)', 'success')
            else:
                flash(f'Waste container "{item["name"]}" created (no templates referenced the original)', 'success')
            
            return redirect(url_for('main.waste_detail', waste_id=item['id']))
        except Exception as e:
            flash(f'Error creating waste container: {str(e)}', 'error')
    
    # Pre-fill form with original data
    replaced = original.copy()
    replaced['name'] = f"{original['name']} (Replacement)"
    replaced['current_fill_percent'] = 0
    replaced['fill_status'] = 'empty'
    replaced['status'] = 'active'
    
    # Get dropdown options
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    users = db.get_users_simple_list()
    locations = db.get_locations_simple_list()
    
    # Waste options
    waste_types = ['chemical', 'biological', 'sharps', 'general', 'radioactive', 'electronic']
    hazard_classes = ['flammable', 'corrosive', 'toxic', 'oxidizer', 'reactive', 'non-hazardous']
    container_types = ['bottle', 'drum', 'sharps_container', 'bag', 'box', 'other']
    status_options = ['active', 'awaiting_collection', 'collected', 'disposed', 'closed']
    fill_status_options = ['empty', 'partial', 'nearly_full', 'full', 'overfull']
    
    return render_template('waste_form.html',
        waste=replaced,
        action='Replace',
        original_waste=original,
        labs=labs,
        projects=projects,
        users=users,
        locations=locations,
        waste_types=waste_types,
        hazard_classes=hazard_classes,
        container_types=container_types,
        status_options=status_options,
        fill_status_options=fill_status_options,
        current_user_id=g.current_user['id'],
    )


@main_bp.route('/waste/<int:waste_id>/precursors', methods=['POST'])
@login_required
def waste_add_precursor(waste_id):
    """Add a precursor to a waste container."""
    db = get_db_service()
    
    if g.current_user is None:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    precursor_id = request.form.get('precursor_id', type=int)
    quantity = request.form.get('quantity', type=float)
    quantity_unit = request.form.get('quantity_unit')
    notes = request.form.get('notes')
    
    if not precursor_id:
        flash('Please select a precursor', 'error')
        return redirect(url_for('main.waste_detail', waste_id=waste_id))
    
    result = db.add_precursor_to_waste(waste_id, precursor_id, quantity, quantity_unit, notes)
    
    if result:
        flash('Precursor added to waste container', 'success')
    else:
        flash('Precursor is already linked to this waste container', 'warning')
    
    return redirect(url_for('main.waste_detail', waste_id=waste_id))


@main_bp.route('/waste/<int:waste_id>/precursors/<int:precursor_id>/remove', methods=['POST'])
@login_required
def waste_remove_precursor(waste_id, precursor_id):
    """Remove a precursor from a waste container."""
    db = get_db_service()
    
    if g.current_user is None:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    if db.remove_precursor_from_waste(waste_id, precursor_id):
        flash('Precursor removed from waste container', 'success')
    else:
        flash('Precursor not found in waste container', 'error')
    
    return redirect(url_for('main.waste_detail', waste_id=waste_id))


@main_bp.route('/waste/<int:waste_id>/qrcode')
def waste_qrcode(waste_id):
    """Generate and download QR code for a waste container."""
    db = get_db_service()
    waste = db.get_waste(waste_id)
    
    if not waste:
        flash('Waste container not found', 'error')
        return redirect(url_for('main.waste_list'))
    
    # Generate QR code URL
    base_url = request.host_url.rstrip('/')
    url = f"{base_url}/waste/{waste_id}"
    
    try:
        import qrcode
        from io import BytesIO
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'waste_{waste_id}_qrcode.png'
        )
    except ImportError:
        flash('QR code library not installed', 'error')
        return redirect(url_for('main.waste_detail', waste_id=waste_id))


@main_bp.route('/waste/<int:waste_id>/qrcode/preview')
def waste_qrcode_preview(waste_id):
    """Generate QR code preview for a waste container."""
    db = get_db_service()
    waste = db.get_waste(waste_id)
    
    if not waste:
        # Return a placeholder image
        return '', 404
    
    base_url = request.host_url.rstrip('/')
    url = f"{base_url}/waste/{waste_id}"
    
    try:
        import qrcode
        from io import BytesIO
        
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return send_file(buffer, mimetype='image/png')
    except ImportError:
        return '', 404


# -------------------- Procedures --------------------

@main_bp.route('/procedures')
def procedures():
    """Procedures list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    procedure_type = request.args.get('type', '')
    lab_id = request.args.get('lab_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    db = get_db_service()
    procedures_list, total = db.get_procedures(
        search=search if search else None,
        procedure_type=procedure_type if procedure_type else None,
        lab_id=lab_id,
        project_id=project_id,
        page=page
    )
    
    # Get labs and projects for filter dropdowns
    labs_list, _ = db.get_labs(per_page=100)
    projects_list = db.get_projects_simple_list()
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'procedure')
    
    return render_template('procedures.html',
        procedures=procedures_list,
        labs=labs_list,
        projects=projects_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        procedure_type=procedure_type,
        lab_id=lab_id,
        project_id=project_id,
        pinned_ids=pinned_ids
    )


@main_bp.route('/procedures/<int:procedure_id>')
def procedure_detail(procedure_id):
    """Procedure detail page."""
    db = get_db_service()
    procedure = db.get_procedure(procedure_id)
    if not procedure:
        flash('Procedure not found', 'error')
        return redirect(url_for('main.procedures'))
    images = db.get_entity_images('procedure', procedure_id)
    attachments = db.get_entity_attachments('procedure', procedure_id)
    return render_template('procedure_detail.html', procedure=procedure, images=images, attachments=attachments)


@main_bp.route('/procedures/new', methods=['GET', 'POST'])
def procedure_new():
    """Create new procedure page."""
    db = get_db_service()
    
    # Check if a template_id was provided (e.g., from QR code scan)
    template_id = request.args.get('template_id', type=int)
    template = None
    prefilled = None
    
    if template_id:
        template = db.get_template(template_id)
        if template and template['entity_type'] == 'procedure':
            td = template.get('template_data', {})
            prefilled = {
                'name': td.get('name', ''),
                'procedure_type': td.get('procedure_type', ''),
                'version': td.get('version', '1.0'),
                'description': td.get('description', ''),
                'steps': td.get('steps', []),
                'estimated_duration_minutes': td.get('estimated_duration_minutes'),
                'safety_requirements': td.get('safety_requirements', ''),
                'created_by': td.get('created_by', ''),
            }
    
    if request.method == 'POST':
        # Parse procedure-level parameters
        proc_params = []
        proc_param_names = request.form.getlist('proc_param_name[]')
        proc_param_types = request.form.getlist('proc_param_type[]')
        proc_param_defaults = request.form.getlist('proc_param_default[]')
        proc_param_units = request.form.getlist('proc_param_unit[]')
        proc_param_options = request.form.getlist('proc_param_options[]')
        
        for i, name in enumerate(proc_param_names):
            if name.strip():
                param = {
                    'name': name.strip(),
                    'type': proc_param_types[i] if i < len(proc_param_types) else 'text',
                    'default': proc_param_defaults[i].strip() if i < len(proc_param_defaults) else '',
                }
                if i < len(proc_param_units) and proc_param_units[i].strip():
                    param['unit'] = proc_param_units[i].strip()
                if i < len(proc_param_options) and proc_param_options[i].strip():
                    param['options'] = [o.strip() for o in proc_param_options[i].split(',') if o.strip()]
                proc_params.append(param)
        
        # Parse steps from form
        steps = []
        step_names = request.form.getlist('step_name[]')
        step_descriptions = request.form.getlist('step_description[]')
        step_durations = request.form.getlist('step_duration[]')
        
        for i, name in enumerate(step_names):
            if name.strip():
                step = {'name': name.strip()}
                if i < len(step_descriptions) and step_descriptions[i].strip():
                    step['description'] = step_descriptions[i].strip()
                if i < len(step_durations) and step_durations[i].strip():
                    try:
                        step['duration_minutes'] = int(step_durations[i])
                    except ValueError:
                        pass
                
                # Parse step-level parameters
                step_param_names = request.form.getlist(f'step_param_name_{i}[]')
                step_param_types = request.form.getlist(f'step_param_type_{i}[]')
                step_param_defaults = request.form.getlist(f'step_param_default_{i}[]')
                step_param_units = request.form.getlist(f'step_param_unit_{i}[]')
                step_param_options = request.form.getlist(f'step_param_options_{i}[]')
                
                step_params = []
                for j, pname in enumerate(step_param_names):
                    if pname.strip():
                        sparam = {
                            'name': pname.strip(),
                            'type': step_param_types[j] if j < len(step_param_types) else 'text',
                            'default': step_param_defaults[j].strip() if j < len(step_param_defaults) else '',
                        }
                        if j < len(step_param_units) and step_param_units[j].strip():
                            sparam['unit'] = step_param_units[j].strip()
                        if j < len(step_param_options) and step_param_options[j].strip():
                            sparam['options'] = [o.strip() for o in step_param_options[j].split(',') if o.strip()]
                        step_params.append(sparam)
                
                if step_params:
                    step['parameters'] = step_params
                
                steps.append(step)
        
        # Parse failure modes
        failure_modes_raw = request.form.get('failure_modes', '').strip()
        failure_modes = [m.strip() for m in failure_modes_raw.split('\n') if m.strip()] if failure_modes_raw else None
        
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        data = {
            'name': request.form.get('name'),
            'procedure_type': request.form.get('procedure_type'),
            'version': request.form.get('version', '1.0'),
            'description': request.form.get('description'),
            'steps': steps if steps else None,
            'parameters': proc_params if proc_params else None,
            'failure_modes': failure_modes,
            'estimated_duration_minutes': int(request.form.get('estimated_duration_minutes')) if request.form.get('estimated_duration_minutes') else None,
            'safety_requirements': request.form.get('safety_requirements'),
            'created_by': request.form.get('created_by'),
            'lab_id': int(lab_id) if lab_id else None,
            'project_id': int(project_id) if project_id else None,
        }
        try:
            procedure = db.create_procedure(data)
            
            # Handle precursors
            precursor_ids = request.form.getlist('precursor_id[]')
            precursor_purposes = request.form.getlist('precursor_purpose[]')
            precursor_quantities = request.form.getlist('precursor_quantity[]')
            precursor_units = request.form.getlist('precursor_unit[]')
            
            precursor_list = []
            for i, prec_id in enumerate(precursor_ids):
                if prec_id:
                    precursor_list.append({
                        'precursor_id': int(prec_id),
                        'purpose': precursor_purposes[i] if i < len(precursor_purposes) else None,
                        'quantity': float(precursor_quantities[i]) if i < len(precursor_quantities) and precursor_quantities[i] else None,
                        'quantity_unit': precursor_units[i] if i < len(precursor_units) else None,
                        'is_required': True
                    })
            
            if precursor_list:
                db.update_procedure_precursor_list(procedure['id'], precursor_list)
            
            flash(f'Procedure "{procedure["name"]}" created successfully', 'success')
            return redirect(url_for('main.procedure_detail', procedure_id=procedure['id']))
        except Exception as e:
            flash(f'Error creating procedure: {str(e)}', 'error')
    
    # Get labs, projects and precursors for dropdowns
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    precursors = db.get_precursors_simple_list()
    
    # Get user defaults
    default_lab_id = None
    default_project_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
        default_project_id = user_prefs.get('default_project_id')
    
    return render_template('procedure_form.html', procedure=prefilled, action='Create', template=template, labs=labs, projects=projects, precursors=precursors, default_lab_id=default_lab_id, default_project_id=default_project_id)


@main_bp.route('/procedures/<int:procedure_id>/edit', methods=['GET', 'POST'])
def procedure_edit(procedure_id):
    """Edit procedure page."""
    db = get_db_service()
    procedure = db.get_procedure(procedure_id)
    
    if not procedure:
        flash('Procedure not found', 'error')
        return redirect(url_for('main.procedures'))
    
    if request.method == 'POST':
        # Parse procedure-level parameters
        proc_params = []
        proc_param_names = request.form.getlist('proc_param_name[]')
        proc_param_types = request.form.getlist('proc_param_type[]')
        proc_param_defaults = request.form.getlist('proc_param_default[]')
        proc_param_units = request.form.getlist('proc_param_unit[]')
        proc_param_options = request.form.getlist('proc_param_options[]')
        
        for i, name in enumerate(proc_param_names):
            if name.strip():
                param = {
                    'name': name.strip(),
                    'type': proc_param_types[i] if i < len(proc_param_types) else 'text',
                    'default': proc_param_defaults[i].strip() if i < len(proc_param_defaults) else '',
                }
                if i < len(proc_param_units) and proc_param_units[i].strip():
                    param['unit'] = proc_param_units[i].strip()
                if i < len(proc_param_options) and proc_param_options[i].strip():
                    param['options'] = [o.strip() for o in proc_param_options[i].split(',') if o.strip()]
                proc_params.append(param)
        
        # Parse steps from form
        steps = []
        step_names = request.form.getlist('step_name[]')
        step_descriptions = request.form.getlist('step_description[]')
        step_durations = request.form.getlist('step_duration[]')
        
        for i, name in enumerate(step_names):
            if name.strip():
                step = {'name': name.strip()}
                if i < len(step_descriptions) and step_descriptions[i].strip():
                    step['description'] = step_descriptions[i].strip()
                if i < len(step_durations) and step_durations[i].strip():
                    try:
                        step['duration_minutes'] = int(step_durations[i])
                    except ValueError:
                        pass
                
                # Parse step-level parameters
                step_param_names = request.form.getlist(f'step_param_name_{i}[]')
                step_param_types = request.form.getlist(f'step_param_type_{i}[]')
                step_param_defaults = request.form.getlist(f'step_param_default_{i}[]')
                step_param_units = request.form.getlist(f'step_param_unit_{i}[]')
                step_param_options = request.form.getlist(f'step_param_options_{i}[]')
                
                step_params = []
                for j, pname in enumerate(step_param_names):
                    if pname.strip():
                        sparam = {
                            'name': pname.strip(),
                            'type': step_param_types[j] if j < len(step_param_types) else 'text',
                            'default': step_param_defaults[j].strip() if j < len(step_param_defaults) else '',
                        }
                        if j < len(step_param_units) and step_param_units[j].strip():
                            sparam['unit'] = step_param_units[j].strip()
                        if j < len(step_param_options) and step_param_options[j].strip():
                            sparam['options'] = [o.strip() for o in step_param_options[j].split(',') if o.strip()]
                        step_params.append(sparam)
                
                if step_params:
                    step['parameters'] = step_params
                
                steps.append(step)
        
        # Parse failure modes
        failure_modes_raw = request.form.get('failure_modes', '').strip()
        failure_modes = [m.strip() for m in failure_modes_raw.split('\n') if m.strip()] if failure_modes_raw else None
        
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        data = {
            'name': request.form.get('name'),
            'procedure_type': request.form.get('procedure_type'),
            'version': request.form.get('version', '1.0'),
            'description': request.form.get('description'),
            'steps': steps if steps else None,
            'parameters': proc_params if proc_params else None,
            'failure_modes': failure_modes,
            'estimated_duration_minutes': int(request.form.get('estimated_duration_minutes')) if request.form.get('estimated_duration_minutes') else None,
            'safety_requirements': request.form.get('safety_requirements'),
            'created_by': request.form.get('created_by'),
            'lab_id': int(lab_id) if lab_id else None,
            'project_id': int(project_id) if project_id else None,
        }
        try:
            updated = db.update_procedure(procedure_id, data)
            
            # Handle precursors
            precursor_ids = request.form.getlist('precursor_id[]')
            precursor_purposes = request.form.getlist('precursor_purpose[]')
            precursor_quantities = request.form.getlist('precursor_quantity[]')
            precursor_units = request.form.getlist('precursor_unit[]')
            
            precursor_list = []
            for i, prec_id in enumerate(precursor_ids):
                if prec_id:
                    precursor_list.append({
                        'precursor_id': int(prec_id),
                        'purpose': precursor_purposes[i] if i < len(precursor_purposes) else None,
                        'quantity': float(precursor_quantities[i]) if i < len(precursor_quantities) and precursor_quantities[i] else None,
                        'quantity_unit': precursor_units[i] if i < len(precursor_units) else None,
                        'is_required': True
                    })
            
            db.update_procedure_precursor_list(procedure_id, precursor_list)
            
            flash(f'Procedure "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.procedure_detail', procedure_id=procedure_id))
        except Exception as e:
            flash(f'Error updating procedure: {str(e)}', 'error')
    
    # Get labs, projects and precursors for dropdowns
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    precursors = db.get_precursors_simple_list()
    
    # Get procedure's existing precursors
    procedure_precursors = db.get_procedure_precursors(procedure_id)
    
    return render_template('procedure_form.html', procedure=procedure, action='Edit', labs=labs, projects=projects, precursors=precursors, procedure_precursors=procedure_precursors)


@main_bp.route('/procedures/<int:procedure_id>/duplicate', methods=['GET', 'POST'])
def procedure_duplicate(procedure_id):
    """Duplicate an existing procedure."""
    db = get_db_service()
    original = db.get_procedure(procedure_id)
    if not original:
        flash('Procedure not found', 'error')
        return redirect(url_for('main.procedures'))
    
    if request.method == 'POST':
        # Parse steps from form
        steps = []
        step_orders = request.form.getlist('step_order[]')
        step_names = request.form.getlist('step_name[]')
        step_descriptions = request.form.getlist('step_description[]')
        step_durations = request.form.getlist('step_duration[]')
        
        for i in range(len(step_names)):
            if step_names[i].strip():
                step = {
                    'order': int(step_orders[i]) if i < len(step_orders) and step_orders[i] else i + 1,
                    'name': step_names[i],
                    'description': step_descriptions[i] if i < len(step_descriptions) else '',
                }
                if i < len(step_durations) and step_durations[i]:
                    try:
                        step['duration_minutes'] = int(step_durations[i])
                    except ValueError:
                        pass
                steps.append(step)
        
        lab_id = request.form.get('lab_id')
        project_id = request.form.get('project_id')
        data = {
            'name': request.form.get('name'),
            'procedure_type': request.form.get('procedure_type'),
            'version': request.form.get('version', '1.0'),
            'description': request.form.get('description'),
            'steps': steps if steps else None,
            'estimated_duration_minutes': int(request.form.get('estimated_duration_minutes')) if request.form.get('estimated_duration_minutes') else None,
            'safety_requirements': request.form.get('safety_requirements'),
            'created_by': request.form.get('created_by'),
            'lab_id': int(lab_id) if lab_id else None,
            'project_id': int(project_id) if project_id else None,
        }
        try:
            new_procedure = db.create_procedure(data)
            flash(f'Procedure "{new_procedure["name"]}" created successfully', 'success')
            return redirect(url_for('main.procedure_detail', procedure_id=new_procedure['id']))
        except Exception as e:
            flash(f'Error creating procedure: {str(e)}', 'error')
    
    # Pre-fill with original data but modify the name
    procedure = dict(original)
    procedure['name'] = f"{original['name']} (Copy)"
    
    # Get labs, projects and precursors for dropdown
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    precursors = db.get_precursors_simple_list()
    
    return render_template('procedure_form.html', procedure=procedure, action='Duplicate', labs=labs, projects=projects, precursors=precursors)


@main_bp.route('/procedures/<int:procedure_id>/delete', methods=['POST'])
@login_required
def procedure_delete(procedure_id):
    """Move a procedure to trash."""
    db = get_db_service()
    procedure = db.get_procedure(procedure_id)
    
    if not procedure:
        flash('Procedure not found', 'error')
        return redirect(url_for('main.procedures'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('procedure', procedure_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash(f'Procedure "{procedure["name"]}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving procedure to trash'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.procedures'))


# -------------------- Labs --------------------

@main_bp.route('/labs')
def labs():
    """Labs list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    db = get_db_service()
    labs_list, total = db.get_labs(
        search=search if search else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    return render_template('labs.html',
        labs=labs_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search
    )


@main_bp.route('/labs/<int:lab_id>')
def lab_detail(lab_id):
    """Lab detail page."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    images = db.get_entity_images('lab', lab_id)
    attachments = db.get_entity_attachments('lab', lab_id)
    teams = db.get_teams(lab_id, include_inactive=False)
    return render_template('lab_detail.html', lab=lab, images=images, attachments=attachments, teams=teams)


@main_bp.route('/labs/new', methods=['GET', 'POST'])
def lab_new():
    """Create new lab page."""
    if request.method == 'POST':
        db = get_db_service()
        
        # Parse comma-separated type lists into arrays
        location_types_str = request.form.get('location_types', '')
        equipment_types_str = request.form.get('equipment_types', '')
        location_types = [t.strip() for t in location_types_str.split(',') if t.strip()] or None
        equipment_types = [t.strip() for t in equipment_types_str.split(',') if t.strip()] or None
        
        data = {
            'name': request.form.get('name'),
            'code': request.form.get('code') or None,
            'university': request.form.get('university'),
            'department': request.form.get('department'),
            'description': request.form.get('description'),
            'address': request.form.get('address'),
            'website': request.form.get('website'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'location_types': location_types,
            'equipment_types': equipment_types,
        }
        try:
            lab = db.create_lab(data)
            flash(f'Lab "{lab["name"]}" created successfully', 'success')
            return redirect(url_for('main.lab_detail', lab_id=lab['id']))
        except Exception as e:
            flash(f'Error creating lab: {str(e)}', 'error')
    
    return render_template('lab_form.html', lab=None, action='Create')


@main_bp.route('/labs/<int:lab_id>/edit', methods=['GET', 'POST'])
def lab_edit(lab_id):
    """Edit lab page."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    if request.method == 'POST':
        # Parse comma-separated type lists into arrays
        location_types_str = request.form.get('location_types', '')
        equipment_types_str = request.form.get('equipment_types', '')
        location_types = [t.strip() for t in location_types_str.split(',') if t.strip()] or None
        equipment_types = [t.strip() for t in equipment_types_str.split(',') if t.strip()] or None
        
        data = {
            'name': request.form.get('name'),
            'code': request.form.get('code') or None,
            'university': request.form.get('university'),
            'department': request.form.get('department'),
            'description': request.form.get('description'),
            'address': request.form.get('address'),
            'website': request.form.get('website'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'location_types': location_types,
            'equipment_types': equipment_types,
        }
        try:
            updated = db.update_lab(lab_id, data)
            flash(f'Lab "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.lab_detail', lab_id=lab_id))
        except Exception as e:
            flash(f'Error updating lab: {str(e)}', 'error')
    
    return render_template('lab_form.html', lab=lab, action='Edit')


@main_bp.route('/labs/<int:lab_id>/members/add', methods=['GET', 'POST'])
def lab_member_add(lab_id):
    """Add member to lab."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'role': request.form.get('role', 'member'),
            'title': request.form.get('title'),
            'orcid': request.form.get('orcid'),
            'phone': request.form.get('phone'),
            'office_location': request.form.get('office_location'),
            'notes': request.form.get('notes'),
        }
        try:
            member = db.create_lab_member(lab_id, data)
            flash(f'Member "{member["name"]}" added successfully', 'success')
            return redirect(url_for('main.lab_detail', lab_id=lab_id))
        except Exception as e:
            flash(f'Error adding member: {str(e)}', 'error')
    
    return render_template('lab_member_form.html', lab=lab, member=None, action='Add')


@main_bp.route('/labs/<int:lab_id>/members/<int:member_id>/edit', methods=['GET', 'POST'])
def lab_member_edit(lab_id, member_id):
    """Edit lab member."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    member = db.get_lab_member(member_id)
    
    if not lab or not member:
        flash('Lab or member not found', 'error')
        return redirect(url_for('main.labs'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'role': request.form.get('role', 'member'),
            'title': request.form.get('title'),
            'orcid': request.form.get('orcid'),
            'phone': request.form.get('phone'),
            'office_location': request.form.get('office_location'),
            'notes': request.form.get('notes'),
            'is_active': 'is_active' in request.form,
        }
        
        # Handle date fields
        left_at = request.form.get('left_at')
        if left_at:
            data['left_at'] = left_at
        
        access_expires_at = request.form.get('access_expires_at')
        if access_expires_at:
            data['access_expires_at'] = access_expires_at
        
        try:
            updated = db.update_lab_member(member_id, data)
            flash(f'Member "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.lab_detail', lab_id=lab_id))
        except Exception as e:
            flash(f'Error updating member: {str(e)}', 'error')
    
    return render_template('lab_member_form.html', lab=lab, member=member, action='Edit')


@main_bp.route('/labs/<int:lab_id>/members/<int:member_id>/remove', methods=['POST'])
def lab_member_remove(lab_id, member_id):
    """Remove member from lab."""
    db = get_db_service()
    if db.remove_lab_member(member_id):
        flash('Member removed successfully', 'success')
    else:
        flash('Error removing member', 'error')
    return redirect(url_for('main.lab_detail', lab_id=lab_id))


@main_bp.route('/labs/<int:lab_id>/delete', methods=['POST'])
@login_required
def lab_delete(lab_id):
    """Move a lab to trash (soft-delete with cascade to all children)."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('lab', lab_id, trashed_by=username, cascade=True)
        
        if result['success']:
            flash(f'Lab "{lab["name"]}" moved to trash. It will be permanently deleted in 30 days.', 'success')
        else:
            flash(result.get('error', 'Error moving lab to trash'), 'error')
    except Exception as e:
        flash(f'Cannot delete lab: {str(e)}', 'error')
    
    return redirect(url_for('main.labs'))


@main_bp.route('/labs/<int:lab_id>/types')
def lab_types(lab_id):
    """Get lab-specific location and equipment types (JSON API)."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        return jsonify({'error': 'Lab not found'}), 404
    
    return jsonify({
        'location_types': lab.get('location_types', ['room', 'cabinet', 'shelf', 'drawer', 'fridge', 'freezer', 'bench', 'other']),
        'equipment_types': lab.get('equipment_types', ['glovebox', 'chamber', 'lithography', 'furnace', 'other'])
    })


# -------------------- Teams --------------------

@main_bp.route('/labs/<int:lab_id>/teams')
def lab_teams(lab_id):
    """List all teams in a lab."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    teams = db.get_teams(lab_id, include_inactive=include_inactive)
    
    return render_template('teams/list.html', 
                           lab=lab, 
                           teams=teams,
                           include_inactive=include_inactive)


@main_bp.route('/labs/<int:lab_id>/teams/<int:team_id>')
def team_detail(lab_id, team_id):
    """View team details with members and access grants."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    team = db.get_team(team_id)
    
    if not team or team['lab_id'] != lab_id:
        flash('Team not found', 'error')
        return redirect(url_for('main.lab_teams', lab_id=lab_id))
    
    # Get available lab members not already in team
    lab_members = db.get_lab_members(lab_id, include_inactive=False)
    team_member_ids = {m['lab_member_id'] for m in team.get('members', [])}
    available_members = [m for m in lab_members if m['id'] not in team_member_ids]
    
    return render_template('teams/detail.html', 
                           lab=lab, 
                           team=team, 
                           available_members=available_members)


@main_bp.route('/labs/<int:lab_id>/teams/new', methods=['GET', 'POST'])
@login_required
def team_create(lab_id):
    """Create a new team in a lab."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'code': request.form.get('code', '').strip() or None,
            'description': request.form.get('description', '').strip() or None,
            'color': request.form.get('color', '#6366f1').strip(),
            'created_by': g.current_user.get('username') if g.current_user else None,
        }
        
        if not data['name']:
            flash('Team name is required', 'error')
            return render_template('teams/form.html', lab=lab, team=None)
        
        try:
            team = db.create_team(lab_id, data)
            flash(f'Team "{team["name"]}" created successfully', 'success')
            return redirect(url_for('main.team_detail', lab_id=lab_id, team_id=team['id']))
        except Exception as e:
            error_str = str(e).lower()
            if 'unique constraint' in error_str and 'name' in error_str:
                flash(f'A team named "{data["name"]}" already exists in this lab', 'error')
            else:
                flash(f'Error creating team: {str(e)}', 'error')
    
    return render_template('teams/form.html', lab=lab, team=None)


@main_bp.route('/labs/<int:lab_id>/teams/<int:team_id>/edit', methods=['GET', 'POST'])
@login_required
def team_edit(lab_id, team_id):
    """Edit an existing team."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    team = db.get_team(team_id)
    
    if not team or team['lab_id'] != lab_id:
        flash('Team not found', 'error')
        return redirect(url_for('main.lab_teams', lab_id=lab_id))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'code': request.form.get('code', '').strip() or None,
            'description': request.form.get('description', '').strip() or None,
            'color': request.form.get('color', '#6366f1').strip(),
        }
        
        if not data['name']:
            flash('Team name is required', 'error')
            return render_template('teams/form.html', lab=lab, team=team)
        
        try:
            updated = db.update_team(team_id, data)
            flash(f'Team "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.team_detail', lab_id=lab_id, team_id=team_id))
        except Exception as e:
            error_str = str(e).lower()
            if 'unique constraint' in error_str and 'name' in error_str:
                flash(f'A team named "{data["name"]}" already exists in this lab', 'error')
            else:
                flash(f'Error updating team: {str(e)}', 'error')
    
    return render_template('teams/form.html', lab=lab, team=team)


@main_bp.route('/labs/<int:lab_id>/teams/<int:team_id>/delete', methods=['POST'])
@login_required
def team_delete(lab_id, team_id):
    """Deactivate a team."""
    db = get_db_service()
    
    if db.delete_team(team_id):
        flash('Team deactivated successfully', 'success')
    else:
        flash('Error deactivating team', 'error')
    
    return redirect(url_for('main.lab_teams', lab_id=lab_id))


@main_bp.route('/labs/<int:lab_id>/teams/<int:team_id>/members/add', methods=['POST'])
@login_required
def team_member_add(lab_id, team_id):
    """Add a member to a team."""
    db = get_db_service()
    
    lab_member_id = request.form.get('lab_member_id', type=int)
    role = request.form.get('role', 'member')
    
    if not lab_member_id:
        flash('Please select a member to add', 'error')
        return redirect(url_for('main.team_detail', lab_id=lab_id, team_id=team_id))
    
    result = db.add_team_member(team_id, lab_member_id, role)
    
    if result:
        flash('Member added to team successfully', 'success')
    else:
        flash('Error adding member to team', 'error')
    
    return redirect(url_for('main.team_detail', lab_id=lab_id, team_id=team_id))


@main_bp.route('/labs/<int:lab_id>/teams/<int:team_id>/members/<int:member_id>/update', methods=['POST'])
@login_required
def team_member_update(lab_id, team_id, member_id):
    """Update a team member's role."""
    db = get_db_service()
    
    data = {
        'role': request.form.get('role', 'member')
    }
    
    result = db.update_team_member(member_id, data)
    
    if result:
        flash('Member role updated successfully', 'success')
    else:
        flash('Error updating member role', 'error')
    
    return redirect(url_for('main.team_detail', lab_id=lab_id, team_id=team_id))


@main_bp.route('/labs/<int:lab_id>/teams/<int:team_id>/members/<int:member_id>/remove', methods=['POST'])
@login_required
def team_member_remove(lab_id, team_id, member_id):
    """Remove a member from a team."""
    db = get_db_service()
    
    # Get the lab_member_id from the team_member_id
    team = db.get_team(team_id)
    if team:
        for m in team.get('members', []):
            if m['id'] == member_id:
                if db.remove_team_member(team_id, m['lab_member_id']):
                    flash('Member removed from team', 'success')
                else:
                    flash('Error removing member from team', 'error')
                break
    
    return redirect(url_for('main.team_detail', lab_id=lab_id, team_id=team_id))


@main_bp.route('/api/teams/<int:team_id>/access', methods=['POST'])
@login_required
def team_access_grant(team_id):
    """Grant team access to an entity (JSON API)."""
    db = get_db_service()
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    entity_type = data.get('entity_type')
    entity_id = data.get('entity_id')
    access_level = data.get('access_level', 'view')
    
    if not entity_type or not entity_id:
        return jsonify({'error': 'entity_type and entity_id are required'}), 400
    
    granted_by = g.current_user.get('username') if g.current_user else None
    
    result = db.grant_team_access(team_id, entity_type, entity_id, access_level, granted_by)
    return jsonify(result)


@main_bp.route('/api/teams/<int:team_id>/access', methods=['DELETE'])
@login_required
def team_access_revoke(team_id):
    """Revoke team access to an entity (JSON API)."""
    db = get_db_service()
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    entity_type = data.get('entity_type')
    entity_id = data.get('entity_id')
    
    if not entity_type or not entity_id:
        return jsonify({'error': 'entity_type and entity_id are required'}), 400
    
    if db.revoke_team_access(team_id, entity_type, entity_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Access not found'}), 404


@main_bp.route('/api/entity/<entity_type>/<int:entity_id>/teams')
def entity_team_access(entity_type, entity_id):
    """Get all teams with access to an entity (JSON API)."""
    db = get_db_service()
    teams = db.get_entity_team_access(entity_type, entity_id)
    return jsonify(teams)


# -------------------- Subscribers & Notifications --------------------

@main_bp.route('/subscribers')
@login_required
def subscriber_list():
    """Subscribers list page for managing notification channels."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    lab_id = session.get('current_lab_id')
    channel_type = request.args.get('channel_type', '')
    is_active = request.args.get('is_active')
    
    # Convert is_active to boolean if provided
    if is_active == 'true':
        is_active = True
    elif is_active == 'false':
        is_active = False
    else:
        is_active = None
    
    subscribers = db.get_subscribers(
        lab_id=lab_id,
        channel_type=channel_type if channel_type else None,
        is_active=is_active
    )
    
    # Channel type options
    channel_types = ['email', 'slack_channel', 'slack_user', 'webhook', 'user']
    
    return render_template('subscriber_list.html',
        subscribers=subscribers,
        channel_type=channel_type,
        is_active=is_active,
        channel_types=channel_types,
        lab_id=lab_id,
    )


@main_bp.route('/subscribers/<int:subscriber_id>')
@login_required
def subscriber_detail(subscriber_id):
    """Subscriber detail page showing rules and notification history."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    subscriber = db.get_subscriber(subscriber_id)
    
    if not subscriber:
        flash('Subscriber not found', 'error')
        return redirect(url_for('main.subscriber_list'))
    
    # Get notification rules for this subscriber
    rules = db.get_notification_rules(subscriber_id=subscriber_id)
    
    # Get recent notification logs
    logs = db.get_notification_logs(subscriber_id=subscriber_id, limit=50)
    
    # Get projects for rule creation form
    projects = db.get_projects_simple_list()
    
    # Event type options
    event_types = [
        'scan_created', 'scan_started', 'scan_completed', 'scan_failed',
        'queue_created', 'queue_item_added', 'queue_item_completed', 'queue_completed',
        'issue_created', 'issue_updated', 'issue_resolved', 'issue_assigned',
        'equipment_status_change', 'equipment_maintenance_due',
        'sample_created', 'sample_status_change',
        'waste_status_change', 'waste_fill_warning', 'waste_collection_requested',
        'lab_member_added', 'lab_member_removed', 'lab_member_role_changed',
    ]
    
    return render_template('subscriber_detail.html',
        subscriber=subscriber,
        rules=rules,
        logs=logs,
        projects=projects,
        event_types=event_types,
    )


@main_bp.route('/subscribers/new', methods=['GET', 'POST'])
@login_required
def subscriber_new():
    """Create a new subscriber."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    lab_id = session.get('current_lab_id')
    if not lab_id:
        flash('Please select a lab first', 'warning')
        return redirect(url_for('main.labs'))
    
    if request.method == 'POST':
        data = {
            'lab_id': lab_id,
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'channel_type': request.form.get('channel_type'),
            'channel_address': request.form.get('channel_address'),
            'slack_workspace_id': request.form.get('slack_workspace_id'),
            'slack_channel_id': request.form.get('slack_channel_id'),
            'webhook_url': request.form.get('webhook_url'),
            'is_active': request.form.get('is_active') == 'on',
            'created_by_id': g.current_user['id'],
        }
        
        # Parse webhook headers if provided
        webhook_headers = request.form.get('webhook_headers')
        if webhook_headers:
            try:
                import json
                data['webhook_headers'] = json.loads(webhook_headers)
            except json.JSONDecodeError:
                flash('Invalid JSON for webhook headers', 'error')
                return redirect(request.url)
        
        try:
            subscriber = db.create_subscriber(**data)
            flash(f'Subscriber "{subscriber["name"]}" created', 'success')
            return redirect(url_for('main.subscriber_detail', subscriber_id=subscriber['id']))
        except Exception as e:
            flash(f'Error creating subscriber: {str(e)}', 'error')
    
    # Channel type options
    channel_types = ['email', 'slack_channel', 'slack_user', 'webhook']
    
    return render_template('subscriber_form.html',
        subscriber=None,
        action='Create',
        channel_types=channel_types,
    )


@main_bp.route('/subscribers/<int:subscriber_id>/edit', methods=['GET', 'POST'])
@login_required
def subscriber_edit(subscriber_id):
    """Edit an existing subscriber."""
    db = get_db_service()
    
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    subscriber = db.get_subscriber(subscriber_id)
    if not subscriber:
        flash('Subscriber not found', 'error')
        return redirect(url_for('main.subscriber_list'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'channel_address': request.form.get('channel_address'),
            'slack_workspace_id': request.form.get('slack_workspace_id'),
            'slack_channel_id': request.form.get('slack_channel_id'),
            'webhook_url': request.form.get('webhook_url'),
            'is_active': request.form.get('is_active') == 'on',
        }
        
        # Parse webhook headers if provided
        webhook_headers = request.form.get('webhook_headers')
        if webhook_headers:
            try:
                import json
                data['webhook_headers'] = json.loads(webhook_headers)
            except json.JSONDecodeError:
                flash('Invalid JSON for webhook headers', 'error')
                return redirect(request.url)
        
        try:
            updated = db.update_subscriber(subscriber_id, **data)
            flash(f'Subscriber "{updated["name"]}" updated', 'success')
            return redirect(url_for('main.subscriber_detail', subscriber_id=subscriber_id))
        except Exception as e:
            flash(f'Error updating subscriber: {str(e)}', 'error')
    
    # Channel type options (read-only in edit - can't change type)
    channel_types = ['email', 'slack_channel', 'slack_user', 'webhook']
    
    return render_template('subscriber_form.html',
        subscriber=subscriber,
        action='Edit',
        channel_types=channel_types,
    )


@main_bp.route('/subscribers/<int:subscriber_id>/delete', methods=['POST'])
@login_required
def subscriber_delete(subscriber_id):
    """Delete (trash) a subscriber."""
    db = get_db_service()
    
    if g.current_user is None:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    if db.trash_subscriber(subscriber_id):
        flash('Subscriber moved to trash', 'success')
    else:
        flash('Error deleting subscriber', 'error')
    
    return redirect(url_for('main.subscriber_list'))


@main_bp.route('/subscribers/<int:subscriber_id>/verify', methods=['POST'])
@login_required
def subscriber_verify(subscriber_id):
    """Manually verify a subscriber (admin action)."""
    db = get_db_service()
    
    if g.current_user is None:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    verified = db.verify_subscriber(subscriber_id, verified=True)
    if verified:
        flash('Subscriber verified', 'success')
    else:
        flash('Error verifying subscriber', 'error')
    
    return redirect(url_for('main.subscriber_detail', subscriber_id=subscriber_id))


@main_bp.route('/subscribers/<int:subscriber_id>/rules/new', methods=['POST'])
@login_required
def subscriber_rule_new(subscriber_id):
    """Create a new notification rule for a subscriber."""
    db = get_db_service()
    
    if g.current_user is None:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    subscriber = db.get_subscriber(subscriber_id)
    if not subscriber:
        flash('Subscriber not found', 'error')
        return redirect(url_for('main.subscriber_list'))
    
    project_id = request.form.get('project_id')
    
    data = {
        'subscriber_id': subscriber_id,
        'name': request.form.get('name'),
        'description': request.form.get('description'),
        'event_type': request.form.get('event_type'),
        'project_id': int(project_id) if project_id else None,
        'owner_only': request.form.get('owner_only') == 'on',
        'custom_message_template': request.form.get('custom_message_template'),
        'priority': int(request.form.get('priority', 0) or 0),
        'is_active': request.form.get('is_active') == 'on',
        'created_by_id': g.current_user['id'],
    }
    
    # Parse conditions JSON if provided
    conditions = request.form.get('conditions')
    if conditions:
        try:
            import json
            data['conditions'] = json.loads(conditions)
        except json.JSONDecodeError:
            flash('Invalid JSON for conditions', 'error')
            return redirect(url_for('main.subscriber_detail', subscriber_id=subscriber_id))
    
    try:
        rule = db.create_notification_rule(**data)
        flash(f'Notification rule "{rule["name"]}" created', 'success')
    except Exception as e:
        flash(f'Error creating rule: {str(e)}', 'error')
    
    return redirect(url_for('main.subscriber_detail', subscriber_id=subscriber_id))


@main_bp.route('/subscribers/<int:subscriber_id>/rules/<int:rule_id>/edit', methods=['POST'])
@login_required
def subscriber_rule_edit(subscriber_id, rule_id):
    """Update a notification rule."""
    db = get_db_service()
    
    if g.current_user is None:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    project_id = request.form.get('project_id')
    
    data = {
        'name': request.form.get('name'),
        'description': request.form.get('description'),
        'event_type': request.form.get('event_type'),
        'project_id': int(project_id) if project_id else None,
        'owner_only': request.form.get('owner_only') == 'on',
        'custom_message_template': request.form.get('custom_message_template'),
        'priority': int(request.form.get('priority', 0) or 0),
        'is_active': request.form.get('is_active') == 'on',
    }
    
    # Parse conditions JSON if provided
    conditions = request.form.get('conditions')
    if conditions:
        try:
            import json
            data['conditions'] = json.loads(conditions)
        except json.JSONDecodeError:
            flash('Invalid JSON for conditions', 'error')
            return redirect(url_for('main.subscriber_detail', subscriber_id=subscriber_id))
    
    try:
        rule = db.update_notification_rule(rule_id, **data)
        if rule:
            flash(f'Notification rule "{rule["name"]}" updated', 'success')
        else:
            flash('Rule not found', 'error')
    except Exception as e:
        flash(f'Error updating rule: {str(e)}', 'error')
    
    return redirect(url_for('main.subscriber_detail', subscriber_id=subscriber_id))


@main_bp.route('/subscribers/<int:subscriber_id>/rules/<int:rule_id>/delete', methods=['POST'])
@login_required
def subscriber_rule_delete(subscriber_id, rule_id):
    """Delete a notification rule."""
    db = get_db_service()
    
    if g.current_user is None:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    if db.trash_notification_rule(rule_id):
        flash('Notification rule deleted', 'success')
    else:
        flash('Error deleting rule', 'error')
    
    return redirect(url_for('main.subscriber_detail', subscriber_id=subscriber_id))


# API endpoints for notifications

@api_bp.route('/subscribers', methods=['GET'])
@api_login_required
def api_get_subscribers():
    """Get all subscribers for the current lab (JSON API)."""
    db = get_db_service()
    lab_id = session.get('current_lab_id')
    
    if not lab_id:
        return jsonify({'success': False, 'error': 'No lab selected'}), 400
    
    channel_type = request.args.get('channel_type')
    is_active = request.args.get('is_active')
    
    if is_active is not None:
        is_active = is_active.lower() == 'true'
    
    subscribers = db.get_subscribers(
        lab_id=lab_id,
        channel_type=channel_type,
        is_active=is_active
    )
    
    return jsonify({'success': True, 'data': subscribers})


@api_bp.route('/subscribers/<int:subscriber_id>', methods=['GET'])
@api_login_required
def api_get_subscriber(subscriber_id):
    """Get a single subscriber (JSON API)."""
    db = get_db_service()
    subscriber = db.get_subscriber(subscriber_id)
    
    if not subscriber:
        return jsonify({'success': False, 'error': 'Subscriber not found'}), 404
    
    return jsonify({'success': True, 'data': subscriber})


@api_bp.route('/subscribers/<int:subscriber_id>/rules', methods=['GET'])
@api_login_required
def api_get_subscriber_rules(subscriber_id):
    """Get all rules for a subscriber (JSON API)."""
    db = get_db_service()
    rules = db.get_notification_rules(subscriber_id=subscriber_id)
    return jsonify({'success': True, 'data': rules})


@api_bp.route('/subscribers/<int:subscriber_id>/logs', methods=['GET'])
@api_login_required
def api_get_subscriber_logs(subscriber_id):
    """Get notification logs for a subscriber (JSON API)."""
    db = get_db_service()
    limit = request.args.get('limit', 50, type=int)
    status = request.args.get('status')
    
    logs = db.get_notification_logs(
        subscriber_id=subscriber_id,
        status=status,
        limit=limit
    )
    
    return jsonify({'success': True, 'data': logs})


@api_bp.route('/notifications/dispatch', methods=['POST'])
@api_login_required
def api_dispatch_notification():
    """Dispatch a notification event (JSON API).
    
    This is the main entry point for programmatically triggering notifications.
    """
    db = get_db_service()
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400
    
    lab_id = data.get('lab_id') or session.get('current_lab_id')
    if not lab_id:
        return jsonify({'success': False, 'error': 'lab_id required'}), 400
    
    required_fields = ['event_type', 'entity_type', 'entity_id']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'{field} required'}), 400
    
    logs = db.dispatch_event(
        lab_id=lab_id,
        event_type=data['event_type'],
        entity_type=data['entity_type'],
        entity_id=data['entity_id'],
        project_id=data.get('project_id'),
        owner_id=data.get('owner_id'),
        event_data=data.get('event_data'),
        message=data.get('message')
    )
    
    return jsonify({'success': True, 'notifications_queued': len(logs), 'data': logs})


# -------------------- Projects --------------------

@main_bp.route('/projects')
def projects():
    """Projects list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    lab_id = request.args.get('lab_id', type=int)
    
    db = get_db_service()
    projects_list, total = db.get_projects(
        search=search if search else None,
        status=status if status else None,
        lab_id=lab_id,
        page=page
    )
    
    # Get labs for filter dropdown
    labs_list, _ = db.get_labs(per_page=100)
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'project')
    
    return render_template('projects.html',
        projects=projects_list,
        labs=labs_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
        lab_id=lab_id,
        pinned_ids=pinned_ids
    )


@main_bp.route('/projects/<int:project_id>')
def project_detail(project_id):
    """Project detail page."""
    db = get_db_service()
    project = db.get_project(project_id)
    if not project:
        flash('Project not found', 'error')
        return redirect(url_for('main.projects'))
    
    # Get guests for this project
    guests = db.get_item_guests('project', project_id)
    project['guests'] = guests
    
    images = db.get_entity_images('project', project_id)
    attachments = db.get_entity_attachments('project', project_id)
    
    return render_template('project_detail.html', project=project, images=images, attachments=attachments)


@main_bp.route('/projects/new', methods=['GET', 'POST'])
def project_new():
    """Create new project page."""
    db = get_db_service()
    labs_list, _ = db.get_labs(per_page=100)
    
    # Get user defaults
    default_lab_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'code': request.form.get('code') or None,
            'lab_id': int(request.form.get('lab_id')) if request.form.get('lab_id') else None,
            'description': request.form.get('description'),
            'status': request.form.get('status', 'active'),
            'start_date': request.form.get('start_date') or None,
            'end_date': request.form.get('end_date') or None,
            'funding_source': request.form.get('funding_source'),
            'grant_number': request.form.get('grant_number'),
            'goals': request.form.get('goals'),
        }
        try:
            project = db.create_project(data)
            flash(f'Project "{project["name"]}" created successfully', 'success')
            return redirect(url_for('main.project_detail', project_id=project['id']))
        except Exception as e:
            flash(f'Error creating project: {str(e)}', 'error')
    
    return render_template('project_form.html', project=None, labs=labs_list, action='Create', default_lab_id=default_lab_id)


@main_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
def project_edit(project_id):
    """Edit project page."""
    db = get_db_service()
    project = db.get_project(project_id)
    labs_list, _ = db.get_labs(per_page=100)
    
    if not project:
        flash('Project not found', 'error')
        return redirect(url_for('main.projects'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'code': request.form.get('code') or None,
            'lab_id': int(request.form.get('lab_id')) if request.form.get('lab_id') else None,
            'description': request.form.get('description'),
            'status': request.form.get('status', 'active'),
            'start_date': request.form.get('start_date') or None,
            'end_date': request.form.get('end_date') or None,
            'funding_source': request.form.get('funding_source'),
            'grant_number': request.form.get('grant_number'),
            'goals': request.form.get('goals'),
        }
        try:
            updated = db.update_project(project_id, data)
            flash(f'Project "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.project_detail', project_id=project_id))
        except Exception as e:
            flash(f'Error updating project: {str(e)}', 'error')
    
    return render_template('project_form.html', project=project, labs=labs_list, action='Edit')


@main_bp.route('/projects/<int:project_id>/members/add', methods=['GET', 'POST'])
def project_member_add(project_id):
    """Add member to project."""
    db = get_db_service()
    project = db.get_project(project_id)
    
    if not project:
        flash('Project not found', 'error')
        return redirect(url_for('main.projects'))
    
    # Get lab members if project is associated with a lab
    lab_members = []
    if project.get('lab_id'):
        lab_members = db.get_lab_members(project['lab_id'])
    
    if request.method == 'POST':
        lab_member_id = request.form.get('lab_member_id')
        data = {
            'role': request.form.get('role', 'member'),
            'notes': request.form.get('notes'),
        }
        
        if lab_member_id:
            data['lab_member_id'] = int(lab_member_id)
        else:
            # External collaborator
            data['external_name'] = request.form.get('external_name')
            data['external_email'] = request.form.get('external_email')
            data['external_affiliation'] = request.form.get('external_affiliation')
        
        try:
            member = db.add_project_member(project_id, data)
            flash(f'Member added successfully', 'success')
            return redirect(url_for('main.project_detail', project_id=project_id))
        except Exception as e:
            flash(f'Error adding member: {str(e)}', 'error')
    
    return render_template('project_member_form.html', project=project, lab_members=lab_members, member=None, action='Add')


@main_bp.route('/projects/<int:project_id>/members/<int:member_id>/remove', methods=['POST'])
def project_member_remove(project_id, member_id):
    """Remove member from project."""
    db = get_db_service()
    if db.remove_project_member(member_id):
        flash('Member removed successfully', 'success')
    else:
        flash('Error removing member', 'error')
    return redirect(url_for('main.project_detail', project_id=project_id))


@main_bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def project_delete(project_id):
    """Move a project to trash (soft-delete with cascade to samples and queues)."""
    db = get_db_service()
    project = db.get_project(project_id)
    
    if not project:
        flash('Project not found', 'error')
        return redirect(url_for('main.projects'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('project', project_id, trashed_by=username, cascade=True)
        
        if result['success']:
            flash(f'Project "{project["name"]}" moved to trash. It will be permanently deleted in 30 days.', 'success')
        else:
            flash(result.get('error', 'Error moving project to trash'), 'error')
    except Exception as e:
        flash(f'Cannot delete project: {str(e)}', 'error')
    
    return redirect(url_for('main.projects'))


# -------------------- Guest Access --------------------

@main_bp.route('/guest/add/<entity_type>/<int:entity_id>', methods=['GET', 'POST'])
def guest_add(entity_type, entity_id):
    """Add guest access to an item."""
    if entity_type not in ['sample', 'scan', 'queue', 'project']:
        flash('Invalid entity type', 'error')
        return redirect(url_for('main.index'))
    
    db = get_db_service()
    
    if request.method == 'POST':
        data = {
            'guest_name': request.form.get('guest_name'),
            'guest_email': request.form.get('guest_email'),
            'guest_affiliation': request.form.get('guest_affiliation'),
            'access_level': request.form.get('access_level', 'view'),
            'granted_by': request.form.get('granted_by'),
            'notes': request.form.get('notes'),
        }
        
        # Handle expiration
        expires = request.form.get('expires_at')
        if expires:
            from datetime import datetime
            data['expires_at'] = datetime.fromisoformat(expires)
        
        try:
            guest = db.add_item_guest(entity_type, entity_id, data)
            flash(f'Guest access granted to {guest["guest_name"]}', 'success')
            
            # Redirect back to the entity detail page
            if entity_type == 'sample':
                return redirect(url_for('main.sample_detail', sample_id=entity_id))
            elif entity_type == 'scan':
                return redirect(url_for('main.scan_detail', scan_id=entity_id))
            elif entity_type == 'queue':
                return redirect(url_for('main.queue_detail', queue_id=entity_id))
            elif entity_type == 'project':
                return redirect(url_for('main.project_detail', project_id=entity_id))
        except Exception as e:
            flash(f'Error granting access: {str(e)}', 'error')
    
    return render_template('guest_form.html', entity_type=entity_type, entity_id=entity_id, guest=None, action='Add')


@main_bp.route('/guest/<int:guest_id>/revoke', methods=['POST'])
def guest_revoke(guest_id):
    """Revoke guest access."""
    db = get_db_service()
    
    # Get guest info for redirect
    # For simplicity, redirect to referrer or index
    if db.remove_item_guest(guest_id):
        flash('Guest access revoked', 'success')
    else:
        flash('Error revoking access', 'error')
    
    return redirect(request.referrer or url_for('main.index'))


# -------------------- Permissions Management --------------------

@main_bp.route('/permissions')
def permissions():
    """Permissions management overview page."""
    db = get_db_service()
    entities = db.get_all_entities_for_permissions()
    return render_template('permissions.html', entities=entities)


@main_bp.route('/permissions/<entity_type>/<int:entity_id>')
def permissions_detail(entity_type, entity_id):
    """View and manage permissions for a specific entity."""
    if entity_type not in ['lab', 'project', 'sample', 'scan', 'queue']:
        flash('Invalid entity type', 'error')
        return redirect(url_for('main.permissions'))
    
    db = get_db_service()
    permissions = db.get_entity_permissions(entity_type, entity_id)
    
    if not permissions.get('entity_name'):
        flash('Entity not found', 'error')
        return redirect(url_for('main.permissions'))
    
    return render_template('permissions_detail.html', 
                           permissions=permissions,
                           entity_type=entity_type,
                           entity_id=entity_id)


@main_bp.route('/permissions/<entity_type>/<int:entity_id>/member/<int:member_id>/role', methods=['POST'])
def permissions_update_member_role(entity_type, entity_id, member_id):
    """Update a member's role."""
    db = get_db_service()
    new_role = request.form.get('role')
    
    if entity_type == 'lab':
        result = db.update_lab_member_role(member_id, new_role)
    elif entity_type == 'project':
        result = db.update_project_member_role(member_id, new_role)
    else:
        flash('Invalid entity type for member roles', 'error')
        return redirect(url_for('main.permissions_detail', entity_type=entity_type, entity_id=entity_id))
    
    if result:
        flash(f'Role updated to {new_role.replace("_", " ").title()}', 'success')
    else:
        flash('Error updating role', 'error')
    
    return redirect(url_for('main.permissions_detail', entity_type=entity_type, entity_id=entity_id))


@main_bp.route('/permissions/<entity_type>/<int:entity_id>/guest/<int:guest_id>/access', methods=['POST'])
def permissions_update_guest_access(entity_type, entity_id, guest_id):
    """Update a guest's access level."""
    db = get_db_service()
    new_access = request.form.get('access_level')
    
    result = db.update_item_guest(guest_id, {'access_level': new_access})
    
    if result:
        flash(f'Access level updated to {new_access.title()}', 'success')
    else:
        flash('Error updating access level', 'error')
    
    return redirect(url_for('main.permissions_detail', entity_type=entity_type, entity_id=entity_id))


@main_bp.route('/permissions/<entity_type>/<int:entity_id>/member/<int:member_id>/remove', methods=['POST'])
def permissions_remove_member(entity_type, entity_id, member_id):
    """Remove a member from an entity."""
    db = get_db_service()
    
    if entity_type == 'lab':
        result = db.delete_lab_member(member_id)
    elif entity_type == 'project':
        result = db.remove_project_member(member_id)
    else:
        flash('Invalid entity type for member removal', 'error')
        return redirect(url_for('main.permissions_detail', entity_type=entity_type, entity_id=entity_id))
    
    if result:
        flash('Member removed successfully', 'success')
    else:
        flash('Error removing member', 'error')
    
    return redirect(url_for('main.permissions_detail', entity_type=entity_type, entity_id=entity_id))


@main_bp.route('/permissions/<entity_type>/<int:entity_id>/guest/<int:guest_id>/revoke', methods=['POST'])
def permissions_revoke_guest(entity_type, entity_id, guest_id):
    """Revoke guest access from permissions page."""
    db = get_db_service()
    
    if db.remove_item_guest(guest_id):
        flash('Guest access revoked', 'success')
    else:
        flash('Error revoking access', 'error')
    
    return redirect(url_for('main.permissions_detail', entity_type=entity_type, entity_id=entity_id))


# -------------------- Authentication --------------------

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if g.current_user:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db_service()
        user = db.verify_password(username, password)
        
        if user:
            session['user_id'] = user['id']
            session.permanent = True
            flash(f'Welcome back, {user["name"] or user["username"]}!', 'success')
            
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('main.index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@main_bp.route('/logout')
def logout():
    """User logout."""
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))


@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if g.current_user:
        return redirect(url_for('main.index'))
    
    db = get_db_service()
    labs = db.get_labs()
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        name = request.form.get('name')
        lab_id = request.form.get('lab_id')
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html', labs=labs)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return render_template('register.html', labs=labs)
        
        # Check if user exists
        if db.get_user_by_username(username):
            flash('Username already taken', 'error')
            return render_template('register.html', labs=labs)
        
        if db.get_user_by_email(email):
            flash('Email already registered', 'error')
            return render_template('register.html', labs=labs)
        
        try:
            user = db.create_user(
                username=username,
                email=email,
                password=password,
                name=name,
                lab_id=int(lab_id) if lab_id else None,
            )
            
            session['user_id'] = user['id']
            flash('Account created successfully!', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'error')
    
    return render_template('register.html', labs=labs)


@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page."""
    db = get_db_service()
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'profile':
            # Handle profile update (includes personal info)
            data = {
                'name': request.form.get('name'),
                'email': request.form.get('email'),
                'phone': request.form.get('phone'),
                'orcid': request.form.get('orcid'),
                'office_location': request.form.get('office_location'),
            }
            
            # Check if email is taken by another user
            existing = db.get_user_by_email(data['email'])
            if existing and existing['id'] != g.current_user['id']:
                flash('Email already in use by another account', 'error')
            else:
                db.update_user(g.current_user['id'], data)
                flash('Profile updated successfully', 'success')
                return redirect(url_for('main.profile'))
        
        elif form_type == 'preferences':
            # Handle preferences update (default lab/project)
            default_lab_id = int(request.form.get('default_lab_id')) if request.form.get('default_lab_id') else None
            default_project_id = int(request.form.get('default_project_id')) if request.form.get('default_project_id') else None
            db.update_user_preferences(g.current_user['id'], default_lab_id=default_lab_id, default_project_id=default_project_id)
            flash('Preferences saved successfully', 'success')
            return redirect(url_for('main.profile'))
    
    user_preferences = db.get_user_preferences(g.current_user['id'])
    profile_data = db.get_user_profile_data(g.current_user['id'])
    
    # Add user fields to preferences for template (phone, orcid, office_location are on User model)
    user = db.get_user_by_id(g.current_user['id'])
    if user:
        user_preferences['phone'] = user.get('phone')
        user_preferences['orcid'] = user.get('orcid')
        user_preferences['office_location'] = user.get('office_location')
    
    # Get labs and projects for select dropdowns
    labs, _ = db.get_labs(per_page=1000)
    projects = db.get_projects_simple_list()
    
    return render_template('profile.html', 
        user_preferences=user_preferences, 
        profile_data=profile_data,
        labs=labs,
        projects=projects
    )


@main_bp.route('/profile/statistics')
@login_required
def user_statistics():
    """User statistics page showing activity metrics and contributions."""
    db = get_db_service()
    stats = db.get_user_statistics(g.current_user['id'])
    
    return render_template('user_statistics.html', stats=stats)


@main_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password."""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    db = get_db_service()
    
    # Verify current password
    user = db.verify_password(g.current_user['username'], current_password)
    if not user:
        flash('Current password is incorrect', 'error')
        return redirect(url_for('main.profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('main.profile'))
    
    if len(new_password) < 6:
        flash('New password must be at least 6 characters', 'error')
        return redirect(url_for('main.profile'))
    
    db.change_password(g.current_user['id'], new_password)
    flash('Password changed successfully', 'success')
    return redirect(url_for('main.profile'))


# -------------------- User Settings & Themes --------------------

@main_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page for theme and preferences management."""
    db = get_db_service()
    
    # Safety check - g.current_user may be None if user was deleted
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'theme_mode':
            # Update theme mode (light/dark/system)
            theme_mode = request.form.get('theme_mode', 'system')
            db.update_user_settings(g.current_user['id'], theme_mode=theme_mode)
            flash('Theme mode updated', 'success')
            return redirect(url_for('main.settings'))
        
        elif form_type == 'active_theme':
            # Set active custom theme
            theme_id = request.form.get('active_theme_id')
            theme_id = int(theme_id) if theme_id else None
            db.update_user_settings(g.current_user['id'], active_theme_id=theme_id)
            flash('Active theme updated', 'success')
            return redirect(url_for('main.settings'))
        
        elif form_type == 'general_settings':
            # Update general settings
            settings_data = {
                'compact_tables': 'compact_tables' in request.form,
                'show_notifications': 'show_notifications' in request.form,
                'default_page_size': int(request.form.get('default_page_size', 20)),
                'sidebar_collapsed': 'sidebar_collapsed' in request.form,
                'date_format': request.form.get('date_format', 'YYYY-MM-DD'),
                'time_format': request.form.get('time_format', '24h'),
            }
            db.update_user_settings(g.current_user['id'], settings=settings_data)
            flash('Settings saved', 'success')
            return redirect(url_for('main.settings'))
        
        elif form_type == 'notification_settings':
            # Update notification preferences
            # Get existing settings and merge with notification preferences
            existing_settings = db.get_user_settings(g.current_user['id'])
            current_settings = existing_settings.get('settings', {}) if existing_settings else {}
            
            notification_settings = {
                **current_settings,
                'email_notifications_enabled': 'email_notifications_enabled' in request.form,
                'slack_notifications_enabled': 'slack_notifications_enabled' in request.form,
                'notify_issues': 'notify_issues' in request.form,
                'notify_issues_owner_only': 'notify_issues_owner_only' in request.form,
                'notify_scans': 'notify_scans' in request.form,
                'notify_scans_owner_only': 'notify_scans_owner_only' in request.form,
                'notify_waste': 'notify_waste' in request.form,
                'notify_waste_owner_only': 'notify_waste_owner_only' in request.form,
                'notify_equipment': 'notify_equipment' in request.form,
                'notify_lab_membership': 'notify_lab_membership' in request.form,
            }
            db.update_user_settings(g.current_user['id'], settings=notification_settings)
            
            # Create/update user's personal subscriber if needed
            lab_id = session.get('current_lab_id')
            if lab_id:
                user_subscriber = db.get_subscriber_by_user(g.current_user['id'])
                if not user_subscriber:
                    # Create personal subscriber for the user
                    db.create_user_subscriber(
                        user_id=g.current_user['id'],
                        lab_id=lab_id,
                        email=g.current_user.get('email')
                    )
            
            flash('Notification preferences saved', 'success')
            return redirect(url_for('main.settings'))
    
    user_settings = db.get_user_settings(g.current_user['id'])
    user_themes = db.get_user_themes(g.current_user['id'])
    default_palettes = db.get_default_theme_palettes()
    
    return render_template('settings.html',
        user_settings=user_settings,
        user_themes=user_themes,
        default_palettes=default_palettes
    )


@main_bp.route('/settings/theme/new', methods=['GET', 'POST'])
@login_required
def new_theme():
    """Create a new custom theme."""
    db = get_db_service()
    
    # Safety check - g.current_user may be None if user was deleted
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', 'New Theme'),
            'description': request.form.get('description'),
            'is_public': 'is_public' in request.form,
        }
        
        # Parse light palette
        light_palette = {}
        dark_palette = {}
        for key in ['primary', 'primary_dark', 'secondary', 'success', 'warning', 'error', 'info',
                    'bg_primary', 'bg_secondary', 'bg_tertiary', 'text_primary', 'text_secondary',
                    'text_muted', 'border', 'border_dark']:
            if request.form.get(f'light_{key}'):
                light_palette[key] = request.form.get(f'light_{key}')
            if request.form.get(f'dark_{key}'):
                dark_palette[key] = request.form.get(f'dark_{key}')
        
        if light_palette:
            data['light_palette'] = light_palette
        if dark_palette:
            data['dark_palette'] = dark_palette
        
        theme = db.create_user_theme(g.current_user['id'], data)
        flash(f'Theme "{theme["name"]}" created', 'success')
        return redirect(url_for('main.settings'))
    
    default_palettes = db.get_default_theme_palettes()
    return render_template('theme_form.html',
        theme=None,
        default_palettes=default_palettes,
        is_new=True
    )


@main_bp.route('/settings/theme/<int:theme_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_theme(theme_id):
    """Edit an existing custom theme."""
    db = get_db_service()
    
    # Safety check - g.current_user may be None if user was deleted
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    theme = db.get_user_theme(theme_id)
    
    if not theme:
        flash('Theme not found', 'error')
        return redirect(url_for('main.settings'))
    
    if theme['user_id'] != g.current_user['id']:
        flash('You can only edit your own themes', 'error')
        return redirect(url_for('main.settings'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', theme['name']),
            'description': request.form.get('description'),
            'is_public': 'is_public' in request.form,
        }
        
        # Parse palettes
        light_palette = {}
        dark_palette = {}
        for key in ['primary', 'primary_dark', 'secondary', 'success', 'warning', 'error', 'info',
                    'bg_primary', 'bg_secondary', 'bg_tertiary', 'text_primary', 'text_secondary',
                    'text_muted', 'border', 'border_dark']:
            if request.form.get(f'light_{key}'):
                light_palette[key] = request.form.get(f'light_{key}')
            if request.form.get(f'dark_{key}'):
                dark_palette[key] = request.form.get(f'dark_{key}')
        
        if light_palette:
            data['light_palette'] = light_palette
        if dark_palette:
            data['dark_palette'] = dark_palette
        
        db.update_user_theme(theme_id, g.current_user['id'], data)
        flash(f'Theme "{data["name"]}" updated', 'success')
        return redirect(url_for('main.settings'))
    
    default_palettes = db.get_default_theme_palettes()
    return render_template('theme_form.html',
        theme=theme,
        default_palettes=default_palettes,
        is_new=False
    )


@main_bp.route('/settings/theme/<int:theme_id>/delete', methods=['POST'])
@login_required
def delete_theme(theme_id):
    """Delete a custom theme."""
    db = get_db_service()
    
    # Safety check - g.current_user may be None if user was deleted
    if g.current_user is None:
        session.clear()
        flash('Please log in again.', 'warning')
        return redirect(url_for('main.login'))
    
    if db.delete_user_theme(theme_id, g.current_user['id']):
        flash('Theme deleted', 'success')
    else:
        flash('Theme not found or you do not have permission to delete it', 'error')
    
    return redirect(url_for('main.settings'))


@main_bp.route('/api/v1/settings/theme-mode', methods=['POST'])
def api_set_theme_mode():
    """API endpoint to set theme mode (for toggle button)."""
    db = get_db_service()
    data = request.get_json() or {}
    theme_mode = data.get('theme_mode', 'system')
    
    if theme_mode not in ('light', 'dark', 'system'):
        return jsonify({'success': False, 'error': 'Invalid theme mode'}), 400
    
    if g.current_user:
        db.update_user_settings(g.current_user['id'], theme_mode=theme_mode)
        return jsonify({'success': True, 'theme_mode': theme_mode})
    else:
        # For non-logged-in users, just return success (handled by localStorage)
        return jsonify({'success': True, 'theme_mode': theme_mode, 'stored': 'client'})


@main_bp.route('/api/v1/settings/theme', methods=['GET'])
def api_get_theme():
    """API endpoint to get current user's theme settings."""
    db = get_db_service()
    
    if g.current_user:
        settings = db.get_user_settings(g.current_user['id'])
        theme_data = {
            'theme_mode': settings.get('theme_mode', 'system'),
            'active_theme_id': settings.get('active_theme_id'),
        }
        
        # Include active theme palette if custom theme selected
        if settings.get('active_theme_id'):
            theme = db.get_user_theme(settings['active_theme_id'])
            if theme:
                theme_data['light_palette'] = theme.get('light_palette', {})
                theme_data['dark_palette'] = theme.get('dark_palette', {})
        
        return jsonify(theme_data)
    else:
        return jsonify({
            'theme_mode': 'system',
            'active_theme_id': None
        })


@main_bp.route('/auth/google')
def google_login():
    """Handle Google OAuth callback."""
    from flask import current_app
    from flask_dance.contrib.google import google
    
    if not current_app.config.get('GOOGLE_OAUTH_ENABLED'):
        flash('Google OAuth is not configured', 'error')
        return redirect(url_for('main.login'))
    
    if not google.authorized:
        flash('Google login failed', 'error')
        return redirect(url_for('main.login'))
    
    try:
        resp = google.get('/oauth2/v2/userinfo')
        if not resp.ok:
            flash('Failed to fetch user info from Google', 'error')
            return redirect(url_for('main.login'))
        
        google_info = resp.json()
        google_id = google_info['id']
        email = google_info['email']
        name = google_info.get('name', '')
        
        db = get_db_service()
        
        # Try to find existing user by Google ID
        user = db.get_user_by_google_id(google_id)
        
        # If not found, try by email
        if not user:
            user = db.get_user_by_email(email)
            if user and not user.get('google_id'):
                # Link Google account to existing user
                db.update_user(user['id'], google_id=google_id)
        
        # Create new user if doesn't exist
        if not user:
            # Generate unique username from email
            username = email.split('@')[0]
            counter = 1
            base_username = username
            while db.get_user_by_username(username):
                username = f"{base_username}{counter}"
                counter += 1
            
            user = db.create_user(
                username=username,
                email=email,
                name=name,
                google_id=google_id,
                role='user'
            )
        
        # Log in the user
        session['user_id'] = user['id']
        db.update_user(user['id'], last_login=datetime.now())
        
        flash(f'Welcome, {user["name"] or user["username"]}!', 'success')
        return redirect(url_for('main.index'))
        
    except Exception as e:
        flash(f'Google login error: {str(e)}', 'error')
        return redirect(url_for('main.login'))


# -------------------- User Pins --------------------

@main_bp.route('/pin/<entity_type>/<int:entity_id>', methods=['GET', 'POST'])
@login_required
def pin_item(entity_type, entity_id):
    """Pin an item for the current user."""
    db = get_db_service()
    
    # Validate entity type
    valid_types = ['sample', 'scan', 'queue', 'equipment', 'precursor', 'procedure', 'project', 'lab', 'instrument']
    if entity_type not in valid_types:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': f'Invalid entity type: {entity_type}'})
        flash(f'Invalid entity type: {entity_type}', 'error')
        return redirect(request.referrer or url_for('main.index'))
    
    try:
        db.pin_item(g.current_user['id'], entity_type, entity_id)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'pinned': True})
        flash(f'{entity_type.title()} pinned successfully', 'success')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': str(e)})
        flash(f'Error pinning item: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/unpin/<entity_type>/<int:entity_id>', methods=['GET', 'POST'])
@login_required
def unpin_item(entity_type, entity_id):
    """Unpin an item for the current user."""
    db = get_db_service()
    
    # Validate entity type
    valid_types = ['sample', 'scan', 'queue', 'equipment', 'precursor', 'procedure', 'project', 'lab', 'instrument']
    if entity_type not in valid_types:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': f'Invalid entity type: {entity_type}'})
        flash(f'Invalid entity type: {entity_type}', 'error')
        return redirect(request.referrer or url_for('main.index'))
    
    try:
        db.unpin_item(g.current_user['id'], entity_type, entity_id)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'pinned': False})
        flash(f'{entity_type.title()} unpinned', 'success')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': str(e)})
        flash(f'Error unpinning item: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('main.index'))


@api_bp.route('/pins/<entity_type>/<int:entity_id>', methods=['POST'])
@api_login_required
def api_pin_item(entity_type, entity_id):
    """API endpoint to pin an item."""
    db = get_db_service()
    
    valid_types = ['sample', 'scan', 'queue', 'equipment', 'precursor', 'procedure', 'project', 'lab', 'instrument', 'fabrication_run']
    if entity_type not in valid_types:
        return jsonify({'success': False, 'error': f'Invalid entity type: {entity_type}'}), 400
    
    try:
        db.pin_item(g.current_user['id'], entity_type, entity_id)
        return jsonify({'success': True, 'pinned': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/pins/<entity_type>/<int:entity_id>', methods=['DELETE'])
@api_login_required
def api_unpin_item(entity_type, entity_id):
    """API endpoint to unpin an item."""
    db = get_db_service()
    
    valid_types = ['sample', 'scan', 'queue', 'equipment', 'precursor', 'procedure', 'project', 'lab', 'instrument', 'fabrication_run']
    if entity_type not in valid_types:
        return jsonify({'success': False, 'error': f'Invalid entity type: {entity_type}'}), 400
    
    try:
        db.unpin_item(g.current_user['id'], entity_type, entity_id)
        return jsonify({'success': True, 'pinned': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/pins', methods=['GET'])
@api_login_required
def api_get_pins():
    """Get all pinned items for the current user."""
    db = get_db_service()
    pins = db.get_user_pins(g.current_user['id'])
    return jsonify({'pins': pins})


# -------------------- Issue Tracking --------------------

@main_bp.route('/issues')
def issues():
    """Issue list page."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    category = request.args.get('category', '')
    
    db = get_db_service()
    issues_list, total = db.get_issues(
        status=status if status else None,
        category=category if category else None,
        page=page
    )
    
    stats = db.get_issue_stats()
    total_pages = (total + 19) // 20
    
    return render_template('issues.html',
        issues=issues_list,
        stats=stats,
        page=page,
        total_pages=total_pages,
        total=total,
        status=status,
        category=category
    )


@main_bp.route('/issues/<int:issue_id>')
def issue_detail(issue_id):
    """Issue detail page."""
    db = get_db_service()
    issue = db.get_issue(issue_id)
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('main.issues'))
    
    users, _ = db.get_users()  # For assignee dropdown
    
    # Get images and attachments for this issue
    images = db.get_entity_images('issue', issue_id)
    attachments = db.get_entity_attachments('issue', issue_id)
    
    # Get update history for timeline
    updates = db.get_issue_updates('issue', issue_id)
    
    return render_template('issue_detail.html', 
        issue=issue, 
        users=users,
        images=images,
        attachments=attachments,
        entity_type='issue',
        entity_id=issue_id,
        issue_type='issue',
        issue_id=issue_id,
        updates=updates,
    )


@main_bp.route('/issues/new', methods=['GET', 'POST'])
def issue_new():
    """Create new issue (report a problem)."""
    if request.method == 'POST':
        db = get_db_service()
        
        data = {
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'error_message': request.form.get('error_message'),
            'steps_to_reproduce': request.form.get('steps_to_reproduce'),
            'category': request.form.get('category', 'bug'),
            'priority': request.form.get('priority', 'medium'),
            'related_url': request.form.get('related_url'),
            'browser_info': request.form.get('browser_info'),
            'reporter_id': g.current_user['id'] if g.current_user else None,
        }
        
        try:
            issue = db.create_issue(data)
            flash('Issue reported successfully. Thank you!', 'success')
            return redirect(url_for('main.issue_detail', issue_id=issue['id']))
        except Exception as e:
            flash(f'Error creating issue: {str(e)}', 'error')
    
    return render_template('issue_form.html', issue=None)


@main_bp.route('/issues/<int:issue_id>/edit', methods=['GET', 'POST'])
@login_required
def issue_edit(issue_id):
    """Edit issue."""
    db = get_db_service()
    issue = db.get_issue(issue_id)
    
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('main.issues'))
    
    # Only admin or reporter can edit
    if g.current_user['role'] != 'admin' and issue['reporter_id'] != g.current_user['id']:
        flash('You do not have permission to edit this issue', 'error')
        return redirect(url_for('main.issue_detail', issue_id=issue_id))
    
    if request.method == 'POST':
        data = {
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'error_message': request.form.get('error_message'),
            'steps_to_reproduce': request.form.get('steps_to_reproduce'),
            'category': request.form.get('category'),
            'priority': request.form.get('priority'),
        }
        
        db.update_issue(issue_id, data)
        flash('Issue updated successfully', 'success')
        return redirect(url_for('main.issue_detail', issue_id=issue_id))
    
    return render_template('issue_form.html', issue=issue)


@main_bp.route('/issues/<int:issue_id>/status', methods=['POST'])
@login_required
def issue_update_status(issue_id):
    """Update issue status."""
    db = get_db_service()
    
    old_issue = db.get_issue(issue_id)
    old_status = old_issue.get('status') if old_issue else None
    
    new_status = request.form.get('status')
    assignee_id = request.form.get('assignee_id') or None
    resolution_note = request.form.get('resolution')
    
    data = {
        'status': new_status,
        'assignee_id': int(assignee_id) if assignee_id else None,
    }
    
    db.update_issue(issue_id, data)
    
    # Create an update entry if there's a status change or resolution note
    if old_status != new_status or resolution_note:
        author_name = None
        author_id = None
        if g.current_user:
            author_name = g.current_user.get('name') or g.current_user.get('username')
            author_id = g.current_user.get('id')
        
        update_type = 'status_change' if old_status != new_status else 'comment'
        if resolution_note and new_status in ['resolved', 'closed']:
            update_type = 'resolution'
        
        db.create_issue_update({
            'issue_type': 'issue',
            'issue_id': issue_id,
            'update_type': update_type,
            'content': resolution_note,
            'old_status': old_status if old_status != new_status else None,
            'new_status': new_status if old_status != new_status else None,
            'author_id': author_id,
            'author_name': author_name,
        })
    
    flash('Issue updated', 'success')
    return redirect(url_for('main.issue_detail', issue_id=issue_id))


@main_bp.route('/issues/<issue_type>/<int:issue_id>/update', methods=['POST'])
@login_required
def issue_add_update(issue_type, issue_id):
    """Add an update to any issue type."""
    db = get_db_service()
    
    content = request.form.get('content')
    update_type = request.form.get('update_type', 'comment')
    new_status = request.form.get('new_status')
    
    # For status changes, content is optional but status is required
    if update_type == 'status_change':
        if not new_status:
            flash('Please select a new status', 'error')
        else:
            # Get current issue status
            old_status = None
            if issue_type == 'issue':
                issue = db.get_issue(issue_id)
                if issue:
                    old_status = issue.get('status')
                    db.update_issue(issue_id, {'status': new_status})
            elif issue_type == 'equipment_issue':
                issue = db.get_equipment_issue(issue_id)
                if issue:
                    old_status = issue.get('status')
                    db.update_equipment_issue(issue_id, {'status': new_status})
            elif issue_type == 'driver_issue':
                issue = db.get_driver_issue(issue_id)
                if issue:
                    old_status = issue.get('status')
                    db.update_driver_issue(issue_id, {'status': new_status})
            
            author_name = None
            author_id = None
            if g.current_user:
                author_name = g.current_user.get('name') or g.current_user.get('username')
                author_id = g.current_user.get('id')
            
            db.create_issue_update({
                'issue_type': issue_type,
                'issue_id': issue_id,
                'update_type': update_type,
                'content': content,
                'old_status': old_status,
                'new_status': new_status,
                'author_id': author_id,
                'author_name': author_name,
            })
            flash('Status updated', 'success')
    elif not content:
        flash('Please enter an update', 'error')
    else:
        author_name = None
        author_id = None
        if g.current_user:
            author_name = g.current_user.get('name') or g.current_user.get('username')
            author_id = g.current_user.get('id')
        
        db.create_issue_update({
            'issue_type': issue_type,
            'issue_id': issue_id,
            'update_type': update_type,
            'content': content,
            'author_id': author_id,
            'author_name': author_name,
        })
        flash('Update added', 'success')
    
    # Redirect back to the appropriate detail page
    if issue_type == 'issue':
        return redirect(url_for('main.issue_detail', issue_id=issue_id))
    elif issue_type == 'equipment_issue':
        # Need to get the equipment_id
        issue = db.get_equipment_issue(issue_id)
        if issue:
            return redirect(url_for('main.equipment_issue_detail', equipment_id=issue['equipment_id'], issue_id=issue_id))
    elif issue_type == 'driver_issue':
        # Need to get the driver_id
        issue = db.get_driver_issue(issue_id)
        if issue:
            return redirect(url_for('main.driver_issue_detail', driver_id=issue['driver_id'], issue_id=issue_id))
    
    return redirect(request.referrer or url_for('main.issues'))


@main_bp.route('/issues/<int:issue_id>/delete', methods=['POST'])
@admin_required
def issue_delete(issue_id):
    """Move an issue to trash (admin only)."""
    db = get_db_service()
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('issue', issue_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash('Issue moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving issue to trash'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.issues'))


# -------------------- Templates & QR Codes --------------------

# Supported entity types for templates and their corresponding new item routes
TEMPLATE_ENTITY_TYPES = {
    'sample': {'route': 'main.sample_new', 'label': 'Sample', 'icon': '🧪', 'new_url': 'samples/new'},
    'precursor': {'route': 'main.precursor_new', 'label': 'Precursor', 'icon': '⚗️', 'new_url': 'precursors/new'},
    'equipment': {'route': 'main.equipment_new', 'label': 'Equipment', 'icon': '🔧', 'new_url': 'equipment/new'},
    'procedure': {'route': 'main.procedure_new', 'label': 'Procedure', 'icon': '📋', 'new_url': 'procedures/new'},
}


TEMPLATE_STATUS_OPTIONS = {
    'active': {'label': 'Active', 'color': 'green'},
    'draft': {'label': 'Draft', 'color': 'gray'},
    'archived': {'label': 'Archived', 'color': 'orange'},
}


@main_bp.route('/templates')
def templates():
    """Templates list page with search, filtering, and QR code download options."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    entity_type = request.args.get('type', '')
    project_id = request.args.get('project_id', type=int)
    status = request.args.get('status', '')
    
    db = get_db_service()
    templates_list, total = db.get_templates(
        search=search if search else None,
        entity_type=entity_type if entity_type else None,
        project_id=project_id,
        status=status if status else None,
        page=page, 
        per_page=20
    )
    
    # Enrich templates with entity type info
    for t in templates_list:
        entity_info = TEMPLATE_ENTITY_TYPES.get(t['entity_type'], {})
        t['entity_icon'] = entity_info.get('icon', '📄')
        t['entity_label'] = entity_info.get('label', t['entity_type'].title())
        # Add status info
        status_info = TEMPLATE_STATUS_OPTIONS.get(t.get('status', 'active'), TEMPLATE_STATUS_OPTIONS['active'])
        t['status_label'] = status_info['label']
        t['status_color'] = status_info['color']
    
    total_pages = (total + 19) // 20
    projects = db.get_projects_simple_list()
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'template')
    
    return render_template('templates.html',
        templates=templates_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        entity_type=entity_type,
        project_id=project_id,
        status=status,
        projects=projects,
        entity_types=TEMPLATE_ENTITY_TYPES,
        status_options=TEMPLATE_STATUS_OPTIONS,
        pinned_ids=pinned_ids
    )


@main_bp.route('/templates/<int:template_id>')
def template_detail(template_id):
    """Template detail page."""
    db = get_db_service()
    template = db.get_template(template_id)
    
    if not template:
        flash('Template not found', 'error')
        return redirect(url_for('main.templates'))
    
    entity_info = TEMPLATE_ENTITY_TYPES.get(template['entity_type'], {})
    template['entity_icon'] = entity_info.get('icon', '📄')
    template['entity_label'] = entity_info.get('label', template['entity_type'].title())
    
    # Get linked precursors, equipment, and parent sample details
    linked_precursors = []
    linked_equipment = []
    parent_sample = None
    
    if template.get('template_data'):
        # Get linked precursors
        precursor_ids = template['template_data'].get('linked_precursor_ids', [])
        if precursor_ids:
            all_precursors = db.get_precursors_simple_list()
            linked_precursors = [p for p in all_precursors if p['id'] in precursor_ids]
        
        # Get linked equipment
        equipment_ids = template['template_data'].get('linked_equipment_ids', [])
        if equipment_ids:
            all_equipment = db.get_equipment_simple_list()
            linked_equipment = [e for e in all_equipment if e['id'] in equipment_ids]
        
        # Get parent sample
        parent_sample_id = template['template_data'].get('parent_sample_id')
        if parent_sample_id:
            all_samples = db.get_samples_simple_list()
            parent_sample = next((s for s in all_samples if s['id'] == int(parent_sample_id)), None)
    
    return render_template('template_detail.html', 
        template=template, 
        entity_types=TEMPLATE_ENTITY_TYPES,
        linked_precursors=linked_precursors,
        linked_equipment=linked_equipment,
        parent_sample=parent_sample
    )


@main_bp.route('/templates/new', methods=['GET', 'POST'])
def template_new():
    """Create new template page."""
    db = get_db_service()
    
    if request.method == 'POST':
        entity_type = request.form.get('entity_type')
        project_id = request.form.get('project_id')
        project_id = int(project_id) if project_id else None
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        
        # Build template_data from form fields based on entity type
        template_data = {}
        for key in request.form:
            if key.startswith('data_') and key not in ('data_linked_precursor_ids', 'data_linked_equipment_ids'):
                field_name = key[5:]  # Remove 'data_' prefix
                value = request.form.get(key)
                if value:
                    template_data[field_name] = value
        
        # Handle linked precursors (multiple values)
        linked_precursor_ids = request.form.getlist('data_linked_precursor_ids')
        linked_precursor_ids = [int(pid) for pid in linked_precursor_ids if pid]
        if linked_precursor_ids:
            template_data['linked_precursor_ids'] = linked_precursor_ids
        
        # Handle linked equipment (multiple values)
        linked_equipment_ids = request.form.getlist('data_linked_equipment_ids')
        linked_equipment_ids = [int(eid) for eid in linked_equipment_ids if eid]
        if linked_equipment_ids:
            template_data['linked_equipment_ids'] = linked_equipment_ids
        
        data = {
            'name': request.form.get('name'),
            'entity_type': entity_type,
            'description': request.form.get('description'),
            'template_data': template_data,
            'status': request.form.get('status', 'active'),
            'project_id': project_id,
            'lab_id': lab_id,
            'created_by': g.current_user['username'] if g.current_user else None,
        }
        
        try:
            template = db.create_template(data)
            flash('Template created successfully', 'success')
            return redirect(url_for('main.template_detail', template_id=template['id']))
        except Exception as e:
            flash(f'Error creating template: {str(e)}', 'error')
    
    projects = db.get_projects_simple_list()
    labs = db.get_labs_simple_list()
    precursors = db.get_precursors_simple_list()
    equipment = db.get_equipment_simple_list()
    samples = db.get_samples_simple_list()
    
    return render_template('template_form.html',
        template=None,
        action='Create',
        projects=projects,
        labs=labs,
        precursors=precursors,
        equipment=equipment,
        samples=samples,
        entity_types=TEMPLATE_ENTITY_TYPES
    )


@main_bp.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
def template_edit(template_id):
    """Edit template page."""
    db = get_db_service()
    template = db.get_template(template_id)
    
    if not template:
        flash('Template not found', 'error')
        return redirect(url_for('main.templates'))
    
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        project_id = int(project_id) if project_id else None
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        
        # Build template_data from form fields
        template_data = {}
        for key in request.form:
            if key.startswith('data_') and key not in ('data_linked_precursor_ids', 'data_linked_equipment_ids'):
                field_name = key[5:]  # Remove 'data_' prefix
                value = request.form.get(key)
                if value:
                    template_data[field_name] = value
        
        # Handle linked precursors (multiple values)
        linked_precursor_ids = request.form.getlist('data_linked_precursor_ids')
        linked_precursor_ids = [int(pid) for pid in linked_precursor_ids if pid]
        if linked_precursor_ids:
            template_data['linked_precursor_ids'] = linked_precursor_ids
        
        # Handle linked equipment (multiple values)
        linked_equipment_ids = request.form.getlist('data_linked_equipment_ids')
        linked_equipment_ids = [int(eid) for eid in linked_equipment_ids if eid]
        if linked_equipment_ids:
            template_data['linked_equipment_ids'] = linked_equipment_ids
        
        data = {
            'name': request.form.get('name'),
            'entity_type': request.form.get('entity_type'),
            'description': request.form.get('description'),
            'template_data': template_data,
            'status': request.form.get('status', 'active'),
            'project_id': project_id,
            'lab_id': lab_id,
        }
        
        try:
            db.update_template(template_id, data)
            flash('Template updated successfully', 'success')
            return redirect(url_for('main.template_detail', template_id=template_id))
        except Exception as e:
            flash(f'Error updating template: {str(e)}', 'error')
    
    projects = db.get_projects_simple_list()
    labs = db.get_labs_simple_list()
    precursors = db.get_precursors_simple_list()
    equipment = db.get_equipment_simple_list()
    samples = db.get_samples_simple_list()
    
    return render_template('template_form.html',
        template=template,
        action='Edit',
        projects=projects,
        labs=labs,
        precursors=precursors,
        equipment=equipment,
        samples=samples,
        entity_types=TEMPLATE_ENTITY_TYPES
    )


@main_bp.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def template_delete(template_id):
    """Move a template to trash."""
    db = get_db_service()
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('template', template_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash('Template moved to trash', 'success')
        else:
            flash(result.get('error', 'Template not found'), 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.templates'))


@main_bp.route('/templates/<int:template_id>/qrcode')
def template_qrcode(template_id):
    """Generate and download a QR code image for a template.
    
    The QR code encodes a URL to create a new entity with the template pre-filled.
    The image includes the template name, entity type, lab name, and project name as text below the QR code.
    """
    db = get_db_service()
    template = db.get_template(template_id)
    
    if not template:
        flash('Template not found', 'error')
        return redirect(url_for('main.templates'))
    
    entity_type = template['entity_type']
    entity_info = TEMPLATE_ENTITY_TYPES.get(entity_type)
    
    if not entity_info:
        flash(f'Unsupported entity type: {entity_type}', 'error')
        return redirect(url_for('main.templates'))
    
    # Generate the URL that the QR code will encode
    target_url = url_for(entity_info['route'], template_id=template_id, _external=True)
    
    # Generate QR code with label
    try:
        qr_image = generate_template_qr_code(
            url=target_url,
            template_name=template['name'],
            entity_type=entity_info['label'],
            lab_name=template.get('lab_name') or template['template_data'].get('lab_name', ''),
            project_name=template.get('project_name') or template['template_data'].get('project_name', '')
        )
        
        # Return as downloadable PNG
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_{entity_type}_{template['name'].replace(' ', '_')}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages. Install with: pip install qrcode[pil] pillow', 'error')
        return redirect(url_for('main.templates'))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.templates'))


@main_bp.route('/templates/<int:template_id>/qrcode/preview')
def template_qrcode_preview(template_id):
    """Return QR code image inline for preview (not as download)."""
    db = get_db_service()
    template = db.get_template(template_id)
    
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    
    entity_type = template['entity_type']
    entity_info = TEMPLATE_ENTITY_TYPES.get(entity_type)
    
    if not entity_info:
        return jsonify({'error': f'Unsupported entity type: {entity_type}'}), 400
    
    # Generate the URL that the QR code will encode
    target_url = url_for(entity_info['route'], template_id=template_id, _external=True)
    
    try:
        qr_image = generate_template_qr_code(
            url=target_url,
            template_name=template['name'],
            entity_type=entity_info['label'],
            lab_name=template.get('lab_name') or template['template_data'].get('lab_name', ''),
            project_name=template.get('project_name') or template['template_data'].get('project_name', '')
        )
        
        return send_file(qr_image, mimetype='image/png')
    except ImportError:
        return jsonify({'error': 'QR code packages not installed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_template_qr_code(url: str, template_name: str, entity_type: str = '', lab_name: str = '', project_name: str = '') -> BytesIO:
    """Generate a QR code image with label text below it.
    
    Args:
        url: The URL to encode in the QR code
        template_name: Template name to display below QR code
        entity_type: Entity type label (e.g., "Sample", "Equipment")
        lab_name: Lab name to display (optional)
        project_name: Project name to display (optional)
    
    Returns:
        BytesIO containing the PNG image
    """
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_width, qr_height = qr_img.size
    
    # Build label text lines
    label_lines = [template_name]
    if entity_type:
        label_lines.append(f"Type: {entity_type}")
    if lab_name:
        label_lines.append(f"Lab: {lab_name}")
    if project_name:
        label_lines.append(f"Project: {project_name}")
    
    # Try to use a nice font, fall back to default if not available
    try:
        # Try common fonts on different systems
        font_size = 20
        title_font_size = 24
        for font_name in ['arial.ttf', 'Arial.ttf', 'DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
            try:
                font = ImageFont.truetype(font_name, font_size)
                title_font = ImageFont.truetype(font_name, title_font_size)
                break
            except (IOError, OSError):
                continue
        else:
            font = ImageFont.load_default()
            title_font = font
    except Exception:
        font = ImageFont.load_default()
        title_font = font
    
    # Calculate text area height
    line_height = 30
    title_height = 40
    text_padding = 20
    text_area_height = title_height + (len(label_lines) - 1) * line_height + text_padding * 2
    
    # Create new image with space for text
    total_height = qr_height + text_area_height
    final_img = Image.new('RGB', (qr_width, total_height), 'white')
    
    # Paste QR code at top
    final_img.paste(qr_img, (0, 0))
    
    # Draw text below QR code
    draw = ImageDraw.Draw(final_img)
    
    y_offset = qr_height + text_padding
    for i, line in enumerate(label_lines):
        # Use title font for first line (template name)
        current_font = title_font if i == 0 else font
        
        # Calculate text width for centering
        bbox = draw.textbbox((0, 0), line, font=current_font)
        text_width = bbox[2] - bbox[0]
        x_offset = (qr_width - text_width) // 2
        
        draw.text((x_offset, y_offset), line, fill='black', font=current_font)
        y_offset += title_height if i == 0 else line_height
    
    # Save to BytesIO
    img_buffer = BytesIO()
    final_img.save(img_buffer, format='PNG', quality=95)
    img_buffer.seek(0)
    
    return img_buffer


def generate_entity_qr_code(url: str, entity_id: str, entity_type: str = '', project_name: str = '') -> BytesIO:
    """Generate a QR code image with ID and project text below it for any entity.
    
    Args:
        url: The URL to encode in the QR code
        entity_id: Entity ID to display below QR code (e.g., "SAMPLE-001")
        entity_type: Entity type label (e.g., "Sample", "Equipment")
        project_name: Project name to display (optional)
    
    Returns:
        BytesIO containing the PNG image
    """
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_width, qr_height = qr_img.size
    
    # Build label text lines
    label_lines = [entity_id]
    if entity_type:
        label_lines.append(f"Type: {entity_type}")
    if project_name:
        label_lines.append(f"Project: {project_name}")
    
    # Try to use a nice font, fall back to default if not available
    try:
        font_size = 20
        title_font_size = 24
        for font_name in ['arial.ttf', 'Arial.ttf', 'DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
            try:
                font = ImageFont.truetype(font_name, font_size)
                title_font = ImageFont.truetype(font_name, title_font_size)
                break
            except (IOError, OSError):
                continue
        else:
            font = ImageFont.load_default()
            title_font = font
    except Exception:
        font = ImageFont.load_default()
        title_font = font
    
    # Calculate text area height
    line_height = 30
    title_height = 40
    text_padding = 20
    text_area_height = title_height + (len(label_lines) - 1) * line_height + text_padding * 2
    
    # Create new image with space for text
    total_height = qr_height + text_area_height
    final_img = Image.new('RGB', (qr_width, total_height), 'white')
    
    # Paste QR code at top
    final_img.paste(qr_img, (0, 0))
    
    # Draw text below QR code
    draw = ImageDraw.Draw(final_img)
    
    y_offset = qr_height + text_padding
    for i, line in enumerate(label_lines):
        current_font = title_font if i == 0 else font
        bbox = draw.textbbox((0, 0), line, font=current_font)
        text_width = bbox[2] - bbox[0]
        x_offset = (qr_width - text_width) // 2
        draw.text((x_offset, y_offset), line, fill='black', font=current_font)
        y_offset += title_height if i == 0 else line_height
    
    # Save to BytesIO
    img_buffer = BytesIO()
    final_img.save(img_buffer, format='PNG', quality=95)
    img_buffer.seek(0)
    
    return img_buffer


# -------------------- Entity QR Code Routes --------------------

def generate_compact_qr_code(url):
    """Generate a compact QR code optimized for small physical labels (1cm).
    
    Uses minimal size settings while maintaining high error correction
    for reliable scanning on small samples.
    
    Args:
        url: The URL to encode in the QR code
    
    Returns:
        BytesIO containing the PNG image
    """
    import qrcode
    
    qr = qrcode.QRCode(
        version=1,  # Smallest version
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for reliability
        box_size=4,  # Small modules - results in ~100-120px image
        border=1,  # Minimal border to save space
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    img_buffer = BytesIO()
    qr_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    return img_buffer


@main_bp.route('/samples/<int:sample_id>/qrcode')
@login_required
def sample_qrcode(sample_id):
    """Generate and download a compact QR code image for a sample.
    
    Optimized for printing on small (1cm) samples - no text labels, minimal size.
    """
    db = get_db_service()
    sample = db.get_sample(sample_id)
    
    if not sample:
        flash('Sample not found', 'error')
        return redirect(url_for('main.samples'))
    
    target_url = url_for('main.sample_detail', sample_id=sample_id, _external=True)
    
    try:
        qr_image = generate_compact_qr_code(url=target_url)
        
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_sample_{sample.get('sample_id', sample_id)}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages.', 'error')
        return redirect(url_for('main.sample_detail', sample_id=sample_id))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.sample_detail', sample_id=sample_id))


@main_bp.route('/samples/<int:sample_id>/qrcode/preview')
def sample_qrcode_preview(sample_id):
    """Return compact QR code image inline for preview.
    
    Uses the same compact format as the download for consistency.
    """
    db = get_db_service()
    sample = db.get_sample(sample_id)
    
    if not sample:
        return jsonify({'error': 'Sample not found'}), 404
    
    target_url = url_for('main.sample_detail', sample_id=sample_id, _external=True)
    
    try:
        qr_image = generate_compact_qr_code(url=target_url)
        return send_file(qr_image, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/precursors/<int:precursor_id>/qrcode')
@login_required
def precursor_qrcode(precursor_id):
    """Generate and download a QR code image for a precursor."""
    db = get_db_service()
    precursor = db.get_precursor(precursor_id)
    
    if not precursor:
        flash('Precursor not found', 'error')
        return redirect(url_for('main.precursors'))
    
    target_url = url_for('main.precursor_detail', precursor_id=precursor_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=precursor.get('name', f'Precursor #{precursor_id}'),
            entity_type='Precursor',
            project_name=''
        )
        
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_precursor_{precursor_id}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages.', 'error')
        return redirect(url_for('main.precursor_detail', precursor_id=precursor_id))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.precursor_detail', precursor_id=precursor_id))


@main_bp.route('/precursors/<int:precursor_id>/qrcode/preview')
def precursor_qrcode_preview(precursor_id):
    """Return QR code image inline for preview."""
    db = get_db_service()
    precursor = db.get_precursor(precursor_id)
    
    if not precursor:
        return jsonify({'error': 'Precursor not found'}), 404
    
    target_url = url_for('main.precursor_detail', precursor_id=precursor_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=precursor.get('name', f'Precursor #{precursor_id}'),
            entity_type='Precursor',
            project_name=''
        )
        return send_file(qr_image, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/equipment/<int:equipment_id>/qrcode')
@login_required
def equipment_qrcode(equipment_id):
    """Generate and download a QR code image for equipment."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    
    if not equipment:
        flash('Equipment not found', 'error')
        return redirect(url_for('main.equipment'))
    
    target_url = url_for('main.equipment_detail', equipment_id=equipment_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=equipment.get('name', f'Equipment #{equipment_id}'),
            entity_type='Equipment',
            project_name=''
        )
        
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_equipment_{equipment_id}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages.', 'error')
        return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))


@main_bp.route('/equipment/<int:equipment_id>/qrcode/preview')
def equipment_qrcode_preview(equipment_id):
    """Return QR code image inline for preview."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    
    if not equipment:
        return jsonify({'error': 'Equipment not found'}), 404
    
    target_url = url_for('main.equipment_detail', equipment_id=equipment_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=equipment.get('name', f'Equipment #{equipment_id}'),
            entity_type='Equipment',
            project_name=''
        )
        return send_file(qr_image, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/procedures/<int:procedure_id>/qrcode')
@login_required
def procedure_qrcode(procedure_id):
    """Generate and download a QR code image for a procedure."""
    db = get_db_service()
    procedure = db.get_procedure(procedure_id)
    
    if not procedure:
        flash('Procedure not found', 'error')
        return redirect(url_for('main.procedures'))
    
    target_url = url_for('main.procedure_detail', procedure_id=procedure_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=procedure.get('name', f'Procedure #{procedure_id}'),
            entity_type='Procedure',
            project_name=''
        )
        
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_procedure_{procedure_id}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages.', 'error')
        return redirect(url_for('main.procedure_detail', procedure_id=procedure_id))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.procedure_detail', procedure_id=procedure_id))


@main_bp.route('/procedures/<int:procedure_id>/qrcode/preview')
def procedure_qrcode_preview(procedure_id):
    """Return QR code image inline for preview."""
    db = get_db_service()
    procedure = db.get_procedure(procedure_id)
    
    if not procedure:
        return jsonify({'error': 'Procedure not found'}), 404
    
    target_url = url_for('main.procedure_detail', procedure_id=procedure_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=procedure.get('name', f'Procedure #{procedure_id}'),
            entity_type='Procedure',
            project_name=''
        )
        return send_file(qr_image, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/labs/<int:lab_id>/qrcode')
@login_required
def lab_qrcode(lab_id):
    """Generate and download a QR code image for a lab."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    target_url = url_for('main.lab_detail', lab_id=lab_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=lab.get('name', f'Lab #{lab_id}'),
            entity_type='Lab',
            project_name=''
        )
        
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_lab_{lab_id}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages.', 'error')
        return redirect(url_for('main.lab_detail', lab_id=lab_id))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.lab_detail', lab_id=lab_id))


@main_bp.route('/labs/<int:lab_id>/qrcode/preview')
def lab_qrcode_preview(lab_id):
    """Return QR code image inline for preview."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        return jsonify({'error': 'Lab not found'}), 404
    
    target_url = url_for('main.lab_detail', lab_id=lab_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=lab.get('name', f'Lab #{lab_id}'),
            entity_type='Lab',
            project_name=''
        )
        return send_file(qr_image, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/projects/<int:project_id>/qrcode')
@login_required
def project_qrcode(project_id):
    """Generate and download a QR code image for a project."""
    db = get_db_service()
    project = db.get_project(project_id)
    
    if not project:
        flash('Project not found', 'error')
        return redirect(url_for('main.projects'))
    
    target_url = url_for('main.project_detail', project_id=project_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=project.get('name', f'Project #{project_id}'),
            entity_type='Project',
            project_name=''
        )
        
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_project_{project_id}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages.', 'error')
        return redirect(url_for('main.project_detail', project_id=project_id))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.project_detail', project_id=project_id))


@main_bp.route('/projects/<int:project_id>/qrcode/preview')
def project_qrcode_preview(project_id):
    """Return QR code image inline for preview."""
    db = get_db_service()
    project = db.get_project(project_id)
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    target_url = url_for('main.project_detail', project_id=project_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=project.get('name', f'Project #{project_id}'),
            entity_type='Project',
            project_name=''
        )
        return send_file(qr_image, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/locations/<int:location_id>/qrcode')
@login_required
def location_qrcode(location_id):
    """Generate and download a QR code image for a location."""
    db = get_db_service()
    location = db.get_location(location_id)
    
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('main.locations'))
    
    target_url = url_for('main.location_detail', location_id=location_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=location.get('name', f'Location #{location_id}'),
            entity_type='Location',
            project_name=''
        )
        
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_location_{location_id}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages.', 'error')
        return redirect(url_for('main.location_detail', location_id=location_id))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.location_detail', location_id=location_id))


@main_bp.route('/locations/<int:location_id>/qrcode/preview')
def location_qrcode_preview(location_id):
    """Return QR code image inline for preview."""
    db = get_db_service()
    location = db.get_location(location_id)
    
    if not location:
        return jsonify({'error': 'Location not found'}), 404
    
    target_url = url_for('main.location_detail', location_id=location_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=location.get('name', f'Location #{location_id}'),
            entity_type='Location',
            project_name=''
        )
        return send_file(qr_image, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== API Routes ====================

@api_bp.route('/search')
def api_search():
    """Global search API."""
    query = request.args.get('q', '')
    db = get_db_service()
    results = db.global_search(query)
    return jsonify(results)


@api_bp.route('/samples')
def api_samples():
    """Get samples list."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    db = get_db_service()
    samples, total = db.get_samples(search=search if search else None, page=page)
    
    return jsonify({
        'samples': samples,
        'total': total,
        'page': page,
    })


@api_bp.route('/samples/<int:sample_id>')
def api_sample(sample_id):
    """Get single sample."""
    db = get_db_service()
    sample = db.get_sample(sample_id)
    if not sample:
        return jsonify({'error': 'Sample not found'}), 404
    return jsonify(sample)


@api_bp.route('/scans')
def api_scans():
    """Get scans list."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    db = get_db_service()
    scans, total = db.get_scans(search=search if search else None, page=page)
    
    return jsonify({
        'scans': scans,
        'total': total,
        'page': page,
    })


@api_bp.route('/scans/<int:scan_id>')
def api_scan(scan_id):
    """Get single scan."""
    db = get_db_service()
    scan = db.get_scan(scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    return jsonify(scan)


@api_bp.route('/scans/<int:scan_id>/data')
def api_scan_data(scan_id):
    """Get scan measurement data points."""
    db = get_db_service()
    data_points = db.get_scan_data_points(scan_id)
    return jsonify({'data_points': data_points})


@api_bp.route('/queues')
def api_queues():
    """Get queues list."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    db = get_db_service()
    queues, total = db.get_queues(search=search if search else None, page=page)
    
    return jsonify({
        'queues': queues,
        'total': total,
        'page': page,
    })


@api_bp.route('/queues/<int:queue_id>')
def api_queue(queue_id):
    """Get single queue."""
    db = get_db_service()
    queue = db.get_queue(queue_id)
    if not queue:
        return jsonify({'error': 'Queue not found'}), 404
    return jsonify(queue)


@api_bp.route('/equipment')
def api_equipment():
    """Get equipment list."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    db = get_db_service()
    equipment, total = db.get_equipment_list(search=search if search else None, page=page)
    
    return jsonify({
        'equipment': equipment,
        'total': total,
        'page': page,
    })


@api_bp.route('/precursors')
def api_precursors():
    """Get precursors list."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    db = get_db_service()
    precursors, total = db.get_precursors(search=search if search else None, page=page)
    
    return jsonify({
        'precursors': precursors,
        'total': total,
        'page': page,
    })


# ==================== Sample Precursor Management API ====================

@api_bp.route('/samples/<int:sample_id>/precursors', methods=['GET'])
def api_sample_precursors(sample_id):
    """Get precursors for a sample."""
    db = get_db_service()
    precursors = db.get_sample_precursors(sample_id)
    return jsonify({'precursors': precursors})


@api_bp.route('/samples/<int:sample_id>/precursors', methods=['POST'])
def api_add_sample_precursor(sample_id):
    """Add a precursor to a sample."""
    db = get_db_service()
    data = request.get_json()
    
    if not data or 'precursor_id' not in data:
        return jsonify({'error': 'precursor_id is required'}), 400
    
    success = db.add_sample_precursor(
        sample_id=sample_id,
        precursor_id=data['precursor_id'],
        quantity_used=data.get('quantity_used'),
        quantity_unit=data.get('quantity_unit'),
        role=data.get('role'),
        composition_percent=data.get('composition_percent')
    )
    
    if success:
        return jsonify({'success': True, 'message': 'Precursor added'})
    else:
        return jsonify({'error': 'Precursor already exists for this sample with that role'}), 409


@api_bp.route('/samples/<int:sample_id>/precursors/<int:precursor_id>', methods=['DELETE'])
def api_remove_sample_precursor(sample_id, precursor_id):
    """Remove a precursor from a sample."""
    db = get_db_service()
    role = request.args.get('role')  # Optional role to specify which association to remove
    
    success = db.remove_sample_precursor(sample_id, precursor_id, role)
    
    if success:
        return jsonify({'success': True, 'message': 'Precursor removed'})
    else:
        return jsonify({'error': 'Precursor association not found'}), 404


# ==================== Simple Lists for Dropdowns ====================

@api_bp.route('/dropdown/projects')
def api_dropdown_projects():
    """Get simple project list for dropdowns."""
    db = get_db_service()
    projects = db.get_projects_simple_list()
    return jsonify({'projects': projects})


@api_bp.route('/dropdown/samples')
def api_dropdown_samples():
    """Get simple sample list for dropdowns."""
    exclude_id = request.args.get('exclude', type=int)
    db = get_db_service()
    samples = db.get_samples_simple_list(exclude_id=exclude_id)
    return jsonify({'samples': samples})


@api_bp.route('/dropdown/precursors')
def api_dropdown_precursors():
    """Get simple precursor list for dropdowns."""
    db = get_db_service()
    precursors = db.get_precursors_simple_list()
    return jsonify({'precursors': precursors})


@api_bp.route('/dropdown/waste')
def api_dropdown_waste():
    """Get simple waste list for dropdowns."""
    lab_id = request.args.get('lab_id', type=int)
    db = get_db_service()
    wastes = db.get_wastes_simple_list(lab_id=lab_id)
    return jsonify({'wastes': wastes})


# ==================== Waste API ====================

@api_bp.route('/waste')
def api_wastes():
    """Get waste containers list."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    waste_type = request.args.get('type', '')
    status = request.args.get('status', '')
    lab_id = request.args.get('lab_id', type=int)
    
    db = get_db_service()
    wastes, total = db.get_wastes(
        search=search if search else None,
        waste_type=waste_type if waste_type else None,
        status=status if status else None,
        lab_id=lab_id,
        page=page
    )
    
    return jsonify({
        'wastes': wastes,
        'total': total,
        'page': page,
    })


@api_bp.route('/waste/<int:waste_id>')
def api_waste(waste_id):
    """Get single waste container."""
    db = get_db_service()
    waste = db.get_waste(waste_id)
    if not waste:
        return jsonify({'error': 'Waste container not found'}), 404
    return jsonify(waste)


@api_bp.route('/waste/<int:waste_id>/precursors', methods=['GET'])
def api_waste_precursors(waste_id):
    """Get precursors linked to a waste container."""
    db = get_db_service()
    precursors = db.get_waste_precursors(waste_id)
    return jsonify({'precursors': precursors})


@api_bp.route('/waste/<int:waste_id>/precursors', methods=['POST'])
@api_login_required
def api_add_waste_precursor(waste_id):
    """Add a precursor to a waste container."""
    db = get_db_service()
    data = request.get_json()
    
    if not data or 'precursor_id' not in data:
        return jsonify({'error': 'precursor_id is required'}), 400
    
    result = db.add_precursor_to_waste(
        waste_id,
        data['precursor_id'],
        data.get('quantity'),
        data.get('quantity_unit'),
        data.get('notes')
    )
    
    if result:
        return jsonify({'success': True, 'association': result})
    else:
        return jsonify({'error': 'Precursor already linked to this waste'}), 400


@api_bp.route('/waste/<int:waste_id>/precursors/<int:precursor_id>', methods=['DELETE'])
@api_login_required
def api_remove_waste_precursor(waste_id, precursor_id):
    """Remove a precursor from a waste container."""
    db = get_db_service()
    
    if db.remove_precursor_from_waste(waste_id, precursor_id):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Precursor not found in waste'}), 404


@api_bp.route('/templates')
def api_templates():
    """Get sample templates list."""
    page = request.args.get('page', 1, type=int)
    entity_type = request.args.get('entity_type', 'sample')
    
    db = get_db_service()
    templates, total = db.get_templates(entity_type=entity_type, page=page)
    
    return jsonify({
        'templates': templates,
        'total': total,
        'page': page,
    })


@api_bp.route('/templates/<int:template_id>')
def api_template(template_id):
    """Get single template."""
    db = get_db_service()
    template = db.get_template(template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    return jsonify(template)


@api_bp.route('/generate-id/<entity_type>')
def api_generate_id(entity_type):
    """Generate the next available ID for an entity type.
    
    Args:
        entity_type: The type of entity (sample, precursor, equipment, procedure)
    """
    db = get_db_service()
    
    if entity_type == 'sample':
        prefix = request.args.get('prefix', 'S')
        next_id = db.generate_next_sample_id(prefix)
        return jsonify({'next_id': next_id})
    else:
        return jsonify({'error': f'Unknown entity type: {entity_type}'}), 400


@api_bp.route('/stats')
def api_stats():
    """Get dashboard statistics."""
    db = get_db_service()
    stats = db.get_dashboard_stats()
    return jsonify(stats)


@api_bp.route('/resolve-qr')
def api_resolve_qr():
    """Resolve a QR code URL to entity information.
    
    This endpoint parses URLs from scanned QR codes and returns
    the entity type, ID, and display name for use in form dropdowns.
    
    Args:
        url: The full URL from the scanned QR code
        expected_type: (optional) The expected entity type for validation
    
    Returns:
        {
            'success': true,
            'entity_type': 'sample',
            'entity_id': 123,
            'display_name': 'Sample ABC-001',
            'url': '/samples/123'
        }
    """
    import re
    from urllib.parse import urlparse
    
    url = request.args.get('url', '')
    expected_type = request.args.get('expected_type', '')
    
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'}), 400
    
    # Parse the URL to extract the path
    try:
        parsed = urlparse(url)
        path = parsed.path
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid URL format'}), 400
    
    # Define entity type patterns and their corresponding getters
    entity_patterns = {
        'sample': (r'/samples/(\d+)', 'get_sample', lambda s: s.get('name') or s.get('sample_id') or f"Sample #{s['id']}"),
        'precursor': (r'/precursors/(\d+)', 'get_precursor', lambda p: p.get('name') or f"Precursor #{p['id']}"),
        'equipment': (r'/equipment/(\d+)', 'get_equipment', lambda e: e.get('name') or f"Equipment #{e['id']}"),
        'procedure': (r'/procedures/(\d+)', 'get_procedure', lambda p: p.get('name') or f"Procedure #{p['id']}"),
        'project': (r'/projects/(\d+)', 'get_project', lambda p: p.get('name') or f"Project #{p['id']}"),
        'lab': (r'/labs/(\d+)', 'get_lab', lambda l: l.get('name') or f"Lab #{l['id']}"),
        'location': (r'/locations/(\d+)', 'get_location', lambda l: l.get('name') or f"Location #{l['id']}"),
        'instrument': (r'/instruments/(\d+)', 'get_instrument', lambda i: i.get('name') or f"Instrument #{i['id']}"),
        'computer': (r'/computers/(\d+)', 'get_computer', lambda c: c.get('nickname') or c.get('computer_name') or f"Computer #{c['id']}"),
        'template': (r'/templates/(\d+)', 'get_template', lambda t: t.get('name') or f"Template #{t['id']}"),
        'driver': (r'/drivers/(\d+)', 'get_driver', lambda d: d.get('display_name') or d.get('class_name') or f"Driver #{d['id']}"),
        'user': (r'/users/(\d+)', 'get_user', lambda u: u.get('display_name') or u.get('username') or f"User #{u['id']}"),
        'waste': (r'/waste/(\d+)', 'get_waste', lambda w: w.get('name') or f"Waste #{w['id']}"),
    }
    
    db = get_db_service()
    
    # Try to match each entity type pattern
    for entity_type, (pattern, getter_name, display_func) in entity_patterns.items():
        match = re.search(pattern, path)
        if match:
            entity_id = int(match.group(1))
            
            # Check if expected type matches (if specified)
            if expected_type and expected_type != entity_type:
                return jsonify({
                    'success': False,
                    'error': f'Expected {expected_type} but scanned {entity_type}',
                    'scanned_type': entity_type
                }), 400
            
            # Get the entity details
            getter = getattr(db, getter_name, None)
            if getter:
                entity = getter(entity_id)
                if entity:
                    # Log QR code scan for analytics
                    user_id = g.current_user['id'] if hasattr(g, 'current_user') and g.current_user else None
                    try:
                        db.log_qr_scan(entity_type, entity_id, user_id=user_id, scanned_url=url)
                    except Exception:
                        pass  # Don't fail the request if logging fails
                    
                    return jsonify({
                        'success': True,
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                        'display_name': display_func(entity),
                        'url': path
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'{entity_type.title()} #{entity_id} not found'
                    }), 404
            
            # If no getter, just return the basic info (also log scan)
            user_id = g.current_user['id'] if hasattr(g, 'current_user') and g.current_user else None
            try:
                db.log_qr_scan(entity_type, entity_id, user_id=user_id, scanned_url=url)
            except Exception:
                pass
            
            return jsonify({
                'success': True,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'display_name': f'{entity_type.title()} #{entity_id}',
                'url': path
            })
    
    return jsonify({
        'success': False,
        'error': 'Could not parse entity from URL'
    }), 400


@api_bp.route('/images/<entity_type>/<int:entity_id>/upload', methods=['POST'])
@api_login_required
def api_upload_entity_image(entity_type, entity_id):
    """Upload an image for any entity type."""
    import os
    import uuid
    from werkzeug.utils import secure_filename
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    
    try:
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
        
        # Save file
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'images')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, stored_filename)
        file.save(filepath)
        
        # Get file info
        file_size = os.path.getsize(filepath)
        
        db = get_db_service()
        image = db.create_entity_image({
            'entity_type': entity_type,
            'entity_id': entity_id,
            'filename': original_filename,
            'stored_filename': stored_filename,
            'file_size_bytes': file_size,
            'mime_type': file.content_type,
            'name': request.form.get('name', original_filename),
            'uploaded_by': g.current_user.get('username') if g.current_user else None,
        })
        
        return jsonify({
            'success': True,
            'image': image,
            'url': f"/static/uploads/images/{stored_filename}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/images/<int:image_id>/delete', methods=['POST'])
@login_required
def delete_entity_image(image_id):
    """Delete an entity image."""
    import os
    
    db = get_db_service()
    
    try:
        # Delete returns the stored filename so we can remove the file
        stored_filename = db.delete_entity_image(image_id)
        
        if stored_filename:
            # Delete the actual file
            filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'images', stored_filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            flash('Image deleted', 'success')
        else:
            flash('Image not found', 'error')
    except Exception as e:
        flash(f'Error deleting image: {str(e)}', 'error')
    
    # Redirect back to referrer or home
    return redirect(request.referrer or url_for('main.index'))


@api_bp.route('/images/<int:image_id>', methods=['PUT'])
@api_login_required
def api_update_entity_image(image_id):
    """Update an entity image's metadata."""
    db = get_db_service()
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    try:
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'description' in data:
            update_data['description'] = data['description']
        
        image = db.update_entity_image(image_id, update_data)
        if image:
            return jsonify({'success': True, 'image': image})
        else:
            return jsonify({'success': False, 'error': 'Image not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/images/<entity_type>/<int:entity_id>/upload-base64', methods=['POST'])
@api_login_required
def api_upload_entity_image_base64(entity_type, entity_id):
    """Upload an image from base64 data (e.g., from chart capture)."""
    import os
    import uuid
    import base64
    
    data = request.get_json()
    if not data or 'image_data' not in data:
        return jsonify({'success': False, 'error': 'No image data provided'}), 400
    
    image_data = data['image_data']
    name = data.get('name', 'Visualization')
    description = data.get('description', '')
    
    # Parse base64 data URL
    # Format: data:image/png;base64,iVBORw0KGgo...
    try:
        if ',' in image_data:
            header, encoded = image_data.split(',', 1)
            # Extract mime type
            if 'image/png' in header:
                ext = 'png'
                mime_type = 'image/png'
            elif 'image/jpeg' in header or 'image/jpg' in header:
                ext = 'jpg'
                mime_type = 'image/jpeg'
            elif 'image/webp' in header:
                ext = 'webp'
                mime_type = 'image/webp'
            else:
                ext = 'png'
                mime_type = 'image/png'
        else:
            encoded = image_data
            ext = 'png'
            mime_type = 'image/png'
        
        # Decode base64
        image_bytes = base64.b64decode(encoded)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        original_filename = f"{safe_name}_{timestamp}.{ext}"
        stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
        
        # Save file
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'images')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, stored_filename)
        
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        
        file_size = len(image_bytes)
        
        db = get_db_service()
        image = db.create_entity_image({
            'entity_type': entity_type,
            'entity_id': entity_id,
            'filename': original_filename,
            'stored_filename': stored_filename,
            'file_size_bytes': file_size,
            'mime_type': mime_type,
            'name': name,
            'description': description,
            'uploaded_by': g.current_user.get('username') if g.current_user else None,
        })
        
        return jsonify({
            'success': True,
            'image': image,
            'url': f"/static/uploads/images/{stored_filename}"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# -------------------- File Attachments API --------------------
# Configurable allowed file types - easily extendable for new scientific file formats
ALLOWED_FILE_EXTENSIONS = {
    # Documents
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp', 'rtf', 'txt',
    # Data formats
    'csv', 'json', 'xml', 'yaml', 'yml', 'toml',
    # Scientific/Lab-specific
    'kdf',          # KLayout design files
    'gds', 'gdsii', # GDSII layout files
    'spm', 'afm',   # Gwyddion AFM/SPM files  
    'nid', 'gsf',   # Gwyddion native formats
    'ibw', 'pxp',   # Igor Pro files
    'dat', 'asc',   # Generic data files
    'sxm', 'mtrx',  # Nanoscope/other SPM formats
    'h5', 'hdf5', 'hdf', 'nc', 'netcdf',  # HDF5 and NetCDF scientific data
    'npy', 'npz',   # NumPy data files
    'mat',          # MATLAB files
    'fits', 'fit',  # FITS astronomical data
    'cif', 'pdb',   # Crystallography/molecular data
    # Archives
    'zip', 'tar', 'gz', 'bz2', '7z', 'rar',
    # Code/scripts
    'py', 'ipynb', 'r', 'jl', 'm',
    # Images (non-gallery, for data files)
    'tif', 'tiff', 'raw', 'dng',
    # Vector graphics
    'svg', 'eps', 'ai',
    # Other
    'log', 'ini', 'cfg',
}


def is_allowed_file(filename: str) -> bool:
    """Check if file extension is in allowed list."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in ALLOWED_FILE_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension."""
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


@api_bp.route('/files/<entity_type>/<int:entity_id>/upload', methods=['POST'])
@api_login_required
def api_upload_entity_file(entity_type, entity_id):
    """Upload a file attachment for any entity type."""
    import os
    import uuid
    from werkzeug.utils import secure_filename
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Validate file type
    if not is_allowed_file(file.filename):
        ext = get_file_extension(file.filename)
        return jsonify({
            'success': False, 
            'error': f'File type .{ext} is not allowed. Contact admin to add support for this file type.'
        }), 400
    
    try:
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
        
        # Save file
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'files')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, stored_filename)
        file.save(filepath)
        
        # Get file info
        file_size = os.path.getsize(filepath)
        ext = get_file_extension(original_filename)
        
        db = get_db_service()
        attachment = db.create_entity_attachment({
            'entity_type': entity_type,
            'entity_id': entity_id,
            'filename': original_filename,
            'stored_filename': stored_filename,
            'file_size_bytes': file_size,
            'mime_type': file.content_type,
            'file_type': ext,
            'name': request.form.get('name', original_filename),
            'description': request.form.get('description', ''),
            'uploaded_by': g.current_user.get('username') if g.current_user else None,
        })
        
        return jsonify({
            'success': True,
            'attachment': attachment,
            'url': f"/static/uploads/files/{stored_filename}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/files/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_entity_attachment(attachment_id):
    """Delete an entity attachment."""
    import os
    
    db = get_db_service()
    
    try:
        # Delete returns the stored filename so we can remove the file
        stored_filename = db.delete_entity_attachment(attachment_id)
        
        if stored_filename:
            # Delete the actual file
            filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'files', stored_filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            flash('File deleted', 'success')
        else:
            flash('File not found', 'error')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}', 'error')
    
    # Redirect back to referrer or home
    return redirect(request.referrer or url_for('main.index'))


@api_bp.route('/files/<int:attachment_id>', methods=['PUT'])
@api_login_required
def api_update_entity_attachment(attachment_id):
    """Update an entity attachment's metadata."""
    db = get_db_service()
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    try:
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'description' in data:
            update_data['description'] = data['description']
        
        attachment = db.update_entity_attachment(attachment_id, update_data)
        if attachment:
            return jsonify({'success': True, 'attachment': attachment})
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/files/allowed-types', methods=['GET'])
def api_get_allowed_file_types():
    """Get list of allowed file extensions."""
    return jsonify({
        'success': True,
        'extensions': sorted(list(ALLOWED_FILE_EXTENSIONS))
    })


# -------------------- Driver Folder Upload --------------------

@api_bp.route('/drivers/upload-folder', methods=['POST'])
@api_login_required
def api_upload_driver_folder():
    """Upload multiple files for a driver (folder upload).
    
    Files should be sent with their relative paths preserved.
    The main instrument definition file must be named 'driver.py' or '<ClassName>_driver.py'.
    
    Returns:
        JSON with file list and detected main file
    """
    import os
    import uuid
    from werkzeug.utils import secure_filename
    
    if 'files[]' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400
    
    files = request.files.getlist('files[]')
    paths = request.form.getlist('paths[]')  # Relative paths from the folder
    
    if not files:
        return jsonify({'success': False, 'error': 'No files selected'}), 400
    
    # Generate unique folder ID for this upload
    upload_id = uuid.uuid4().hex[:12]
    driver_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'drivers', upload_id)
    os.makedirs(driver_folder, exist_ok=True)
    
    file_list = []
    main_file_path = None
    main_file_content = None
    
    try:
        for i, file in enumerate(files):
            if file.filename == '':
                continue
            
            # Get relative path (from JavaScript webkitRelativePath)
            rel_path = paths[i] if i < len(paths) else file.filename
            
            # Remove leading folder name if present (e.g., "MyDriver/driver.py" -> "driver.py")
            path_parts = rel_path.replace('\\', '/').split('/')
            if len(path_parts) > 1:
                # Remove the root folder name
                rel_path = '/'.join(path_parts[1:])
            
            # Secure each path component
            safe_parts = [secure_filename(p) for p in rel_path.split('/') if p]
            safe_rel_path = '/'.join(safe_parts)
            
            if not safe_rel_path:
                continue
            
            # Create subdirectories if needed
            file_dir = os.path.join(driver_folder, os.path.dirname(safe_rel_path))
            os.makedirs(file_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(driver_folder, safe_rel_path)
            file.save(file_path)
            
            file_size = os.path.getsize(file_path)
            
            file_info = {
                'path': safe_rel_path,
                'size': file_size,
                'is_python': safe_rel_path.endswith('.py'),
            }
            file_list.append(file_info)
            
            # Check if this is the main driver file
            filename = os.path.basename(safe_rel_path)
            if filename == 'driver.py' or filename.endswith('_driver.py'):
                main_file_path = safe_rel_path
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    main_file_content = f.read()
        
        if not file_list:
            return jsonify({'success': False, 'error': 'No valid files found'}), 400
        
        # If no main file found with naming convention, check for a .py file with a class definition
        if not main_file_path:
            for f in file_list:
                if f['is_python']:
                    fpath = os.path.join(driver_folder, f['path'])
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as pf:
                        content = pf.read()
                        if 'class ' in content and ('Measurement' in content or 'Movement' in content):
                            main_file_path = f['path']
                            main_file_content = content
                            break
        
        return jsonify({
            'success': True,
            'upload_id': upload_id,
            'files': file_list,
            'main_file_path': main_file_path,
            'main_file_content': main_file_content,
            'folder_path': driver_folder,
        })
        
    except Exception as e:
        # Clean up on error
        import shutil
        if os.path.exists(driver_folder):
            shutil.rmtree(driver_folder)
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/drivers/<int:driver_id>/files/<path:file_path>')
def api_get_driver_file_content(driver_id, file_path):
    """Get content of a specific file in a driver folder."""
    import os
    
    db = get_db_service()
    driver = db.get_driver(driver_id)
    
    if not driver:
        return jsonify({'success': False, 'error': 'Driver not found'}), 404
    
    if not driver.get('has_folder_upload'):
        return jsonify({'success': False, 'error': 'Driver does not have folder files'}), 400
    
    # Find the upload folder for this driver
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'drivers')
    
    # Look through driver_files to find a matching folder
    driver_files = driver.get('driver_files', [])
    if not driver_files:
        return jsonify({'success': False, 'error': 'No files found for this driver'}), 404
    
    # The upload_id should be stored somewhere - for now, we'll look for it based on driver_id
    # In a production system, you'd store the upload_id in the driver record
    driver_folder = os.path.join(upload_folder, f"driver_{driver_id}")
    
    if not os.path.exists(driver_folder):
        return jsonify({'success': False, 'error': 'Driver folder not found'}), 404
    
    file_full_path = os.path.join(driver_folder, file_path)
    
    # Security check - make sure the path doesn't escape the driver folder
    if not os.path.realpath(file_full_path).startswith(os.path.realpath(driver_folder)):
        return jsonify({'success': False, 'error': 'Invalid file path'}), 400
    
    if not os.path.exists(file_full_path):
        return jsonify({'success': False, 'error': 'File not found'}), 404
    
    try:
        with open(file_full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'path': file_path,
            'content': content,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# -------------------- Instruments --------------------

@main_bp.route('/instruments')
def instruments():
    """Instruments list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    lab_id = request.args.get('lab_id', type=int)
    
    db = get_db_service()
    instruments_list, total = db.get_instruments_list(
        search=search if search else None,
        status=status if status else None,
        lab_id=lab_id,
        page=page
    )
    
    # Get labs for filter dropdown
    labs_list, _ = db.get_labs(per_page=100)
    
    total_pages = (total + 19) // 20
    
    # Get pinned instrument IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'instrument')
    
    return render_template('instruments.html',
        instruments=instruments_list,
        labs=labs_list,
        total=total,
        page=page,
        total_pages=total_pages,
        search=search,
        status=status,
        lab_id=lab_id,
        pinned_ids=pinned_ids,
    )


@main_bp.route('/instruments/<int:instrument_id>')
def instrument_detail(instrument_id):
    """Instrument detail page."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instruments'))
    images = db.get_entity_images('instrument', instrument_id)
    attachments = db.get_entity_attachments('instrument', instrument_id)
    object_location = db.get_object_location('instrument', instrument_id)
    locations_list = db.get_locations_simple_list()
    return render_template('instrument_detail.html', instrument=instrument, images=images, attachments=attachments,
                           object_type='instrument', object_id=instrument_id, object_location=object_location, locations_list=locations_list)


@main_bp.route('/instruments/<int:instrument_id>/qrcode/preview')
def instrument_qrcode_preview(instrument_id):
    """Return QR code image inline for preview."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        return jsonify({'error': 'Instrument not found'}), 404
    
    target_url = url_for('main.instrument_detail', instrument_id=instrument_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=instrument.get('name', f'Instrument #{instrument_id}'),
            entity_type='Instrument',
            project_name=''
        )
        return send_file(qr_image, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/instruments/<int:instrument_id>/qrcode')
@login_required
def instrument_qrcode(instrument_id):
    """Generate and download a QR code image for an instrument."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instruments'))
    
    target_url = url_for('main.instrument_detail', instrument_id=instrument_id, _external=True)
    
    try:
        qr_image = generate_entity_qr_code(
            url=target_url,
            entity_id=instrument.get('name', f'Instrument #{instrument_id}'),
            entity_type='Instrument',
            project_name=''
        )
        
        return send_file(
            qr_image,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_instrument_{instrument_id}.png"
        )
    except ImportError:
        flash('QR code generation requires qrcode and Pillow packages.', 'error')
        return redirect(url_for('main.instrument_detail', instrument_id=instrument_id))
    except Exception as e:
        flash(f'Error generating QR code: {str(e)}', 'error')
        return redirect(url_for('main.instrument_detail', instrument_id=instrument_id))


@main_bp.route('/instruments/new', methods=['GET', 'POST'])
@login_required
def instrument_new():
    """Create new instrument page."""
    db = get_db_service()
    
    # Get equipment_id from query params for pre-selection
    pre_equipment_id = request.args.get('equipment_id', type=int)
    return_url = request.args.get('return_url') or request.referrer
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        driver_id = request.form.get('driver_id')
        driver_id = int(driver_id) if driver_id else None
        equipment_id = request.form.get('equipment_id')
        equipment_id = int(equipment_id) if equipment_id else None
        
        data = {
            'name': request.form.get('name'),
            'instrument_type': request.form.get('instrument_type'),
            'driver_id': driver_id,
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'status': request.form.get('status', 'available'),
            'lab_id': lab_id,
            'equipment_id': equipment_id,
            'created_by': g.current_user.get('username') if g.current_user else None,
        }
        
        try:
            instrument = db.create_instrument(data)
            flash(f'Instrument "{instrument["name"]}" created successfully', 'success')
            return redirect(url_for('main.instrument_detail', instrument_id=instrument['id']))
        except Exception as e:
            flash(f'Error creating instrument: {str(e)}', 'error')
    
    labs = db.get_labs_simple_list()
    drivers = db.get_drivers()
    equipment_list = db.get_equipment_simple_list() if hasattr(db, 'get_equipment_simple_list') else []
    default_lab_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
    
    return render_template('instrument_form.html',
        instrument=None,
        action='New',
        labs=labs,
        drivers=drivers,
        equipment_list=equipment_list,
        default_lab_id=default_lab_id,
        pre_equipment_id=pre_equipment_id,
        return_url=return_url,
    )


@main_bp.route('/instruments/<int:instrument_id>/edit', methods=['GET', 'POST'])
@login_required
def instrument_edit(instrument_id):
    """Edit instrument page."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instruments'))
    
    return_url = request.args.get('return_url') or request.referrer
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        driver_id = request.form.get('driver_id')
        driver_id = int(driver_id) if driver_id else None
        equipment_id = request.form.get('equipment_id')
        equipment_id = int(equipment_id) if equipment_id else None
        
        data = {
            'name': request.form.get('name'),
            'instrument_type': request.form.get('instrument_type'),
            'driver_id': driver_id,
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'status': request.form.get('status', 'available'),
            'lab_id': lab_id,
            'equipment_id': equipment_id,
        }
        
        try:
            db.update_instrument(instrument_id, data)
            flash(f'Instrument "{data["name"]}" updated successfully', 'success')
            return redirect(url_for('main.instrument_detail', instrument_id=instrument_id))
        except Exception as e:
            flash(f'Error updating instrument: {str(e)}', 'error')
    
    labs = db.get_labs_simple_list()
    drivers = db.get_drivers()
    equipment_list = db.get_equipment_simple_list() if hasattr(db, 'get_equipment_simple_list') else []
    
    return render_template('instrument_form.html',
        instrument=instrument,
        action='Edit',
        labs=labs,
        drivers=drivers,
        equipment_list=equipment_list,
        default_lab_id=None,
        return_url=return_url,
    )


@main_bp.route('/instruments/<int:instrument_id>/delete', methods=['POST'])
@login_required
def instrument_delete(instrument_id):
    """Move an instrument to trash."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instruments'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('instrument', instrument_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash(f'Instrument "{instrument["name"]}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving instrument to trash'), 'error')
    except Exception as e:
        flash(f'Error deleting instrument: {str(e)}', 'error')
    
    return redirect(url_for('main.instruments'))


@main_bp.route('/instruments/<int:instrument_id>/duplicate', methods=['GET', 'POST'])
@login_required
def instrument_duplicate(instrument_id):
    """Duplicate an existing instrument."""
    db = get_db_service()
    original = db.get_instrument(instrument_id)
    if not original:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instruments'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        
        data = {
            'name': request.form.get('name'),
            'instrument_type': request.form.get('instrument_type'),
            'pybirch_class': request.form.get('pybirch_class'),
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'status': request.form.get('status', 'available'),
            'lab_id': lab_id,
        }
        
        try:
            new_instrument = db.create_instrument(data)
            flash(f'Instrument "{new_instrument["name"]}" created from duplicate', 'success')
            return redirect(url_for('main.instrument_detail', instrument_id=new_instrument['id']))
        except Exception as e:
            flash(f'Error creating instrument: {str(e)}', 'error')
    
    # Pre-fill form with original data but new name
    instrument = dict(original)
    instrument['name'] = f"{original['name']} (Copy)"
    instrument['serial_number'] = ''  # Clear serial number for duplicate
    
    labs = db.get_labs_simple_list()
    drivers = db.get_drivers()
    equipment_list = db.get_equipment_simple_list() if hasattr(db, 'get_equipment_simple_list') else []
    
    return render_template('instrument_form.html',
        instrument=instrument,
        action='Duplicate',
        labs=labs,
        drivers=drivers,
        equipment_list=equipment_list,
        default_lab_id=None,
    )


# -------------------- Drivers --------------------

@main_bp.route('/drivers')
def drivers():
    """Drivers list page."""
    search = request.args.get('search', '')
    instrument_type = request.args.get('type', '')
    category = request.args.get('category', '')
    
    db = get_db_service()
    drivers = db.get_drivers(
        instrument_type=instrument_type if instrument_type else None,
        category=category if category else None,
        search=search if search else None,
    )
    
    # Get unique categories for filter dropdown
    categories = sorted(set(d['category'] for d in drivers if d.get('category')))
    
    return render_template('drivers.html',
        drivers=drivers,
        total=len(drivers),
        search=search,
        instrument_type=instrument_type,
        category=category,
        categories=categories,
    )


@main_bp.route('/drivers/<int:driver_id>')
def driver_detail(driver_id):
    """Driver detail page."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    # Get version history
    versions = db.get_driver_versions(driver_id)
    
    # Get instrument instances using this driver (with their computer bindings)
    instruments = db.get_instruments_by_driver(driver_id, include_bindings=True)
    
    return render_template('driver_detail.html', 
        driver=driver,
        versions=versions,
        instruments=instruments,
    )


@main_bp.route('/drivers/new', methods=['GET', 'POST'])
@login_required
def driver_new():
    """Create new driver page."""
    import os
    import shutil
    import json
    
    db = get_db_service()
    
    if request.method == 'POST':
        # Check if this is a folder upload
        upload_id = request.form.get('upload_id', '').strip()
        driver_files_json = request.form.get('driver_files', '')
        main_file_path = request.form.get('main_file_path', '').strip()
        has_folder_upload = upload_id and driver_files_json
        
        data = {
            'name': request.form.get('name', '').strip(),
            'display_name': request.form.get('display_name', '').strip(),
            'description': request.form.get('description', '').strip() or None,
            'instrument_type': request.form.get('instrument_type'),
            'category': request.form.get('category', '').strip() or None,
            'manufacturer': request.form.get('manufacturer', '').strip() or None,
            'source_code': request.form.get('source_code', ''),
            'base_class': request.form.get('base_class', '').strip(),
            'dependencies': request.form.get('dependencies', '').strip() or None,
            'is_public': request.form.get('is_public') == 'on',
            'status': request.form.get('status', 'operational'),
            'created_by': g.current_user.get('username') if g.current_user else None,
            # Multi-file driver support
            'has_folder_upload': has_folder_upload,
            'main_file_path': main_file_path if has_folder_upload else None,
            'driver_files': json.loads(driver_files_json) if driver_files_json else None,
        }
        
        # Validate required fields
        errors = []
        if not data['name']:
            errors.append('Class name is required')
        if not data['display_name']:
            errors.append('Display name is required')
        if not data['instrument_type']:
            errors.append('Instrument type is required')
        if not data['source_code']:
            errors.append('Source code is required')
        if not data['base_class']:
            errors.append('Base class is required')
        
        # Validate Python syntax
        if data['source_code']:
            try:
                compile(data['source_code'], '<code>', 'exec')
            except SyntaxError as e:
                errors.append(f'Syntax error at line {e.lineno}: {e.msg}')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('driver_form.html',
                driver=data,
                form_action=url_for('main.driver_new'),
                form_title='New Driver',
            )
        
        try:
            driver = db.create_driver(data)
            
            # If folder upload, rename temp folder to use driver ID
            if upload_id and has_folder_upload:
                temp_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'drivers', upload_id)
                permanent_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'drivers', f'driver_{driver["id"]}')
                if os.path.exists(temp_folder):
                    if os.path.exists(permanent_folder):
                        shutil.rmtree(permanent_folder)
                    os.rename(temp_folder, permanent_folder)
                    
                    # Update driver with new folder path references
                    if driver_files_json:
                        # Update file paths to use permanent folder
                        updated_files = []
                        for f in json.loads(driver_files_json):
                            updated_files.append(f)  # Paths are relative, no update needed
                        db.update_driver(driver['id'], {'driver_files': updated_files})
            
            flash(f'Driver "{driver["display_name"]}" created successfully', 'success')
            return redirect(url_for('main.driver_detail', driver_id=driver['id']))
        except Exception as e:
            flash(f'Error creating driver: {str(e)}', 'error')
            return render_template('driver_form.html',
                driver=data,
                form_action=url_for('main.driver_new'),
                form_title='New Driver',
            )
    
    # GET request - show empty form with template
    template_source = '''from pybirch.Instruments.measurement import Measurement
# Or: from pybirch.Instruments.movement import Movement


class MyInstrument(Measurement):
    """A custom instrument class.
    
    Attributes:
        Add your instrument attributes here.
    """
    
    def __init__(self, name="MyInstrument"):
        super().__init__(name=name)
        # Initialize your instrument here
    
    def measure(self):
        """Perform a measurement.
        
        Returns:
            dict: Measurement results
        """
        # Implement measurement logic
        return {"value": 0.0}
    
    def close(self):
        """Clean up resources."""
        super().close()
'''
    
    return render_template('driver_form.html',
        driver={'source_code': template_source, 'base_class': 'Measurement'},
        form_action=url_for('main.driver_new'),
        form_title='New Driver',
    )


@main_bp.route('/drivers/<int:driver_id>/edit', methods=['GET', 'POST'])
@login_required
def driver_edit(driver_id):
    """Edit driver page."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    if request.method == 'POST':
        data = {
            'display_name': request.form.get('display_name', '').strip(),
            'description': request.form.get('description', '').strip() or None,
            'category': request.form.get('category', '').strip() or None,
            'manufacturer': request.form.get('manufacturer', '').strip() or None,
            'source_code': request.form.get('source_code', ''),
            'base_class': request.form.get('base_class', '').strip(),
            'dependencies': request.form.get('dependencies', '').strip() or None,
            'is_public': request.form.get('is_public') == 'on',
            'status': request.form.get('status', 'operational'),
        }
        change_summary = request.form.get('change_summary', '').strip() or None
        
        # Validate required fields
        errors = []
        if not data['display_name']:
            errors.append('Display name is required')
        if not data['source_code']:
            errors.append('Source code is required')
        if not data['base_class']:
            errors.append('Base class is required')
        
        # Validate Python syntax
        if data['source_code']:
            try:
                compile(data['source_code'], '<code>', 'exec')
            except SyntaxError as e:
                errors.append(f'Syntax error at line {e.lineno}: {e.msg}')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            # Merge data back into driver for re-rendering
            driver.update(data)
            return render_template('driver_form.html',
                driver=driver,
                form_action=url_for('main.driver_edit', driver_id=driver_id),
                form_title=f'Edit {driver["display_name"]}',
            )
        
        try:
            updated = db.update_driver(
                driver_id,
                data,
                change_summary=change_summary,
                updated_by=g.current_user.get('username') if g.current_user else None,
            )
            flash(f'Driver "{updated["display_name"]}" updated successfully', 'success')
            return redirect(url_for('main.driver_detail', driver_id=driver_id))
        except Exception as e:
            flash(f'Error updating driver: {str(e)}', 'error')
            driver.update(data)
            return render_template('driver_form.html',
                driver=driver,
                form_action=url_for('main.driver_edit', driver_id=driver_id),
                form_title=f'Edit {driver["display_name"]}',
            )
    
    return render_template('driver_form.html',
        driver=driver,
        form_action=url_for('main.driver_edit', driver_id=driver_id),
        form_title=f'Edit {driver["display_name"]}',
    )


@main_bp.route('/drivers/<int:driver_id>/delete', methods=['POST'])
@login_required
def driver_delete(driver_id):
    """Move a driver to trash."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('driver', driver_id, trashed_by=username, cascade=False)
        
        if result['success']:
            flash(f'Driver "{driver["display_name"]}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Error moving driver to trash'), 'error')
    except Exception as e:
        flash(f'Error deleting driver: {str(e)}', 'error')
    
    return redirect(url_for('main.drivers'))


@main_bp.route('/drivers/<int:driver_id>/duplicate', methods=['GET', 'POST'])
@login_required
def driver_duplicate(driver_id):
    """Duplicate a driver."""
    db = get_db_service()
    original = db.get_driver(driver_id)
    
    if not original:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'display_name': request.form.get('display_name', '').strip(),
            'description': request.form.get('description', '').strip() or None,
            'instrument_type': original['instrument_type'],
            'category': request.form.get('category', '').strip() or None,
            'manufacturer': request.form.get('manufacturer', '').strip() or None,
            'source_code': request.form.get('source_code', ''),
            'base_class': request.form.get('base_class', '').strip(),
            'dependencies': request.form.get('dependencies', '').strip() or None,
            'is_public': request.form.get('is_public') == 'on',
            'created_by': g.current_user.get('username') if g.current_user else None,
        }
        
        try:
            driver = db.create_driver(data)
            flash(f'Driver "{driver["display_name"]}" created from duplicate', 'success')
            return redirect(url_for('main.driver_detail', driver_id=driver['id']))
        except Exception as e:
            flash(f'Error creating driver: {str(e)}', 'error')
    
    # Pre-fill form with original data but new name
    duplicated = original.copy()
    duplicated['name'] = f"{original['name']}_copy"
    duplicated['display_name'] = f"{original['display_name']} (Copy)"
    
    return render_template('driver_form.html',
        driver=duplicated,
        form_action=url_for('main.driver_duplicate', driver_id=driver_id),
        form_title=f'Duplicate {original["display_name"]}',
    )


@main_bp.route('/drivers/<int:driver_id>/versions/<int:version>')
def driver_version(driver_id, version):
    """View a specific version of a driver."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    versions = db.get_driver_versions(driver_id)
    version_data = next((v for v in versions if v['version'] == version), None)
    
    if not version_data:
        flash(f'Version {version} not found', 'error')
        return redirect(url_for('main.driver_detail', driver_id=driver_id))
    
    return render_template('driver_version.html',
        driver=driver,
        version_data=version_data,
        all_versions=versions,
    )


# -------------------- Instrument Instances (for Drivers) --------------------

@main_bp.route('/drivers/<int:driver_id>/instruments/new', methods=['GET', 'POST'])
@login_required
def driver_new_instance(driver_id):
    """Create a new instrument instance from a driver."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'serial_number': request.form.get('serial_number', '').strip() or None,
            'location': request.form.get('location', '').strip() or None,
            'manufacturer': request.form.get('manufacturer', '').strip() or None,
            'model': request.form.get('model', '').strip() or None,
            'lab_id': request.form.get('lab_id') or None,
        }
        
        if data['lab_id']:
            data['lab_id'] = int(data['lab_id'])
        
        if not data['name']:
            flash('Instrument name is required', 'error')
            labs = db.get_labs_simple_list()
            return render_template('instrument_instance_form.html',
                driver=driver,
                instrument=data,
                labs=labs,
                form_action=url_for('main.driver_new_instance', driver_id=driver_id),
                form_title=f'New {driver["display_name"]} Instance',
            )
        
        try:
            instrument = db.create_instrument_for_driver(driver_id, data)
            if instrument:
                flash(f'Instrument "{instrument["name"]}" created successfully', 'success')
                return redirect(url_for('main.driver_detail', driver_id=driver_id))
            else:
                flash('Failed to create instrument', 'error')
        except Exception as e:
            flash(f'Error creating instrument: {str(e)}', 'error')
    
    # GET - show form
    labs = db.get_labs_simple_list()
    return render_template('instrument_instance_form.html',
        driver=driver,
        instrument={},
        labs=labs,
        form_action=url_for('main.driver_new_instance', driver_id=driver_id),
        form_title=f'New {driver["display_name"]} Instance',
    )


@main_bp.route('/drivers/<int:driver_id>/instruments/<int:instrument_id>/delete', methods=['POST'])
@login_required
def driver_delete_instance(driver_id, instrument_id):
    """Delete an instrument instance."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.driver_detail', driver_id=driver_id))
    
    try:
        db.delete_instrument(instrument_id)
        flash(f'Instrument "{instrument["name"]}" deleted', 'success')
    except Exception as e:
        flash(f'Error deleting instrument: {str(e)}', 'error')
    
    return redirect(url_for('main.driver_detail', driver_id=driver_id))


@main_bp.route('/drivers/<int:driver_id>/link-instrument', methods=['GET', 'POST'])
@login_required
def driver_link_instrument(driver_id):
    """Link an existing instrument to this driver."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    if request.method == 'POST':
        instrument_id = request.form.get('instrument_id')
        if not instrument_id:
            flash('Please select an instrument to link', 'error')
        else:
            try:
                result = db.link_instrument_to_driver(int(instrument_id), driver_id)
                if result:
                    flash(f'Instrument "{result["name"]}" linked to {driver["display_name"]}', 'success')
                else:
                    flash('Failed to link instrument', 'error')
            except Exception as e:
                flash(f'Error linking instrument: {str(e)}', 'error')
        
        return redirect(url_for('main.driver_detail', driver_id=driver_id))
    
    # GET - show available instruments
    unlinked_instruments = db.get_instruments_without_driver()
    
    return render_template('driver_link.html',
        driver=driver,
        instruments=unlinked_instruments,
    )


@main_bp.route('/drivers/<int:driver_id>/instruments/<int:instrument_id>/unlink', methods=['POST'])
@login_required
def driver_unlink_instrument(driver_id, instrument_id):
    """Unlink an instrument from this driver."""
    db = get_db_service()
    
    try:
        result = db.unlink_instrument_from_driver(instrument_id)
        if result:
            flash(f'Instrument "{result["name"]}" unlinked from driver', 'success')
        else:
            flash('Instrument not found', 'error')
    except Exception as e:
        flash(f'Error unlinking instrument: {str(e)}', 'error')
    
    return redirect(url_for('main.driver_detail', driver_id=driver_id))


# -------------------- Driver Issues --------------------

@main_bp.route('/drivers/<int:driver_id>/issues')
def driver_issues(driver_id):
    """List issues for a specific driver."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    
    db = get_db_service()
    driver = db.get_driver(driver_id)
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    issues, total = db.get_driver_issues(
        driver_id=driver_id,
        status=status if status else None,
        priority=priority if priority else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    return render_template('driver_issues.html',
        driver=driver,
        issues=issues,
        page=page,
        total_pages=total_pages,
        total=total,
        status=status,
        priority=priority,
    )


@main_bp.route('/drivers/<int:driver_id>/issues/<int:issue_id>')
def driver_issue_detail(driver_id, issue_id):
    """View a specific driver issue."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    issue = db.get_driver_issue(issue_id)
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('main.driver_issues', driver_id=driver_id))
    
    # Get versions for display
    versions = db.get_driver_versions(driver_id)
    
    # Get users for assignee dropdown
    users, _ = db.get_users(per_page=1000)
    
    # Get images and attachments for this issue
    images = db.get_entity_images('driver_issue', issue_id)
    attachments = db.get_entity_attachments('driver_issue', issue_id)
    
    # Get update history for timeline
    updates = db.get_issue_updates('driver_issue', issue_id)
    
    return render_template('driver_issue_detail.html',
        driver=driver,
        issue=issue,
        versions=versions,
        users=users,
        images=images,
        attachments=attachments,
        entity_type='driver_issue',
        entity_id=issue_id,
        issue_type='driver_issue',
        issue_id=issue_id,
        updates=updates,
    )


@main_bp.route('/drivers/<int:driver_id>/issues/new', methods=['GET', 'POST'])
@login_required
def driver_issue_new(driver_id):
    """Create a new issue for a driver."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    if request.method == 'POST':
        assignee_id = request.form.get('assignee_id')
        affected_version = request.form.get('affected_version')
        data = {
            'driver_id': driver_id,
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'priority': request.form.get('priority', 'medium'),
            'category': request.form.get('category', 'bug'),
            'status': 'open',
            'assignee_id': int(assignee_id) if assignee_id else None,
            'error_message': request.form.get('error_message'),
            'steps_to_reproduce': request.form.get('steps_to_reproduce'),
            'environment_info': request.form.get('environment_info'),
            'affected_version': int(affected_version) if affected_version else None,
        }
        
        # Set reporter from current user
        if g.current_user:
            data['reporter_id'] = g.current_user.get('id')
        
        try:
            issue = db.create_driver_issue(data)
            flash(f'Issue "{issue["title"]}" reported successfully', 'success')
            return redirect(url_for('main.driver_issue_detail', driver_id=driver_id, issue_id=issue['id']))
        except Exception as e:
            flash(f'Error reporting issue: {str(e)}', 'error')
    
    # Get users for assignee dropdown
    users, _ = db.get_users(per_page=1000)
    
    # Get versions for dropdown
    versions = db.get_driver_versions(driver_id)
    
    return render_template('driver_issue_form.html',
        driver=driver,
        issue=None,
        action='Report',
        users=users,
        versions=versions,
    )


@main_bp.route('/drivers/<int:driver_id>/issues/<int:issue_id>/edit', methods=['GET', 'POST'])
@login_required
def driver_issue_edit(driver_id, issue_id):
    """Edit a driver issue."""
    db = get_db_service()
    driver = db.get_driver(driver_id)
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('main.drivers'))
    
    issue = db.get_driver_issue(issue_id)
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('main.driver_issues', driver_id=driver_id))
    
    if request.method == 'POST':
        assignee_id = request.form.get('assignee_id')
        affected_version = request.form.get('affected_version')
        fixed_in_version = request.form.get('fixed_in_version')
        data = {
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'priority': request.form.get('priority'),
            'category': request.form.get('category'),
            'status': request.form.get('status'),
            'assignee_id': int(assignee_id) if assignee_id else None,
            'error_message': request.form.get('error_message'),
            'steps_to_reproduce': request.form.get('steps_to_reproduce'),
            'environment_info': request.form.get('environment_info'),
            'resolution': request.form.get('resolution'),
            'resolution_steps': request.form.get('resolution_steps'),
            'affected_version': int(affected_version) if affected_version else None,
            'fixed_in_version': int(fixed_in_version) if fixed_in_version else None,
        }
        
        # Handle resolved_at based on status change
        from datetime import datetime
        if data['status'] in ['resolved', 'closed'] and issue['status'] not in ['resolved', 'closed']:
            data['resolved_at'] = datetime.utcnow()
        
        try:
            db.update_driver_issue(issue_id, data)
            flash('Issue updated successfully', 'success')
            return redirect(url_for('main.driver_issue_detail', driver_id=driver_id, issue_id=issue_id))
        except Exception as e:
            flash(f'Error updating issue: {str(e)}', 'error')
    
    # Get users for assignee dropdown
    users, _ = db.get_users(per_page=1000)
    
    # Get versions for dropdown
    versions = db.get_driver_versions(driver_id)
    
    return render_template('driver_issue_form.html',
        driver=driver,
        issue=issue,
        action='Update',
        users=users,
        versions=versions,
    )


@main_bp.route('/drivers/<int:driver_id>/issues/<int:issue_id>/status', methods=['POST'])
@login_required
def driver_issue_update_status(driver_id, issue_id):
    """Update driver issue status (quick update without full edit)."""
    db = get_db_service()
    
    issue = db.get_driver_issue(issue_id)
    if not issue:
        flash('Issue not found', 'error')
        return redirect(url_for('main.driver_issues', driver_id=driver_id))
    
    old_status = issue.get('status')
    new_status = request.form.get('status')
    resolution_note = request.form.get('resolution')
    
    data = {
        'status': new_status,
    }
    
    assignee_id = request.form.get('assignee_id')
    if assignee_id:
        data['assignee_id'] = int(assignee_id)
    else:
        data['assignee_id'] = None
    
    # Handle resolved_at based on status change
    from datetime import datetime
    if new_status in ['resolved', 'closed'] and old_status not in ['resolved', 'closed']:
        data['resolved_at'] = datetime.utcnow()
    
    try:
        db.update_driver_issue(issue_id, data)
        
        # Create an update entry if there's a status change or resolution note
        if old_status != new_status or resolution_note:
            author_name = None
            author_id = None
            if g.current_user:
                author_name = g.current_user.get('name') or g.current_user.get('username')
                author_id = g.current_user.get('id')
            
            update_type = 'status_change' if old_status != new_status else 'comment'
            if resolution_note and new_status in ['resolved', 'closed']:
                update_type = 'resolution'
            
            db.create_issue_update({
                'issue_type': 'driver_issue',
                'issue_id': issue_id,
                'update_type': update_type,
                'content': resolution_note,
                'old_status': old_status if old_status != new_status else None,
                'new_status': new_status if old_status != new_status else None,
                'author_id': author_id,
                'author_name': author_name,
            })
        
        flash('Issue status updated', 'success')
    except Exception as e:
        flash(f'Error updating issue: {str(e)}', 'error')
    
    return redirect(url_for('main.driver_issue_detail', driver_id=driver_id, issue_id=issue_id))


@main_bp.route('/drivers/issues')
def all_driver_issues():
    """List all driver issues across all drivers."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    
    db = get_db_service()
    issues, total = db.get_driver_issues(
        status=status if status else None,
        priority=priority if priority else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    return render_template('all_driver_issues.html',
        issues=issues,
        page=page,
        total_pages=total_pages,
        total=total,
        status=status,
        priority=priority,
    )


# -------------------- Computer Bindings --------------------

@main_bp.route('/instruments/<int:instrument_id>/bindings/new', methods=['GET', 'POST'])
@login_required
def instrument_binding_new(instrument_id):
    """Add a computer binding to an instrument."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.drivers'))
    
    # Get driver for redirect
    driver_id = None
    if instrument.get('driver_id'):
        driver_id = instrument['driver_id']
    
    if request.method == 'POST':
        data = {
            'instrument_id': instrument_id,
            'computer_name': request.form.get('computer_name', '').strip(),
            'computer_id': request.form.get('computer_id', '').strip() or None,
            'username': request.form.get('username', '').strip() or None,
            'nickname': request.form.get('nickname', '').strip() or None,
            'adapter': request.form.get('adapter', '').strip() or None,
            'adapter_type': request.form.get('adapter_type', '').strip() or None,
            'is_primary': request.form.get('is_primary') == 'on',
        }
        
        if not data['computer_name']:
            flash('Computer name (hostname) is required', 'error')
        else:
            try:
                binding = db.bind_instrument_to_computer(
                    instrument_id=data['instrument_id'],
                    computer_name=data['computer_name'],
                    computer_id=data.get('computer_id'),
                    username=data.get('username'),
                    adapter=data.get('adapter'),
                    adapter_type=data.get('adapter_type'),
                    is_primary=data.get('is_primary', True),
                    nickname=data.get('nickname'),
                )
                flash(f'Binding to {data["computer_name"]} created successfully', 'success')
                if driver_id:
                    return redirect(url_for('main.driver_detail', driver_id=driver_id))
                return redirect(url_for('main.instruments'))
            except Exception as e:
                flash(f'Error creating binding: {str(e)}', 'error')
    
    # GET - show form with current computer info pre-filled
    from pybirch.Instruments.factory import get_computer_info
    try:
        computer_info = get_computer_info()
    except:
        computer_info = {'computer_name': '', 'computer_id': '', 'username': ''}
    
    # Check if this computer already exists in the database (to show existing nickname)
    current_computer_name = computer_info.get('computer_name', '')
    existing_computer = None
    if current_computer_name:
        existing_computer = db.get_computer(current_computer_name)
    
    return render_template('computer_binding_form.html',
        instrument=instrument,
        driver_id=driver_id,
        binding={
            'computer_name': current_computer_name,
            'computer_id': computer_info.get('computer_id', ''),
            'username': computer_info.get('username', ''),
        },
        computer=existing_computer,
        form_action=url_for('main.instrument_binding_new', instrument_id=instrument_id),
        form_title=f'Bind {instrument["name"]} to Computer',
    )


@main_bp.route('/instruments/<int:instrument_id>/bindings/<int:binding_id>/delete', methods=['POST'])
@login_required
def instrument_binding_delete(instrument_id, binding_id):
    """Delete a computer binding."""
    db = get_db_service()
    
    # Get instrument for redirect info
    instrument = db.get_instrument(instrument_id)
    driver_id = instrument.get('driver_id') if instrument else None
    
    try:
        db.delete_computer_binding(binding_id)
        flash('Binding deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting binding: {str(e)}', 'error')
    
    if driver_id:
        return redirect(url_for('main.driver_detail', driver_id=driver_id))
    return redirect(url_for('main.instruments'))


@main_bp.route('/instruments/<int:instrument_id>/bindings/<int:binding_id>/edit', methods=['GET', 'POST'])
@login_required
def instrument_binding_edit(instrument_id, binding_id):
    """Edit a computer binding from the instrument page."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    binding = db.get_computer_binding(binding_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instruments'))
    
    if not binding:
        flash('Binding not found', 'error')
        return redirect(url_for('main.instrument_detail', instrument_id=instrument_id))
    
    driver_id = instrument.get('driver_id')
    
    if request.method == 'POST':
        data = {
            'computer_name': request.form.get('computer_name', '').strip(),
            'computer_id': request.form.get('computer_id', '').strip() or None,
            'username': request.form.get('username', '').strip() or None,
            'adapter': request.form.get('adapter', '').strip() or None,
            'adapter_type': request.form.get('adapter_type', '').strip() or None,
            'is_primary': request.form.get('is_primary') == 'on',
        }
        
        if not data['computer_name']:
            flash('Computer name (hostname) is required', 'error')
        else:
            try:
                db.update_computer_binding(binding_id, data)
                
                # Update Computer nickname if provided
                nickname = request.form.get('nickname', '').strip()
                if nickname:
                    existing_computer = db.get_computer(data['computer_name'])
                    if existing_computer:
                        db.update_computer(existing_computer['id'], {'nickname': nickname})
                
                flash('Binding updated successfully', 'success')
                return redirect(url_for('main.instrument_detail', instrument_id=instrument_id))
            except Exception as e:
                flash(f'Error updating binding: {str(e)}', 'error')
    
    # Get existing computer info for nickname
    existing_computer = db.get_computer(binding['computer_name']) if binding.get('computer_name') else None
    
    return render_template('computer_binding_form.html',
        instrument=instrument,
        driver_id=driver_id,
        binding=binding,
        computer=existing_computer,
        form_action=url_for('main.instrument_binding_edit', instrument_id=instrument_id, binding_id=binding_id),
        form_title=f'Edit Binding for {instrument["name"]}',
        is_edit=True,
        return_url=url_for('main.instrument_detail', instrument_id=instrument_id),
    )


@main_bp.route('/computers/<int:computer_id>/bindings/<int:binding_id>/edit', methods=['GET', 'POST'])
@login_required
def computer_binding_edit(computer_id, binding_id):
    """Edit a computer binding from the computer page."""
    db = get_db_service()
    computer = db.get_computer_by_id(computer_id)
    binding = db.get_computer_binding(binding_id)
    
    if not computer:
        flash('Computer not found', 'error')
        return redirect(url_for('main.computers'))
    
    if not binding:
        flash('Binding not found', 'error')
        return redirect(url_for('main.computer_detail', computer_id=computer_id))
    
    # Get the instrument for display
    instrument = db.get_instrument(binding['instrument_id'])
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.computer_detail', computer_id=computer_id))
    
    if request.method == 'POST':
        data = {
            'computer_name': request.form.get('computer_name', '').strip(),
            'computer_id': request.form.get('computer_id', '').strip() or None,
            'username': request.form.get('username', '').strip() or None,
            'adapter': request.form.get('adapter', '').strip() or None,
            'adapter_type': request.form.get('adapter_type', '').strip() or None,
            'is_primary': request.form.get('is_primary') == 'on',
        }
        
        if not data['computer_name']:
            flash('Computer name (hostname) is required', 'error')
        else:
            try:
                db.update_computer_binding(binding_id, data)
                
                # Update Computer nickname if provided
                nickname = request.form.get('nickname', '').strip()
                if nickname and data['computer_name'] == computer['computer_name']:
                    db.update_computer(computer_id, {'nickname': nickname})
                
                flash('Binding updated successfully', 'success')
                return redirect(url_for('main.computer_detail', computer_id=computer_id))
            except Exception as e:
                flash(f'Error updating binding: {str(e)}', 'error')
    
    return render_template('computer_binding_form.html',
        instrument=instrument,
        driver_id=instrument.get('driver_id'),
        binding=binding,
        computer=computer,
        form_action=url_for('main.computer_binding_edit', computer_id=computer_id, binding_id=binding_id),
        form_title=f'Edit Binding for {instrument["name"]}',
        is_edit=True,
        return_url=url_for('main.computer_detail', computer_id=computer_id),
    )


# -------------------- Computers --------------------

@main_bp.route('/computers')
def computers():
    """Computers list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    db = get_db_service()
    computers_list, total = db.get_computers(
        search=search if search else None,
        page=page,
    )
    
    return render_template('computers.html',
        computers=computers_list,
        total=total,
        search=search,
        page=page,
    )


@main_bp.route('/computers/<int:computer_id>')
def computer_detail(computer_id):
    """Computer detail page."""
    db = get_db_service()
    computer = db.get_computer_with_bindings(computer_id)
    
    if not computer:
        flash('Computer not found', 'error')
        return redirect(url_for('main.computers'))
    
    object_location = db.get_object_location('computer', computer_id)
    locations_list = db.get_locations_simple_list()
    
    return render_template('computer_detail.html', computer=computer,
                           object_type='computer', object_id=computer_id, object_location=object_location, locations_list=locations_list)


@main_bp.route('/computers/new', methods=['GET', 'POST'])
@login_required
def computer_new():
    """Create a new computer."""
    db = get_db_service()
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        data = {
            'computer_name': request.form.get('computer_name', '').strip(),
            'computer_id': request.form.get('computer_id', '').strip() or None,
            'nickname': request.form.get('nickname', '').strip() or None,
            'location': request.form.get('location', '').strip() or None,
            'description': request.form.get('description', '').strip() or None,
            'lab_id': int(lab_id) if lab_id else None,
        }
        
        if not data['computer_name']:
            flash('Computer name (hostname) is required', 'error')
        else:
            try:
                computer = db.create_computer(**data)
                flash(f'Computer "{data["computer_name"]}" created successfully', 'success')
                return redirect(url_for('main.computer_detail', computer_id=computer['id']))
            except Exception as e:
                flash(f'Error creating computer: {str(e)}', 'error')
    
    # Pre-fill with current computer info
    from pybirch.Instruments.factory import get_computer_info
    try:
        computer_info = get_computer_info()
    except:
        computer_info = {'computer_name': '', 'computer_id': '', 'username': ''}
    
    # Get labs and default lab
    labs = db.get_labs_simple_list()
    default_lab_id = g.current_user.get('default_lab_id') if g.current_user else None
    
    return render_template('computer_form.html',
        action='New',
        computer={
            'computer_name': computer_info.get('computer_name', ''),
            'computer_id': computer_info.get('computer_id', ''),
        },
        labs=labs,
        default_lab_id=default_lab_id,
    )


@main_bp.route('/computers/<int:computer_id>/edit', methods=['GET', 'POST'])
@login_required
def computer_edit(computer_id):
    """Edit a computer."""
    db = get_db_service()
    computer = db.get_computer_by_id(computer_id)
    
    if not computer:
        flash('Computer not found', 'error')
        return redirect(url_for('main.computers'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        data = {
            'computer_name': request.form.get('computer_name', '').strip() or None,
            'computer_id': request.form.get('computer_id', '').strip() or None,
            'nickname': request.form.get('nickname', '').strip() or None,
            'location': request.form.get('location', '').strip() or None,
            'description': request.form.get('description', '').strip() or None,
            'lab_id': int(lab_id) if lab_id else None,
        }
        
        try:
            db.update_computer_by_id(computer_id, **data)
            flash('Computer updated successfully', 'success')
            return redirect(url_for('main.computer_detail', computer_id=computer_id))
        except Exception as e:
            flash(f'Error updating computer: {str(e)}', 'error')
    
    # Get labs
    labs = db.get_labs_simple_list()
    
    return render_template('computer_form.html',
        action='Edit',
        computer=computer,
        labs=labs,
    )


@main_bp.route('/computers/<int:computer_id>/delete', methods=['POST'])
@login_required
def computer_delete(computer_id):
    """Move a computer to trash."""
    db = get_db_service()
    computer = db.get_computer_by_id(computer_id)
    
    try:
        trash_svc = get_trash_service()
        username = g.current_user.get('username') if g.current_user else None
        result = trash_svc.trash_item('computer', computer_id, trashed_by=username, cascade=False)
        
        if result['success']:
            name = computer.get('computer_name', f'#{computer_id}') if computer else f'#{computer_id}'
            flash(f'Computer "{name}" moved to trash', 'success')
        else:
            flash(result.get('error', 'Computer not found'), 'error')
    except Exception as e:
        flash(f'Error deleting computer: {str(e)}', 'error')
    
    return redirect(url_for('main.computers'))


@main_bp.route('/computers/<int:computer_id>/bindings/new', methods=['GET', 'POST'])
@login_required
def computer_binding_new(computer_id):
    """Add an instrument binding to a computer."""
    db = get_db_service()
    computer = db.get_computer_by_id(computer_id)
    
    if not computer:
        flash('Computer not found', 'error')
        return redirect(url_for('main.computers'))
    
    if request.method == 'POST':
        instrument_id = request.form.get('instrument_id', type=int)
        if not instrument_id:
            flash('Please select an instrument', 'error')
        else:
            data = {
                'instrument_id': instrument_id,
                'computer_name': computer['computer_name'],
                'computer_id': computer.get('computer_id'),
                'adapter': request.form.get('adapter', '').strip() or None,
                'adapter_type': request.form.get('adapter_type', '').strip() or None,
                'is_primary': request.form.get('is_primary') == 'on',
            }
            
            try:
                db.bind_instrument_to_computer(
                    instrument_id=data['instrument_id'],
                    computer_name=data['computer_name'],
                    computer_id=data.get('computer_id'),
                    adapter=data.get('adapter'),
                    adapter_type=data.get('adapter_type'),
                    is_primary=data.get('is_primary', True),
                )
                flash('Instrument bound successfully', 'success')
                return redirect(url_for('main.computer_detail', computer_id=computer_id))
            except Exception as e:
                flash(f'Error creating binding: {str(e)}', 'error')
    
    # GET - show form with instrument dropdown
    instruments = db.get_instruments_simple_list()
    
    return render_template('computer_binding_add.html',
        computer=computer,
        instruments=instruments,
    )


# ==================== Trash Management ====================

from database.trash_service import TrashService

def get_trash_service():
    """Get trash service instance."""
    return TrashService()

@main_bp.route('/trash')
@login_required
def trash():
    """Trash management page - view and manage trashed items."""
    trash_svc = get_trash_service()
    
    # Get filter parameters
    entity_type = request.args.get('type', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get trashed items
    items = []
    total = 0
    total_pages = 1
    if entity_type:
        result = trash_svc.get_trashed_items(entity_type, page=page, per_page=per_page)
        items = result.get('items', [])
        total = result.get('total', 0)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    
    # Get stats for sidebar
    stats = trash_svc.get_trash_stats()
    
    return render_template('trash.html',
        items=items,
        stats=stats,
        entity_type=entity_type,
        page=page,
        total=total,
        total_pages=total_pages
    )


@api_bp.route('/trash/<entity_type>/<int:entity_id>', methods=['POST'])
@api_login_required
def api_trash_item(entity_type, entity_id):
    """Move an item to trash (soft-delete)."""
    trash_svc = get_trash_service()
    
    username = g.current_user.get('username') if g.current_user else None
    cascade = request.json.get('cascade', True) if request.is_json else True
    
    result = trash_svc.trash_item(entity_type, entity_id, trashed_by=username, cascade=cascade)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@api_bp.route('/trash/<entity_type>/<int:entity_id>/restore', methods=['POST'])
@api_login_required
def api_restore_item(entity_type, entity_id):
    """Restore an item from trash."""
    trash_svc = get_trash_service()
    
    cascade = request.json.get('cascade', True) if request.is_json else True
    
    result = trash_svc.restore_item(entity_type, entity_id, cascade=cascade)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@api_bp.route('/trash/<entity_type>/<int:entity_id>', methods=['DELETE'])
@api_login_required
def api_permanent_delete(entity_type, entity_id):
    """Permanently delete a trashed item."""
    trash_svc = get_trash_service()
    
    result = trash_svc.permanently_delete_item(entity_type, entity_id)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@api_bp.route('/trash/stats', methods=['GET'])
@api_login_required
def api_trash_stats():
    """Get trash statistics."""
    trash_svc = get_trash_service()
    stats = trash_svc.get_trash_stats()
    return jsonify(stats)


@api_bp.route('/trash/cleanup', methods=['POST'])
@admin_required
def api_trash_cleanup():
    """Permanently delete all expired trash items (admin only)."""
    trash_svc = get_trash_service()
    result = trash_svc.cleanup_expired_trash()
    return jsonify(result)

# ==================== Archive Management ====================

from database.archive_service import ArchiveService

def get_archive_service():
    """Get archive service instance."""
    return ArchiveService()


@main_bp.route('/archive')
@login_required
def archive():
    """Archive management page - view and manage archived items."""
    archive_svc = get_archive_service()
    
    # Get filter parameters
    entity_type = request.args.get('type', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get archived items
    result = archive_svc.get_archived_items(
        entity_type=entity_type if entity_type else None,
        page=page,
        per_page=per_page
    )
    
    # Get stats for sidebar
    stats = archive_svc.get_archive_stats()
    
    return render_template('archive.html',
        items=result['items'],
        stats=stats,
        entity_type=entity_type,
        page=page,
        total_pages=result['total_pages'],
        total=result['total']
    )


@api_bp.route('/archive/<entity_type>/<int:entity_id>', methods=['POST'])
@api_login_required
def api_archive_item(entity_type, entity_id):
    """Archive an item (hide from normal queries)."""
    archive_svc = get_archive_service()
    
    username = g.current_user.get('username') if g.current_user else None
    
    result = archive_svc.archive_item(entity_type, entity_id, archived_by=username)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@api_bp.route('/archive/<entity_type>/<int:entity_id>/unarchive', methods=['POST'])
@api_login_required
def api_unarchive_item(entity_type, entity_id):
    """Unarchive an item (restore to normal visibility)."""
    archive_svc = get_archive_service()
    
    result = archive_svc.unarchive_item(entity_type, entity_id)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@api_bp.route('/archive/stats', methods=['GET'])
@api_login_required
def api_archive_stats():
    """Get archive statistics."""
    archive_svc = get_archive_service()
    stats = archive_svc.get_archive_stats()
    return jsonify(stats)


# ==================== Page View Tracking ====================

@api_bp.route('/track/page-duration', methods=['POST'])
def api_track_page_duration():
    """Update the duration and scroll distance for the current page view.
    
    This endpoint is called via beacon API when user leaves a page.
    Does not require authentication - uses session-based page view ID.
    """
    try:
        # Parse JSON data - use force=True to handle beacon requests
        data = request.get_json(force=True, silent=True) or {}
        page_view_id = data.get('page_view_id') or session.get('_current_page_view_id')
        duration = data.get('duration', 0)
        
        if not page_view_id:
            return jsonify({'success': False, 'error': 'No page view to update'}), 400
        
        # Validate duration (must be positive, cap at 30 minutes)
        try:
            duration = int(duration)
            if duration < 0:
                duration = 0
            elif duration > 1800:
                duration = 1800
        except (TypeError, ValueError):
            duration = 0
        
        db = get_db_service()
        success = db.update_page_view_duration(page_view_id, duration)
        
        return jsonify({'success': success})
    except Exception as e:
        current_app.logger.warning(f"Page duration tracking error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/track/page-view', methods=['POST'])
def api_log_page_view():
    """Manually log a page view (for SPA navigation or custom tracking).
    
    This is an alternative to automatic after_request tracking.
    """
    try:
        data = request.get_json(silent=True) or {}
        page_path = data.get('path', request.path)
        page_title = data.get('title')
        referrer = data.get('referrer', request.referrer)
        
        db = get_db_service()
        user_id = session.get('user_id')
        session_id = session.get('_id')
        
        result = db.log_page_view(
            page_path=page_path,
            user_id=user_id,
            page_title=page_title,
            referrer=referrer,
            session_id=str(session_id) if session_id else None
        )
        
        session['_current_page_view_id'] = result['id']
        
        return jsonify({'success': True, 'page_view_id': result['id']})
    except Exception as e:
        current_app.logger.warning(f"Page view logging error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
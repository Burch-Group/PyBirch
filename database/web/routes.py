"""
PyBirch Database Web Routes
===========================
Flask route handlers for the web UI and REST API.
"""

from datetime import datetime
from functools import wraps
from io import BytesIO
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, g, send_file, Response, current_app
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
    
    # Store in session
    session['filter_lab_id'] = int(lab_id) if lab_id else None
    session['filter_project_id'] = int(project_id) if project_id else None
    
    # Redirect back to the referring page or index
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/clear-site-filters')
def clear_site_filters():
    """Clear site-wide lab and project filters."""
    session.pop('filter_lab_id', None)
    session.pop('filter_project_id', None)
    
    # Redirect back to the referring page or index
    return redirect(request.referrer or url_for('main.index'))


# -------------------- Samples --------------------

@main_bp.route('/samples')
def samples():
    """Samples list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    db = get_db_service()
    samples_list, total = db.get_samples(
        search=search if search else None,
        status=status if status else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned sample IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'sample')
    
    return render_template('samples.html',
        samples=samples_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
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
    return render_template('sample_detail.html', sample=sample, images=images)


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
            'storage_location': request.form.get('storage_location'),
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
            
            flash(f'Sample {sample["sample_id"]} created successfully', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample['id']))
        except Exception as e:
            flash(f'Error creating sample: {str(e)}', 'error')
    
    # Get dropdown data
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    samples_list = db.get_samples_simple_list()
    precursors = db.get_precursors_simple_list()
    
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
            'storage_location': request.form.get('storage_location'),
            'description': request.form.get('description'),
            'lab_id': lab_id,
            'project_id': project_id,
            'parent_sample_id': parent_sample_id,
        }
        try:
            db.update_sample(sample_id, data)
            flash('Sample updated successfully', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample_id))
        except Exception as e:
            flash(f'Error updating sample: {str(e)}', 'error')
    
    # Get dropdown data
    labs = db.get_labs_simple_list()
    projects = db.get_projects_simple_list()
    samples_list = db.get_samples_simple_list(exclude_id=sample_id)  # Exclude self
    precursors = db.get_precursors_simple_list()
    sample_precursors = db.get_sample_precursors(sample_id)
    
    return render_template('sample_form.html', 
                          sample=sample, 
                          action='Edit',
                          labs=labs,
                          projects=projects,
                          samples_list=samples_list,
                          precursors=precursors,
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
            'storage_location': request.form.get('storage_location'),
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
        
        data = {
            'sample_id': sample_id,
            'procedure_id': int(request.form.get('procedure_id')),
            'run_number': int(request.form.get('run_number')) if request.form.get('run_number') else None,
            'operator': request.form.get('operator') or g.current_user.get('username'),
            'status': request.form.get('status', 'pending'),
            'started_at': started_at,
            'notes': request.form.get('notes'),
        }
        
        try:
            run = db.create_fabrication_run(data, fetch_weather=True)
            flash(f'Fabrication run added successfully', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample_id))
        except Exception as e:
            flash(f'Error creating fabrication run: {str(e)}', 'error')
    
    procedures = db.get_procedures_simple_list()
    
    # Get current datetime for auto-populating started_at
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    
    return render_template('fabrication_run_form.html',
                          sample=sample,
                          procedures=procedures,
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
            'operator': run_obj.operator,
            'started_at': run_obj.started_at.isoformat() if run_obj.started_at else None,
            'completed_at': run_obj.completed_at.isoformat() if run_obj.completed_at else None,
            'notes': run_obj.notes,
            'results': run_obj.results,
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
        
        data = {
            'procedure_id': int(request.form.get('procedure_id')),
            'run_number': int(request.form.get('run_number')) if request.form.get('run_number') else None,
            'operator': request.form.get('operator'),
            'status': request.form.get('status', 'pending'),
            'started_at': started_at,
            'completed_at': completed_at,
            'notes': request.form.get('notes'),
            'results': request.form.get('results'),
        }
        
        try:
            db.update_fabrication_run(run_id, data)
            flash('Fabrication run updated successfully', 'success')
            return redirect(url_for('main.sample_detail', sample_id=sample_id))
        except Exception as e:
            flash(f'Error updating fabrication run: {str(e)}', 'error')
    
    procedures = db.get_procedures_simple_list()
    
    return render_template('fabrication_run_form.html',
                          sample=sample,
                          procedures=procedures,
                          action='Edit',
                          run=run)


@main_bp.route('/fabrication-runs/<int:run_id>/delete', methods=['POST'])
@login_required
def fabrication_run_delete(run_id):
    """Delete a fabrication run."""
    db = get_db_service()
    
    # Get sample_id before deleting
    with db.session_scope() as session:
        from database.models import FabricationRun
        run = session.query(FabricationRun).filter(FabricationRun.id == run_id).first()
        if not run:
            flash('Fabrication run not found', 'error')
            return redirect(url_for('main.samples'))
        sample_id = run.sample_id
    
    if db.delete_fabrication_run(run_id):
        flash('Fabrication run deleted', 'success')
    else:
        flash('Error deleting fabrication run', 'error')
    
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


# -------------------- Scans --------------------

@main_bp.route('/scans')
def scans():
    """Scans list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    db = get_db_service()
    scans_list, total = db.get_scans(
        search=search if search else None,
        status=status if status else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'scan')
    
    return render_template('scans.html',
        scans=scans_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
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
    
    return render_template('scan_detail.html', 
                          scan=scan, 
                          data_points=data_points,
                          visualization_data=visualization_data)


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


# -------------------- Queues --------------------

@main_bp.route('/queues')
def queues():
    """Queues list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    db = get_db_service()
    queues_list, total = db.get_queues(
        search=search if search else None,
        status=status if status else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'queue')
    
    return render_template('queues.html',
        queues=queues_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
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
    return render_template('queue_detail.html', queue=queue)


# -------------------- Equipment --------------------

@main_bp.route('/equipment')
def equipment():
    """Equipment list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    db = get_db_service()
    equipment_list, total = db.get_equipment_list(
        search=search if search else None,
        status=status if status else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'equipment')
    
    return render_template('equipment.html',
        equipment=equipment_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        status=status,
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
    return render_template('equipment_detail.html', equipment=item)


@main_bp.route('/equipment/new', methods=['GET', 'POST'])
def equipment_new():
    """Create new equipment page."""
    db = get_db_service()
    
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
                'adapter': td.get('adapter', ''),
                'location': td.get('location', ''),
                'status': td.get('status', 'available'),
            }
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        data = {
            'name': request.form.get('name'),
            'equipment_type': request.form.get('equipment_type'),
            'pybirch_class': request.form.get('pybirch_class'),
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'adapter': request.form.get('adapter'),
            'location': request.form.get('location'),
            'status': request.form.get('status', 'available'),
            'lab_id': int(lab_id) if lab_id else None,
        }
        try:
            item = db.create_equipment(data)
            flash(f'Equipment {item["name"]} created successfully', 'success')
            return redirect(url_for('main.equipment_detail', equipment_id=item['id']))
        except Exception as e:
            flash(f'Error creating equipment: {str(e)}', 'error')
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    # Get user defaults
    default_lab_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
    
    return render_template('equipment_form.html', equipment=prefilled, action='Create', template=template, labs=labs, default_lab_id=default_lab_id)


@main_bp.route('/equipment/<int:equipment_id>/edit', methods=['GET', 'POST'])
def equipment_edit(equipment_id):
    """Edit equipment page."""
    db = get_db_service()
    equipment = db.get_equipment(equipment_id)
    
    if not equipment:
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
            'adapter': request.form.get('adapter'),
            'location': request.form.get('location'),
            'status': request.form.get('status', 'available'),
            'lab_id': int(lab_id) if lab_id else None,
        }
        try:
            updated = db.update_equipment(equipment_id, data)
            flash(f'Equipment "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.equipment_detail', equipment_id=equipment_id))
        except Exception as e:
            flash(f'Error updating equipment: {str(e)}', 'error')
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    return render_template('equipment_form.html', equipment=equipment, action='Edit', labs=labs)


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
            'adapter': request.form.get('adapter'),
            'location': request.form.get('location'),
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
    
    return render_template('equipment_issue_detail.html',
        equipment=equipment,
        issue=issue,
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


# -------------------- Precursors --------------------

@main_bp.route('/precursors')
def precursors():
    """Precursors list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    db = get_db_service()
    precursors_list, total = db.get_precursors(
        search=search if search else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'precursor')
    
    return render_template('precursors.html',
        precursors=precursors_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
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
    return render_template('precursor_detail.html', precursor=item, images=images)


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
        }
        try:
            item = db.create_precursor(data)
            flash(f'Precursor {item["name"]} created successfully', 'success')
            return redirect(url_for('main.precursor_detail', precursor_id=item['id']))
        except Exception as e:
            flash(f'Error creating precursor: {str(e)}', 'error')
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    # Get user defaults
    default_lab_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
    
    return render_template('precursor_form.html', precursor=prefilled, action='Create', template=template, labs=labs, default_lab_id=default_lab_id)


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
        }
        try:
            updated = db.update_precursor(precursor_id, data)
            flash(f'Precursor "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.precursor_detail', precursor_id=precursor_id))
        except Exception as e:
            flash(f'Error updating precursor: {str(e)}', 'error')
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    return render_template('precursor_form.html', precursor=precursor, action='Edit', labs=labs)


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
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    return render_template('precursor_form.html',
        precursor=duplicated,
        action='Duplicate',
        labs=labs,
    )


# -------------------- Procedures --------------------

@main_bp.route('/procedures')
def procedures():
    """Procedures list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    procedure_type = request.args.get('type', '')
    
    db = get_db_service()
    procedures_list, total = db.get_procedures(
        search=search if search else None,
        procedure_type=procedure_type if procedure_type else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'procedure')
    
    return render_template('procedures.html',
        procedures=procedures_list,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        procedure_type=procedure_type,
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
    return render_template('procedure_detail.html', procedure=procedure, images=images)


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
                steps.append(step)
        
        lab_id = request.form.get('lab_id')
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
        }
        try:
            procedure = db.create_procedure(data)
            flash(f'Procedure "{procedure["name"]}" created successfully', 'success')
            return redirect(url_for('main.procedure_detail', procedure_id=procedure['id']))
        except Exception as e:
            flash(f'Error creating procedure: {str(e)}', 'error')
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    # Get user defaults
    default_lab_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
    
    return render_template('procedure_form.html', procedure=prefilled, action='Create', template=template, labs=labs, default_lab_id=default_lab_id)


@main_bp.route('/procedures/<int:procedure_id>/edit', methods=['GET', 'POST'])
def procedure_edit(procedure_id):
    """Edit procedure page."""
    db = get_db_service()
    procedure = db.get_procedure(procedure_id)
    
    if not procedure:
        flash('Procedure not found', 'error')
        return redirect(url_for('main.procedures'))
    
    if request.method == 'POST':
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
                steps.append(step)
        
        lab_id = request.form.get('lab_id')
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
        }
        try:
            updated = db.update_procedure(procedure_id, data)
            flash(f'Procedure "{updated["name"]}" updated successfully', 'success')
            return redirect(url_for('main.procedure_detail', procedure_id=procedure_id))
        except Exception as e:
            flash(f'Error updating procedure: {str(e)}', 'error')
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    return render_template('procedure_form.html', procedure=procedure, action='Edit', labs=labs)


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
    
    # Get labs for dropdown
    labs = db.get_labs_simple_list()
    
    return render_template('procedure_form.html', procedure=procedure, action='Duplicate', labs=labs)


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
    return render_template('lab_detail.html', lab=lab)


@main_bp.route('/labs/new', methods=['GET', 'POST'])
def lab_new():
    """Create new lab page."""
    if request.method == 'POST':
        db = get_db_service()
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
        }
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
    """Delete a lab."""
    db = get_db_service()
    lab = db.get_lab(lab_id)
    
    if not lab:
        flash('Lab not found', 'error')
        return redirect(url_for('main.labs'))
    
    try:
        if db.delete_lab(lab_id):
            flash(f'Lab "{lab["name"]}" deleted successfully', 'success')
        else:
            flash('Error deleting lab', 'error')
    except Exception as e:
        flash(f'Cannot delete lab: {str(e)}', 'error')
    
    return redirect(url_for('main.labs'))


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
    
    return render_template('project_detail.html', project=project)


@main_bp.route('/projects/new', methods=['GET', 'POST'])
def project_new():
    """Create new project page."""
    db = get_db_service()
    labs_list, _ = db.get_labs(per_page=100)
    
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
    
    return render_template('project_form.html', project=None, labs=labs_list, action='Create')


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
    """Delete a project."""
    db = get_db_service()
    project = db.get_project(project_id)
    
    if not project:
        flash('Project not found', 'error')
        return redirect(url_for('main.projects'))
    
    try:
        if db.delete_project(project_id):
            flash(f'Project "{project["name"]}" deleted successfully', 'success')
        else:
            flash('Error deleting project', 'error')
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
    
    valid_types = ['sample', 'scan', 'queue', 'equipment', 'precursor', 'procedure', 'project', 'lab', 'instrument']
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
    
    valid_types = ['sample', 'scan', 'queue', 'equipment', 'precursor', 'procedure', 'project', 'lab', 'instrument']
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
    return render_template('issue_detail.html', issue=issue, users=users)


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
    
    data = {
        'status': request.form.get('status'),
        'assignee_id': request.form.get('assignee_id') or None,
        'resolution': request.form.get('resolution'),
    }
    
    if data['assignee_id']:
        data['assignee_id'] = int(data['assignee_id'])
    
    db.update_issue(issue_id, data)
    flash('Issue updated', 'success')
    return redirect(url_for('main.issue_detail', issue_id=issue_id))


@main_bp.route('/issues/<int:issue_id>/delete', methods=['POST'])
@admin_required
def issue_delete(issue_id):
    """Delete an issue (admin only)."""
    db = get_db_service()
    
    if db.delete_issue(issue_id):
        flash('Issue deleted', 'success')
    else:
        flash('Error deleting issue', 'error')
    
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
def template_delete(template_id):
    """Delete (soft) a template."""
    db = get_db_service()
    
    if db.delete_template(template_id):
        flash('Template deleted successfully', 'success')
    else:
        flash('Template not found', 'error')
    
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


# -------------------- Instruments --------------------

@main_bp.route('/instruments')
def instruments():
    """Instruments list page."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    db = get_db_service()
    instruments_list, total = db.get_instruments_list(
        search=search if search else None,
        status=status if status else None,
        page=page
    )
    
    total_pages = (total + 19) // 20
    
    # Get pinned instrument IDs for current user
    pinned_ids = []
    if g.current_user:
        pinned_ids = db.get_pinned_ids(g.current_user['id'], 'instrument')
    
    return render_template('instruments.html',
        instruments=instruments_list,
        total=total,
        page=page,
        total_pages=total_pages,
        search=search,
        status=status,
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
    return render_template('instrument_detail.html', instrument=instrument, images=images)


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
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        definition_id = request.form.get('definition_id')
        definition_id = int(definition_id) if definition_id else None
        equipment_id = request.form.get('equipment_id')
        equipment_id = int(equipment_id) if equipment_id else None
        
        data = {
            'name': request.form.get('name'),
            'instrument_type': request.form.get('instrument_type'),
            'definition_id': definition_id,
            'adapter': request.form.get('adapter'),
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'location': request.form.get('location'),
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
    definitions = db.get_instrument_definitions()
    equipment_list = db.get_equipment_simple_list() if hasattr(db, 'get_equipment_simple_list') else []
    default_lab_id = None
    if g.current_user:
        user_prefs = db.get_user_preferences(g.current_user['id'])
        default_lab_id = user_prefs.get('default_lab_id')
    
    return render_template('instrument_form.html',
        instrument=None,
        action='New',
        labs=labs,
        definitions=definitions,
        equipment_list=equipment_list,
        default_lab_id=default_lab_id,
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
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        lab_id = int(lab_id) if lab_id else None
        definition_id = request.form.get('definition_id')
        definition_id = int(definition_id) if definition_id else None
        equipment_id = request.form.get('equipment_id')
        equipment_id = int(equipment_id) if equipment_id else None
        
        data = {
            'name': request.form.get('name'),
            'instrument_type': request.form.get('instrument_type'),
            'definition_id': definition_id,
            'adapter': request.form.get('adapter'),
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'location': request.form.get('location'),
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
    definitions = db.get_instrument_definitions()
    equipment_list = db.get_equipment_simple_list() if hasattr(db, 'get_equipment_simple_list') else []
    
    return render_template('instrument_form.html',
        instrument=instrument,
        action='Edit',
        labs=labs,
        definitions=definitions,
        equipment_list=equipment_list,
        default_lab_id=None,
    )


@main_bp.route('/instruments/<int:instrument_id>/delete', methods=['POST'])
@login_required
def instrument_delete(instrument_id):
    """Delete an instrument."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instruments'))
    
    try:
        db.delete_instrument(instrument_id)
        flash(f'Instrument "{instrument["name"]}" deleted', 'success')
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
            'adapter': request.form.get('adapter'),
            'manufacturer': request.form.get('manufacturer'),
            'model': request.form.get('model'),
            'serial_number': request.form.get('serial_number'),
            'description': request.form.get('description'),
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
    
    return render_template('instrument_form.html',
        instrument=instrument,
        action='Duplicate',
        labs=labs,
        default_lab_id=None,
    )


# -------------------- Instrument Definitions --------------------

@main_bp.route('/instrument-definitions')
def instrument_definitions():
    """Instrument definitions list page."""
    search = request.args.get('search', '')
    instrument_type = request.args.get('type', '')
    category = request.args.get('category', '')
    
    db = get_db_service()
    definitions = db.get_instrument_definitions(
        instrument_type=instrument_type if instrument_type else None,
        category=category if category else None,
        search=search if search else None,
    )
    
    # Get unique categories for filter dropdown
    categories = sorted(set(d['category'] for d in definitions if d.get('category')))
    
    return render_template('instrument_definitions.html',
        definitions=definitions,
        total=len(definitions),
        search=search,
        instrument_type=instrument_type,
        category=category,
        categories=categories,
    )


@main_bp.route('/instrument-definitions/<int:definition_id>')
def instrument_definition_detail(definition_id):
    """Instrument definition detail page."""
    db = get_db_service()
    definition = db.get_instrument_definition(definition_id)
    if not definition:
        flash('Instrument definition not found', 'error')
        return redirect(url_for('main.instrument_definitions'))
    
    # Get version history
    versions = db.get_instrument_definition_versions(definition_id)
    
    # Get instrument instances using this definition (with their computer bindings)
    instruments = db.get_instruments_by_definition(definition_id, include_bindings=True)
    
    return render_template('instrument_definition_detail.html', 
        definition=definition, 
        versions=versions,
        instruments=instruments,
    )


@main_bp.route('/instrument-definitions/new', methods=['GET', 'POST'])
@login_required
def instrument_definition_new():
    """Create new instrument definition page."""
    db = get_db_service()
    
    if request.method == 'POST':
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
            'created_by': g.current_user.get('username') if g.current_user else None,
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
            return render_template('instrument_definition_form.html',
                definition=data,
                form_action=url_for('main.instrument_definition_new'),
                form_title='New Instrument Definition',
            )
        
        try:
            definition = db.create_instrument_definition(data)
            flash(f'Instrument definition "{definition["display_name"]}" created successfully', 'success')
            return redirect(url_for('main.instrument_definition_detail', definition_id=definition['id']))
        except Exception as e:
            flash(f'Error creating instrument definition: {str(e)}', 'error')
            return render_template('instrument_definition_form.html',
                definition=data,
                form_action=url_for('main.instrument_definition_new'),
                form_title='New Instrument Definition',
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
    
    return render_template('instrument_definition_form.html',
        definition={'source_code': template_source, 'base_class': 'Measurement'},
        form_action=url_for('main.instrument_definition_new'),
        form_title='New Instrument Definition',
    )


@main_bp.route('/instrument-definitions/<int:definition_id>/edit', methods=['GET', 'POST'])
@login_required
def instrument_definition_edit(definition_id):
    """Edit instrument definition page."""
    db = get_db_service()
    definition = db.get_instrument_definition(definition_id)
    
    if not definition:
        flash('Instrument definition not found', 'error')
        return redirect(url_for('main.instrument_definitions'))
    
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
            # Merge data back into definition for re-rendering
            definition.update(data)
            return render_template('instrument_definition_form.html',
                definition=definition,
                form_action=url_for('main.instrument_definition_edit', definition_id=definition_id),
                form_title=f'Edit {definition["display_name"]}',
            )
        
        try:
            updated = db.update_instrument_definition(
                definition_id,
                data,
                change_summary=change_summary,
                updated_by=g.current_user.get('username') if g.current_user else None,
            )
            flash(f'Instrument definition "{updated["display_name"]}" updated successfully', 'success')
            return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))
        except Exception as e:
            flash(f'Error updating instrument definition: {str(e)}', 'error')
            definition.update(data)
            return render_template('instrument_definition_form.html',
                definition=definition,
                form_action=url_for('main.instrument_definition_edit', definition_id=definition_id),
                form_title=f'Edit {definition["display_name"]}',
            )
    
    return render_template('instrument_definition_form.html',
        definition=definition,
        form_action=url_for('main.instrument_definition_edit', definition_id=definition_id),
        form_title=f'Edit {definition["display_name"]}',
    )


@main_bp.route('/instrument-definitions/<int:definition_id>/delete', methods=['POST'])
@login_required
def instrument_definition_delete(definition_id):
    """Delete an instrument definition."""
    db = get_db_service()
    definition = db.get_instrument_definition(definition_id)
    
    if not definition:
        flash('Instrument definition not found', 'error')
        return redirect(url_for('main.instrument_definitions'))
    
    try:
        db.delete_instrument_definition(definition_id)
        flash(f'Instrument definition "{definition["display_name"]}" deleted', 'success')
    except Exception as e:
        flash(f'Error deleting instrument definition: {str(e)}', 'error')
    
    return redirect(url_for('main.instrument_definitions'))


@main_bp.route('/instrument-definitions/<int:definition_id>/duplicate', methods=['GET', 'POST'])
@login_required
def instrument_definition_duplicate(definition_id):
    """Duplicate an instrument definition."""
    db = get_db_service()
    original = db.get_instrument_definition(definition_id)
    
    if not original:
        flash('Instrument definition not found', 'error')
        return redirect(url_for('main.instrument_definitions'))
    
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
            definition = db.create_instrument_definition(data)
            flash(f'Instrument definition "{definition["display_name"]}" created from duplicate', 'success')
            return redirect(url_for('main.instrument_definition_detail', definition_id=definition['id']))
        except Exception as e:
            flash(f'Error creating instrument definition: {str(e)}', 'error')
    
    # Pre-fill form with original data but new name
    duplicated = original.copy()
    duplicated['name'] = f"{original['name']}_copy"
    duplicated['display_name'] = f"{original['display_name']} (Copy)"
    
    return render_template('instrument_definition_form.html',
        definition=duplicated,
        form_action=url_for('main.instrument_definition_duplicate', definition_id=definition_id),
        form_title=f'Duplicate {original["display_name"]}',
    )


@main_bp.route('/instrument-definitions/<int:definition_id>/versions/<int:version>')
def instrument_definition_version(definition_id, version):
    """View a specific version of an instrument definition."""
    db = get_db_service()
    definition = db.get_instrument_definition(definition_id)
    
    if not definition:
        flash('Instrument definition not found', 'error')
        return redirect(url_for('main.instrument_definitions'))
    
    versions = db.get_instrument_definition_versions(definition_id)
    version_data = next((v for v in versions if v['version'] == version), None)
    
    if not version_data:
        flash(f'Version {version} not found', 'error')
        return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))
    
    return render_template('instrument_definition_version.html',
        definition=definition,
        version_data=version_data,
        all_versions=versions,
    )


# -------------------- Instrument Instances (for Definitions) --------------------

@main_bp.route('/instrument-definitions/<int:definition_id>/instruments/new', methods=['GET', 'POST'])
@login_required
def instrument_definition_new_instance(definition_id):
    """Create a new instrument instance from a definition."""
    db = get_db_service()
    definition = db.get_instrument_definition(definition_id)
    
    if not definition:
        flash('Instrument definition not found', 'error')
        return redirect(url_for('main.instrument_definitions'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'adapter': request.form.get('adapter', '').strip() or None,
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
                definition=definition,
                instrument=data,
                labs=labs,
                form_action=url_for('main.instrument_definition_new_instance', definition_id=definition_id),
                form_title=f'New {definition["display_name"]} Instance',
            )
        
        try:
            instrument = db.create_instrument_for_definition(definition_id, data)
            if instrument:
                flash(f'Instrument "{instrument["name"]}" created successfully', 'success')
                return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))
            else:
                flash('Failed to create instrument', 'error')
        except Exception as e:
            flash(f'Error creating instrument: {str(e)}', 'error')
    
    # GET - show form
    labs = db.get_labs_simple_list()
    return render_template('instrument_instance_form.html',
        definition=definition,
        instrument={},
        labs=labs,
        form_action=url_for('main.instrument_definition_new_instance', definition_id=definition_id),
        form_title=f'New {definition["display_name"]} Instance',
    )


@main_bp.route('/instrument-definitions/<int:definition_id>/instruments/<int:instrument_id>/delete', methods=['POST'])
@login_required
def instrument_definition_delete_instance(definition_id, instrument_id):
    """Delete an instrument instance."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))
    
    try:
        db.delete_instrument(instrument_id)
        flash(f'Instrument "{instrument["name"]}" deleted', 'success')
    except Exception as e:
        flash(f'Error deleting instrument: {str(e)}', 'error')
    
    return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))


@main_bp.route('/instrument-definitions/<int:definition_id>/link-instrument', methods=['GET', 'POST'])
@login_required
def instrument_definition_link_instrument(definition_id):
    """Link an existing instrument to this definition."""
    db = get_db_service()
    definition = db.get_instrument_definition(definition_id)
    
    if not definition:
        flash('Instrument definition not found', 'error')
        return redirect(url_for('main.instrument_definitions'))
    
    if request.method == 'POST':
        instrument_id = request.form.get('instrument_id')
        if not instrument_id:
            flash('Please select an instrument to link', 'error')
        else:
            try:
                result = db.link_instrument_to_definition(int(instrument_id), definition_id)
                if result:
                    flash(f'Instrument "{result["name"]}" linked to {definition["display_name"]}', 'success')
                else:
                    flash('Failed to link instrument', 'error')
            except Exception as e:
                flash(f'Error linking instrument: {str(e)}', 'error')
        
        return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))
    
    # GET - show available instruments
    unlinked_instruments = db.get_instruments_without_definition()
    
    return render_template('instrument_definition_link.html',
        definition=definition,
        instruments=unlinked_instruments,
    )


@main_bp.route('/instrument-definitions/<int:definition_id>/instruments/<int:instrument_id>/unlink', methods=['POST'])
@login_required
def instrument_definition_unlink_instrument(definition_id, instrument_id):
    """Unlink an instrument from this definition."""
    db = get_db_service()
    
    try:
        result = db.unlink_instrument_from_definition(instrument_id)
        if result:
            flash(f'Instrument "{result["name"]}" unlinked from definition', 'success')
        else:
            flash('Instrument not found', 'error')
    except Exception as e:
        flash(f'Error unlinking instrument: {str(e)}', 'error')
    
    return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))


# -------------------- Computer Bindings --------------------

@main_bp.route('/instruments/<int:instrument_id>/bindings/new', methods=['GET', 'POST'])
@login_required
def instrument_binding_new(instrument_id):
    """Add a computer binding to an instrument."""
    db = get_db_service()
    instrument = db.get_instrument(instrument_id)
    
    if not instrument:
        flash('Instrument not found', 'error')
        return redirect(url_for('main.instrument_definitions'))
    
    # Get definition for redirect
    definition_id = None
    if instrument.get('definition_id'):
        definition_id = instrument['definition_id']
    
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
                if definition_id:
                    return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))
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
        definition_id=definition_id,
        binding={
            'computer_name': current_computer_name,
            'computer_id': computer_info.get('computer_id', ''),
            'username': computer_info.get('username', ''),
            'adapter': instrument.get('adapter', ''),
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
    definition_id = instrument.get('definition_id') if instrument else None
    
    try:
        db.delete_computer_binding(binding_id)
        flash('Binding deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting binding: {str(e)}', 'error')
    
    if definition_id:
        return redirect(url_for('main.instrument_definition_detail', definition_id=definition_id))
    return redirect(url_for('main.instruments'))

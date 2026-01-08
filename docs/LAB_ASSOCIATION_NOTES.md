# Lab Association & Autofill - Implementation Notes

## Design Decisions

### Decision 1: User Defaults Storage
**Chosen Approach**: Add fields directly to User model

**Reasoning**:
- Simpler than separate UserPreferences table
- User model already exists with lab_id
- Fewer joins needed when loading defaults
- Can always extend to JSON preferences field later

**Fields to Add**:
```python
default_lab_id: Optional[int]  # User's preferred lab
default_project_id: Optional[int]  # User's preferred project
```

---

### Decision 2: Default Priority Order
When populating form fields:

1. **Template value** (if using template) - Highest priority
2. **User's saved default** - Second priority  
3. **User's current lab membership** - Third priority
4. **Empty/None** - Lowest priority (user must select)

---

### Decision 3: Lab Field Requirement
**Policy**: lab_id will be **optional** (nullable) for all objects

**Reasoning**:
- Maintains backwards compatibility
- Allows for shared/cross-lab resources
- Reduces friction for quick data entry
- Can be enforced per-lab via settings later

---

### Decision 4: Autofill UX
**Approach**: Automatic + Manual Override

1. Forms pre-populate with defaults automatically
2. "Set as Default" link appears next to lab/project dropdowns
3. Clicking saves that selection as user's new default
4. Toast/flash notification confirms "Default updated"

---

## Technical Notes

### Note 1: Migration Strategy
```python
# For each table missing lab_id:
# 1. Add nullable lab_id column
# 2. Add foreign key constraint
# 3. Update existing rows from project.lab_id where possible
# 4. Add index for performance

ALTER TABLE precursors ADD COLUMN lab_id INTEGER REFERENCES labs(id);
UPDATE precursors SET lab_id = (
    SELECT lab_id FROM projects WHERE projects.id = precursors.project_id
) WHERE project_id IS NOT NULL;
CREATE INDEX idx_precursors_lab ON precursors(lab_id);
```

---

### Note 2: Service Method Pattern
For each entity service, follow this pattern:

```python
def create_precursor(self, data: Dict) -> Dict:
    # If no lab_id provided, try to get from project
    if 'lab_id' not in data and data.get('project_id'):
        project = self.get_project(data['project_id'])
        if project:
            data['lab_id'] = project.get('lab_id')
    
    # ... rest of create logic
```

---

### Note 3: Form Template Pattern
```html
<div class="form-group">
    <label for="lab_id">Lab</label>
    <select id="lab_id" name="lab_id" class="searchable-select" data-entity-type="lab">
        <option value="">Select Lab...</option>
        {% for lab in labs %}
        <option value="{{ lab.id }}" 
            {% if (entity and entity.lab_id == lab.id) or 
                  (not entity and default_lab_id == lab.id) %}selected{% endif %}>
            {{ lab.name }}
        </option>
        {% endfor %}
    </select>
    {% if current_user %}
    <a href="#" class="set-default-link" data-field="lab_id" data-value="">Set as Default</a>
    {% endif %}
</div>
```

---

### Note 4: JavaScript for Set Default
```javascript
document.querySelectorAll('.set-default-link').forEach(link => {
    link.addEventListener('click', async (e) => {
        e.preventDefault();
        const field = link.dataset.field;
        const select = document.getElementById(field);
        const value = select.value;
        
        const response = await fetch('/api/user/preferences', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({[`default_${field}`]: value || null})
        });
        
        if (response.ok) {
            showToast(`Default ${field.replace('_id', '')} updated`);
        }
    });
});
```

---

### Note 5: Route Context Pattern
```python
@main_bp.route('/precursors/new')
def precursor_new():
    db = get_db_service()
    
    # Get user defaults
    default_lab_id = None
    default_project_id = None
    if 'user_id' in session:
        user = db.get_user(session['user_id'])
        if user:
            default_lab_id = user.get('default_lab_id')
            default_project_id = user.get('default_project_id')
    
    # Template overrides defaults
    template_id = request.args.get('template_id')
    if template_id:
        template = db.get_template(template_id)
        if template:
            default_lab_id = template.get('lab_id') or default_lab_id
            default_project_id = template.get('project_id') or default_project_id
    
    return render_template('precursor_form.html',
        labs=db.get_labs()[0],
        projects=db.get_projects()[0],
        default_lab_id=default_lab_id,
        default_project_id=default_project_id,
        # ...
    )
```

---

## Files to Modify Summary

### Models
- `database/models.py` - Add lab_id to 7 models, add defaults to User

### Migrations  
- `database/migrations/add_lab_to_all_objects.py` (new)

### Services
- `database/services.py` - Update create/get/list methods for all affected entities

### Routes
- `database/web/routes.py` - Pass defaults to templates, add preferences API

### Templates
- `precursor_form.html` - Add lab field, autofill support
- `procedure_form.html` - Add lab field, autofill support
- `sample_form.html` - Add autofill support (already has lab)
- `equipment_form.html` - Add autofill support (already has lab)
- `instrument_form.html` - Add autofill support (already has lab)

### Static JS
- `database/web/static/js/main.js` - Add setDefault functionality

---

## Testing Checklist

- [ ] Create precursor with default lab
- [ ] Create procedure with default lab  
- [ ] Set default lab via dropdown link
- [ ] Set default project via dropdown link
- [ ] Verify template overrides defaults
- [ ] Verify user can override template
- [ ] Check existing objects still work (no lab_id)
- [ ] Filter by lab works for new entities
- [ ] Migration runs without errors
- [ ] Migration sets lab_id from project correctly
